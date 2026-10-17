"""SPEC-189 durable orders and atomic signed-event → wallet fulfillment.

The caller must authenticate raw bytes using verify_event before accept_event.
Orders/SKUs own money and credit units; metadata is only an opaque lookup.
"""
from __future__ import annotations
from infrastructure.db_roles import admin_connection

from datetime import datetime, timedelta, timezone
from decimal import Decimal
import re
from uuid import UUID, uuid4

from psycopg.types.json import Jsonb

from infrastructure.contracts import Principal
from infrastructure.pricing_catalog import quote_published_sku
from infrastructure.wallet import PostgresWallet
from services.shard_pricing import PricingUnavailable
from services.stripe_checkout import OpenOrdersLimit, StripeError, StripeSettings, checkout_url_valid

PAID_EVENTS = {"checkout.session.completed", "checkout.session.async_payment_succeeded"}
FINANCIAL_EVENTS = {"charge.refunded", "charge.dispute.created", "charge.dispute.closed"}
TERMINAL = {"refunded", "disputed", "reconciliation_required"}


def _id(value, prefix: str) -> str | None:
    if isinstance(value, dict):
        value = value.get("id")
    return value if (isinstance(value, str) and value.startswith(prefix) and len(value) <= 160
                     and re.fullmatch(r"[A-Za-z0-9_-]+", value)) else None


def _int(value) -> int | None:
    return value if isinstance(value, int) and not isinstance(value, bool) and 0 <= value < 2**63 else None


def _facts(event: dict) -> dict:
    obj = event["data"]["object"]
    metadata = obj.get("metadata") or {}
    order_id = None
    try:
        order_id = str(UUID(metadata.get("order_id", "")))
    except (ValueError, AttributeError, TypeError):
        pass
    return {"object_id": _id(obj.get("id"), ""), "order_id": order_id,
            "payment_intent": _id(obj.get("payment_intent"), "pi_"),
            "mode": obj.get("mode") if obj.get("mode") in ("payment", "subscription", "setup") else None,
            "payment_status": obj.get("payment_status") if obj.get("payment_status") in ("paid", "unpaid", "no_payment_required") else None,
            "amount_total": _int(obj.get("amount_total")), "amount": _int(obj.get("amount")),
            "amount_refunded": _int(obj.get("amount_refunded")),
            "currency": obj.get("currency") if isinstance(obj.get("currency"), str)
                and re.fullmatch(r"[a-z]{3}", obj["currency"]) else None,
            "dispute_status": obj.get("status") if obj.get("status") in
                ("won", "lost", "needs_response", "under_review", "warning_closed",
                 "warning_needs_response", "warning_under_review", "prevented") else None}


def _public(row, *, include_url=False) -> dict:
    result = {"order_id": str(row["order_id"]), "status": row["status"],
              "sku_id": row["sku_id"], "gross_brl": format(Decimal(row["gross_cents"]) / 100, ".2f"),
              "shard_milli": str(row["shard_milli"])}
    if include_url:
        result["checkout_url"] = row["checkout_url"] if row["status"] in {"created", "checkout_pending"} else None
    return result


def _account_deleted(db, owner_id: UUID) -> bool:
    # SPEC-189's isolated rollback fixture deliberately applies only its own
    # migration. The production schema always has SPEC-190 once deletion opens.
    present = db.execute("select to_regclass('app.account_deletions') as relation").fetchone()
    if present["relation"] is None:
        return False
    return db.execute("select 1 from app.account_deletions where owner_id=%s", (owner_id,)).fetchone() is not None


class StripePayments:
    def __init__(self, pool, settings: StripeSettings, adapter, *, at: datetime | None = None) -> None:
        self.pool, self.settings, self.adapter = pool, settings, adapter
        self.wallet = PostgresWallet(pool)
        self.at = at

    def _now(self) -> datetime:
        return self.at or datetime.now(timezone.utc)

    def skus(self) -> dict:
        items = []
        with admin_connection(self.pool) as db:
            for sku in self.settings.allowed_skus:
                try:
                    quote = quote_published_sku(db, sku, at=self._now())
                    if quote.channel == "web":
                        items.append({"sku_id": sku, "gross_brl": format(quote.gross_brl, ".2f"),
                                      "shard_milli": str(quote.shard_milli_granted)})
                except PricingUnavailable:
                    continue
        if not items:
            raise StripeError("stripe_catalog_unavailable")
        return {"items": items}

    def order(self, owner: Principal, order_id: str) -> dict | None:
        with admin_connection(self.pool) as db:
            row = db.execute("select * from app.payment_orders where owner_id=%s and order_id=%s",
                             (owner.user_id, UUID(order_id))).fetchone()
        return _public(row) if row else None

    def close_deleted_owner_checkouts(self, owner_id: UUID) -> bool:
        """Provider-close open sessions before final erasure; retry safely."""
        with admin_connection(self.pool) as db:
            pending = db.execute("""select * from app.payment_orders where owner_id=%s
                and status <> 'paid' and checkout_closed_at is null
                order by created_at,order_id""", (owner_id,)).fetchall()
        for order in pending:
            session_id = order["stripe_session_id"]
            if not session_id:
                # Recover an in-flight/lost create with the SAME order id and
                # Stripe idempotency key. Never invent a second paid order.
                order_id = str(order["order_id"])
                session = self.adapter.create_session(
                    order_id, amount_cents=order["gross_cents"],
                    success_url=self.settings.origin + "/?checkout=success&order_id=" + order_id,
                    cancel_url=self.settings.origin + "/?checkout=cancel&order_id=" + order_id)
                if not _id(session.get("id"), "cs_test_"):
                    raise StripeError("stripe_session_invalid")
                session_id = session["id"]
                with admin_connection(self.pool) as db, db.transaction():
                    row = db.execute("select * from app.payment_orders where order_id=%s for update",
                                     (order["order_id"],)).fetchone()
                    if row["stripe_session_id"] not in (None, session_id):
                        raise StripeError("stripe_checkout_session_conflict")
                    db.execute("""update app.payment_orders set stripe_session_id=%s,checkout_url=null,
                        updated_at=now() where order_id=%s""", (session_id, order["order_id"]))
            closed = self.adapter.expire_session(session_id)
            with admin_connection(self.pool) as db, db.transaction():
                row = db.execute("select * from app.payment_orders where order_id=%s for update",
                                 (order["order_id"],)).fetchone()
                # A completed session may be awaiting its paid webhook. Preserve
                # an explicit financial hold instead of crediting a dead wallet.
                status = "reconciliation_required" if closed == "complete" else "expired"
                if row["status"] in TERMINAL | {"paid"}:
                    status = row["status"]
                db.execute("""update app.payment_orders set status=%s,checkout_url=null,
                    checkout_closed_at=now(),updated_at=now() where order_id=%s""",
                    (status, order["order_id"]))
        with admin_connection(self.pool) as db:
            return not db.execute("""select 1 from app.payment_orders where owner_id=%s
                and status <> 'paid' and checkout_closed_at is null limit 1""",
                (owner_id,)).fetchone()

    @staticmethod
    def _guard_open_orders(db, owner_id: UUID, now: datetime) -> None:
        import os
        try:
            limit = int(os.getenv("RPG_LIMIT_PAYMENTS_OPEN_ORDERS", "3"))
        except ValueError:
            limit = 3
        if limit <= 0:
            return
        row = db.execute("""select count(*) as n from app.payment_orders
            where owner_id=%s and status in ('created','checkout_pending') and expires_at > %s""",
                         (owner_id, now)).fetchone()
        if int(row["n"]) >= limit:
            raise OpenOrdersLimit("stripe_open_orders_limit")

    def checkout(self, owner: Principal, sku_id: str, request_id: UUID) -> dict:
        if sku_id not in self.settings.allowed_skus or not isinstance(request_id, UUID):
            raise StripeError("stripe_sku_not_allowed")
        now = self._now()
        with admin_connection(self.pool) as db, db.transaction():
            prior = db.execute("select * from app.payment_orders where owner_id=%s and request_id=%s for update",
                               (owner.user_id, request_id)).fetchone()
            if prior is None:
                from services.kill_switches import require_purchases  # SPEC-196: NEW orders only
                require_purchases("stripe")
                self._guard_open_orders(db, owner.user_id, now)   # SPEC-219: ordens abertas por owner
                quote = quote_published_sku(db, sku_id, at=now)
                if quote.channel != "web":
                    raise StripeError("stripe_sku_channel_invalid")
                # Re-read after competing create, while immutable SKU facts stay authoritative.
                db.execute("""insert into app.payment_orders
                    (order_id,owner_id,request_id,sku_id,pricing_version_id,gross_cents,shard_milli,
                     estimated_fee_cents,allocated_budget_brl,expires_at)
                    values (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s) on conflict (owner_id,request_id) do nothing""",
                    (uuid4(),owner.user_id,request_id,sku_id,quote.pricing_version,
                     int(quote.gross_brl*100),quote.shard_milli_granted,int(quote.channel_fee_brl*100),
                     quote.allocated_budget_brl,now + timedelta(hours=23)))
                prior = db.execute("select * from app.payment_orders where owner_id=%s and request_id=%s for update",
                                   (owner.user_id,request_id)).fetchone()
            if prior["sku_id"] != sku_id:
                raise StripeError("stripe_checkout_replay_conflict")
            if prior["status"] in TERMINAL | {"paid", "expired"}:
                return _public(prior, include_url=True)
            if now >= prior["expires_at"]:
                db.execute("update app.payment_orders set status='expired',updated_at=now() where order_id=%s",
                           (prior["order_id"],))
                return {**_public(prior, include_url=True), "status": "expired", "checkout_url": None}
            if prior["stripe_session_id"]:
                return _public(prior, include_url=True)
            order_id = str(prior["order_id"])
            amount = int(prior["gross_cents"])
        # No remote network within the financial transaction. A lost response can
        # be retried only within 23h, below Stripe's 24h idempotency retention.
        with admin_connection(self.pool) as db:
            if _account_deleted(db, owner.user_id):
                raise StripeError("account_deleted")
        session = self.adapter.create_session(order_id, amount_cents=amount,
            success_url=self.settings.origin + "/?checkout=success&order_id=" + order_id,
            cancel_url=self.settings.origin + "/?checkout=cancel&order_id=" + order_id)
        if not _id(session.get("id"), "cs_test_") or not checkout_url_valid(session.get("url")):
            raise StripeError("stripe_session_invalid")
        deleted_after_create = False
        with admin_connection(self.pool) as db, db.transaction():
            row = db.execute("select * from app.payment_orders where order_id=%s for update", (UUID(order_id),)).fetchone()
            if row["stripe_session_id"] not in (None, session["id"]):
                raise StripeError("stripe_checkout_session_conflict")
            row = db.execute("""update app.payment_orders set stripe_session_id=%s,checkout_url=%s,
                status=case when status='created' then 'checkout_pending' else status end,updated_at=now()
                where order_id=%s returning *""", (session["id"],session["url"],UUID(order_id))).fetchone()
            deleted_after_create = _account_deleted(db, owner.user_id)
            result = _public(row, include_url=True)
        if deleted_after_create:
            self.close_deleted_owner_checkouts(owner.user_id)
            raise StripeError("account_deleted")
        return result

    def accept_event(self, event: dict, *, body_sha256: str) -> dict:
        facts = _facts(event)
        intent_for_fee = None
        with admin_connection(self.pool) as db, db.transaction():
            # This lock coordinates financial events with a Checkout that is
            # binding its payment_intent for the first time. Order locks alone
            # cannot serialize an initially orphan refund/dispute.
            lock_key = facts["payment_intent"] or facts["order_id"] or event["id"]
            db.execute("select pg_advisory_xact_lock(hashtextextended(%s,189))", (lock_key,))
            previous = db.execute("select * from app.stripe_events where event_id=%s", (event["id"],)).fetchone()
            if previous:
                if previous["body_sha256"] != body_sha256:
                    raise StripeError("stripe_event_replay_conflict")
            else:
                db.execute("""insert into app.stripe_events(event_id,event_type,body_sha256,provider_created,facts)
                              values (%s,%s,%s,%s,%s)""",
                           (event["id"],event["type"],body_sha256,event["created"],Jsonb(facts)))
            if event["type"] in PAID_EVENTS:
                row = self._checkout_event(db, event["id"], event["type"], facts)
                if row and row["stripe_payment_intent"]:
                    intent_for_fee = row["stripe_payment_intent"]
            elif event["type"] in FINANCIAL_EVENTS:
                row = self._find_financial_order(db, facts)
                if row:
                    self._financial_event(db, row, event["id"], event["type"], facts)
        # Fee reconciliation is optional and recoverable on duplicate paid
        # delivery; a provider outage never rolls back a verified purchase.
        if intent_for_fee:
            self.reconcile_fee(intent_for_fee)
        if facts["payment_intent"] and (event["type"] in FINANCIAL_EVENTS or event["type"] in PAID_EVENTS):
            self._reconcile_wallet(facts["payment_intent"])
        return {"received": True, "duplicate": previous is not None}

    def _checkout_event(self, db, event_id: str, kind: str, facts: dict):
        if not facts["order_id"]:
            return None
        row = db.execute("select * from app.payment_orders where order_id=%s for update",
                         (UUID(facts["order_id"]),)).fetchone()
        if row is None:
            return None
        if (not _id(facts["object_id"], "cs_test_") or facts["mode"] != "payment"
                or facts["amount_total"] != row["gross_cents"] or facts["currency"] != row["currency"]
                or row["stripe_session_id"] not in (None, facts["object_id"])):
            raise StripeError("stripe_checkout_event_mismatch")
        if facts["payment_status"] != "paid":
            return row
        if not facts["payment_intent"] or row["stripe_payment_intent"] not in (None, facts["payment_intent"]):
            raise StripeError("stripe_checkout_intent_mismatch")
        row = db.execute("""update app.payment_orders set stripe_session_id=%s,stripe_payment_intent=%s,
            updated_at=now() where order_id=%s returning *""",
            (facts["object_id"],facts["payment_intent"],row["order_id"])).fetchone()
        # Delayed financial events can predate the paid Checkout. Apply them
        # first so payment never resurrects a refunded/disputed grant.
        pending = db.execute("""select * from app.stripe_events where event_type=any(%s)
            and facts->>'payment_intent'=%s order by provider_created,event_id""",
            (list(FINANCIAL_EVENTS),facts["payment_intent"])).fetchall()
        for item in pending:
            self._financial_event(db, row, item["event_id"], item["event_type"], item["facts"])
            row = db.execute("select * from app.payment_orders where order_id=%s", (row["order_id"],)).fetchone()
        if _account_deleted(db, row["owner_id"]):
            outcome = "already_refunded" if row["status"] == "refunded" else "refund_required"
            db.execute("""insert into app.payment_financial_events
                (financial_id,order_id,stripe_event_id,kind,provider_reference,amount_cents,currency,outcome)
                values (%s,%s,%s,'late_paid_after_delete',%s,%s,%s,%s)
                on conflict (order_id,kind,provider_reference) do nothing""",
                (uuid4(),row["order_id"],event_id,facts["payment_intent"],row["gross_cents"],
                 row["currency"],outcome))
            if outcome != "already_refunded":
                row = db.execute("""update app.payment_orders set status='reconciliation_required',
                    checkout_url=null,updated_at=now() where order_id=%s returning *""",
                    (row["order_id"],)).fetchone()
            return row
        if row["status"] not in TERMINAL:
            sku = db.execute("select * from app.purchase_skus where sku_id=%s", (row["sku_id"],)).fetchone()
            if (not sku or sku["channel"] != "web" or sku["pricing_version_id"] != row["pricing_version_id"]
                    or sku["shard_milli"] != row["shard_milli"] or int(sku["gross_brl"]*100) != row["gross_cents"]):
                raise StripeError("stripe_order_sku_authority_mismatch")
            self.wallet.credit_verified_purchase(
                Principal(row["owner_id"], "stripe", str(row["owner_id"])), channel="web",
                payment_id=facts["payment_intent"], sku_id=row["sku_id"], verified=True, connection=db)
            row = db.execute("update app.payment_orders set status='paid',updated_at=now() where order_id=%s returning *",
                             (row["order_id"],)).fetchone()
        return row

    def _reconcile_wallet(self, payment_intent: str) -> None:
        """Best-effort immediate SPEC-195 pass; the cron job retries anything left pending."""
        try:
            from infrastructure.reconciliation import PostgresStore
            store = PostgresStore(self.pool)
            store.ingest_backlog(50)
            store.reconcile("stripe", payment_intent)
        except Exception as exc:  # never fail a verified webhook delivery on a recoverable pass
            import logging  # error class only: no ids/amounts/PII in the log line
            logging.getLogger("rpg.reconciliation").warning(
                "immediate_reconcile_failed error=%s", type(exc).__name__)
            return

    @staticmethod
    def _find_financial_order(db, facts):
        if not facts["payment_intent"]:
            return None
        # Financial events bind via payment intent, never customer metadata.
        return db.execute("select * from app.payment_orders where stripe_payment_intent=%s for update",
                          (facts["payment_intent"],)).fetchone()

    def _financial_event(self, db, row, event_id: str, event_type: str, facts: dict) -> None:
        kind = {"charge.refunded": "refund", "charge.dispute.created": "dispute",
                "charge.dispute.closed": "dispute_closed"}[event_type]
        reference = facts["object_id"]
        amount = facts["amount_refunded"] if kind == "refund" else facts["amount"]
        expected_prefix = "ch_" if kind == "refund" else "du_"
        if (not _id(reference, expected_prefix) or amount is None or amount <= 0
                or facts["currency"] is None
                or (kind == "refund" and (amount > row["gross_cents"] or facts["currency"] != row["currency"]))):
            raise StripeError("stripe_financial_event_mismatch")
        # Refund is cumulative per charge. Distinct partial/full notifications
        # keep their own immutable facts, while one purchase is reversed once.
        fact_key = reference + ":" + str(amount) if kind == "refund" else reference
        prior = db.execute("select 1 from app.payment_financial_events where order_id=%s and kind=%s and provider_reference=%s",
                           (row["order_id"],kind,fact_key)).fetchone()
        if prior:
            return
        purchase = db.execute("select entry_id from app.wallet_entries where entry_type='purchase' "
                              "and reference_type='payment:web' and reference_id=%s",
                              (row["stripe_payment_intent"],)).fetchone()
        status = "refunded" if kind == "refund" else "disputed"
        outcome = "blocked_before_credit"
        if kind == "dispute_closed":
            # Won/lost facts never silently undo a debit. Restoration requires
            # an audited operator correction and keeps the prior reversal.
            outcome = "dispute_" + str(facts["dispute_status"])
            # SPEC-195: won releases the hold via compensating entries; lost keeps the claw-back.
            status = "paid" if facts["dispute_status"] in ("won", "warning_closed") else (
                "disputed" if facts["dispute_status"] == "lost" else "reconciliation_required")
        elif kind == "dispute" and (facts["dispute_status"] is None
                or facts["dispute_status"].startswith("warning_") or facts["dispute_status"] == "prevented"):
            status, outcome = "reconciliation_required", "inquiry_" + str(facts["dispute_status"])
        elif facts["currency"] != row["currency"]:
            status = "reconciliation_required"
            outcome = "currency_requires_reconciliation"
        elif purchase:
            # SPEC-195: the wallet effect (claw-back, debt, release) is applied by the
            # idempotent reconciler from the normalized event, never by this handler.
            outcome = "queued_reconciliation"
            if kind == "refund" and amount < row["gross_cents"]:
                status = row["status"]  # partial refund: purchase stays paid
        elif kind == "refund" and amount < row["gross_cents"]:
            # SPEC-236 R6: a PARTIAL refund delivered before the paid Checkout must not block the
            # credit of a paid purchase. The order keeps its status, the Checkout credits in
            # full, and the reconciler (SPEC-195) then claws back the proportional share.
            status, outcome = row["status"], "pending_partial_refund"
        db.execute("""insert into app.payment_financial_events
            (financial_id,order_id,stripe_event_id,kind,provider_reference,amount_cents,currency,outcome)
            values (%s,%s,%s,%s,%s,%s,%s,%s)""",
            (uuid4(),row["order_id"],event_id,kind,fact_key,amount,facts["currency"],outcome))
        if kind == "dispute" and status == "disputed" and db.execute(
                "select 1 from app.payment_financial_events where order_id=%s and kind='dispute_closed' "
                "and provider_reference=%s and outcome in ('dispute_won','dispute_warning_closed')",
                (row["order_id"], reference)).fetchone():
            status = "paid"  # a late `created` must not reopen a dispute already closed as won
        # Never downgrade a reconciliation hold by a late created/refund event.
        if row["status"] == "reconciliation_required":
            status = "reconciliation_required"
        db.execute("update app.payment_orders set status=%s,updated_at=now() where order_id=%s",
                   (status,row["order_id"]))

    def reconcile_fee(self, payment_intent: str) -> None:
        with admin_connection(self.pool) as db:
            existing = db.execute("select actual_fee_cents from app.payment_orders where stripe_payment_intent=%s",
                                  (payment_intent,)).fetchone()
        if not existing or existing["actual_fee_cents"] is not None:
            return
        try:
            economics = self.adapter.payment_economics(payment_intent)
        except StripeError:
            return
        if not economics:
            return
        with admin_connection(self.pool) as db, db.transaction():
            row = db.execute("select * from app.payment_orders where stripe_payment_intent=%s for update",
                             (payment_intent,)).fetchone()
            if (not row or economics.get("currency") != row["currency"]
                    or _int(economics.get("fee_cents")) is None
                    or not _id(economics.get("balance_transaction_id"), "txn_")):
                return
            inserted = db.execute("""insert into app.payment_financial_events
                (financial_id,order_id,kind,provider_reference,amount_cents,currency,outcome)
                values (%s,%s,'fee_reconciled',%s,%s,'brl','actual_balance_transaction')
                on conflict (order_id,kind,provider_reference) do nothing returning financial_id""",
                (uuid4(),row["order_id"],economics["balance_transaction_id"],economics["fee_cents"])).fetchone()
            if inserted:
                db.execute("""update app.payment_orders set actual_fee_cents=%s,
                           actual_contribution_margin_brl=(gross_cents-%s)::numeric/100-allocated_budget_brl,
                           updated_at=now() where order_id=%s""",
                           (economics["fee_cents"],economics["fee_cents"],row["order_id"]))
