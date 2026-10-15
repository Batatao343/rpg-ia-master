"""SPEC-192 R4/R5/R9: cron endpoints, drain budget, recovery dedup (offline)."""
from __future__ import annotations

import threading
from contextlib import nullcontext
from types import SimpleNamespace
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

import api
from scripts import recover_account_deletions as cli
from services import cron_internal
from workers.drain import drain_jobs

SECRET = "s" * 40
client = TestClient(api.app)
H = {"Authorization": f"Bearer {SECRET}"}


@pytest.fixture(autouse=True)
def _env(monkeypatch):
    monkeypatch.setenv("RPG_CRON_SECRET", SECRET)
    cron_internal._failures.clear()


@pytest.mark.parametrize("path", ["jobs", "account-deletions", "operations"])
def test_auth_matrix(path, monkeypatch):
    url = f"/internal/cron/{path}"
    assert client.post(url).status_code == 401
    assert client.post(url, headers={"Authorization": "Bearer nope"}).status_code == 401
    assert client.post(url, headers={"Authorization": SECRET}).status_code == 401
    monkeypatch.setenv("RPG_CRON_SECRET", "short")
    assert client.post(url, headers={"Authorization": "Bearer short"}).status_code == 503
    monkeypatch.delenv("RPG_CRON_SECRET")
    assert client.post(url, headers=H).status_code == 503


def test_budget_capped_below_max_duration(monkeypatch):
    monkeypatch.setenv("RPG_CRON_BUDGET_SECONDS", "500")
    monkeypatch.setenv("RPG_CRON_MAX_DURATION_SECONDS", "60")
    assert cron_internal.budget_seconds() == 55
    monkeypatch.setenv("RPG_CRON_BUDGET_SECONDS", "x")
    assert cron_internal.budget_seconds() == 50


class Clock:
    t = 0.0

    def __call__(self):
        return self.t


class FakeWorker:
    def __init__(self, jobs, clock=None, cost=0.0):
        self.jobs, self.clock, self.cost = jobs, clock, cost

    def run_once(self, *, limit=10):
        if not self.jobs:
            return 0
        self.jobs -= 1
        if self.clock:
            self.clock.t += self.cost
        return 1


def test_drain_stops_when_empty():
    out = drain_jobs(50, 10, "w", worker=FakeWorker(3))
    assert out["processed"] == 3 and out["stopped_reason"] == "empty"


def test_drain_respects_max_jobs():
    out = drain_jobs(50, 2, "w", worker=FakeWorker(5))
    assert out["processed"] == 2 and out["stopped_reason"] == "max_jobs"


def test_drain_budget_with_fake_clock():
    clock = Clock()
    out = drain_jobs(50, 100, "w", worker=FakeWorker(100, clock, cost=10.0), clock=clock)
    # stop_at=47; a job starts only while >=15s remain: t=0,10,20,30 -> 4 jobs
    assert out["processed"] == 4 and out["stopped_reason"] == "deadline"
    assert drain_jobs(10, 5, "w", worker=FakeWorker(5), clock=Clock())["processed"] == 0


def test_jobs_endpoint_response_shape(monkeypatch):
    monkeypatch.setattr("workers.drain.drain_jobs",
                        lambda *a, **k: {"processed": 2, "stopped_reason": "empty", "elapsed_s": 0.1})
    r = client.post("/internal/cron/jobs", headers=H)
    assert r.status_code == 200 and r.json()["processed"] == 2 and r.json()["ok"] is True


def test_task_failure_is_500_and_escalates_to_error_log(monkeypatch, caplog):
    def boom(*a, **k):
        raise RuntimeError("secret@example.com")
    monkeypatch.setattr("workers.drain.drain_jobs", boom)
    with caplog.at_level("INFO", logger="rpg.cron"):
        for _ in range(3):
            r = client.post("/internal/cron/jobs", headers=H)
            assert r.status_code == 500 and "example.com" not in r.text
    levels = [rec.levelname for rec in caplog.records if rec.name == "rpg.cron"]
    assert levels == ["WARNING", "WARNING", "ERROR"]
    assert "example.com" not in caplog.text and '"consecutive_failures": 3' in caplog.text


class _DB:
    rowcount = 0

    def __init__(self, store):
        self.s = store

    def execute(self, sql, params=()):
        return self

    def fetchall(self):
        return self.s.claim()

    def transaction(self):
        return nullcontext()


class _Store:
    """Fake of FOR UPDATE SKIP LOCKED: a claimed owner is invisible to others."""

    def __init__(self, owners):
        self.pending, self.lock = list(owners), threading.Lock()

    def claim(self):
        with self.lock:
            return [{"owner_id": self.pending.pop(0)}] if self.pending else []

    def connection(self):
        return nullcontext(_DB(self))


def _runtime(store):
    return SimpleNamespace(game_store=SimpleNamespace(pool=store),
                           identity_verifier=object(), blob_store=object())


def test_account_deletion_endpoint_dedups_and_hides_ids(monkeypatch):
    owner = uuid4()
    store, finished = _Store([owner]), []

    class Lifecycle:
        def __init__(self, *_a): pass

        def finish(self, o):
            finished.append(o)
            return "deleted"
    monkeypatch.setattr(cli, "PostgresAccountLifecycle", Lifecycle)
    monkeypatch.setattr(cron_internal, "_runtime", lambda: _runtime(store))
    monkeypatch.setenv("RPG_RUNTIME_PROFILE", "hosted-supabase")
    responses = []
    threads = [threading.Thread(target=lambda: responses.append(
        client.post("/internal/cron/account-deletions", headers=H))) for _ in range(2)]
    [t.start() for t in threads]
    [t.join() for t in threads]
    assert finished == [owner]  # processed exactly once
    assert sorted(r.json()["claimed"] for r in responses) == [0, 1]
    assert all(str(owner) not in r.text and "@" not in r.text for r in responses)


def test_account_deletion_failure_counts(monkeypatch):
    store = _Store([uuid4()])

    class Lifecycle:
        def __init__(self, *_a): pass

        def finish(self, o):
            raise ValueError("x")
    monkeypatch.setattr(cli, "PostgresAccountLifecycle", Lifecycle)
    monkeypatch.setattr(cron_internal, "_runtime", lambda: _runtime(store))
    monkeypatch.setenv("RPG_RUNTIME_PROFILE", "hosted-supabase")
    r = client.post("/internal/cron/account-deletions", headers=H)
    body = r.json()
    assert r.status_code == 500  # F1: failures surface as non-2xx for pg_net
    assert body["failed"] == 1 and body["ok"] is False and "@" not in r.text


def test_account_deletions_wrong_profile_fails(monkeypatch):
    monkeypatch.setenv("RPG_RUNTIME_PROFILE", "local")
    assert client.post("/internal/cron/account-deletions", headers=H).status_code == 500


def test_operations_endpoint(monkeypatch):
    monkeypatch.setattr(cron_internal, "_runtime", lambda: _runtime(object()))
    monkeypatch.setattr("services.operation_recovery.recover_expired",
                        lambda pool, n: {"orphans_seen": 2, "released": 2})
    body = client.post("/internal/cron/operations", headers=H).json()
    assert body["released"] == 2 and body["ok"] is True


def test_security_headers_csp():
    r = client.get("/health")
    csp = r.headers["content-security-policy"]
    assert r.headers["x-frame-options"] == "DENY"
    for part in ("default-src 'self'", "frame-ancestors 'none'", "object-src 'none'",
                 "script-src 'self' https://challenges.cloudflare.com", "base-uri 'self'"):
        assert part in csp
    assert "unsafe-eval" not in csp and "script-src 'self' 'unsafe-inline'" not in csp
    # Vite output must keep scripts external (no inline <script>) for this CSP to hold
    import re
    from pathlib import Path
    index = Path("web/dist/index.html")
    if index.exists():
        assert not re.search(r"<script(?![^>]*\bsrc=)[^>]*>\s*\S", index.read_text(encoding="utf-8"))


def test_claim_pending_has_reclaim_cooldown():
    seen = {}

    class DB:
        def execute(self, sql, params=()):
            seen["sql"] = sql
            return self

        def fetchall(self):
            return []

        def transaction(self):
            return nullcontext()

    class Pool:
        def connection(self):
            return nullcontext(DB())
    cli.claim_pending(Pool(), 5)
    assert "recovery_attempted_at is null" in seen["sql"]
    assert "recovery_attempted_at < now() - interval '2 minutes'" in seen["sql"]
