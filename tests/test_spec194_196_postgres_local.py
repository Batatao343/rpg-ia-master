"""SPEC-194/195/196 on REAL PostgreSQL (lab): Google Play fulfillment, refund debt, kill switches, FinOps.

Skips without RPG_TEST_DATABASE_URL. Every case uses fresh UUID owners/SKUs/versions, so it is safe to
run repeatedly against the lab database."""
from __future__ import annotations

import os
import threading
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone, UTC
from decimal import Decimal
from types import SimpleNamespace
from uuid import uuid4

import pytest

from infrastructure.contracts import Principal
from infrastructure.finops_reader import PostgresFinopsReader
from infrastructure.google_play_payments import GooglePlayPurchases, PostgresPurchaseStore
from infrastructure.kill_switch_store import PostgresSwitchStore
from infrastructure.postgres import PostgresPool
from infrastructure.reconciliation import PostgresStore, Reconciler
from infrastructure.wallet import FinancialHold, PostgresWallet
from services import kill_switches as ks
from services.google_play import (
    GooglePlayError,
    ProductPurchase,
    obfuscated_account_id,
    token_digest,
)
from services.purchase_reconciliation import GOOGLE, STRIPE, Event
from services.shard_pricing import INSTALLED_RATE_CARD_OBSERVED_AT, INSTALLED_RATE_CARD_SHA256
from services.usage_metering import RATE_CARD_VERSION
from tests.fakes.local_pricing import installed_card_max_age_seconds

pytestmark = pytest.mark.infra_local
SHARD = 311
GROSS = Decimal("10.50")
GROSS_CENTS = 1050


class FakeGoogle:
    def __init__(self, product_id, order_id):
        self.base = dict(product_id=product_id, order_id=order_id, purchase_state=0, consumption_state=0,
                         acknowledgement_state=0, quantity=1, purchase_time_millis=1,
                         account_id=None, purchase_type=None)
        self.consumed, self.lock = 0, threading.Lock()

    def get_purchase(self, product_id, token):
        return ProductPurchase(**self.base)

    def consume(self, product_id, token):
        with self.lock:
            self.consumed += 1


@pytest.fixture
def lab():
    pytest.importorskip("psycopg")
    from psycopg.types.json import Jsonb
    dsn = os.getenv("RPG_TEST_DATABASE_URL")
    if not dsn:
        pytest.skip("RPG_TEST_DATABASE_URL ausente")
    import psycopg
    with psycopg.connect(dsn) as c:
        for table in ("app.google_play_purchases", "app.purchase_reconciliation_events",
                      "app.wallet_debt_entries", "app.kill_switches"):
            if c.execute("select to_regclass(%s)", (table,)).fetchone()[0] is None:
                pytest.skip("migrations SPEC-194/195/196 não aplicadas")
        version, product, web_sku, gp_sku = ("lab-" + uuid4().hex[:12] for _ in range(4))
        product = "gp_" + uuid4().hex[:12]
        at = datetime.now(UTC)
        c.execute("""insert into app.pricing_versions
            (version_id,shard_budget_unit_brl,fx_usd_brl,fx_source,fx_observed_at,fx_max_age_seconds,
             fx_buffer_rate,rate_card_version,rate_card_sha256,rate_card_source,
             rate_card_observed_at,rate_card_max_age_seconds,channel_fees)
            values (%s,0.03,5,'lab',%s,864000,0.1,%s,%s,'lab',%s,%s,%s)""",
                  (version, at, RATE_CARD_VERSION, INSTALLED_RATE_CARD_SHA256,
                   INSTALLED_RATE_CARD_OBSERVED_AT, installed_card_max_age_seconds(),
                   Jsonb({"web": {"percentage": "0.04", "fixed_brl": "0.20"},
                          "google_play": {"percentage": "0.15", "fixed_brl": "0"}})))
        for sku, channel, store_id in ((web_sku, "web", web_sku), (gp_sku, "google_play", product)):
            c.execute("""insert into app.purchase_skus
                (sku_id,pricing_version_id,channel,store_product_id,gross_brl,shard_milli)
                values (%s,%s,%s,%s,%s,%s)""", (sku, version, channel, store_id, GROSS, SHARD))
    pool = PostgresPool(dsn, max_size=12)
    try:
        yield SimpleNamespace(dsn=dsn, pool=pool, version=version, product=product, web_sku=web_sku,
                              gp_sku=gp_sku, wallet=PostgresWallet(pool), store=PostgresStore(pool), at=at)
    finally:
        pool.close()


@pytest.fixture
def lab_rb(lab):
    """Same lab, but every statement runs on ONE connection that is rolled back at the end.

    Stripe orders/events must not leak into the shared lab: the legacy SPEC-189 tests count
    app.stripe_events / payment_orders globally."""
    from contextlib import nullcontext

    import psycopg
    from psycopg.rows import dict_row
    db = psycopg.connect(lab.dsn, row_factory=dict_row)
    db.execute("select 1")  # open the implicit tx so db.transaction() is a savepoint, never a COMMIT

    class Pool:
        def connection(self):
            return nullcontext(db)

    pool = Pool()
    try:
        yield SimpleNamespace(**{**vars(lab), "pool": pool, "wallet": PostgresWallet(pool),
                                 "store": PostgresStore(pool)})
    finally:
        db.rollback()
        db.close()


def balance(lab, owner):
    return lab.wallet.balance(owner).available_milli


def debt(lab, owner):
    with lab.pool.connection() as c:
        return int(c.execute("select coalesce(sum(debt_delta),0) as d from app.wallet_debt_entries "
                             "where owner_id=%s", (owner.user_id,)).fetchone()["d"])


def web_purchase(lab, owner, ref=None):
    """Real SPEC-189 flow: checkout -> paid webhook (credits the wallet). Returns the payment_intent."""
    import hashlib

    from infrastructure.stripe_payments import StripePayments
    from services.stripe_checkout import StripeSettings
    from tests.test_stripe_checkout_local import FakeStripe, event
    repo = StripePayments(lab.pool, StripeSettings("sk_test_fixture", "whsec_fixture",
                          "https://game.example", (lab.web_sku,)), FakeStripe(), at=lab.at)
    order = repo.checkout(owner, lab.web_sku, uuid4())
    item = event(None, order)
    repo.accept_event(item, body_sha256=hashlib.sha256(str(item).encode()).hexdigest())
    return "pi_" + order["order_id"]


def reserve(lab, owner, ceiling):
    return lab.wallet.reserve(owner, reference_type="other", reference_id=str(uuid4()),
                              pricing_version_id=lab.version, ceiling_milli=ceiling,
                              fence_token=uuid4(), at=lab.at)


def ev(kind, ref, n, amount=None, sub=None, provider=STRIPE):
    return Event(provider, f"{ref}-{n}", kind, ref, amount, sub, 0)


# ---------------------------------------------------------------- SPEC-194: Google Play
def test_google_fulfillment_single_credit_under_8_concurrent_verifies_then_consumed(lab):
    owner = Principal(uuid4(), "test", "gp")
    order, token = "GPA." + uuid4().hex[:12], "tok_" + uuid4().hex
    google = FakeGoogle(lab.product, order)
    google.base["account_id"] = obfuscated_account_id(owner.user_id)
    svc = GooglePlayPurchases(PostgresPurchaseStore(lab.pool), google)
    barrier = threading.Barrier(8)

    def run(_):
        barrier.wait(timeout=10)
        return svc.verify(owner, lab.product, token)

    with ThreadPoolExecutor(max_workers=8) as ex:
        results = list(ex.map(run, range(8)))
    assert balance(lab, owner) == SHARD
    assert all(r["consumed"] for r in results)
    import psycopg
    with psycopg.connect(lab.dsn) as c:
        assert c.execute("select count(*) from app.wallet_entries where owner_id=%s and entry_type='purchase'",
                         (owner.user_id,)).fetchone()[0] == 1
        rows = c.execute("select state from app.google_play_purchases where token_sha256=%s",
                         (token_digest(token),)).fetchall()
    assert rows == [("consumed",)]
    assert svc.verify(owner, lab.product, token)["consumed"] and balance(lab, owner) == SHARD


def test_google_consume_failure_keeps_credit_and_retry_consumes_once_persisted(lab):
    owner = Principal(uuid4(), "test", "gp2")
    order, token = "GPA." + uuid4().hex[:12], "tok_" + uuid4().hex
    google = FakeGoogle(lab.product, order)
    google.base["account_id"] = obfuscated_account_id(owner.user_id)
    store = PostgresPurchaseStore(lab.pool)
    svc = GooglePlayPurchases(store, google)
    original = google.consume

    def boom(*a):
        raise GooglePlayError("google_play_unavailable")

    google.consume = boom
    try:
        svc.verify(owner, lab.product, token)
    except GooglePlayError:
        pass  # consume failure may surface or be swallowed; either way the credit must stand
    assert balance(lab, owner) == SHARD  # fulfilled BEFORE consume; credit is never lost
    assert store.get_by_token(token_digest(token))["state"] == "fulfilled_unconsumed"
    google.consume = original
    assert svc.verify(owner, lab.product, token)["consumed"]
    assert balance(lab, owner) == SHARD and google.consumed == 1
    other = Principal(uuid4(), "test", "thief")
    with pytest.raises(GooglePlayError):
        svc.verify(other, lab.product, token)


# ---------------------------------------------------------------- SPEC-195: reconciliation
def test_refund_after_partial_spend_makes_debt_and_blocks_reservation(lab_rb):
    lab = lab_rb
    owner = Principal(uuid4(), "test", "r1")
    ref = web_purchase(lab, owner)
    lab.wallet.adjust_admin(owner, adjustment_id=str(uuid4()), signed_milli=-200, actor_id=uuid4(),
                            reason="spent for test")
    assert balance(lab, owner) == SHARD - 200
    rec = Reconciler(lab.store)
    rec.ingest(ev("refund", ref, 1, GROSS_CENTS, "ch_x"))
    assert lab.store.reconcile(STRIPE, ref) == "applied"
    # V2: claw all that is still available (111), the spent 200 becomes debt
    assert balance(lab, owner) == 0 and debt(lab, owner) == 200
    with pytest.raises(FinancialHold):
        reserve(lab, owner, 10)
    # duplicate provider event: no-op
    assert rec.ingest(ev("refund", ref, 1, GROSS_CENTS, "ch_x")) is False
    lab.store.reconcile(STRIPE, ref)
    assert balance(lab, owner) == 0 and debt(lab, owner) == 200
    # V3: a new purchase settles the debt FIRST, remainder is spendable
    web_purchase(lab, owner)
    assert debt(lab, owner) == 0 and balance(lab, owner) == SHARD - 200
    reserve(lab, owner, 10)  # hold lifted: reservation allowed again


def test_dispute_won_releases_debt_and_credit_by_compensating_entries(lab_rb):
    lab = lab_rb
    owner = Principal(uuid4(), "test", "r2")
    ref = web_purchase(lab, owner)
    lab.wallet.adjust_admin(owner, adjustment_id=str(uuid4()), signed_milli=-200, actor_id=uuid4(),
                            reason="spent for test")
    rec = Reconciler(lab.store)
    rec.ingest(ev("dispute_open", ref, 1, GROSS_CENTS, "du_1"))
    lab.store.reconcile(STRIPE, ref)
    assert (balance(lab, owner), debt(lab, owner)) == (0, 200)
    rec.ingest(ev("dispute_won", ref, 2, GROSS_CENTS, "du_1"))
    lab.store.reconcile(STRIPE, ref)
    assert (balance(lab, owner), debt(lab, owner)) == (SHARD - 200, 0)


def test_refund_before_purchase_is_parked_then_applied(lab_rb):
    lab = lab_rb
    owner, ref = Principal(uuid4(), "test", "r3"), "pi_" + uuid4().hex
    rec = Reconciler(lab.store)
    rec.ingest(ev("refund", ref, 1, GROSS_CENTS, "ch_y"))
    assert lab.store.reconcile(STRIPE, ref) == "parked"
    ref = web_purchase(lab, owner)  # a different, real purchase must be untouched by the parked ref
    assert balance(lab, owner) == SHARD
    rec.ingest(ev("fee_reconciled", ref, 2, 40))
    assert lab.store.reconcile(STRIPE, ref) == "applied"
    assert balance(lab, owner) == SHARD and debt(lab, owner) == 0
    with lab.pool.connection() as c:
        assert c.execute("select count(*) as n from app.purchase_fee_records where purchase_ref=%s",
                         (ref,)).fetchone()["n"] == 1
    rec.ingest(ev("fee_reconciled", ref, 2, 40))  # duplicate provider event id: no second record
    lab.store.reconcile(STRIPE, ref)
    with lab.pool.connection() as c:
        assert c.execute("select count(*) as n from app.purchase_fee_records where purchase_ref=%s",
                         (ref,)).fetchone()["n"] == 1


def test_debt_trigger_is_nonnegative_and_append_only(lab):
    import psycopg
    owner = uuid4()
    with psycopg.connect(lab.dsn) as c:
        with pytest.raises(psycopg.Error):
            with c.transaction():
                c.execute("""insert into app.wallet_debt_entries
                    (debt_entry_id,owner_id,kind,purchase_key,amount_milli,debt_delta,reference_id)
                    values (%s,%s,'release','k',5,-5,'x')""", (uuid4(), owner))
        c.execute("""insert into app.wallet_debt_entries
            (debt_entry_id,owner_id,kind,purchase_key,amount_milli,debt_delta,reference_id)
            values (%s,%s,'open','k',5,5,'y')""", (uuid4(), owner))
        with pytest.raises(psycopg.Error):
            with c.transaction():
                c.execute("update app.wallet_debt_entries set amount_milli=6 where owner_id=%s", (owner,))
        c.rollback()


def test_google_void_after_consumption_creates_debt(lab):
    owner = Principal(uuid4(), "test", "gv")
    order, token = "GPA." + uuid4().hex[:12], "tok_" + uuid4().hex
    google = FakeGoogle(lab.product, order)
    google.base["account_id"] = obfuscated_account_id(owner.user_id)
    GooglePlayPurchases(PostgresPurchaseStore(lab.pool), google).verify(owner, lab.product, token)
    lab.wallet.adjust_admin(owner, adjustment_id=str(uuid4()), signed_milli=-SHARD, actor_id=uuid4(),
                            reason="spent")
    Reconciler(lab.store).ingest(Event(GOOGLE, "void-" + order, "voided", order, None, None, 0))
    assert lab.store.reconcile(GOOGLE, order) == "applied"
    assert (balance(lab, owner), debt(lab, owner)) == (0, SHARD)


# ---------------------------------------------------------------- SPEC-196: kill switch + FinOps
def test_kill_switch_set_and_audit_via_postgres_store(lab):
    store = PostgresSwitchStore(lab.pool)
    store.set(ks.IMAGE, False, actor_id="ana", reason="lab-off")
    assert store.load()[ks.IMAGE] is False
    store.set(ks.IMAGE, True, actor_id="ana", reason="lab-on")
    assert store.load()[ks.IMAGE] is True
    audit = [a for a in store.audit(10) if a["key"] == ks.IMAGE]
    assert [a["enabled"] for a in audit[:2]] == [True, False]
    assert audit[0]["previous_enabled"] is False and audit[0]["actor_id"] == "ana"
    with pytest.raises(Exception):
        store.set(ks.IMAGE, False, actor_id="", reason="")


def test_finops_reader_returns_expected_aggregates_for_seeded_scenario(lab_rb):
    lab = lab_rb
    owner = Principal(uuid4(), "test", "fo")
    ref_web = web_purchase(lab, owner)
    Reconciler(lab.store).ingest(ev("fee_reconciled", ref_web, 1, 57))
    lab.store.reconcile(STRIPE, ref_web)
    order, token = "GPA." + uuid4().hex[:12], "tok_" + uuid4().hex
    google = FakeGoogle(lab.product, order)
    google.base["account_id"] = obfuscated_account_id(owner.user_id)
    GooglePlayPurchases(PostgresPurchaseStore(lab.pool), google).verify(owner, lab.product, token)
    reader = PostgresFinopsReader(lab.pool)
    refs, fresh = reader.pricing()
    assert lab.version in refs and "google_play" in refs[lab.version].fees and fresh
    now = datetime.now(UTC)
    mine = [p for p in reader.purchases(now - timedelta(hours=1), now + timedelta(hours=1))
            if p.owner_key == str(owner.user_id)]
    assert {p.sku_channel for p in mine} == {"web", "google_play"} and len(mine) == 2
    by = {p.sku_channel: p for p in mine}
    assert by["web"].gross_brl == GROSS and by["web"].shard_milli == SHARD
    assert by["web"].fee_actual_brl == Decimal("0.57")  # real fee wins over the estimate
    assert by["google_play"].fee_actual_brl is None
    assert reader.wallet_mismatch()[0] == 0  # ledger == accounts everywhere in the lab
    reader.ops_counts(now - timedelta(hours=1), now)  # query shape valid on the real schema
    reader.usage_groups(now - timedelta(hours=1), now)
    reader.owner_usage(now - timedelta(hours=1), now)
    reader.backlogs(now)


def test_google_poison_consume_counts_attempts_then_terminal_consume_failed(lab):
    import psycopg
    owner = Principal(uuid4(), "test", "gp-poison")
    order, token = "GPA." + uuid4().hex[:12], "tok_" + uuid4().hex
    google = FakeGoogle(lab.product, order)
    google.base["account_id"] = obfuscated_account_id(owner.user_id)

    def not_found(*a):
        raise GooglePlayError("google_play_purchase_not_found")
    google.consume = not_found
    store = PostgresPurchaseStore(lab.pool)
    svc = GooglePlayPurchases(store, google)
    assert svc.verify(owner, lab.product, token)["state"] == "fulfilled_unconsumed"   # attempt 1
    sha = token_digest(token)

    def backdate():
        with psycopg.connect(lab.dsn) as c:
            c.execute("update app.google_play_purchases set updated_at=now()-interval '5 minutes' "
                      "where token_sha256=%s", (sha,))
    for _ in range(7):
        backdate()
        assert any(r["token_sha256"] == sha for r in store.unconsumed(500))
        svc.retry_unconsumed(500)
    row = store.get_by_token(sha)
    assert row["state"] == "consume_failed" and row["consume_attempts"] == 8
    backdate()
    assert all(r["token_sha256"] != sha for r in store.unconsumed(500))   # terminal: leaves the batch
    assert svc.verify(owner, lab.product, token)["state"] == "consume_failed"
    assert balance(lab, owner) == SHARD
    with psycopg.connect(lab.dsn) as c, pytest.raises(psycopg.Error):
        c.execute("update app.google_play_purchases set state='fulfilled' where token_sha256=%s", (sha,))
