"""SPEC-367 R18/R19: pool tolerante e retry só de checkout nos scripts de operação."""

from __future__ import annotations

import pytest
from psycopg import OperationalError
from psycopg_pool import PoolTimeout

from scripts import admin_kill_switch as cli
from scripts.staging import art_preflight, ops_pool
from services import kill_switches as ks


@pytest.fixture(autouse=True)
def _no_sleep(monkeypatch):
    monkeypatch.setattr(ops_pool.time, "sleep", lambda s: None)


def test_retry_on_checkout_timeout_then_ok(capsys):
    calls = []

    def fn():
        calls.append(1)
        if len(calls) == 1:
            raise PoolTimeout("couldn't get a connection secret-dsn-host")
        return "ok"

    assert ops_pool.with_checkout_retry(fn) == "ok"
    assert len(calls) == 2
    err = capsys.readouterr().err
    assert "ops.db_retry attempt=1 error_class=PoolTimeout" in err
    assert "secret-dsn-host" not in err


def test_no_retry_after_execute_error():
    class Conn:
        def execute(self):
            raise OperationalError("connection dropped mid-command")

    calls = []

    def fn():
        calls.append(1)
        Conn().execute()

    with pytest.raises(OperationalError):
        ops_pool.with_checkout_retry(fn)
    assert len(calls) == 1


def test_retry_operational_error_at_checkout():
    calls = []

    def getconn():
        raise OperationalError("connect failed")

    def fn():
        calls.append(1)
        if len(calls) < 3:
            getconn()
        return 1

    assert ops_pool.with_checkout_retry(fn) == 1 and len(calls) == 3


def test_open_ops_pool_params(monkeypatch):
    seen = {}

    class P:
        def __init__(self, dsn, **kw):
            seen.update(kw)

    monkeypatch.setattr("infrastructure.postgres.PostgresPool", P)
    ops_pool.open_ops_pool("postgresql://x")
    assert seen == {"max_size": 1, "timeout": 20.0, "connect_timeout": 10.0}


class _Flaky(ks.MemorySwitchStore):
    """Primeira tentativa de cada operação falha no checkout; a segunda conclui."""

    def __init__(self):
        super().__init__()
        self.attempts = {"load": 0, "set": 0}
        self.applied = 0

    def load(self):
        self.attempts["load"] += 1
        if self.attempts["load"] == 1:
            raise PoolTimeout("t")
        return super().load()

    def set(self, key, enabled, **kw):
        self.attempts["set"] += 1
        if self.attempts["set"] == 1:
            raise PoolTimeout("t")
        self.applied += 1
        return super().set(key, enabled, **kw)


def test_kill_switch_apply_sets_once(capsys):
    store = _Flaky()
    args = ["off", ks.IMAGE, "--actor", "ana", "--reason", "x", "--apply"]
    assert cli.main(args, store=store) == 0
    assert store.applied == 1 and len(store.audit_rows) == 1
    assert cli.main(["list"], store=store) == 0


def test_exhausted_retries_exit_nonzero_short_message(capsys):
    class Dead(ks.MemorySwitchStore):
        def load(self):
            raise PoolTimeout("long secret message postgresql://u:pw@host")

    assert cli.main(["list"], store=Dead()) != 0
    out = capsys.readouterr()
    assert "error: db_unavailable" in out.err
    assert "pw@host" not in out.err + out.out


class _Pool:
    def __init__(self):
        self.closed = 0

    def close(self):
        self.closed += 1


def test_preflight_closes_pool_on_error(monkeypatch, tmp_path):
    pool = _Pool()
    env = tmp_path / "e.env"
    env.write_text("RPG_STAGING_DB_URL=postgresql://u:pw@h/db\n", encoding="utf-8")
    monkeypatch.setattr(art_preflight, "open_ops_pool", lambda dsn: pool)

    class Boom:
        def __init__(self, _pool):
            pass

        def load(self):
            raise RuntimeError("boom")

        def audit(self, n):
            return []

    monkeypatch.setattr("infrastructure.kill_switch_store.PostgresSwitchStore", Boom)
    monkeypatch.setattr(
        "services.image_quotes.ImageQuoteRepository",
        lambda p: type("R", (), {"peek_ceiling": lambda self, k: 15000})(),
    )
    with pytest.raises(RuntimeError):
        art_preflight.main(["--env-file", str(env)])
    assert pool.closed == 1


def test_no_dsn_in_output(monkeypatch, tmp_path, capsys):
    pool = _Pool()
    env = tmp_path / "e.env"
    env.write_text("RPG_STAGING_DB_URL=postgresql://u:pw@h/db\n", encoding="utf-8")
    monkeypatch.setattr(art_preflight, "open_ops_pool", lambda dsn: pool)

    class Dead:
        def __init__(self, _pool):
            pass

        def load(self):
            raise PoolTimeout("postgresql://u:pw@h/db")

        def audit(self, n):
            return []

    monkeypatch.setattr("infrastructure.kill_switch_store.PostgresSwitchStore", Dead)
    monkeypatch.setattr(
        "services.image_quotes.ImageQuoteRepository",
        lambda p: type("R", (), {"peek_ceiling": lambda self, k: 15000})(),
    )
    assert art_preflight.main(["--env-file", str(env)]) != 0
    captured = capsys.readouterr()
    assert "pw@h" not in captured.out + captured.err
    assert "error: db_unavailable" in captured.err
    assert pool.closed == 1


def test_no_retry_on_commit_error():
    """P2-1: falha no commit (depois do insert) não é repetida: 1 única escrita."""
    writes = []

    class Tx:
        def __enter__(self):
            return self

        def __exit__(self, *a):
            raise OperationalError("server closed the connection after commit")

    def store_set():
        writes.append(1)  # o insert já foi enviado
        with Tx():
            pass

    with pytest.raises(OperationalError):
        ops_pool.with_checkout_retry(store_set)
    assert len(writes) == 1
