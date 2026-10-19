"""SPEC-189 real PostgreSQL financial invariants; every fixture rolls back."""
import hashlib
import os
from contextlib import nullcontext
from datetime import datetime, timezone, UTC
from pathlib import Path
from types import SimpleNamespace
from uuid import uuid4

import pytest

from infrastructure.contracts import Principal
from infrastructure.stripe_payments import StripePayments
from services.shard_pricing import INSTALLED_RATE_CARD_OBSERVED_AT, INSTALLED_RATE_CARD_SHA256
from services.stripe_checkout import StripeError, StripeSettings
from services.usage_metering import RATE_CARD_VERSION


class FakeStripe:
    def __init__(self):
        self.sessions = {}
        self.calls = 0
        self.economics = None

    def create_session(self, order_id, **kwargs):
        self.calls += 1
        return self.sessions.setdefault(order_id, {"id": "cs_test_" + order_id,
            "livemode": False, "url": "https://checkout.stripe.com/c/pay/test_" + order_id})

    def payment_economics(self, _intent):
        return self.economics


@pytest.fixture
def payment_case():
    psycopg = pytest.importorskip("psycopg")
    from psycopg.rows import dict_row
    from psycopg.types.json import Jsonb
    dsn = os.getenv("RPG_TEST_DATABASE_URL")
    if not dsn:
        pytest.skip("RPG_TEST_DATABASE_URL absent")
    with psycopg.connect(dsn, row_factory=dict_row) as db:
        try:
            if db.execute("select to_regclass('app.payment_orders') t").fetchone()["t"] is None:
                db.execute(Path("supabase/migrations/20261013120000_stripe_checkout.sql").read_text(encoding="utf-8"))
            class Pool:
                def connection(self):
                    return nullcontext(db)
            at = datetime(2026, 10, 13, 12, tzinfo=UTC)
            version, sku = "stripe-" + str(uuid4()), "stripe-" + str(uuid4())
            db.execute("""insert into app.pricing_versions
                (version_id,shard_budget_unit_brl,fx_usd_brl,fx_source,fx_observed_at,fx_max_age_seconds,
                 fx_buffer_rate,rate_card_version,rate_card_sha256,rate_card_source,
                 rate_card_observed_at,rate_card_max_age_seconds,channel_fees)
                values (%s,0.03,5,'test',%s,864000,0.1,%s,%s,'test',%s,864000,%s)""",
                (version,at,RATE_CARD_VERSION,INSTALLED_RATE_CARD_SHA256,INSTALLED_RATE_CARD_OBSERVED_AT,
                 Jsonb({"web": {"percentage": "0.04", "fixed_brl": "0.20"}})))
            db.execute("""insert into app.purchase_skus
                (sku_id,pricing_version_id,channel,store_product_id,gross_brl,shard_milli)
                values (%s,%s,'web',%s,10.50,311)""", (sku,version,sku))
            owner = Principal(uuid4(), "test", "owner")
            fake = FakeStripe()
            pool = Pool()
            settings = StripeSettings("sk_test_fixture", "whsec_fixture", "https://game.example", (sku,))
            repo = StripePayments(pool, settings, fake, at=at)
            yield SimpleNamespace(repo=repo, owner=owner, fake=fake, db=db, sku=sku, version=version, at=at)
        finally:
            db.rollback()


def checkout(case, key=None):
    return case.repo.checkout(case.owner, case.sku, key or uuid4())


def event(case, order, *, kind="checkout.session.completed", paid=True, eid=None, intent=None):
    oid = order["order_id"]
    obj = {"id": "cs_test_" + oid, "metadata": {"order_id": oid}, "mode": "payment",
           "payment_status": "paid" if paid else "unpaid", "amount_total": 1050,
           "currency": "brl", "payment_intent": intent or "pi_" + oid}
    if kind.startswith("charge."):
        obj = {"id": "ch_" + oid, "metadata": {}, "payment_intent": intent or "pi_" + oid,
               "currency": "brl", "amount": 1050, "amount_refunded": 1050}
    return {"id": eid or "evt_" + str(uuid4()), "type": kind, "created": 1791892800,
            "livemode": False, "data": {"object": obj}}


def debt(case):
    """Outstanding SPEC-195 refund debt (open - settle - release - forgive)."""
    return int(case.db.execute("select coalesce(sum(debt_delta),0) n from app.wallet_debt_entries "
                               "where owner_id=%s", (case.owner.user_id,)).fetchone()["n"])


def entries(case, kind):
    return int(case.db.execute("select coalesce(sum(amount_milli),0) n from app.wallet_entries "
                               "where owner_id=%s and entry_type=%s", (case.owner.user_id, kind)).fetchone()["n"])


def deliver(case, item):
    return case.repo.accept_event(item, body_sha256=hashlib.sha256(str(item).encode()).hexdigest())


def test_price_and_request_replay_are_server_owned(payment_case):
    c = payment_case
    key = uuid4()
    first = checkout(c, key)
    assert checkout(c, key) == first
    assert c.fake.calls == 1
    assert c.repo.order(c.owner, first["order_id"])["shard_milli"] == "311"
    assert c.repo.order(Principal(uuid4(), "test", "other"), first["order_id"]) is None
    assert c.repo.wallet.balance(c.owner).available_milli == 0
    with pytest.raises(StripeError):
        c.repo.checkout(c.owner, "client-invented-sku", uuid4())


def test_paid_duplicate_distinct_delayed_and_out_of_order(payment_case):
    c = payment_case
    order = checkout(c)
    deliver(c, event(c, order, paid=False))
    assert c.repo.wallet.balance(c.owner).available_milli == 0
    paid = event(c, order, kind="checkout.session.async_payment_succeeded")
    deliver(c, paid)
    deliver(c, paid)
    deliver(c, event(c, order))
    deliver(c, event(c, order, paid=False))
    assert c.repo.wallet.balance(c.owner).available_milli == 311
    assert c.repo.order(c.owner, order["order_id"])["status"] == "paid"
    assert c.db.execute("select count(*) n from app.wallet_entries where owner_id=%s", (c.owner.user_id,)).fetchone()["n"] == 1


@pytest.mark.parametrize("change", [{"amount_total": 1}, {"currency": "usd"},
                                   {"mode": "subscription"}, {"id": "cs_test_wrong"}])
def test_mismatched_paid_event_cannot_credit(payment_case, change):
    c = payment_case
    order = checkout(c)
    item = event(c, order)
    item["data"]["object"].update(change)
    with pytest.raises(StripeError):
        deliver(c, item)
    assert c.repo.wallet.balance(c.owner).available_milli == 0
    assert c.db.execute("select count(*) n from app.stripe_events").fetchone()["n"] == 0


def test_refund_before_payment_with_no_metadata_prevents_late_credit(payment_case):
    c = payment_case
    order = checkout(c)
    refund = event(c, order, kind="charge.refunded")
    deliver(c, refund)
    deliver(c, event(c, order))
    assert c.repo.wallet.balance(c.owner).available_milli == 0
    assert c.repo.order(c.owner, order["order_id"])["status"] == "refunded"
    assert c.db.execute("select count(*) n from app.payment_financial_events").fetchone()["n"] == 1


@pytest.mark.parametrize("spent", [False, True])
def test_refund_keeps_purchase_and_audits_spent_funds(payment_case, spent):
    c = payment_case
    order = checkout(c)
    deliver(c, event(c, order))
    if spent:
        c.repo.wallet.adjust_admin(c.owner, adjustment_id=str(uuid4()), signed_milli=-300,
                                  actor_id=uuid4(), reason="synthetic already spent")
    refund = event(c, order, kind="charge.refunded")
    deliver(c, refund)
    deliver(c, refund)
    deliver(c, event(c, order))
    # SPEC-195 (V1/V2): refund -> normalized event queued -> reconciler claws back what is
    # still available (311 or 11) and records the unrecoverable remainder as debt (0 or 300).
    assert c.repo.wallet.balance(c.owner).available_milli == 0
    assert debt(c) == (300 if spent else 0)
    assert entries(c, "clawback") == (11 if spent else 311)
    assert c.repo.order(c.owner, order["order_id"])["status"] == "refunded"
    assert c.db.execute("select outcome from app.payment_financial_events").fetchone()["outcome"] == "queued_reconciliation"
    # money conservation: purchase + adjustments - clawback == available
    assert c.db.execute("select sum(available_delta) n from app.wallet_entries where owner_id=%s",
                        (c.owner.user_id,)).fetchone()["n"] == 0
    assert c.db.execute("select count(*) n from app.wallet_entries where entry_type='purchase' and owner_id=%s", (c.owner.user_id,)).fetchone()["n"] == 1
    assert c.db.execute("select count(*) n from app.payment_financial_events").fetchone()["n"] == 1


def test_event_credit_crash_rolls_back_dedupe_and_allows_retry(payment_case, monkeypatch):
    c = payment_case
    order = checkout(c)
    item = event(c, order)
    original = c.repo.wallet.credit_verified_purchase
    def fault(*args, **kwargs):
        original(*args, **kwargs)
        raise RuntimeError("crash after wallet credit")
    monkeypatch.setattr(c.repo.wallet, "credit_verified_purchase", fault)
    with pytest.raises(RuntimeError):
        deliver(c, item)
    assert c.repo.wallet.balance(c.owner).available_milli == 0
    assert c.db.execute("select count(*) n from app.stripe_events").fetchone()["n"] == 0
    monkeypatch.setattr(c.repo.wallet, "credit_verified_purchase", original)
    deliver(c, item)
    assert c.repo.wallet.balance(c.owner).available_milli == 311


def test_fee_reconciled_as_append_only_fact(payment_case):
    c = payment_case
    order = checkout(c)
    item = event(c, order)
    deliver(c, item)
    assert c.db.execute("select actual_fee_cents from app.payment_orders").fetchone()["actual_fee_cents"] is None
    c.fake.economics = {"balance_transaction_id": "txn_fixture", "currency": "brl", "fee_cents": 57}
    deliver(c, item)
    deliver(c, item)
    assert c.db.execute("select actual_fee_cents from app.payment_orders").fetchone()["actual_fee_cents"] == 57
    assert str(c.db.execute("select actual_contribution_margin_brl from app.payment_orders").fetchone()["actual_contribution_margin_brl"]) == "0.6000000000"
    assert c.db.execute("select count(*) n from app.payment_financial_events where kind='fee_reconciled'").fetchone()["n"] == 1


@pytest.mark.parametrize("first", ["charge.dispute.created", "charge.dispute.closed"])
def test_dispute_reordered_and_closed_preserves_reversal_and_hold(payment_case, first):
    c = payment_case
    order = checkout(c)
    deliver(c, event(c, order))
    dispute = event(c, order, kind=first)
    dispute["data"]["object"].update(id="du_fixture", status="won")
    deliver(c, dispute)
    late = event(c, order, kind="charge.dispute.created")
    late["data"]["object"].update(id="du_fixture", status="needs_response")
    deliver(c, late)
    closed = event(c, order, kind="charge.dispute.closed")
    closed["data"]["object"].update(id="du_fixture", status="won")
    deliver(c, closed)
    deliver(c, event(c, order))
    # SPEC-195 (V6): the final fact is "won" whatever the arrival order -> hold released by
    # compensating entries (history is never rewritten), full balance back, no debt.
    assert c.repo.wallet.balance(c.owner).available_milli == 311
    assert debt(c) == 0
    assert entries(c, "clawback") == entries(c, "claw_release")
    assert c.repo.order(c.owner, order["order_id"])["status"] == "paid"
    assert c.db.execute("select count(*) n from app.payment_financial_events where kind like 'dispute%'").fetchone()["n"] == 2
    assert c.db.execute("select count(*) n from app.wallet_entries where owner_id=%s and entry_type='reversal'", (c.owner.user_id,)).fetchone()["n"] == 0


def test_partial_refund_is_audited_and_never_silently_rounded(payment_case):
    c = payment_case
    order = checkout(c)
    deliver(c, event(c, order))
    item = event(c, order, kind="charge.refunded")
    item["data"]["object"]["amount_refunded"] = 500
    deliver(c, item)
    deliver(c, item)
    deliver(c, event(c, order))
    # SPEC-195 (V4): 500/1050c of 311 = floor(148.09) = 148 clawed back, never silently rounded
    # up; the purchase stays paid and the fact is queued for the reconciler.
    assert c.repo.wallet.balance(c.owner).available_milli == 311 - 148
    assert debt(c) == 0
    assert c.repo.order(c.owner, order["order_id"])["status"] == "paid"
    assert c.db.execute("select outcome from app.payment_financial_events").fetchone()["outcome"] == "queued_reconciliation"


def test_facts_immutable_private_and_order_owner_scoped_in_rls(payment_case):
    c = payment_case
    order = checkout(c)
    deliver(c, event(c, order))
    for sql in ["update app.payment_orders set shard_milli=999", "delete from app.payment_orders",
                "delete from app.stripe_events"]:
        with pytest.raises(Exception), c.db.transaction():
            c.db.execute(sql)
    with c.db.transaction():
        c.db.execute("set local role rpg_api")
        c.db.execute("select set_config('request.jwt.claim.sub',%s,true)", (str(uuid4()),))
        assert c.db.execute("select count(*) n from app.payment_orders").fetchone()["n"] == 0
        c.db.execute("select set_config('request.jwt.claim.sub',%s,true)", (str(c.owner.user_id),))
        assert c.db.execute("select count(*) n from app.payment_orders").fetchone()["n"] == 1
        for table in ["payment_orders", "stripe_events", "payment_financial_events"]:
            with pytest.raises(Exception), c.db.transaction():
                c.db.execute("delete from app." + table)
    for role in ["anon", "authenticated"]:
        for table in ["payment_orders", "stripe_events", "payment_financial_events"]:
            with pytest.raises(Exception), c.db.transaction():
                c.db.execute("set local role " + role)
                c.db.execute("select * from app." + table)


def test_no_new_session_retry_after_stripe_idempotency_window(payment_case):
    from datetime import timedelta
    c = payment_case
    # Provider failure leaves a durable created order, safe to retry before 23h.
    original = c.fake.create_session
    def fail(*args, **kwargs):
        raise StripeError("provider timeout")
    c.fake.create_session = fail
    key = uuid4()
    with pytest.raises(StripeError):
        checkout(c, key)
    c.fake.create_session = original
    c.repo.at = c.at + timedelta(hours=24)
    expired = checkout(c, key)
    assert expired["status"] == "expired" and expired["checkout_url"] is None
    assert c.fake.calls == 0
    assert c.repo.wallet.balance(c.owner).available_milli == 0


@pytest.mark.parametrize("status", ["warning_needs_response", "warning_under_review", "prevented", "warning_closed"])
def test_inquiry_and_prevented_dispute_do_not_debit_wallet(payment_case, status):
    c = payment_case
    order = checkout(c)
    deliver(c, event(c, order))
    item = event(c, order, kind="charge.dispute.created")
    item["data"]["object"].update(id="du_inquiry", status=status)
    deliver(c, item)
    assert c.repo.wallet.balance(c.owner).available_milli == 311
    assert c.repo.order(c.owner, order["order_id"])["status"] == "reconciliation_required"
    assert c.db.execute("select outcome from app.payment_financial_events").fetchone()["outcome"] == "inquiry_" + status


@pytest.mark.parametrize("amount,currency,remaining", [(1100, "brl", 0), (1050, "usd", 0), (900, "eur", 311 - 266)])
def test_dispute_fx_or_amount_difference_is_audited_without_rejecting_provider(payment_case, amount, currency, remaining):
    c = payment_case
    order = checkout(c)
    deliver(c, event(c, order))
    item = event(c, order, kind="charge.dispute.created")
    item["data"]["object"].update(id="du_fx", status="needs_response", amount=amount, currency=currency)
    deliver(c, item)
    # SPEC-195: reversed = min(gross, disputed amount); target = floor(311 * reversed / 1050).
    assert c.repo.wallet.balance(c.owner).available_milli == remaining
    assert debt(c) == 0
    assert c.repo.order(c.owner, order["order_id"])["status"] in ("disputed", "reconciliation_required")
    fact = c.db.execute("select amount_cents,currency from app.payment_financial_events").fetchone()
    assert (fact["amount_cents"],fact["currency"]) == (amount,currency)
