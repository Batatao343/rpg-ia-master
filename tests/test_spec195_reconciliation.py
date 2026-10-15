"""SPEC-195 offline contracts: golden vectors (docs/spec195/refund-debt-policy.md), state
machines, idempotency, order independence, debt hold. Postgres store tests skip without a DSN."""
import itertools
import os
from uuid import uuid4

import httpx
import pytest

from infrastructure.reconciliation import MemoryStore, Reconciler
from services.google_play import GooglePlayClient, GooglePlaySettings
from services.purchase_reconciliation import (
    GOOGLE, STRIPE, Event, FinancialHold, Ledger, ReconciliationError, fold, normalize_google_voided,
    normalize_stripe_event, plan_adjustment, target_milli, transition_allowed,
)

S, G = 5000, 500


def ev(kind, n, amount=None, sub=None, provider=STRIPE, ref="pi_1", created=0, **kw):
    return Event(provider, f"evt_{n}", kind, ref, amount, sub, created, **kw)


def setup(spent=0, provider=STRIPE, ref="pi_1", shard=S, gross=G):
    store, owner = MemoryStore(), uuid4()
    store.credit_purchase(owner, provider, ref, shard, gross)
    if spent:
        store.spend(owner, spent)
    return store, owner, Reconciler(store)


def apply(rec, *events):
    for e in events:
        rec.ingest(e)
    for p, r in rec.store.open_refs(100):
        rec.store.reconcile(p, r)


def state(store, owner):
    return store.available(owner), store.debt_of(owner)


def check_invariants(store, owner):
    entries = [e for e in store.entries if e["owner"] == owner]
    amt = lambda t: sum(e["amount"] for e in entries if e["type"] == t)  # noqa: E731
    assert store.available(owner) >= 0 and store.debt_of(owner) >= 0
    assert store.available(owner) == (amt("purchase") + amt("claw_release") - amt("clawback")
                                      - amt("debt_settlement") - amt("reserve"))
    debt = [d for d in store.debt if d["owner"] == owner]
    kind = lambda k: sum(d["amount"] for d in debt if d["kind"] == k)  # noqa: E731
    assert store.debt_of(owner) == kind("open") - kind("settle") - kind("release")


# ------------------------------------------------------------------ golden vectors

def test_v1_full_refund_unspent():
    store, owner, rec = setup()
    apply(rec, ev("refund", 1, 500))
    assert state(store, owner) == (0, 0)
    check_invariants(store, owner)


def test_v2_full_refund_after_spend_makes_debt_and_blocks_reservation():
    store, owner, rec = setup(spent=3000)
    apply(rec, ev("refund", 1, 500))
    assert state(store, owner) == (0, 3000)
    with pytest.raises(FinancialHold):
        store.spend(owner, 1)
    check_invariants(store, owner)


def test_v3_new_purchase_settles_debt_first():
    store, owner, rec = setup(spent=3000)
    apply(rec, ev("refund", 1, 500))
    store.credit_purchase(owner, STRIPE, "pi_2", 5000, 500)
    assert state(store, owner) == (2000, 0)
    store.spend(owner, 100)  # hold released
    check_invariants(store, owner)


def test_v4_partial_then_full_refund():
    store, owner, rec = setup()
    apply(rec, ev("refund", 1, 200))
    assert state(store, owner) == (3000, 0)
    apply(rec, ev("refund", 2, 500))
    assert state(store, owner) == (0, 0)


def test_v5_partial_refund_after_heavy_spend():
    store, owner, rec = setup(spent=4500)
    apply(rec, ev("refund", 1, 200))
    assert state(store, owner) == (0, 1500)
    check_invariants(store, owner)


def test_v6_dispute_won_releases_hold_by_compensating_entries():
    store, owner, rec = setup(spent=3000)
    before = len(store.entries)
    apply(rec, ev("dispute_open", 1, 500, "du_1"))
    assert state(store, owner) == (0, 3000)
    apply(rec, ev("dispute_won", 2, 500, "du_1"))
    assert state(store, owner) == (2000, 0)
    assert len(store.entries) > before  # nothing removed; compensating rows appended
    check_invariants(store, owner)
    store.spend(owner, 10)


def test_v7_dispute_lost_keeps_claim():
    store, owner, rec = setup(spent=3000)
    apply(rec, ev("dispute_open", 1, 500, "du_1"), ev("dispute_lost", 2, 500, "du_1"))
    assert state(store, owner) == (0, 3000)
    assert store.states[(STRIPE, "pi_1")] == "dispute_lost"


def test_v8_dispute_won_after_debt_was_settled_by_new_purchase():
    store, owner, rec = setup(spent=3000)
    apply(rec, ev("dispute_open", 1, 500, "du_1"))
    store.credit_purchase(owner, STRIPE, "pi_2", 5000, 500)
    assert state(store, owner) == (2000, 0)
    apply(rec, ev("dispute_won", 2, 500, "du_1"))
    assert state(store, owner) == (7000, 0)
    check_invariants(store, owner)


def test_v9_duplicate_event_id_is_noop():
    store, owner, rec = setup(spent=3000)
    assert rec.ingest(ev("refund", 1, 500)) is True
    assert rec.ingest(ev("refund", 1, 500)) is False
    apply(rec)
    snap = (state(store, owner), len(store.entries), len(store.debt))
    apply(rec, ev("refund", 1, 500))
    apply(rec)
    assert (state(store, owner), len(store.entries), len(store.debt)) == snap


def test_v10_refund_before_purchase_is_parked_then_applied():
    clock = [1000.0]
    store, owner = MemoryStore(clock=lambda: clock[0]), uuid4()
    rec = Reconciler(store)
    rec.ingest(ev("refund", 1, 500))
    assert rec.reconcile_batch()["parked"] == 1
    assert rec.reconcile_batch()["parked"] == 0  # backing off: not re-selected until due
    store.credit_purchase(owner, STRIPE, "pi_1", S, G)
    clock[0] += 400  # past the first backoff window
    assert rec.reconcile_batch()["applied"] == 1
    assert state(store, owner) == (0, 0)


def test_v11_google_void_after_consumption_creates_debt():
    store, owner, rec = setup(spent=5000, provider=GOOGLE, ref="GPA.1")
    store.set_row_state(GOOGLE, "GPA.1", "consumed")
    e = normalize_google_voided({"orderId": "GPA.1", "voidedTimeMillis": "9", "voidedReason": 7})
    assert e.kind == "revoked"
    apply(rec, e)
    assert state(store, owner) == (0, 5000)
    assert store.states[(GOOGLE, "GPA.1")] == "revoked"
    with pytest.raises(FinancialHold):
        store.spend(owner, 1)


def test_v12_cumulative_refunds_out_of_order_claim_once():
    store, owner, rec = setup()
    apply(rec, ev("refund", 1, 500), ev("refund", 2, 200))
    assert state(store, owner) == (0, 0)
    assert sum(1 for e in store.entries if e["type"] == "clawback") == 1


def test_v13_fee_reconciled_separate_record_dedup():
    store, owner, rec = setup()
    n = len(store.entries)
    apply(rec, ev("fee_reconciled", 1, 30), ev("fee_reconciled", 1, 30))
    assert len(store.fees) == 1 and len(store.entries) == n
    assert state(store, owner) == (S, 0)


# ------------------------------------------------------------------ properties

EVENT_SET = [ev("refund", 1, 200), ev("dispute_open", 2, 100, "du_1"),
             ev("dispute_lost", 3, 100, "du_1"), ev("refund", 4, 350),
             ev("dispute_open", 5, 150, "du_2"), ev("dispute_won", 6, 150, "du_2")]


@pytest.mark.parametrize("spent", [0, 2500, 5000])
def test_all_permutations_converge_and_conserve(spent):
    finals = set()
    for order in itertools.permutations(EVENT_SET):
        store, owner, rec = setup(spent=spent)
        for e in order:  # reconcile after EVERY arrival: also exercises state transitions
            apply(rec, e)
        check_invariants(store, owner)
        finals.add((state(store, owner), store.states[(STRIPE, "pi_1")]))
    assert len(finals) == 1


def test_provisional_state_never_violates_transition_table():
    for order in itertools.permutations(EVENT_SET):
        store, owner, rec = setup(spent=1000)
        for e in order:
            apply(rec, e)  # raises ReconciliationError on a forbidden transition
        for _, _, old, new in store.transitions:
            assert transition_allowed(STRIPE, old, new)


def test_target_is_pure_function_of_event_set():
    a = fold(EVENT_SET)
    b = fold(list(reversed(EVENT_SET)) + EVENT_SET)  # reordered + duplicated
    assert a == b
    assert target_milli(a, S, G) == S * min(G, 350 + 100) // G


def test_no_negative_available_ever_under_random_spend():
    store, owner, rec = setup(spent=4999)
    apply(rec, ev("refund", 1, 500))
    assert store.available(owner) == 0 and store.debt_of(owner) == 4999


def test_plan_adjustment_vectors():
    assert plan_adjustment(5000, Ledger(2000, 0, 0)).clawback == 2000
    assert plan_adjustment(5000, Ledger(2000, 0, 0)).debt_open == 3000
    p = plan_adjustment(0, Ledger(0, 5000, 3000))
    assert (p.debt_release, p.credit_release) == (3000, 2000)
    assert plan_adjustment(2000, Ledger(9, 2000, 0)).empty


def test_state_machines_are_closed():
    assert transition_allowed(STRIPE, "paid", "disputed")
    assert not transition_allowed(STRIPE, "refunded_full", "paid")
    assert not transition_allowed(STRIPE, "paid", "created")
    assert transition_allowed(GOOGLE, "consumed", "voided")
    assert not transition_allowed(GOOGLE, "voided", "fulfilled")
    with pytest.raises(ReconciliationError):
        Event("paypal", "x", "refund", "r")
    with pytest.raises(ReconciliationError):
        Event(STRIPE, "x", "refund", "r", -1)


# ------------------------------------------------------------------ normalization / jobs

def test_normalize_stripe_events():
    refund = normalize_stripe_event("charge.refunded", "evt_a", {
        "payment_intent": "pi_1", "amount_refunded": 200, "object_id": "ch_1"})
    assert (refund.kind, refund.amount_cents) == ("refund", 200)
    assert normalize_stripe_event("charge.dispute.created", "e", {
        "payment_intent": "pi_1", "dispute_status": "warning_needs_response", "amount": 5}) is None
    closed = normalize_stripe_event("charge.dispute.closed", "e", {
        "payment_intent": "pi_1", "dispute_status": "won", "amount": 500, "object_id": "du_1"})
    assert closed.kind == "dispute_won"
    assert normalize_stripe_event("charge.refunded", "e", {"payment_intent": None}) is None


class _Google:
    def __init__(self, events):
        self.events, self.calls = events, 0

    def list_voided_events(self, *a, **k):
        self.calls += 1
        return self.events


class _Purchases:
    def __init__(self):
        self.n = 0

    def retry_unconsumed(self, limit):
        self.n += 1
        return 2


def test_batch_polls_google_dedups_and_retries_unconsumed():
    store, owner, _ = setup(spent=1000, provider=GOOGLE, ref="GPA.7")
    voided = normalize_google_voided({"orderId": "GPA.7", "voidedTimeMillis": "5", "voidedReason": 1})
    purchases = _Purchases()
    rec = Reconciler(store, _Google([voided]), purchases)
    assert rec.poll_google_voided() == 1
    assert rec.poll_google_voided() == 0  # same voided record next poll: no-op
    out = rec.reconcile_batch()
    assert out["applied"] == 1 and out["unconsumed_retried"] == 2 and purchases.n == 1
    assert state(store, owner) == (0, 1000)
    again = rec.reconcile_batch()
    assert again["applied"] == 0 and state(store, owner) == (0, 1000)


def test_google_client_lists_voided_with_pagination():
    seen = []

    def handler(request: httpx.Request):
        if request.url.host == "oauth2.googleapis.com":
            return httpx.Response(200, json={"access_token": "t", "expires_in": 3000})
        seen.append(dict(request.url.params))
        if "token" not in request.url.params:
            return httpx.Response(200, json={"voidedPurchases": [
                {"orderId": "GPA.1", "voidedTimeMillis": "10", "voidedReason": 6, "voidedSource": 2}],
                "tokenPagination": {"nextPageToken": "n1"}})
        return httpx.Response(200, json={"voidedPurchases": [{"orderId": "GPA.2", "voidedTimeMillis": "11"}]})
    client = GooglePlayClient(GooglePlaySettings("com.x.y", {"private_key": "k", "client_email": "e"}),
                              transport=httpx.MockTransport(handler), clock=lambda: 2_000_000_000)
    client._assertion = lambda: "jwt"
    events = client.list_voided_events()
    assert [e.kind for e in events] == ["revoked", "voided"]
    assert seen[0]["type"] == "0" and "startTime" in seen[0] and seen[1]["token"] == "n1"
    assert seen[0]["maxResults"] == "1000" and seen[1]["maxResults"] == "1000"
    assert not any(k.startswith("pageSelection") for page in seen for k in page)
    assert seen[1]["startTime"] == seen[0]["startTime"]


def test_cron_reconciliation_route(monkeypatch):
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    from services import cron_internal
    monkeypatch.setenv("RPG_CRON_SECRET", "s" * 40)
    store, owner, _ = setup(spent=3000)
    rec = Reconciler(store, _Google([]), _Purchases())
    rec.ingest(ev("refund", 1, 500))
    monkeypatch.setattr(cron_internal, "_reconciler", lambda: rec)
    app = FastAPI()
    app.include_router(cron_internal.router)
    client = TestClient(app)
    assert client.post("/internal/cron/reconciliation").status_code == 401
    body = client.post("/internal/cron/reconciliation", headers={"Authorization": "Bearer " + "s" * 40}).json()
    assert body["ok"] and body["applied"] == 1 and state(store, owner) == (0, 3000)


def test_admin_cli_requires_audit_fields_and_confirmation():
    from scripts import admin_wallet_adjust as cli
    parser = cli.build_parser()
    owner = str(uuid4())
    base = ["credit", "--owner", owner, "--amount-milli", "10", "--actor", str(uuid4()),
            "--reason", "r", "--reference", "INC-1"]
    args = parser.parse_args(base)
    cli.validate(args, parser)
    assert args.apply is False  # dry-run default
    for missing in ("--actor", "--reason", "--reference"):
        argv = list(base)
        i = argv.index(missing)
        del argv[i:i + 2]
        with pytest.raises(SystemExit):
            parser.parse_args(argv)
    with pytest.raises(SystemExit):
        cli.validate(parser.parse_args(base + ["--apply"]), parser)
    with pytest.raises(SystemExit):
        cli.validate(parser.parse_args(base + ["--apply", "--confirm-owner", str(uuid4())]), parser)


def test_no_public_endpoint_for_adjustment():
    import api
    paths = {getattr(r, "path", "") for r in api.app.routes}
    assert not any("adjust" in p or "forgive" in p for p in paths)


@pytest.mark.skipif(not os.getenv("RPG_TEST_DATABASE_URL"), reason="RPG_TEST_DATABASE_URL absent")
def test_postgres_store_requires_migration_applied():
    import psycopg
    with psycopg.connect(os.environ["RPG_TEST_DATABASE_URL"]) as db:
        row = db.execute("select to_regclass('app.wallet_debt_entries')").fetchone()
    assert row[0] is not None


# ------------------------------------------------------------------ review fixes (H1/H2/M1/M3/L6)

def test_h1_debt_only_passes_never_collide_on_reference_ids():
    store, owner, rec = setup(spent=5000)  # everything spent: available 0
    apply(rec, ev("refund", 1, 200))       # debt 2000
    assert state(store, owner) == (0, 2000)
    apply(rec, ev("refund", 2, 500))       # +3000 debt, second debt-only pass
    assert state(store, owner) == (0, 5000)
    refs = [(d["owner"], d["kind"], d["ref"]) for d in store.debt]
    assert len(refs) == len(set(refs))
    check_invariants(store, owner)


def test_h1_open_then_won_then_refund_with_zero_available():
    store, owner, rec = setup(spent=5000)
    apply(rec, ev("dispute_open", 1, 500, "du_1"))
    assert state(store, owner) == (0, 5000)
    apply(rec, ev("dispute_won", 2, 500, "du_1"))
    assert state(store, owner) == (0, 0)
    apply(rec, ev("refund", 3, 500))       # reopens the debt: reference ids must be fresh
    assert state(store, owner) == (0, 5000)
    check_invariants(store, owner)


def test_memory_store_enforces_debt_reference_uniqueness():
    store = MemoryStore()
    owner = uuid4()
    store._debt(owner, "open", "k", 10, "ref")
    with pytest.raises(ReconciliationError):
        store._debt(owner, "open", "k", 10, "ref")


def test_h2_unresolvable_events_do_not_starve_new_refunds():
    clock = [1000.0]
    store, owner = MemoryStore(clock=lambda: clock[0]), uuid4()
    rec = Reconciler(store)
    for i in range(30):
        rec.ingest(ev("refund", f"orphan{i}", 500, ref=f"pi_missing_{i}"))
    for _ in range(3):
        assert rec.reconcile_batch(10)["parked"] == 10
    store.credit_purchase(owner, STRIPE, "pi_real", S, G)
    rec.ingest(ev("refund", "real", 500, ref="pi_real"))
    out = rec.reconcile_batch(5)  # small batch: the NEW refund wins over unparked backlog
    assert out["applied"] == 1 and state(store, owner) == (0, 0)


def test_h2_parked_event_becomes_orphaned_after_max_attempts():
    from services.purchase_reconciliation import PARK_MAX_ATTEMPTS
    clock = [1000.0]
    store = MemoryStore(clock=lambda: clock[0])
    rec = Reconciler(store)
    rec.ingest(ev("refund", 1, 500, ref="pi_never"))
    outcomes = []
    for _ in range(PARK_MAX_ATTEMPTS + 2):
        out = rec.reconcile_batch()
        outcomes.append((out["parked"], out["orphaned"]))
        clock[0] += 7 * 3600  # beyond the backoff cap
    assert sum(o for _, o in outcomes) == 1 and store.parking_counts() == {"parked": 0, "orphaned": 1}
    assert rec.reconcile_batch()["orphaned_total"] == 1 and store.open_refs(10) == []


def test_m1_forgiven_debt_released_by_won_dispute_never_becomes_credit():
    store, owner, rec = setup(spent=3000)
    apply(rec, ev("dispute_open", 1, 500, "du_1"))
    assert state(store, owner) == (0, 3000)
    assert store.forgive(owner, 3000, "INC-1") == 3000
    assert state(store, owner) == (0, 0)
    apply(rec, ev("dispute_won", 2, 500, "du_1"))
    # only the 2000 actually clawed returns; the forgiven 3000 closes the forgive (no money)
    assert state(store, owner) == (2000, 0)
    assert sum(d["amount"] for d in store.debt if d["kind"] == "forgive_close") == 3000
    # idempotent
    apply(rec)
    assert state(store, owner) == (2000, 0)


def test_m1_partial_forgive_then_release_splits_debt_forgive_and_credit():
    store, owner, rec = setup(spent=3000)
    apply(rec, ev("dispute_open", 1, 500, "du_1"))
    store.forgive(owner, 1000, "INC-2")  # outstanding 2000, forgiven 1000
    apply(rec, ev("dispute_won", 2, 500, "du_1"))
    assert state(store, owner) == (2000, 0)


def test_m3_revoke_reasons_follow_google_enum():
    for reason, kind in ((5, "revoked"), (6, "revoked"), (7, "revoked"),
                         (8, "voided"), (0, "voided"), (1, "voided"), (2, "voided"), (3, "voided"),
                         (4, "voided"), (99, "voided")):
        e = normalize_google_voided({"orderId": "GPA.9", "voidedTimeMillis": "1", "voidedReason": reason})
        assert e.kind == kind, reason


def test_l6_settlement_order_is_oldest_purchase_first_then_key():
    store, owner = MemoryStore(), uuid4()
    rec = Reconciler(store)
    for ref in ("pi_b", "pi_a"):
        store.credit_purchase(owner, STRIPE, ref, 1000, 100)
        store.spend(owner, 1000)
    apply(rec, ev("refund", "b", 100, ref="pi_b"))   # b opens first (older)
    apply(rec, ev("refund", "a", 100, ref="pi_a"))
    store.credit_purchase(owner, STRIPE, "pi_c", 1500, 150)
    settles = [d for d in store.debt if d["kind"] == "settle"]
    assert [d["key"] for d in settles] == ["stripe:pi_b", "stripe:pi_a"][:len(settles)]
    assert settles[0]["amount"] == 1000 and settles[1]["amount"] == 500


def test_l4_cli_rejects_like_wildcards_in_reference():
    from scripts import admin_wallet_adjust as cli
    parser = cli.build_parser()
    for bad in ("INC%", "INC_1"):
        args = parser.parse_args(["forgive-debt", "--owner", str(uuid4()), "--amount-milli", "1",
                                  "--actor", str(uuid4()), "--reason", "r", "--reference", bad])
        with pytest.raises(SystemExit):
            cli.validate(args, parser)
