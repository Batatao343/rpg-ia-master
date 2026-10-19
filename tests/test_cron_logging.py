"""SPEC-256: cron run_id, started/failed, persisted failure count, item failures, auth rejects."""

from __future__ import annotations

import json
import logging
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

import api
from services import cron_internal

SECRET = "s" * 40
H = {"Authorization": f"Bearer {SECRET}"}
client = TestClient(api.app)


@pytest.fixture(autouse=True)
def _env(monkeypatch, caplog):
    monkeypatch.setenv("RPG_CRON_SECRET", SECRET)
    cron_internal._failures.clear()
    caplog.set_level(logging.DEBUG, logger="rpg.cron")


def _events(caplog):
    out = []
    for rec in caplog.records:
        if rec.name == "rpg.cron":
            try:
                out.append(json.loads(rec.getMessage()))
            except ValueError:
                pass
    return out


def test_run_id_on_start_and_finish(monkeypatch, caplog):
    monkeypatch.setattr("workers.drain.drain_jobs", lambda *a, **k: {"processed": 1})
    assert client.post("/internal/cron/jobs", headers=H).status_code == 200
    ev = _events(caplog)
    started = next(e for e in ev if e["event"] == "cron.started")
    finished = next(e for e in ev if e["event"] == "rpg.cron")
    assert started["run_id"] == finished["run_id"] and len(started["run_id"]) == 12
    assert finished["outcome"] == "ok"
    client.post("/internal/cron/jobs", headers=H)
    assert len({e["run_id"] for e in _events(caplog) if e["event"] == "cron.started"}) == 2


def test_failure_logs_stack_without_message(monkeypatch, caplog):
    def boom(*a, **k):
        raise RuntimeError("secret@example.com")

    monkeypatch.setattr("workers.drain.drain_jobs", boom)
    assert client.post("/internal/cron/jobs", headers=H).status_code == 500
    failed = next(e for e in _events(caplog) if e["event"] == "cron.failed")
    assert failed["error_type"] == "RuntimeError" and failed["stack"]
    assert "example.com" not in caplog.text


def test_item_failure_logged(caplog):
    cron_internal.item_failed(
        "account_deletions", "account_deletion", "owner-123", ValueError("a@b.com")
    )
    e = next(e for e in _events(caplog) if e["event"] == "cron.item_failed")
    assert e["item_kind"] == "account_deletion" and e["error_type"] == "ValueError"
    assert e["item_ref"] != "owner-123" and "a@b.com" not in caplog.text


def test_item_failure_in_recovery_batch(caplog):
    from scripts import recover_account_deletions as cli

    class Life:
        def __init__(self, *a):
            pass

        def finish(self, o):
            raise RuntimeError("x@y.com")

    class Pool:
        def connection(self):
            from contextlib import nullcontext

            return nullcontext(
                SimpleNamespace(
                    execute=lambda *a, **k: SimpleNamespace(rowcount=0),
                    transaction=lambda: __import__("contextlib").nullcontext(),
                )
            )

    runtime = SimpleNamespace(
        game_store=SimpleNamespace(pool=Pool()), identity_verifier=None, blob_store=None
    )
    orig = cli.PostgresAccountLifecycle
    cli.PostgresAccountLifecycle = Life
    try:
        cli.run_recovery_batch(
            runtime, 1, rows=[{"owner_id": "11111111-1111-1111-1111-111111111111"}]
        )
    finally:
        cli.PostgresAccountLifecycle = orig
    e = next(e for e in _events(caplog) if e["event"] == "cron.item_failed")
    assert e["item_kind"] == "account_deletion" and "1111111111" not in json.dumps(e)


def test_consecutive_failures_persisted(monkeypatch, caplog):
    store = {"n": 0}

    class Conn:
        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

        def execute(self, sql, params):
            store["n"] = 0 if params[3] else store["n"] + 1
            return SimpleNamespace(fetchone=lambda: {"consecutive_failures": store["n"]})

    pool = SimpleNamespace(connection=lambda: Conn())
    monkeypatch.setattr(
        cron_internal, "_runtime", lambda: SimpleNamespace(game_store=SimpleNamespace(pool=pool))
    )
    monkeypatch.setattr(
        "workers.drain.drain_jobs", lambda *a, **k: (_ for _ in ()).throw(RuntimeError("x"))
    )
    for _ in range(3):
        cron_internal._failures.clear()  # simulate a cold start between runs
        client.post("/internal/cron/jobs", headers=H)
    last = [e for e in _events(caplog) if e["event"] == "rpg.cron"][-1]
    assert last["consecutive_failures"] == 3
    assert [r.levelname for r in caplog.records if '"event": "rpg.cron"' in r.getMessage()][
        -1
    ] == "ERROR"


def test_db_unavailable_falls_back_to_memory(monkeypatch, caplog):
    def broken():
        raise RuntimeError("dsn=postgres://u:p@h/db")

    monkeypatch.setattr(cron_internal, "_runtime", broken)
    monkeypatch.setattr("workers.drain.drain_jobs", lambda *a, **k: {"processed": 0})
    assert client.post("/internal/cron/jobs", headers=H).status_code == 200
    assert "postgres://" not in caplog.text


def test_auth_rejected_logged(monkeypatch, caplog):
    client.post("/internal/cron/jobs")
    client.post("/internal/cron/jobs", headers={"Authorization": "Bearer nope"})
    monkeypatch.delenv("RPG_CRON_SECRET")
    client.post("/internal/cron/jobs", headers=H)
    reasons = [e["reason"] for e in _events(caplog) if e["event"] == "cron.auth_rejected"]
    assert reasons == ["missing", "invalid", "not_configured"]
    assert "nope" not in caplog.text
