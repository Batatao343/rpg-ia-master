"""SPEC-236 Sol review: real-concurrency races on the wallet sweep and the poisoned-job lease.

Separate connections commit (unique owners/kinds per run, like ``test_wallet_local.py``)."""

from __future__ import annotations

import os
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone, UTC
from threading import Barrier
from uuid import uuid4

import pytest

from infrastructure.contracts import JobRequest, Principal
from services.shard_pricing import INSTALLED_RATE_CARD_OBSERVED_AT, INSTALLED_RATE_CARD_SHA256
from services.usage_metering import RATE_CARD_VERSION, normalize_attempts
from tests.fakes.local_pricing import installed_card_max_age_seconds

pytestmark = pytest.mark.infra_local
AT = datetime(2026, 10, 12, 12, tzinfo=UTC)


@pytest.fixture
def race_case():
    psycopg = pytest.importorskip("psycopg")
    from psycopg.types.json import Jsonb

    from infrastructure.postgres import PostgresPool
    from infrastructure.wallet import PostgresWallet

    dsn = os.getenv("RPG_TEST_DATABASE_URL")
    if not dsn:
        pytest.skip("RPG_TEST_DATABASE_URL absent")
    version = "spec236-race-" + str(uuid4())
    with psycopg.connect(dsn) as connection:
        if connection.execute("select to_regclass('app.wallet_accounts')").fetchone()[0] is None:
            pytest.skip("SPEC-184 migration absent")
        connection.execute(
            """insert into app.pricing_versions
          (version_id,shard_budget_unit_brl,fx_usd_brl,fx_source,fx_observed_at,fx_max_age_seconds,
           fx_buffer_rate,rate_card_version,rate_card_sha256,rate_card_source,
           rate_card_observed_at,rate_card_max_age_seconds,channel_fees)
          values (%s,0.03,5,'test',%s,864000,0.1,%s,%s,'test',%s,%s,%s)""",
            (
                version,
                AT,
                RATE_CARD_VERSION,
                INSTALLED_RATE_CARD_SHA256,
                INSTALLED_RATE_CARD_OBSERVED_AT,
                installed_card_max_age_seconds(),
                Jsonb({"web": {"percentage": "0.04", "fixed_brl": "0.20"}}),
            ),
        )
    pool = PostgresPool(dsn, max_size=8)
    wallet = PostgresWallet(pool)
    owner = Principal(uuid4(), "test", "race")
    wallet.adjust_admin(
        owner,
        adjustment_id=str(uuid4()),
        signed_milli=1000,
        actor_id=uuid4(),
        reason="spec236 race fixture",
    )
    try:
        yield dsn, pool, wallet, owner, version
    finally:
        pool.close()


def _sql(dsn, sql, params=()):
    import psycopg
    from psycopg.rows import dict_row

    with psycopg.connect(dsn, row_factory=dict_row) as connection:
        cursor = connection.execute(sql, params)
        return cursor.fetchall() if cursor.description else None


def _operation(dsn, owner, status):
    op = uuid4()
    _sql(
        dsn,
        "insert into app.operations(id,owner_id,kind,status,request_sha256) "
        "values (%s,%s,'turn',%s,%s)",
        (op, owner.user_id, status, "f" * 64),
    )
    return op


def _ledger_ok(dsn, wallet, owner):
    row = _sql(
        dsn,
        "select coalesce(sum(available_delta),0) a,coalesce(sum(reserved_delta),0) r "
        "from app.wallet_entries where owner_id=%s",
        (owner.user_id,),
    )[0]
    balance = wallet.balance(owner)
    return (int(row["a"]), int(row["r"])) == (balance.available_milli, balance.reserved_milli)


def _parallel(n, fn):
    barrier = Barrier(n)

    def run():
        barrier.wait()
        return fn()

    with ThreadPoolExecutor(max_workers=n) as executor:
        return [f.result() for f in [executor.submit(run) for _ in range(n)]]


def test_concurrent_sweeps_release_an_orphan_exactly_once(race_case):
    from services.wallet_recovery import recover_wallet_reservations

    dsn, pool, wallet, owner, version = race_case
    op = _operation(dsn, owner, "abandoned")
    held = wallet.reserve(
        owner,
        reference_type="operation",
        reference_id=str(op),
        pricing_version_id=version,
        ceiling_milli=7,
        fence_token=uuid4(),
        usage_operation_id=op,
        at=AT,
    )
    _sql(
        dsn,
        "update app.wallet_reservations set created_at=now()-interval '2 hours' "
        "where reservation_id=%s",
        (held.reservation_id,),
    )
    results = _parallel(3, lambda: recover_wallet_reservations(pool, owner_id=owner.user_id))
    assert sum(r["wallet_errors"] for r in results) == 0
    releases = _sql(
        dsn,
        "select count(*) n from app.wallet_entries where reservation_id=%s "
        "and entry_type='release'",
        (held.reservation_id,),
    )[0]["n"]
    assert releases == 1  # never double-released
    assert (
        wallet.balance(owner).available_milli == 1000 and wallet.balance(owner).reserved_milli == 0
    )
    assert _ledger_ok(dsn, wallet, owner)


def test_concurrent_sweeps_and_owner_settle_one_terminal_outcome(race_case):
    import psycopg
    from psycopg.rows import dict_row

    from infrastructure.usage_events import append_usage_events
    from infrastructure.wallet import UncertainEffect
    from services.wallet_recovery import recover_wallet_reservations

    dsn, pool, wallet, owner, version = race_case
    op = _operation(dsn, owner, "completed")
    held = wallet.reserve(
        owner,
        reference_type="operation",
        reference_id=str(op),
        pricing_version_id=version,
        ceiling_milli=20,
        fence_token=uuid4(),
        usage_operation_id=op,
        at=AT,
    )
    wallet.admit_attempt(
        owner,
        held.reservation_id,
        fence_token=held.fence_token,
        attempt_key="a1",
        provider="groq",
        model="openai/gpt-oss-120b",
        at=AT,
    )
    events = normalize_attempts(
        [
            {
                "provider": "groq",
                "model": "openai/gpt-oss-120b",
                "outcome": "success",
                "network_attempted": True,
                "usage": {"input_tokens": 1000, "output_tokens": 300},
            }
        ],
        operation_id=op,
    )
    with psycopg.connect(dsn, row_factory=dict_row) as connection, connection.transaction():
        append_usage_events(
            connection, owner_id=owner.user_id, operation_id=op, game_id=None, events=events
        )
    _sql(
        dsn,
        "update app.wallet_reservations set created_at=now()-interval '2 hours' "
        "where reservation_id=%s",
        (held.reservation_id,),
    )
    calls = iter(["sweep", "owner", "sweep"])

    def act():
        if next(calls) == "owner":
            try:
                return wallet.settle_usage(
                    owner,
                    held.reservation_id,
                    fence_token=held.fence_token,
                    usage_event_ids=[events[0].event_id],
                    at=AT,
                ).status
            except UncertainEffect:
                return "fenced"
        return recover_wallet_reservations(pool, owner_id=owner.user_id)

    _parallel(3, act)
    row = _sql(
        dsn,
        "select status from app.wallet_reservations where reservation_id=%s",
        (held.reservation_id,),
    )[0]
    settles = _sql(
        dsn,
        "select count(*) n from app.wallet_entries where reservation_id=%s and entry_type='settle'",
        (held.reservation_id,),
    )[0]["n"]
    assert row["status"] in ("settled", "uncertain")
    assert settles == (1 if row["status"] == "settled" else 0)
    assert _ledger_ok(dsn, wallet, owner)


def test_concurrent_workers_never_lease_a_poisoned_job(race_case):
    from infrastructure.postgres_jobs import PostgresJobQueue

    dsn, pool, wallet, owner, version = race_case
    queue = PostgresJobQueue(pool, lease_seconds=30)
    kind = "spec236_race_" + uuid4().hex[:8]
    job_id = queue.enqueue(JobRequest(kind, "k", {}, max_attempts=2))
    for _ in range(2):
        assert len(queue.lease("w", {kind}, 1)) == 1
        _sql(
            dsn, "update app.jobs set lease_until=now()-interval '1 second' where id=%s", (job_id,)
        )
    leased = _parallel(4, lambda: queue.lease("w", {kind}, 1))
    assert all(batch == [] for batch in leased)
    row = _sql(dsn, "select status,attempts,last_error_code from app.jobs where id=%s", (job_id,))[
        0
    ]
    assert (row["status"], row["attempts"], row["last_error_code"]) == (
        "dead",
        2,
        "lease_expired_max_attempts",
    )
