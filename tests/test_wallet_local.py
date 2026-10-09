"""SPEC-184 Postgres conservation, replay, recovery, concurrency and RLS gates."""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
import os
import random
from uuid import UUID, uuid4

import pytest

from infrastructure.contracts import Principal
from infrastructure.postgres import PostgresPool
from infrastructure.usage_events import append_usage_events
from infrastructure.wallet import (
    InsufficientShards, PostgresWallet, SpendCeilingExceeded,
    UncertainEffect, WalletConflict,
)
from services.shard_pricing import INSTALLED_RATE_CARD_OBSERVED_AT, INSTALLED_RATE_CARD_SHA256
from services.usage_metering import RATE_CARD_VERSION, normalize_attempts


pytestmark = pytest.mark.infra_local
TEST_AT = datetime(2026, 10, 8, 12, tzinfo=timezone.utc)


@pytest.fixture
def wallet_case():
    psycopg = pytest.importorskip("psycopg")
    from psycopg.types.json import Jsonb

    dsn = os.getenv("RPG_TEST_DATABASE_URL")
    if not dsn:
        pytest.skip("RPG_TEST_DATABASE_URL ausente")
    owner = uuid4()
    version_id = "wallet-test-" + str(uuid4())
    sku_id = "wallet-test-" + str(uuid4())
    now = TEST_AT
    with psycopg.connect(dsn) as connection:
        if connection.execute("select to_regclass('app.wallet_accounts')").fetchone()[0] is None:
            pytest.skip("migration SPEC-184 não aplicada")
        connection.execute(
            """insert into app.pricing_versions
            (version_id,shard_budget_unit_brl,fx_usd_brl,fx_source,
             fx_observed_at,fx_max_age_seconds,fx_buffer_rate,
             rate_card_version,rate_card_sha256,rate_card_source,
             rate_card_observed_at,rate_card_max_age_seconds,channel_fees)
            values (%s,0.03,5,'test FX',%s,86400,0.10,%s,%s,'test card',%s,86400,%s)""",
            (version_id, now, RATE_CARD_VERSION, INSTALLED_RATE_CARD_SHA256,
             INSTALLED_RATE_CARD_OBSERVED_AT,
             Jsonb({"web": {"percentage": "0.04", "fixed_brl": "0.20"}})),
        )
        connection.execute(
            """insert into app.purchase_skus
            (sku_id,pricing_version_id,channel,store_product_id,gross_brl,shard_milli)
            values (%s,%s,'web',%s,10.50,311)""",
            (sku_id, version_id, sku_id),
        )
    pool = PostgresPool(dsn, max_size=8)
    wallet = PostgresWallet(pool)
    principal = Principal(owner, "test", str(owner))
    wallet.credit_verified_purchase(principal, channel="web", payment_id=str(uuid4()),
                                    sku_id=sku_id, verified=True)
    try:
        yield wallet, principal, version_id, sku_id, dsn
    finally:
        pool.close()


def _reserve(wallet, principal, version_id, ceiling=20, operation_id=None):
    reference_type = "operation" if operation_id else "other"
    reference_id = str(operation_id or uuid4())
    fence = uuid4()
    return wallet.reserve(principal, reference_type=reference_type,
                          reference_id=reference_id, pricing_version_id=version_id,
                          ceiling_milli=ceiling, fence_token=fence,
                          usage_operation_id=operation_id, at=TEST_AT)


def _ledger_sums(dsn, owner):
    import psycopg

    with psycopg.connect(dsn) as connection:
        return connection.execute(
            "select coalesce(sum(available_delta),0),coalesce(sum(reserved_delta),0) "
            "from app.wallet_entries where owner_id=%s", (owner,),
        ).fetchone()


def test_purchase_reserve_release_replay_and_conservation(wallet_case):
    wallet, principal, version, sku, dsn = wallet_case
    assert wallet.balance(principal).available_milli == 311
    with pytest.raises(WalletConflict):
        wallet.credit_verified_purchase(principal, channel="web", payment_id=str(uuid4()),
                                        sku_id=sku, verified=False)
    fence = uuid4()
    ref = str(uuid4())
    first = wallet.reserve(principal, reference_type="other", reference_id=ref,
                           pricing_version_id=version, ceiling_milli=100,
                           fence_token=fence, at=TEST_AT)
    assert wallet.reserve(principal, reference_type="other", reference_id=ref,
                          pricing_version_id=version, ceiling_milli=100,
                          fence_token=fence, at=TEST_AT) == first
    with pytest.raises(WalletConflict):
        wallet.reserve(principal, reference_type="other", reference_id=ref,
                       pricing_version_id=version, ceiling_milli=101,
                       fence_token=fence, at=TEST_AT)
    assert wallet.balance(principal).available_milli == 211
    assert wallet.balance(principal).reserved_milli == 100
    done = wallet.release_pre_effect(principal, first.reservation_id, fence_token=fence)
    assert done.status == "released" and done.released_milli == 100
    assert wallet.release_pre_effect(principal, first.reservation_id, fence_token=fence) == done
    assert wallet.balance(principal).available_milli == 311
    assert tuple(wallet.balance(principal).__dict__.values()) == _ledger_sums(dsn, principal.user_id)


def test_concurrent_reservations_cannot_double_spend(wallet_case):
    wallet, principal, version, _, dsn = wallet_case
    def reserve_one(_):
        try:
            return _reserve(wallet, principal, version, ceiling=200)
        except InsufficientShards:
            return None
    with ThreadPoolExecutor(max_workers=2) as executor:
        results = list(executor.map(reserve_one, range(2)))
    assert sum(value is not None for value in results) == 1
    assert wallet.balance(principal).available_milli == 111
    assert wallet.balance(principal).reserved_milli == 200
    assert _ledger_sums(dsn, principal.user_id) == (111, 200)


def test_ticketed_crash_holds_and_fences_replay(wallet_case):
    wallet, principal, version, _, dsn = wallet_case
    reserve = _reserve(wallet, principal, version)
    old_fence = reserve.fence_token
    liability = wallet.admit_attempt(
        principal, reserve.reservation_id, fence_token=old_fence,
        attempt_key="attempt-1", provider="groq", model="openai/gpt-oss-20b", at=TEST_AT,
    )
    assert liability > 0
    with pytest.raises(UncertainEffect):
        wallet.admit_attempt(principal, reserve.reservation_id, fence_token=old_fence,
                             attempt_key="attempt-1", provider="groq",
                             model="openai/gpt-oss-20b", at=TEST_AT)
    with pytest.raises(UncertainEffect):
        wallet.release_pre_effect(principal, reserve.reservation_id, fence_token=old_fence)
    new_fence = uuid4()
    recovered = wallet.recover(principal, reserve.reservation_id, new_fence_token=new_fence)
    assert recovered.status == "uncertain" and recovered.fence_token == new_fence
    with pytest.raises(UncertainEffect):
        wallet.admit_attempt(principal, reserve.reservation_id, fence_token=old_fence,
                             attempt_key="attempt-2", provider="groq",
                             model="openai/gpt-oss-20b", at=TEST_AT)
    assert wallet.balance(principal).reserved_milli == 20
    assert _ledger_sums(dsn, principal.user_id) == (291, 20)


def test_spend_ceiling_blocks_next_attempt_before_ticket(wallet_case):
    wallet, principal, version, _, dsn = wallet_case
    reserve = _reserve(wallet, principal, version, ceiling=1)
    with pytest.raises(SpendCeilingExceeded):
        wallet.admit_attempt(principal, reserve.reservation_id,
                             fence_token=reserve.fence_token, attempt_key="blocked",
                             provider="groq", model="openai/gpt-oss-20b", at=TEST_AT)
    with pytest.raises(SpendCeilingExceeded):
        wallet.admit_attempt(principal, reserve.reservation_id,
                             fence_token=reserve.fence_token, attempt_key="unknown",
                             provider="unknown", model="unknown", at=TEST_AT)
    assert wallet.recover(principal, reserve.reservation_id,
                          new_fence_token=uuid4()).status == "released"
    assert _ledger_sums(dsn, principal.user_id) == (311, 0)


def test_exact_usage_settles_once_after_pricing_expires(wallet_case):
    import psycopg
    from psycopg.rows import dict_row

    wallet, principal, version, _, dsn = wallet_case
    operation_id = uuid4()
    with psycopg.connect(dsn) as connection:
        connection.execute(
            "insert into app.operations(id,owner_id,kind,status,request_sha256) "
            "values (%s,%s,'embedding','running',%s)",
            (operation_id, principal.user_id, "a" * 64),
        )
    reserve = _reserve(wallet, principal, version, ceiling=20, operation_id=operation_id)
    wallet.admit_attempt(principal, reserve.reservation_id,
                         fence_token=reserve.fence_token, attempt_key="attempt-1",
                         provider="groq", model="openai/gpt-oss-20b", at=TEST_AT)
    events = normalize_attempts([{
        "provider": "groq", "model": "openai/gpt-oss-20b", "outcome": "success",
        "network_attempted": True,
        "usage": {"input_tokens": 1000, "output_tokens": 100},
    }], operation_id=operation_id)
    with psycopg.connect(dsn, row_factory=dict_row) as connection:
        with connection.transaction():
            append_usage_events(connection, owner_id=principal.user_id,
                                operation_id=operation_id, game_id=None,
                                events=events)
    result = wallet.settle_usage(principal, reserve.reservation_id,
                                 fence_token=reserve.fence_token,
                                 usage_event_ids=[events[0].event_id],
                                 at=datetime.now(timezone.utc) + timedelta(days=2))
    assert result.status == "settled" and result.settled_milli > 0
    assert result.settled_milli + result.released_milli == 20
    assert wallet.settle_usage(principal, reserve.reservation_id,
                               fence_token=reserve.fence_token,
                               usage_event_ids=[events[0].event_id]) == result
    assert wallet.balance(principal).reserved_milli == 0
    assert _ledger_sums(dsn, principal.user_id) == (
        311 - result.settled_milli, 0,
    )


def test_client_roles_only_see_own_views_and_cannot_write(wallet_case):
    import psycopg
    from psycopg.rows import dict_row

    wallet, principal, _, _, dsn = wallet_case
    other = Principal(uuid4(), "test", "other")
    assert wallet.balance(other).available_milli == 0
    with psycopg.connect(dsn, row_factory=dict_row) as connection:
        for relation in ("wallet_accounts", "wallet_entries", "wallet_reservations",
                         "wallet_attempt_tickets", "wallet_settled_usage"):
            for role in ("authenticated", "anon", "rpg_api"):
                for privilege in ("INSERT", "UPDATE", "DELETE"):
                    assert not connection.execute(
                        "select has_table_privilege(%s,%s,%s)",
                        (role, f"app.{relation}", privilege),
                    ).fetchone()["has_table_privilege"]
        assert not connection.execute(
            "select has_schema_privilege('authenticated','app','USAGE')"
        ).fetchone()["has_schema_privilege"]
        for view in ("wallet_balance_view", "wallet_history_view"):
            options = connection.execute(
                "select reloptions from pg_class where oid=%s::regclass",
                (f"public.{view}",),
            ).fetchone()["reloptions"]
            assert "security_barrier=true" in options
            for role in ("authenticated", "anon", "rpg_api"):
                assert connection.execute(
                    "select has_table_privilege(%s,%s,'SELECT')",
                    (role, f"public.{view}"),
                ).fetchone()["has_table_privilege"] is (role == "authenticated")
                for privilege in ("INSERT", "UPDATE", "DELETE"):
                    assert not connection.execute(
                        "select has_table_privilege(%s,%s,%s)",
                        (role, f"public.{view}", privilege),
                    ).fetchone()["has_table_privilege"]
        with connection.transaction():
            connection.execute("set local role authenticated")
            connection.execute("select set_config('request.jwt.claim.sub',%s,true)",
                               (str(principal.user_id),))
            rows = connection.execute("select * from public.wallet_balance_view").fetchall()
            assert len(rows) == 1 and rows[0]["available_milli"] == 311
            connection.execute("select set_config('request.jwt.claim.sub',%s,true)",
                               (str(other.user_id),))
            assert connection.execute("select * from public.wallet_balance_view").fetchall() == []
            with pytest.raises(psycopg.Error):
                with connection.transaction():
                    connection.execute("insert into app.wallet_accounts(owner_id) values (%s)",
                                       (other.user_id,))


def test_refund_admin_adjustment_and_cross_owner_payment_replay(wallet_case):
    import psycopg

    wallet, principal, _, sku, dsn = wallet_case
    with psycopg.connect(dsn) as connection:
        purchase_id = connection.execute(
            "select entry_id from app.wallet_entries where owner_id=%s and entry_type='purchase'",
            (principal.user_id,),
        ).fetchone()[0]
        payment_id = connection.execute(
            "select reference_id from app.wallet_entries where entry_id=%s",
            (purchase_id,),
        ).fetchone()[0]
    other = Principal(uuid4(), "test", "other")
    with pytest.raises(WalletConflict):
        wallet.credit_verified_purchase(other, channel="web", payment_id=payment_id,
                                        sku_id=sku, verified=True)
    actor = uuid4()
    assert wallet.adjust_admin(principal, adjustment_id=str(uuid4()),
                               signed_milli=5, actor_id=actor,
                               reason="operator correction").available_milli == 316
    refund_id = str(uuid4())
    assert wallet.refund_purchase(principal, purchase_entry_id=purchase_id,
                                  refund_id=refund_id).available_milli == 5
    assert wallet.refund_purchase(principal, purchase_entry_id=purchase_id,
                                  refund_id=refund_id).available_milli == 5
    with pytest.raises(WalletConflict):
        wallet.refund_purchase(principal, purchase_entry_id=purchase_id,
                               refund_id=str(uuid4()), kind="reversal")
    with pytest.raises(InsufficientShards):
        wallet.adjust_admin(principal, adjustment_id=str(uuid4()), signed_milli=-6,
                            actor_id=actor, reason="exceeds balance")
    assert _ledger_sums(dsn, principal.user_id) == (5, 0)


def test_database_rejects_projection_drift_and_ledger_mutation(wallet_case):
    import psycopg

    _, principal, _, _, dsn = wallet_case
    with psycopg.connect(dsn) as connection:
        with pytest.raises(psycopg.Error):
            with connection.transaction():
                connection.execute(
                    "update app.wallet_accounts set available_milli=available_milli+1 "
                    "where owner_id=%s", (principal.user_id,),
                )
        with pytest.raises(psycopg.Error):
            with connection.transaction():
                connection.execute(
                    "update app.wallet_entries set amount_milli=amount_milli+1 "
                    "where owner_id=%s", (principal.user_id,),
                )
    assert _ledger_sums(dsn, principal.user_id) == (311, 0)


def test_cross_owner_operation_and_amount_overflow_fail_closed(wallet_case):
    import psycopg

    wallet, principal, version, _, dsn = wallet_case
    other = Principal(uuid4(), "test", "other")
    operation_id = uuid4()
    with psycopg.connect(dsn) as connection:
        connection.execute(
            "insert into app.operations(id,owner_id,kind,status,request_sha256) "
            "values (%s,%s,'embedding','running',%s)",
            (operation_id, other.user_id, "b" * 64),
        )
    with pytest.raises(WalletConflict):
        _reserve(wallet, principal, version, ceiling=2, operation_id=operation_id)
    with pytest.raises(WalletConflict):
        _reserve(wallet, principal, version, ceiling=2**63)
    assert wallet.balance(principal).available_milli == 311


def test_uncertain_hold_requires_operator_no_charge_evidence(wallet_case):
    wallet, principal, version, _, dsn = wallet_case
    reserve = _reserve(wallet, principal, version)
    wallet.admit_attempt(principal, reserve.reservation_id,
                         fence_token=reserve.fence_token, attempt_key="ticket",
                         provider="groq", model="openai/gpt-oss-20b", at=TEST_AT)
    new_fence = uuid4()
    assert wallet.recover(principal, reserve.reservation_id,
                          new_fence_token=new_fence).status == "uncertain"
    with pytest.raises(UncertainEffect):
        wallet.reconcile_proven_no_charge(
            principal, reserve.reservation_id, fence_token=reserve.fence_token,
            actor_id=uuid4(), evidence_reference="provider-case-1",
        )
    actor = uuid4()
    done = wallet.reconcile_proven_no_charge(
        principal, reserve.reservation_id, fence_token=new_fence,
        actor_id=actor, evidence_reference="provider-case-1",
    )
    assert done.status == "released" and done.released_milli == 20
    assert wallet.reconcile_proven_no_charge(
        principal, reserve.reservation_id, fence_token=new_fence,
        actor_id=actor, evidence_reference="provider-case-1",
    ) == done
    with pytest.raises(WalletConflict):
        wallet.reconcile_proven_no_charge(
            principal, reserve.reservation_id, fence_token=new_fence,
            actor_id=actor, evidence_reference="different-proof",
        )
    assert _ledger_sums(dsn, principal.user_id) == (311, 0)


def test_operation_reclaim_keeps_ticketed_hold_and_fences_old_worker(wallet_case):
    import psycopg

    wallet, principal, version, _, dsn = wallet_case
    operation_id = uuid4()
    lease = datetime.now(timezone.utc) + timedelta(minutes=5)
    with psycopg.connect(dsn) as connection:
        connection.execute(
            "insert into app.operations(id,owner_id,kind,status,request_sha256,lease_until) "
            "values (%s,%s,'embedding','running',%s,%s)",
            (operation_id, principal.user_id, "c" * 64, lease),
        )
    held = _reserve(wallet, principal, version, operation_id=operation_id)
    wallet.admit_attempt(principal, held.reservation_id, fence_token=held.fence_token,
                         attempt_key="first", provider="groq",
                         model="openai/gpt-oss-20b", at=TEST_AT)
    with pytest.raises(WalletConflict):
        wallet.reserve(principal, reference_type="operation", reference_id=str(operation_id),
                       usage_operation_id=operation_id, pricing_version_id=version,
                       ceiling_milli=20, fence_token=uuid4(), at=TEST_AT)
    with pytest.raises(UncertainEffect, match="lease"):
        wallet.recover(principal, held.reservation_id, new_fence_token=uuid4())
    with psycopg.connect(dsn) as connection:
        connection.execute("update app.operations set lease_until=%s where id=%s",
                           (datetime.now(timezone.utc) - timedelta(seconds=1), operation_id))
    new_fence = uuid4()
    uncertain = wallet.recover(principal, held.reservation_id,
                               new_fence_token=new_fence)
    assert uncertain.status == "uncertain" and uncertain.fence_token == new_fence
    with pytest.raises(UncertainEffect):
        wallet.admit_attempt(principal, held.reservation_id,
                             fence_token=held.fence_token, attempt_key="retry",
                             provider="groq", model="openai/gpt-oss-20b", at=TEST_AT)
    assert _ledger_sums(dsn, principal.user_id) == (291, 20)


def test_one_usage_event_cannot_settle_two_reservations(wallet_case):
    import psycopg
    from psycopg.rows import dict_row

    wallet, principal, version, _, dsn = wallet_case
    operation_id = uuid4()
    with psycopg.connect(dsn) as connection:
        connection.execute(
            "insert into app.operations(id,owner_id,kind,status,request_sha256) "
            "values (%s,%s,'embedding','running',%s)",
            (operation_id, principal.user_id, "d" * 64),
        )
    reservations = []
    for _ in range(2):
        held = wallet.reserve(principal, reference_type="other", reference_id=str(uuid4()),
                              usage_operation_id=operation_id, pricing_version_id=version,
                              ceiling_milli=20, fence_token=uuid4(), at=TEST_AT)
        wallet.admit_attempt(principal, held.reservation_id, fence_token=held.fence_token,
                             attempt_key="first", provider="groq",
                             model="openai/gpt-oss-20b", at=TEST_AT)
        reservations.append(held)
    events = normalize_attempts([{
        "provider": "groq", "model": "openai/gpt-oss-20b", "outcome": "success",
        "network_attempted": True,
        "usage": {"input_tokens": 1000, "output_tokens": 100},
    }], operation_id=operation_id)
    with psycopg.connect(dsn, row_factory=dict_row) as connection:
        with connection.transaction():
            append_usage_events(connection, owner_id=principal.user_id,
                                operation_id=operation_id, game_id=None, events=events)
    first, second = reservations
    wallet.settle_usage(principal, first.reservation_id,
                        fence_token=first.fence_token,
                        usage_event_ids=[events[0].event_id])
    with pytest.raises(psycopg.errors.UniqueViolation):
        wallet.settle_usage(principal, second.reservation_id,
                            fence_token=second.fence_token,
                            usage_event_ids=[events[0].event_id])
    assert wallet.balance(principal).reserved_milli == 20
    assert tuple(wallet.balance(principal).__dict__.values()) == _ledger_sums(
        dsn, principal.user_id,
    )


def test_settlement_and_recovery_race_preserves_one_terminal_outcome(wallet_case):
    import psycopg
    from psycopg.rows import dict_row

    wallet, principal, version, _, dsn = wallet_case
    operation_id = uuid4()
    with psycopg.connect(dsn) as connection:
        connection.execute(
            "insert into app.operations(id,owner_id,kind,status,request_sha256) "
            "values (%s,%s,'embedding','running',%s)",
            (operation_id, principal.user_id, "e" * 64),
        )
    held = _reserve(wallet, principal, version, operation_id=operation_id)
    wallet.admit_attempt(principal, held.reservation_id, fence_token=held.fence_token,
                         attempt_key="first", provider="groq",
                         model="openai/gpt-oss-20b", at=TEST_AT)
    events = normalize_attempts([{
        "provider": "groq", "model": "openai/gpt-oss-20b", "outcome": "success",
        "network_attempted": True,
        "usage": {"input_tokens": 1000, "output_tokens": 100},
    }], operation_id=operation_id)
    with psycopg.connect(dsn, row_factory=dict_row) as connection:
        with connection.transaction():
            append_usage_events(connection, owner_id=principal.user_id,
                                operation_id=operation_id, game_id=None, events=events)

    def settle():
        try:
            return wallet.settle_usage(principal, held.reservation_id,
                                       fence_token=held.fence_token,
                                       usage_event_ids=[events[0].event_id]).status
        except UncertainEffect:
            return "fenced"

    def recover():
        return wallet.recover(principal, held.reservation_id,
                              new_fence_token=uuid4()).status

    with ThreadPoolExecutor(max_workers=2) as executor:
        settlement = executor.submit(settle)
        recovery = executor.submit(recover)
        outcomes = settlement.result(), recovery.result()
    assert outcomes in {("settled", "settled"), ("fenced", "uncertain")}
    balance = wallet.balance(principal)
    assert (balance.available_milli, balance.reserved_milli) == _ledger_sums(
        dsn, principal.user_id,
    )
    assert balance.reserved_milli == (0 if outcomes[0] == "settled" else 20)


def test_seeded_transfer_sequence_reconstructs_both_balances(wallet_case):
    wallet, principal, version, _, dsn = wallet_case
    rng = random.Random(184)
    actor = uuid4()
    for index in range(24):
        balance = wallet.balance(principal)
        if index % 3 == 0:
            amount = rng.randint(1, 15)
            held = _reserve(wallet, principal, version, ceiling=amount)
            assert wallet.release_pre_effect(
                principal, held.reservation_id, fence_token=held.fence_token,
            ).status == "released"
        else:
            amount = rng.randint(1, min(15, balance.available_milli))
            signed = amount if index % 3 == 1 else -amount
            wallet.adjust_admin(principal, adjustment_id=str(uuid4()),
                                signed_milli=signed, actor_id=actor,
                                reason="seeded conservation sequence")
        balance = wallet.balance(principal)
        assert balance.available_milli >= 0 and balance.reserved_milli >= 0
        assert (balance.available_milli, balance.reserved_milli) == _ledger_sums(
            dsn, principal.user_id,
        )
