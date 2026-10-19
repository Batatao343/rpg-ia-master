"""SPEC-254: logs do Postgres (lease/versao/pool/timeouts) sem SQL, parametros, DSN ou host."""
import ast
import json
import uuid
from contextlib import contextmanager
from pathlib import Path

import pytest

from infrastructure import db_log
from infrastructure.postgres import PostgresPool
from observability import logging_setup
from observability.metrics import metrics

ROOT = Path(__file__).resolve().parents[1]
DSN = "postgresql://user:pw-SENTINELA@db-SENTINELA.invalid:5432/prod"


@pytest.fixture(autouse=True)
def _logs():
    logging_setup.configure_logging({"RPG_LOG_LEVEL": "debug"})


def _lines(capsys):
    out = []
    for raw in capsys.readouterr().out.splitlines():
        try:
            out.append(json.loads(raw))
        except ValueError:
            pass
    return out


def test_pool_timeout_logged(capsys):
    pool = PostgresPool(DSN, min_size=0, max_size=2, timeout=0.6, connect_timeout=1)
    try:
        with pytest.raises(Exception):
            with pool.connection():
                pass
    finally:
        pool.close()
    out = capsys.readouterr().out
    lines = [json.loads(x) for x in out.splitlines() if x.startswith("{")]
    (line,) = [x for x in lines if x["event"] in {"db.pool_timeout", "db.connect_failed"}]
    assert line["pool"] == "request" and line["wait_ms"] >= 0 and line["level"] == "error"
    assert "SENTINELA" not in out and "invalid" not in out.replace("error_type", "")


def test_admin_pool_label(capsys):
    pool = PostgresPool(DSN, min_size=0, max_size=1, timeout=0.5, connect_timeout=1)
    try:
        with pytest.raises(Exception):
            with pool.admin_connection():
                pass
    finally:
        pool.close()
    lines = [json.loads(x) for x in capsys.readouterr().out.splitlines() if x.startswith("{")]
    assert any(x.get("pool") == "admin" for x in lines)


class _QueryCanceled(Exception):
    pass


_QueryCanceled.__name__ = "QueryCanceled"


class _LockNotAvailable(Exception):
    pass


_LockNotAvailable.__name__ = "LockNotAvailable"


def _fake_pool():
    class _Fake:
        def get_stats(self):
            return {"pool_size": 2, "pool_available": 0}

        @contextmanager
        def connection(self):
            yield object()

    pool = object.__new__(PostgresPool)
    pool._pool, pool._transaction_pooler, pool._request_rls, pool.admin_pool = _Fake(), False, False, None
    return pool


@pytest.mark.parametrize("exc_class,event", [(_QueryCanceled, "db.statement_timeout"),
                                             (_LockNotAvailable, "db.lock_timeout")])
def test_statement_and_lock_timeout_logged(capsys, exc_class, event):
    pool = _fake_pool()

    @db_log.timed_call("turn.claim")
    def run():
        with pool.connection():
            raise exc_class("select * from app.games where secret = 'SQL-SENTINELA'")

    with pytest.raises(exc_class):
        run()
    out = capsys.readouterr().out
    lines = [json.loads(x) for x in out.splitlines() if x.startswith("{")]
    (line,) = [x for x in lines if x["event"] == event]
    assert line["query_name"] == "turn.claim" and line["level"] == "error"
    assert "SQL-SENTINELA" not in out and "select" not in out


def test_slow_query_and_metric(capsys, monkeypatch):
    monkeypatch.setenv("RPG_DB_SLOW_MS", "0")
    with db_log.timed("unit.slow"):
        pass
    (line,) = [x for x in _lines(capsys) if x["event"] == "db.slow_query"]
    assert line["query_name"] == "unit.slow" and line["level"] == "warning"
    assert any("rpg_db_query_seconds" in key and "unit.slow" in key for key in metrics.snapshot())


def test_fast_query_is_not_slow(capsys, monkeypatch):
    monkeypatch.setenv("RPG_DB_SLOW_MS", "60000")
    with db_log.timed("unit.fast"):
        pass
    assert not [x for x in _lines(capsys) if x["event"] == "db.slow_query"]


def test_conflict_log_uses_pseudonyms(capsys):
    op, game = uuid.uuid4(), uuid.uuid4()
    db_log.conflict("lease_conflict", "fence_invalid", op_kind="turn", operation_id=op, game_id=game)
    out = capsys.readouterr().out
    (line,) = [json.loads(x) for x in out.splitlines() if "db.lease_conflict" in x]
    assert line["reason"] == "fence_invalid" and line["op_kind"] == "turn"
    assert str(op) not in out and str(game) not in out and line["op_ref"] and line["game_ref"]


def _raise_sites(path):
    tree = ast.parse((ROOT / path).read_text(encoding="utf-8"))
    sites = []
    # (lista plana de statements por bloco, para olhar o statement imediatamente anterior ao raise)
    for node in ast.walk(tree):
        body = getattr(node, "body", None)
        if isinstance(body, list):
            for idx, stmt in enumerate(body):
                if (isinstance(stmt, ast.Raise) and isinstance(stmt.exc, ast.Call)
                        and getattr(stmt.exc.func, "id", "") in {"LeaseHeld", "StaleVersion"}):
                    prev = body[idx - 1] if idx else None
                    sites.append((stmt.lineno, prev))
    return sites


@pytest.mark.parametrize("path", ["infrastructure/postgres_turns.py", "infrastructure/postgres_jobs.py",
                                  "services/lease_heartbeat.py"])
def test_every_lease_or_version_raise_is_logged(path):
    sites = _raise_sites(path)
    assert sites, path
    for lineno, prev in sites:
        src = ast.unparse(prev) if prev is not None else ""
        assert "conflict(" in src, f"{path}:{lineno} levanta sem log db.* antes"


def test_postgres_modules_do_not_log_sql():
    for path in ("infrastructure/postgres.py", "infrastructure/postgres_turns.py",
                 "infrastructure/postgres_jobs.py", "infrastructure/db_log.py"):
        tree = ast.parse((ROOT / path).read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.Call) and getattr(node.func, "id", "") in {"log_event", "_log_event"}:
                for kw in node.keywords:
                    assert kw.arg not in {"sql", "query", "params", "dsn", "host"}, (path, node.lineno)
