"""SPEC-195 review-fix regressions against the local Postgres lab (RPG_TEST_DATABASE_URL).

Every test runs on the rolled-back single-connection fixture (`lab_rb`)."""
from __future__ import annotations

from uuid import uuid4

import pytest

from infrastructure.contracts import Principal
from infrastructure.reconciliation import Reconciler
from infrastructure.wallet import FinancialHold, _hold_guard
from infrastructure.wallet_debt import forgive_debt, forgive_replay
from services.purchase_reconciliation import PARK_MAX_ATTEMPTS, STRIPE
from tests.test_spec194_196_postgres_local import (  # noqa: F401  (fixtures + helpers)
    GROSS_CENTS,
    SHARD,
    balance,
    debt,
    ev,
    lab,
    lab_rb,
    reserve,
    web_purchase,
)

pytestmark = pytest.mark.infra_local


def spend_all(lab, owner):
    lab.wallet.adjust_admin(owner, adjustment_id=str(uuid4()), signed_milli=-balance(lab, owner),
                            actor_id=uuid4(), reason="spent for test")


def run(lab, ref, *events):
    rec = Reconciler(lab.store)
    for e in events:
        rec.ingest(e)
    return lab.store.reconcile(STRIPE, ref)


def test_h1_debt_only_passes_do_not_collide(lab_rb):
    lab = lab_rb
    owner = Principal(uuid4(), "test", "h1a")
    ref = web_purchase(lab, owner)
    spend_all(lab, owner)
    assert run(lab, ref, ev("refund", ref, 1, 200, "ch_1")) == "applied"
    debt1 = debt(lab, owner)
    assert debt1 > 0 and balance(lab, owner) == 0
    assert run(lab, ref, ev("refund", ref, 2, 500, "ch_1")) == "applied"  # second debt-only pass
    assert debt(lab, owner) == SHARD * 500 // GROSS_CENTS > debt1
    assert run(lab, ref, ev("refund", ref, 3, GROSS_CENTS, "ch_1")) == "applied"  # third pass
    assert (balance(lab, owner), debt(lab, owner)) == (0, SHARD)
    assert run(lab, ref) == "applied"  # replay: nothing new
    assert debt(lab, owner) == SHARD


def test_h1_open_won_refund_with_zero_available(lab_rb):
    lab = lab_rb
    owner = Principal(uuid4(), "test", "h1b")
    ref = web_purchase(lab, owner)
    spend_all(lab, owner)
    run(lab, ref, ev("dispute_open", ref, 1, GROSS_CENTS, "du_1"))
    assert debt(lab, owner) == SHARD
    run(lab, ref, ev("dispute_won", ref, 2, GROSS_CENTS, "du_1"))
    assert (balance(lab, owner), debt(lab, owner)) == (0, 0)
    run(lab, ref, ev("refund", ref, 3, GROSS_CENTS, "ch_1"))
    assert (balance(lab, owner), debt(lab, owner)) == (0, SHARD)


def test_h2_unresolvable_rows_are_parked_with_backoff_and_do_not_block(lab_rb):
    lab = lab_rb
    owner = Principal(uuid4(), "test", "h2a")
    rec = Reconciler(lab.store)
    missing = ["pi_missing_" + uuid4().hex for _ in range(6)]
    for i, m in enumerate(missing):
        rec.ingest(ev("refund", m, i, GROSS_CENTS, "ch_m"))
    for m in missing:
        assert lab.store.reconcile(STRIPE, m) == "parked"
    ref = web_purchase(lab, owner)
    rec.ingest(ev("refund", ref, 99, GROSS_CENTS, "ch_real"))
    due = [r for p, r in lab.store.open_refs(3)]
    assert due == [ref]  # parked refs are backing off; the new refund is not starved
    out = Reconciler(lab.store).reconcile_batch(3)
    assert out["applied"] == 1 and out["parked_total"] >= 6


def test_h2_orphaned_after_max_attempts(lab_rb):
    lab = lab_rb
    ref = "pi_never_" + uuid4().hex
    Reconciler(lab.store).ingest(ev("refund", ref, 1, GROSS_CENTS, "ch_x"))
    outcome = None
    for _ in range(PARK_MAX_ATTEMPTS):
        with lab.pool.connection() as db:
            db.execute("update app.purchase_reconciliation_events set next_attempt_at=now() "
                       "where purchase_ref=%s", (ref,))
        outcome = lab.store.reconcile(STRIPE, ref)
    assert outcome == "orphaned"
    assert ref not in [r for _, r in lab.store.open_refs(1000)]
    assert lab.store.parking_counts().get("orphaned", 0) >= 1


def test_h2_stripe_event_without_financial_effect_is_marked_once(lab_rb):
    lab = lab_rb
    eid = "evt_inquiry_" + uuid4().hex
    with lab.pool.connection() as db:
        db.execute("""insert into app.stripe_events(event_id,event_type,body_sha256,provider_created,facts)
            values (%s,'charge.dispute.created',%s,1,%s::jsonb)""",
                   (eid, "a" * 64, '{"payment_intent":"pi_x","dispute_status":"warning_needs_response"}'))
    lab.store.ingest_backlog(1000)
    with lab.pool.connection() as db:
        skip = db.execute("select count(*) as n from app.purchase_reconciliation_skips "
                          "where provider_event_id=%s", (eid,)).fetchone()["n"]
        events = db.execute("select count(*) as n from app.purchase_reconciliation_events "
                            "where provider_event_id=%s", (eid,)).fetchone()["n"]
    assert (skip, events) == (1, 0)
    assert lab.store.ingest_backlog(1000) == 0  # not re-selected, no duplicate marker (pk would fail)


def test_m1_forgiven_debt_released_by_won_dispute_is_not_credited(lab_rb):
    lab = lab_rb
    owner = Principal(uuid4(), "test", "m1")
    ref = web_purchase(lab, owner)
    spend_all(lab, owner)
    run(lab, ref, ev("dispute_open", ref, 1, GROSS_CENTS, "du_1"))
    assert debt(lab, owner) == SHARD
    with lab.pool.connection() as db:
        assert forgive_debt(db, owner.user_id, SHARD, reference="INC-M1", actor_id=uuid4(),
                            reason="goodwill") == SHARD
    assert debt(lab, owner) == 0
    run(lab, ref, ev("dispute_won", ref, 2, GROSS_CENTS, "du_1"))
    assert (balance(lab, owner), debt(lab, owner)) == (0, 0)  # nothing was taken, nothing returns
    with lab.pool.connection() as db:
        assert db.execute("select coalesce(sum(amount_milli),0) as s from app.wallet_debt_entries "
                          "where owner_id=%s and kind='forgive_close'",
                          (owner.user_id,)).fetchone()["s"] == SHARD
    assert run(lab, ref) == "applied" and (balance(lab, owner), debt(lab, owner)) == (0, 0)


def test_m1_partial_credit_returns_only_what_was_clawed(lab_rb):
    lab = lab_rb
    owner = Principal(uuid4(), "test", "m1b")
    ref = web_purchase(lab, owner)
    lab.wallet.adjust_admin(owner, adjustment_id=str(uuid4()), signed_milli=-200, actor_id=uuid4(),
                            reason="spent for test")
    run(lab, ref, ev("dispute_open", ref, 1, GROSS_CENTS, "du_1"))  # claw SHARD-200, debt 200
    with lab.pool.connection() as db:
        forgive_debt(db, owner.user_id, 200, reference="INC-M1B", actor_id=uuid4(), reason="goodwill")
    run(lab, ref, ev("dispute_won", ref, 2, GROSS_CENTS, "du_1"))
    assert (balance(lab, owner), debt(lab, owner)) == (SHARD - 200, 0)


def test_l2_state_transitions_are_recorded_append_only(lab_rb):
    import psycopg
    lab = lab_rb
    owner = Principal(uuid4(), "test", "l2")
    ref = web_purchase(lab, owner)
    run(lab, ref, ev("dispute_open", ref, 1, GROSS_CENTS, "du_1"))
    run(lab, ref, ev("dispute_won", ref, 2, GROSS_CENTS, "du_1"))
    with lab.pool.connection() as db:
        rows = db.execute("select old_state,new_state from app.purchase_reconciliation_transitions "
                          "where purchase_ref=%s order by created_at, new_state", (ref,)).fetchall()
        assert {(r["old_state"], r["new_state"]) for r in rows} == {("paid", "disputed"),
                                                                    ("disputed", "dispute_won")}
        with pytest.raises(psycopg.Error), db.transaction():
            db.execute("delete from app.purchase_reconciliation_transitions where purchase_ref=%s", (ref,))


def test_l5_db_financial_hold_trigger_maps_to_app_error(lab_rb):
    lab = lab_rb
    owner = Principal(uuid4(), "test", "l5")
    ref = web_purchase(lab, owner)
    spend_all(lab, owner)
    run(lab, ref, ev("refund", ref, 1, GROSS_CENTS, "ch_1"))
    assert debt(lab, owner) > 0
    with lab.pool.connection() as db, pytest.raises(FinancialHold), db.transaction(), _hold_guard():
        db.execute("""insert into app.wallet_reservations
            (reservation_id,owner_id,reference_type,reference_id,pricing_version_id,fence_token,ceiling_milli)
            values (%s,%s,'other',%s,%s,%s,1)""",
                   (uuid4(), owner.user_id, str(uuid4()), lab.version, uuid4()))
    with pytest.raises(FinancialHold):
        reserve(lab, owner, 1)


def test_l4_forgive_reference_wildcards_do_not_match_other_forgives(lab_rb):
    lab = lab_rb
    owner = Principal(uuid4(), "test", "l4")
    ref = web_purchase(lab, owner)
    spend_all(lab, owner)
    run(lab, ref, ev("refund", ref, 1, GROSS_CENTS, "ch_1"))
    with lab.pool.connection() as db:
        forgive_debt(db, owner.user_id, 10, reference="INC-A1", actor_id=uuid4(), reason="r")
        # '_' must not behave as a LIKE wildcard: INC-A_ is a different (unseen) reference
        assert forgive_replay(db, owner.user_id, "INC-A_") is None
        assert forgive_replay(db, owner.user_id, "INC-A1")["total_milli"] == 10
