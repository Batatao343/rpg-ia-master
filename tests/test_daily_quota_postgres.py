"""SPEC-219 R3: cota diaria por owner em Postgres real (Supabase local), migration idempotente e purge."""

from __future__ import annotations

import os
import threading
from pathlib import Path
from uuid import uuid4

import pytest

pytestmark = pytest.mark.infra_local

MIGRATION = Path("supabase/migrations/20261017110000_owner_daily_counters.sql")


@pytest.fixture
def pool():
    pytest.importorskip("psycopg")
    dsn = os.getenv("RPG_TEST_DATABASE_URL")
    if not dsn:
        pytest.skip("RPG_TEST_DATABASE_URL ausente")
    from infrastructure.postgres import PostgresPool

    pool = PostgresPool(dsn, max_size=4)
    with pool.connection() as db:
        db.execute(MIGRATION.read_text(encoding="utf-8"))  # idempotente: 2a aplicacao e segura
        db.execute(MIGRATION.read_text(encoding="utf-8"))
    owners: list = []
    pool.owners = owners
    try:
        yield pool
    finally:
        with pool.connection() as db:
            db.execute("delete from app.owner_daily_counters where owner_id = any(%s)", (owners,))
        pool.close()


def _owner(pool):
    owner = uuid4()
    pool.owners.append(owner)
    return owner


def test_limit_then_denied_with_retry_until_midnight_utc(pool):
    from infrastructure.postgres_turns import PostgresDailyQuota

    quota = PostgresDailyQuota(pool)
    owner = _owner(pool)
    for expected in range(1, 6):
        decision = quota.bump(owner, "turn", 5)
        assert decision.allowed and decision.count == expected
    denied = quota.bump(owner, "turn", 5)
    assert not denied.allowed and denied.count == 5 and 1 <= denied.retry_after_seconds <= 86400
    assert quota.bump(owner, "turn", 5).count == 5  # recusa NAO consome
    assert quota.bump(owner, "llm_aux", 5).allowed  # outra classe
    assert quota.bump(_owner(pool), "turn", 5).allowed  # outro owner


def test_concurrent_bumps_never_exceed_the_limit(pool):
    from infrastructure.postgres_turns import PostgresDailyQuota

    quota = PostgresDailyQuota(pool)
    owner = _owner(pool)
    results: list[bool] = []
    lock = threading.Lock()

    def worker():
        for _ in range(10):
            allowed = quota.bump(owner, "turn", 7).allowed
            with lock:
                results.append(allowed)

    threads = [threading.Thread(target=worker) for _ in range(2)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert len(results) == 20 and sum(results) == 7
    with pool.connection() as db:
        row = db.execute(
            "select count from app.owner_daily_counters where owner_id=%s and class='turn'",
            (owner,),
        ).fetchone()
    assert row["count"] == 7


def test_table_is_backend_only_and_purged(pool):
    from services.retention import purge_expired

    owner = _owner(pool)
    with pool.connection() as db:
        db.execute(
            "insert into app.owner_daily_counters(owner_id, day, class, count) values "
            "(%s, (now() at time zone 'utc')::date - 10, 'turn', 3), "
            "(%s, (now() at time zone 'utc')::date, 'turn', 1)",
            (owner, owner),
        )
        assert db.execute(
            "select relrowsecurity and relforcerowsecurity as ok from pg_class "
            "where oid='app.owner_daily_counters'::regclass"
        ).fetchone()["ok"]
        for role in ("anon", "authenticated", "rpg_api"):
            assert not db.execute(
                "select has_table_privilege(%s,'app.owner_daily_counters','SELECT') as p", (role,)
            ).fetchone()["p"]
    result = purge_expired(pool)
    assert result["purged_owner_daily_counters"] >= 1
    with pool.connection() as db:
        rows = db.execute(
            "select day from app.owner_daily_counters where owner_id=%s", (owner,)
        ).fetchall()
    assert len(rows) == 1


def test_rejects_non_positive_limit(pool):
    from infrastructure.postgres_turns import PostgresDailyQuota

    with pytest.raises(ValueError):
        PostgresDailyQuota(pool).bump(_owner(pool), "turn", 0)
