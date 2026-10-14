"""Durable owner-scoped erasure. Financial facts are deliberately separate."""
from __future__ import annotations

from uuid import UUID

from infrastructure.contracts import Principal, Unauthorized

PRIVATE_TABLES = ("game_checkpoints", "game_events", "turns", "art_generations", "assets",
                  "chronicle_digests", "memory_documents", "runtime_catalog", "usage_events",
                  "operations", "jobs", "games", "image_quotes")
FINANCIAL_TABLES = ("wallet_accounts", "wallet_entries", "wallet_reservations",
                    "wallet_attempt_tickets", "wallet_settled_usage", "payment_orders")


class PostgresAccountLifecycle:
    def __init__(self, pool, identity, blobs, payments=None) -> None:
        self.pool, self.identity, self.blobs, self.payments = pool, identity, blobs, payments

    def _payments(self):
        if self.payments is not None:
            return self.payments
        from infrastructure.stripe_payments import StripePayments
        from services.stripe_checkout import StripeSettings, StripeTestAdapter

        settings = StripeSettings.for_cleanup()
        return StripePayments(self.pool, settings, StripeTestAdapter(settings.secret_key))

    def export(self, principal: Principal) -> dict:
        with self.pool.connection() as db, db.transaction():
            # Coordinate deletion/private writes; no caller-selected owner or auth rows.
            db.execute("select pg_advisory_xact_lock(hashtextextended(%s,190))", (str(principal.user_id),))
            if db.execute("select 1 from app.account_deletions where owner_id=%s", (principal.user_id,)).fetchone():
                raise Unauthorized("account_deleted")
            data = {table: db.execute(f"select * from app.{table} where owner_id=%s", (principal.user_id,)).fetchall()
                    for table in PRIVATE_TABLES + FINANCIAL_TABLES}
            data["payment_financial_events"] = db.execute("""select f.* from app.payment_financial_events f
                join app.payment_orders o on o.order_id=f.order_id where o.owner_id=%s""", (principal.user_id,)).fetchall()
        return {"format_version": 1, "owner_id": str(principal.user_id), "data": data}

    def begin(self, owner: UUID) -> None:
        with self.pool.connection() as db, db.transaction():
            db.execute("select pg_advisory_xact_lock(hashtextextended(%s,190))", (str(owner),))
            if db.execute("select 1 from app.account_deletions where owner_id=%s", (owner,)).fetchone():
                return
            from services.account_security import auth_email_bucket_keys
            user = db.execute("select email from auth.users where id=%s", (owner,)).fetchone()
            if user and user["email"]:
                db.execute("delete from app.rate_limit_buckets where bucket_key=any(%s)",
                           (list(auth_email_bucket_keys(user["email"])),))
            prefix = f"users/{owner}/"
            keys = {row["name"] for row in db.execute("""select name from storage.objects
                where bucket_id=%s and starts_with(name,%s)""", (self.blobs.bucket, prefix)).fetchall()}
            keys.update(row["object_key"] for row in db.execute(
                "select object_key from app.assets where owner_id=%s", (owner,)).fetchall()
                        if row["object_key"].startswith(prefix))
            # Global auth revocation is authoritative before private cleanup begins.
            db.execute("delete from auth.sessions where user_id=%s", (owner,))
            db.execute("delete from auth.refresh_tokens where user_id=%s", (str(owner),))
            # Fence queued AND leased work before tombstone triggers deny later writes.
            db.execute("""update app.jobs set status='cancelled',lease_token=null,lease_owner=null,
                lease_until=null,payload='{}',result=null,last_error_code='account_deleted',updated_at=now()
                where owner_id=%s""", (owner,))
            db.execute("""insert into app.account_deletions(owner_id,blob_keys,sessions_revoked_at)
                values (%s,%s,now())""", (owner, sorted(keys)))

    def finish(self, owner: UUID) -> str:
        with self.pool.connection() as db:
            row = db.execute("select * from app.account_deletions where owner_id=%s", (owner,)).fetchone()
        if not row:
            raise Unauthorized("account_delete_not_requested")
        if row["status"] == "deleted":
            return "deleted"
        # A previously issued Checkout link remains payable even after we clear
        # its DB URL. Close every provider session before final account removal.
        with self.pool.connection() as db:
            open_checkout = db.execute("""select 1 from app.payment_orders
                where owner_id=%s and status <> 'paid'
                  and checkout_closed_at is null limit 1""", (owner,)).fetchone()
        checkouts_closed = not open_checkout
        if open_checkout:
            from services.stripe_checkout import StripeError
            try:
                checkouts_closed = self._payments().close_deleted_owner_checkouts(owner)
            except StripeError:
                # Provider availability must not delay erasure of personal data.
                # The financial order and tombstone remain for a later retry.
                checkouts_closed = False
        # Sweep again: covers unregistered blobs uploaded immediately before denial.
        with self.pool.connection() as db:
            extra = db.execute("select name from storage.objects where bucket_id=%s and starts_with(name,%s)",
                               (self.blobs.bucket, f"users/{owner}/")).fetchall()
        keys = set(row["blob_keys"]) | {item["name"] for item in extra}
        blobs_deleted = True
        for key in keys:
            if not key.startswith(f"users/{owner}/"):
                raise Unauthorized("invalid_blob_owner")
            if not self.blobs.delete(key):
                blobs_deleted = False
        with self.pool.connection() as db, db.transaction():
            db.execute("select pg_advisory_xact_lock(hashtextextended(%s,190))", (str(owner),))
            # Each explicit predicate uses only the owner authenticated before revocation.
            for table in PRIVATE_TABLES:
                db.execute(f"delete from app.{table} where owner_id=%s", (owner,))
            # A retained financial row contains opaque IDs/numbers, no private prompt/data.
            db.execute("update app.payment_orders set checkout_url=null where owner_id=%s", (owner,))
        self.identity.delete_user(owner)
        if not (checkouts_closed and blobs_deleted):
            return "deleting"
        with self.pool.connection() as db:
            db.execute("""update app.account_deletions set status='deleted',blob_keys='{}',completed_at=now()
                where owner_id=%s""", (owner,))
        return "deleted"

    def delete(self, owner: UUID) -> str:
        self.begin(owner)
        return self.finish(owner)
