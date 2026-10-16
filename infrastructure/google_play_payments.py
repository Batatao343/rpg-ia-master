"""SPEC-194 idempotent Google Play fulfillment: verify -> credit -> consume."""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Protocol
from uuid import UUID, uuid4

from psycopg.types.json import Jsonb

from infrastructure.contracts import Principal
from infrastructure.wallet import PostgresWallet
from services.google_play import (
    CANCELLED, ORDER_RE, PENDING, PRODUCT_RE, PURCHASED, TOKEN_RE, GooglePlayError,
    ProductPurchase, obfuscated_account_id, token_digest,
)

CHANNEL = "google_play"
MAX_CONSUME_ATTEMPTS = 8  # poison consume (400/404/410, still unconsumed at Google) -> terminal consume_failed
log = logging.getLogger("rpg.google_play")


class PurchaseStore(Protocol):
    def sku_for_product(self, product_id: str) -> dict | None: ...
    def owner_deleted(self, owner_id: UUID) -> bool: ...
    def get_by_token(self, token_sha: str) -> dict | None: ...
    def fulfill(self, owner_id: UUID, sku: dict, token: str, order_id: str,
                facts: ProductPurchase) -> dict: ...
    def set_state(self, token_sha: str, state: str) -> None: ...
    def record_consume_failure(self, token_sha: str, limit: int) -> str: ...
    def unconsumed(self, limit: int) -> list[dict]: ...


def _public(row: dict) -> dict:
    return {"status": "fulfilled", "state": row["state"], "product_id": row["product_id"],
            "sku_id": row["sku_id"], "shard_milli": str(row["shard_milli"]),
            "consumed": row["state"] == "consumed"}


class GooglePlayPurchases:
    def __init__(self, store: PurchaseStore, client) -> None:
        self.store, self.client = store, client

    def verify(self, owner: Principal, product_id: str, purchase_token: str,
               order_id: str | None = None) -> dict:
        if not PRODUCT_RE.fullmatch(product_id or "") or not TOKEN_RE.fullmatch(purchase_token or "") \
                or (order_id is not None and not ORDER_RE.fullmatch(order_id)):
            raise GooglePlayError("google_play_input_invalid")
        sku = self.store.sku_for_product(product_id)
        if sku is None:
            raise GooglePlayError("google_play_product_unknown")
        if self.store.owner_deleted(owner.user_id):
            raise GooglePlayError("account_deleted")
        digest = token_digest(purchase_token)
        prior = self.store.get_by_token(digest)
        if prior is not None:
            if prior["owner_id"] != owner.user_id or prior["product_id"] != product_id:
                raise GooglePlayError("google_play_token_conflict")
            if prior["state"] not in ("consumed", "consume_failed"):
                self._consume(prior)
                prior = self.store.get_by_token(digest)
            return _public(prior)
        from services.kill_switches import SwitchOff, require_purchases  # SPEC-196: NEW purchases only
        try:
            require_purchases("google_play")
        except SwitchOff:
            raise GooglePlayError("new_purchases_disabled") from None
        facts = self.client.get_purchase(product_id, purchase_token)
        if facts.product_id != product_id:
            raise GooglePlayError("google_play_product_mismatch")
        if facts.purchase_state == PENDING:
            return {"status": "pending"}
        if facts.purchase_state == CANCELLED:
            raise GooglePlayError("google_play_purchase_cancelled")
        if facts.purchase_state != PURCHASED:
            raise GooglePlayError("google_play_response_invalid")
        if not facts.order_id or not ORDER_RE.fullmatch(facts.order_id) \
                or (order_id is not None and order_id != facts.order_id):
            raise GooglePlayError("google_play_order_mismatch")
        if facts.quantity != 1:
            raise GooglePlayError("google_play_quantity_unsupported")
        if facts.account_id != obfuscated_account_id(owner.user_id):
            raise GooglePlayError("google_play_account_mismatch")
        if facts.consumption_state != 0:
            # A concurrent duplicate may have fulfilled and consumed meanwhile.
            raced = self.store.get_by_token(digest)
            if raced is not None and raced["owner_id"] == owner.user_id:
                return _public(raced)
            # Consumed before we persisted fulfillment: never credit blindly.
            raise GooglePlayError("google_play_already_consumed")
        row = self.store.fulfill(owner.user_id, sku, purchase_token, facts.order_id, facts)
        if row["state"] != "consumed":
            self._consume(row)
        return _public(self.store.get_by_token(digest))

    def _consume(self, row: dict) -> str:
        """Only called once the fulfillment row is committed. Returns the resulting state."""
        sha = row["token_sha256"]
        try:
            self.client.consume(row["product_id"], row["purchase_token"])
        except GooglePlayError as exc:
            if str(exc) != "google_play_purchase_not_found":  # transient (5xx/network): retry forever
                self.store.set_state(sha, "fulfilled_unconsumed")
                return "fulfilled_unconsumed"
            # Poison candidate (400/404/410): the purchase may simply already be consumed.
            try:
                already = self.client.get_purchase(row["product_id"], row["purchase_token"]).consumption_state == 1
            except GooglePlayError:
                already = False
            if already:
                self.store.set_state(sha, "consumed")
                return "consumed"
            state = self.store.record_consume_failure(sha, MAX_CONSUME_ATTEMPTS)
            if state == "consume_failed":
                log.error("google_play_consume_failed_terminal error=%s", type(exc).__name__)
            return state
        self.store.set_state(sha, "consumed")
        return "consumed"

    def retry_unconsumed(self, limit: int = 20) -> int:
        """Worker/cron entry; re-consuming a consumed token is harmless.

        `last_retry` carries the cron summary: attempted rows and rows that went terminal now.
        """
        rows = self.store.unconsumed(limit)
        newly_failed = sum(1 for row in rows if self._consume(row) == "consume_failed")
        self.last_retry = {"retried": len(rows), "consume_failed": newly_failed}
        return len(rows)


class PostgresPurchaseStore:
    def __init__(self, pool) -> None:
        self.pool, self.wallet = pool, PostgresWallet(pool)

    def sku_for_product(self, product_id):
        with self.pool.connection() as db:
            row = db.execute("select sku_id,shard_milli,pricing_version_id from app.purchase_skus "
                             "where channel='google_play' and store_product_id=%s "
                             "order by created_at desc limit 1", (product_id,)).fetchone()
        return dict(row) if row else None

    def list_products(self):
        """Newest SKU per google_play product; shard amount only (never a price)."""
        with self.pool.connection() as db:
            rows = db.execute("select distinct on (store_product_id) store_product_id,sku_id,shard_milli "
                              "from app.purchase_skus where channel='google_play' "
                              "order by store_product_id, created_at desc").fetchall()
        return [{"product_id": r["store_product_id"], "sku_id": r["sku_id"],
                 "shard_milli": str(r["shard_milli"])} for r in rows]

    def owner_deleted(self, owner_id):
        with self.pool.connection() as db:
            if db.execute("select to_regclass('app.account_deletions') as r").fetchone()["r"] is None:
                return False
            return db.execute("select 1 from app.account_deletions where owner_id=%s",
                              (owner_id,)).fetchone() is not None

    def get_by_token(self, token_sha):
        with self.pool.connection() as db:
            row = db.execute("select p.*,s.shard_milli from app.google_play_purchases p "
                             "join app.purchase_skus s using (sku_id) where token_sha256=%s",
                             (token_sha,)).fetchone()
        return dict(row) if row else None

    def fulfill(self, owner_id, sku, token, order_id, facts):
        sha = token_digest(token)
        with self.pool.connection() as db, db.transaction():
            db.execute("select pg_advisory_xact_lock(hashtextextended(%s,194))", (sha,))
            row = db.execute("select * from app.google_play_purchases where token_sha256=%s or order_id=%s",
                             (sha, order_id)).fetchone()
            if row is None:
                # Wallet credit and purchase row share this transaction.
                self.wallet.credit_verified_purchase(
                    Principal(owner_id, "google_play", str(owner_id)), channel=CHANNEL,
                    payment_id=order_id, sku_id=sku["sku_id"], verified=True, connection=db)
                when = (datetime.fromtimestamp(facts.purchase_time_millis / 1000, timezone.utc)
                        if facts.purchase_time_millis else None)
                db.execute("""insert into app.google_play_purchases
                    (purchase_id,owner_id,product_id,sku_id,pricing_version_id,token_sha256,
                     purchase_token,order_id,purchased_at,google_state,state)
                    values (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,'fulfilled')""",
                    (uuid4(), owner_id, facts.product_id, sku["sku_id"], sku["pricing_version_id"],
                     sha, token, order_id, when, Jsonb(facts.snapshot())))
            elif row["token_sha256"] != sha or row["owner_id"] != owner_id:
                raise GooglePlayError("google_play_token_conflict")
        self._reconcile_order(order_id)
        return self.get_by_token(sha)

    def _reconcile_order(self, order_id) -> None:
        """Best-effort SPEC-195 pass (a void may have arrived first); the cron retries on failure."""
        try:
            from infrastructure.reconciliation import PostgresStore
            with self.pool.connection() as db:  # nothing to apply unless a void/fee already arrived
                waiting = db.execute("select 1 from app.purchase_reconciliation_events where "
                                     "provider='google_play' and purchase_ref=%s limit 1", (order_id,)).fetchone()
            if waiting:
                PostgresStore(self.pool).reconcile("google_play", order_id)
        except Exception as exc:  # never fail a fulfilled purchase on a recoverable pass
            import logging  # error class only: no ids/amounts/PII
            logging.getLogger("rpg.reconciliation").warning(
                "immediate_reconcile_failed error=%s", type(exc).__name__)

    def set_state(self, token_sha, state):
        with self.pool.connection() as db, db.transaction():
            db.execute("update app.google_play_purchases set state=%s,updated_at=now() "
                       "where token_sha256=%s and state not in ('consumed','consume_failed')", (state, token_sha))

    def record_consume_failure(self, token_sha, limit):
        """Count one poison attempt; at `limit` the row becomes terminal `consume_failed`."""
        with self.pool.connection() as db, db.transaction():
            row = db.execute(
                "update app.google_play_purchases set consume_attempts=consume_attempts+1,"
                "state=case when consume_attempts+1>=%s then 'consume_failed' else 'fulfilled_unconsumed' end,"
                "updated_at=now() where token_sha256=%s and state not in ('consumed','consume_failed') "
                "returning state", (limit, token_sha)).fetchone()
        return row["state"] if row else self.get_by_token(token_sha)["state"]

    def unconsumed(self, limit):
        with self.pool.connection() as db:
            return [dict(r) for r in db.execute(
                "select * from app.google_play_purchases where state in ('fulfilled','fulfilled_unconsumed') "
                # SPEC-222 R4: a deleted account's row loses its token; nothing left to consume.
                "and purchase_token is not null "
                "and updated_at < now() - interval '1 minute' order by updated_at limit %s",
                (limit,)).fetchall()]
