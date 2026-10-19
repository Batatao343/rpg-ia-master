"""SPEC-195 re-review follow-ups: orphan recovery, void watermark, CLI reference, 2-thread safety."""

from __future__ import annotations

import threading
from uuid import uuid4

import httpx
import pytest

from infrastructure.contracts import Principal
from infrastructure.google_play_payments import GooglePlayPurchases, PostgresPurchaseStore
from infrastructure.reconciliation import MemoryStore, Reconciler
from services.google_play import GooglePlayClient, GooglePlaySettings, obfuscated_account_id
from services.purchase_reconciliation import (
    GOOGLE,
    PARK_MAX_ATTEMPTS,
    STRIPE,
    Event,
    normalize_google_voided,
)

S, G = 5000, 500


def _exhaust(rec, clock, provider_ref_count=1):
    """Run batches, jumping the clock past each backoff, until the ref is given up on."""
    for _ in range(PARK_MAX_ATTEMPTS + 1):
        clock[0] += 7 * 3600
        rec.reconcile_batch()


# ------------------------------------------------------------------ F1 orphan recovery (memory)


@pytest.mark.parametrize(
    "provider,ref,event",
    [
        (GOOGLE, "GPA.9", Event(GOOGLE, "void:GPA.9:5", "voided", "GPA.9", None, None, 5)),
        (STRIPE, "pi_9", Event(STRIPE, "evt_9", "refund", "pi_9", G, "ch_9", 5)),
    ],
)
def test_orphaned_event_applies_once_the_purchase_is_credited(provider, ref, event):
    clock, owner = [1000.0], uuid4()
    store = MemoryStore(clock=lambda: clock[0])
    rec = Reconciler(store)
    rec.ingest(event)
    _exhaust(rec, clock)
    assert store.parking_counts()["orphaned"] == 1
    assert rec.reconcile_batch()["applied"] == 0  # still no purchase: stays orphaned
    store.credit_purchase(owner, provider, ref, S, G)
    out = rec.reconcile_batch()
    assert out["applied"] == 1 and out["orphaned_total"] == 0
    assert (store.available(owner), store.debt_of(owner)) == (0, 0)
    assert rec.reconcile_batch()["applied"] == 0  # replay: nothing new


# ------------------------------------------------------------------ F2 watermark


def test_poll_persists_watermark_and_keeps_it_when_truncated():
    calls = []

    class Google:
        last_poll_complete = True

        def list_voided_events(self, start_ms=None, end_ms=None, **k):
            calls.append(start_ms)
            return []

    store, google = MemoryStore(), Google()
    rec = Reconciler(store, google)
    rec.poll_google_voided()
    first = store.get_cursor(GOOGLE)
    assert calls[0] is None and first is not None
    rec.poll_google_voided()
    assert calls[1] == first
    google.last_poll_complete = False  # page budget exhausted: do not skip the unread tail
    store.cursors[GOOGLE] = 10
    rec.poll_google_voided()
    assert store.get_cursor(GOOGLE) == 10


def test_google_client_pages_1000_and_reports_truncation():
    def handler(request: httpx.Request):
        if request.url.host == "oauth2.googleapis.com":
            return httpx.Response(200, json={"access_token": "t", "expires_in": 3000})
        n = int(request.url.params.get("token", "0"))
        return httpx.Response(
            200,
            json={
                "voidedPurchases": [{"orderId": f"GPA.{n}", "voidedTimeMillis": str(n + 1)}],
                "tokenPagination": {"nextPageToken": str(n + 1)},
            },
        )

    client = GooglePlayClient(
        GooglePlaySettings("com.x.y", {"private_key": "k", "client_email": "e"}),
        transport=httpx.MockTransport(handler),
        clock=lambda: 2_000_000_000,
    )
    client._assertion = lambda: "jwt"
    assert len(client.list_voided_events(max_pages=3)) == 3 and client.last_poll_complete is False


# ------------------------------------------------------------------ F3 CLI


def test_cli_rejects_colon_in_reference():
    from scripts import admin_wallet_adjust as cli

    parser = cli.build_parser()
    args = parser.parse_args(
        [
            "credit",
            "--owner",
            str(uuid4()),
            "--amount-milli",
            "1",
            "--actor",
            str(uuid4()),
            "--reason",
            "r",
            "--reference",
            "INC:1",
        ]
    )
    with pytest.raises(SystemExit):
        cli.validate(args, parser)


# ------------------------------------------------------------------ policy vector V15


def test_v15_partial_reversal_returns_paid_money_before_closing_forgiven_debt():
    store, owner = MemoryStore(), uuid4()
    store.credit_purchase(owner, STRIPE, "pi_1", S, G)
    store.spend(owner, 3000)
    rec = Reconciler(store)
    rec.ingest(Event(STRIPE, "e1", "refund", "pi_1", 200, "ch_1", 0))
    rec.ingest(Event(STRIPE, "e2", "dispute_open", "pi_1", 300, "du_1", 0))
    rec.reconcile_batch()
    assert (store.available(owner), store.debt_of(owner)) == (0, 3000)  # claw 2000 + debt 3000
    assert store.forgive(owner, 3000, "INC-1") == 3000
    rec.ingest(Event(STRIPE, "e3", "dispute_won", "pi_1", 300, "du_1", 0))
    rec.reconcile_batch()
    # target falls 5000 -> 2000: the 2000 actually clawed returns; 1000 of forgiveness just closes
    assert (store.available(owner), store.debt_of(owner)) == (2000, 0)
    assert any(d["kind"] == "forgive_close" and d["amount"] == 1000 for d in store.debt)


# ------------------------------------------------------------------ F1/F4 Postgres (lab)

from tests.test_spec194_196_postgres_local import (  # noqa: E402,F401
    SHARD,
    FakeGoogle,
    balance,
    debt,
    lab,
    lab_rb,
    reserve,
)


def _gp_verify(lab, owner, order):
    google = FakeGoogle(lab.product, order)
    google.base["account_id"] = obfuscated_account_id(owner.user_id)
    return GooglePlayPurchases(PostgresPurchaseStore(lab.pool), google).verify(
        owner, lab.product, "tok_" + uuid4().hex
    )


def _orphan_void(lab, order):
    rec = Reconciler(lab.store)
    rec.ingest(Event(GOOGLE, "void:" + order, "voided", order, None, None, 0))
    for _ in range(PARK_MAX_ATTEMPTS):
        with lab.pool.connection() as db:
            db.execute(
                "update app.purchase_reconciliation_events set next_attempt_at=now() "
                "where purchase_ref=%s",
                (order,),
            )
        outcome = lab.store.reconcile(GOOGLE, order)
    assert outcome == "orphaned"
    return rec


@pytest.mark.infra_local
def test_pg_google_void_orphaned_then_credited_next_batch_applies(lab_rb, monkeypatch):
    lab, owner = lab_rb, Principal(uuid4(), "test", "o1")
    order = "GPA." + uuid4().hex[:12]
    rec = _orphan_void(lab, order)
    monkeypatch.setattr(PostgresPurchaseStore, "_reconcile_order", lambda self, o: None)
    _gp_verify(lab, owner, order)  # hook disabled: credit alone does not settle the void
    assert balance(lab, owner) == SHARD
    assert (GOOGLE, order) in lab.store.open_refs(1000)
    assert rec.reconcile_batch(1000)["applied"] >= 1
    assert (balance(lab, owner), debt(lab, owner)) == (0, 0)
    assert (GOOGLE, order) not in lab.store.open_refs(1000)


@pytest.mark.infra_local
def test_pg_google_fulfill_triggers_immediate_reconcile_for_orphaned_void(lab_rb):
    lab, owner = lab_rb, Principal(uuid4(), "test", "o2")
    order = "GPA." + uuid4().hex[:12]
    _orphan_void(lab, order)
    _gp_verify(lab, owner, order)
    assert (balance(lab, owner), debt(lab, owner)) == (0, 0)


@pytest.mark.infra_local
def test_pg_stripe_orphan_with_credited_purchase_applies_in_later_batch(lab_rb):
    from tests.test_spec194_196_postgres_local import GROSS_CENTS, web_purchase

    lab, owner = lab_rb, Principal(uuid4(), "test", "o3")
    ref = web_purchase(lab, owner)
    rec = Reconciler(lab.store)
    rec.ingest(Event(STRIPE, ref + "-1", "refund", ref, GROSS_CENTS, "ch_1", 0))
    with lab.pool.connection() as db:  # the paid-webhook pass failed; attempts ran out earlier
        db.execute(
            "update app.purchase_reconciliation_events set status='orphaned' where purchase_ref=%s",
            (ref,),
        )
    assert (STRIPE, ref) in lab.store.open_refs(1000)
    assert rec.reconcile_batch(1000)["applied"] >= 1
    assert (balance(lab, owner), debt(lab, owner)) == (0, 0)


@pytest.mark.infra_local
def test_pg_void_watermark_roundtrip_only_moves_forward(lab_rb):
    store = lab_rb.store
    store.set_cursor(GOOGLE, 5_000)
    store.set_cursor(GOOGLE, 1_000)
    assert store.get_cursor(GOOGLE) >= 5_000


@pytest.mark.infra_local
def test_pg_concurrent_reconcilers_same_owner_different_refs(lab):
    owner = Principal(uuid4(), "test", "t1")
    orders = ["GPA." + uuid4().hex[:12] for _ in range(2)]
    for o in orders:
        _gp_verify(lab, owner, o)
    spent = SHARD  # one purchase worth spent: clawed + debt must sum to both purchases
    lab.wallet.adjust_admin(
        owner, adjustment_id=str(uuid4()), signed_milli=-spent, actor_id=uuid4(), reason="spent"
    )
    rec = Reconciler(lab.store)
    for o in orders:
        rec.ingest(Event(GOOGLE, "void:" + o, "voided", o, None, None, 0))
    barrier, errors = threading.Barrier(2), []

    def work(o):
        try:
            barrier.wait(timeout=10)
            assert lab.store.reconcile(GOOGLE, o) == "applied"
        except Exception as exc:  # noqa: BLE001
            errors.append(exc)

    threads = [threading.Thread(target=work, args=(o,)) for o in orders]
    [t.start() for t in threads]
    [t.join(timeout=30) for t in threads]
    assert not any(t.is_alive() for t in threads), "deadlock"
    assert not errors, errors
    assert (balance(lab, owner), debt(lab, owner)) == (0, spent)


@pytest.mark.infra_local
def test_pg_reservation_release_while_reconcile_in_flight(lab):
    owner = Principal(uuid4(), "test", "t2")
    order = "GPA." + uuid4().hex[:12]
    _gp_verify(lab, owner, order)
    fence = uuid4()
    reservation = lab.wallet.reserve(
        owner,
        reference_type="other",
        reference_id=str(uuid4()),
        pricing_version_id=lab.version,
        ceiling_milli=100,
        fence_token=fence,
        at=lab.at,
    )
    Reconciler(lab.store).ingest(Event(GOOGLE, "void:" + order, "voided", order, None, None, 0))
    barrier, errors = threading.Barrier(2), []

    def reconcile():
        try:
            barrier.wait(timeout=10)
            lab.store.reconcile(GOOGLE, order)
        except Exception as exc:  # noqa: BLE001
            errors.append(exc)

    def release():
        try:
            barrier.wait(timeout=10)
            lab.wallet.release_pre_effect(owner, reservation.reservation_id, fence_token=fence)
        except Exception as exc:  # noqa: BLE001
            errors.append(exc)

    threads = [threading.Thread(target=reconcile), threading.Thread(target=release)]
    [t.start() for t in threads]
    [t.join(timeout=30) for t in threads]
    assert not any(t.is_alive() for t in threads), "deadlock"
    assert not errors, errors
    # conservation: whatever the interleaving, the whole purchase is reclaimed, nothing left over
    assert (balance(lab, owner), debt(lab, owner)) == (0, 0)


def test_orphaned_alert_rule_and_fixture_are_consistent():
    from pathlib import Path

    import yaml

    rules = yaml.safe_load(
        Path("observability/alerts/reconciliation.yml").read_text(encoding="utf-8")
    )
    rule = rules["groups"][0]["rules"][0]
    assert rule["alert"] == "ReconciliationOrphaned" and rule["for"] == "1h"
    assert 'status="orphaned"' in rule["expr"]
    fixture = yaml.safe_load(
        Path("observability/alerts/reconciliation.test.yml").read_text(encoding="utf-8")
    )
    assert fixture["rule_files"] == ["reconciliation.yml"]
