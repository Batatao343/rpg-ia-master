"""Durable owner-scoped erasure. Financial facts are deliberately separate."""
from __future__ import annotations
from infrastructure.db_roles import admin_connection

from uuid import UUID

from infrastructure.contracts import Principal, Unauthorized

PRIVATE_TABLES = ("game_checkpoints", "game_events", "turns", "art_generations", "assets",
                  "chronicle_digests", "memory_documents", "runtime_catalog", "usage_events",
                  "operations", "jobs", "games", "image_quotes", "owner_daily_counters")
FINANCIAL_TABLES = ("wallet_accounts", "wallet_entries", "wallet_reservations",
                    "wallet_attempt_tickets", "wallet_settled_usage", "payment_orders",
                    "wallet_debt_entries", "purchase_reconciliation_state")
# SPEC-222 R3/R10: toda tabela app.* com owner_id que SOBREVIVE à exclusão tem motivo
# legal e prazo declarados aqui. É a fonte da seção de retenção da política
# (docs/spec222/retencao.md, validado por teste).
_FINANCIAL_REASON = ("obrigação contábil/fiscal e defesa em disputa (extrato por identificador "
                     "opaco, sem conteúdo de jogo) — 5 anos após a transação")
RETAINED_WITH_REASON: dict[str, str] = {
    **{table: _FINANCIAL_REASON for table in FINANCIAL_TABLES},
    "google_play_purchases": ("obrigação fiscal e antifraude da compra Google Play; purchase_token "
                              "anulado após consumo/exclusão, google_state minimizado — 5 anos"),
    "account_deletions": ("prova da exclusão (tombstone reduzido a owner_id e data após 30 dias) "
                          "— 5 anos, prazo prescricional"),
}
GOOGLE_STATE_RETAINED_KEYS = ("purchase_state", "consumption_state", "purchase_type", "quantity")
EXPORT_SIGNED_URL_SECONDS = 300
# SPEC-222 R5: colunas explícitas (fim do select *). Colunas técnicas internas
# (leases, fencing, hashes de requisição, payload/resultado de jobs, vetores,
# purchase_token) ficam fora do export do titular.
EXPORT_COLUMNS: dict[str, tuple[str, ...]] = {
    "game_checkpoints": ("game_id", "owner_id", "game_version", "canonical_turn", "timeline_epoch",
                         "memory_commit_version", "state", "created_at"),
    "game_events": ("game_id", "owner_id", "event_id", "turn", "event_type", "payload", "source",
                    "created_at"),
    "turns": ("operation_id", "game_id", "owner_id", "sequence", "timeline_epoch", "route",
              "state_version_before", "state_version_after", "latency_ms", "llm_cost_usd",
              "presentation_entry_id"),
    "art_generations": ("generation_id", "owner_id", "game_id", "timeline_epoch", "trigger_kind",
                        "subject_type", "subject_id", "status", "model", "private_brief",
                        "asset_id", "attempt_count", "cost_usd", "error_code", "created_at",
                        "updated_at", "image_quote_id"),
    "assets": ("id", "owner_id", "game_id", "entity_id", "asset_kind", "variant", "status",
               "visibility", "object_key", "mime_type", "bytes", "width", "height", "sha256",
               "source_provider", "source_model", "created_at", "ready_at", "deleted_at"),
    "chronicle_digests": ("id", "owner_id", "game_id", "timeline_epoch", "chapter_id", "status",
                          "digest", "created_at"),
    "memory_documents": ("id", "owner_id", "game_id", "npc_id", "scope", "content", "metadata",
                         "provenance", "confidence", "source_turn", "canonical_entity_ids",
                         "visibility", "timeline_epoch", "discarded_at", "created_at"),
    "runtime_catalog": ("id", "namespace", "item_key", "scope", "owner_id", "game_id", "document",
                        "version", "provenance", "created_at", "updated_at"),
    "usage_events": ("event_id", "operation_id", "owner_id", "game_id", "component",
                     "attempt_ordinal", "category", "provider", "model", "outcome", "input_units",
                     "output_units", "cached_units", "audio_units", "image_units", "cost_usd",
                     "cost_basis", "pricing_version", "created_at", "counts_as_spend"),
    "operations": ("id", "owner_id", "game_id", "kind", "status", "committed_game_version",
                   "error_code", "started_at", "finished_at"),
    "jobs": ("id", "owner_id", "game_id", "kind", "status", "attempts", "last_error_code",
             "created_at", "updated_at"),
    "games": ("id", "owner_id", "schema_version", "version", "state", "status", "player_name",
              "class_name", "player_level", "location_name", "world_day", "game_over",
              "combat_simulation", "created_at", "updated_at", "last_action_at"),
    "image_quotes": ("quote_id", "owner_id", "game_id", "timeline_epoch", "image_type",
                     "credits_milli", "pricing_version_id", "expires_at", "model",
                     "private_brief", "trigger", "reformulation", "created_at"),
    "wallet_accounts": ("owner_id", "available_milli", "reserved_milli", "updated_at"),
    "wallet_entries": ("entry_id", "owner_id", "entry_type", "reference_type", "reference_id",
                       "reservation_id", "related_entry_id", "pricing_version_id", "sku_id",
                       "amount_milli", "available_delta", "reserved_delta", "reason",
                       "created_at"),
    "wallet_reservations": ("reservation_id", "owner_id", "reference_type", "reference_id",
                            "ceiling_milli", "settled_milli", "released_milli", "status",
                            "created_at", "finished_at"),
    "wallet_attempt_tickets": ("ticket_id", "reservation_id", "owner_id", "provider", "model",
                               "max_liability_milli", "created_at"),
    "wallet_settled_usage": ("usage_event_id", "reservation_id", "owner_id", "cost_usd",
                             "cost_basis", "pricing_version", "created_at"),
    "payment_orders": ("order_id", "owner_id", "sku_id", "pricing_version_id", "gross_cents",
                       "currency", "shard_milli", "status", "expires_at", "created_at",
                       "updated_at"),
    "wallet_debt_entries": ("debt_entry_id", "owner_id", "kind", "purchase_key", "amount_milli",
                            "debt_delta", "reference_id", "reason", "created_at"),
    "purchase_reconciliation_state": ("provider", "purchase_ref", "owner_id", "state",
                                      "target_milli", "updated_at"),
    "google_play_purchases": ("purchase_id", "owner_id", "product_id", "sku_id", "order_id",
                              "purchased_at", "google_state", "state", "voided_at", "void_reason",
                              "created_at", "updated_at"),
}
EXPORT_COLUMNS["owner_daily_counters"] = ("owner_id", "day", "class", "count", "updated_at")  # SPEC-219
EXPORT_TABLES = PRIVATE_TABLES + FINANCIAL_TABLES + ("google_play_purchases",)
# Tabelas cuja migration pode ainda nao estar aplicada quando o codigo sobe (deploy antes da
# migration): export/exclusao as pulam se ausentes em vez de quebrar a conta inteira.
OPTIONAL_TABLES = frozenset({"owner_daily_counters"})  # SPEC-219


def _present_tables(db, tables) -> tuple[str, ...]:
    missing = {t for t in tables if t in OPTIONAL_TABLES and db.execute(
        "select to_regclass(%s) as r", (f"app.{t}",)).fetchone()["r"] is None}
    return tuple(t for t in tables if t not in missing)


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
        with admin_connection(self.pool) as db, db.transaction():
            # Coordinate deletion/private writes; no caller-selected owner or auth rows.
            db.execute("select pg_advisory_xact_lock(hashtextextended(%s,190))", (str(principal.user_id),))
            if db.execute("select 1 from app.account_deletions where owner_id=%s", (principal.user_id,)).fetchone():
                raise Unauthorized("account_deleted")
            data = {table: db.execute(
                        f"select {', '.join(EXPORT_COLUMNS[table])} from app.{table} where owner_id=%s",
                        (principal.user_id,)).fetchall()
                    for table in _present_tables(db, EXPORT_TABLES)}
            data["payment_financial_events"] = db.execute("""select f.financial_id,f.order_id,f.kind,
                f.amount_cents,f.currency,f.outcome,f.created_at from app.payment_financial_events f
                join app.payment_orders o on o.order_id=f.order_id where o.owner_id=%s""",
                (principal.user_id,)).fetchall()
        return {"format_version": 2, "owner_id": str(principal.user_id), "data": data,
                "asset_downloads": self._asset_downloads(principal, data["assets"])}

    def _asset_downloads(self, principal: Principal, assets: list) -> list[dict]:
        """SPEC-222 R5 (D-A): URLs assinadas curtas p/ os arquivos do titular (ZIP fica p/ spec futura)."""
        prefix = f"users/{principal.user_id}/"
        downloads = []
        for row in assets:
            key = row["object_key"]
            if row["status"] != "ready" or not key.startswith(prefix):
                continue
            try:
                url = self.blobs.signed_url(key, EXPORT_SIGNED_URL_SECONDS)
            except Exception:  # Storage indisponível: o export segue com os metadados.
                url = None
            downloads.append({"asset_id": str(row["id"]), "object_key": key, "url": url,
                              "expires_in_seconds": EXPORT_SIGNED_URL_SECONDS})
        return downloads

    def begin(self, owner: UUID) -> None:
        with admin_connection(self.pool) as db, db.transaction():
            db.execute("select pg_advisory_xact_lock(hashtextextended(%s,190))", (str(owner),))
            if db.execute("select 1 from app.account_deletions where owner_id=%s", (owner,)).fetchone():
                return
            from services.account_security import auth_email_bucket_keys, auth_email_bucket_prefixes
            email = db.execute("select app.runtime_auth_email(%s) as email", (owner,)).fetchone()["email"]
            if email:
                db.execute("""delete from app.rate_limit_buckets where bucket_key=any(%s)
                    or exists (select 1 from unnest(%s::text[]) p(prefix)
                               where starts_with(bucket_key, p.prefix))""",
                           (list(auth_email_bucket_keys(email)), list(auth_email_bucket_prefixes(email))))
            prefix = f"users/{owner}/"
            keys = {row["name"] for row in db.execute("""select name from storage.objects
                where bucket_id=%s and starts_with(name,%s)""", (self.blobs.bucket, prefix)).fetchall()}
            keys.update(row["object_key"] for row in db.execute(
                "select object_key from app.assets where owner_id=%s", (owner,)).fetchall()
                        if row["object_key"].startswith(prefix))
            # Global auth revocation is authoritative before private cleanup begins.
            db.execute("select app.runtime_revoke_auth(%s)", (owner,))
            # Fence queued AND leased work before tombstone triggers deny later writes.
            db.execute("""update app.jobs set status='cancelled',lease_token=null,lease_owner=null,
                lease_until=null,payload='{}',result=null,last_error_code='account_deleted',updated_at=now()
                where owner_id=%s""", (owner,))
            # SPEC-222 R4: retained Play rows keep only financial facts. Runs before the
            # tombstone because the account write fence denies later updates. Skipped (deploy
            # safety) until migration 20261016120000 exists; the migration backfills deleted owners.
            if db.execute("select to_regproc('app.minimize_google_state') as f").fetchone()["f"]:
                db.execute("""update app.google_play_purchases set purchase_token=null,
                google_state=app.minimize_google_state(google_state),updated_at=now()
                where owner_id=%s and (purchase_token is not null
                  or google_state is distinct from app.minimize_google_state(google_state))""", (owner,))
            db.execute("""insert into app.account_deletions(owner_id,blob_keys,sessions_revoked_at)
                values (%s,%s,now())""", (owner, sorted(keys)))

    def finish(self, owner: UUID) -> str:
        with admin_connection(self.pool) as db:
            row = db.execute("select * from app.account_deletions where owner_id=%s", (owner,)).fetchone()
        if not row:
            raise Unauthorized("account_delete_not_requested")
        if row["status"] == "deleted":
            return "deleted"
        # A previously issued Checkout link remains payable even after we clear
        # its DB URL. Close every provider session before final account removal.
        with admin_connection(self.pool) as db:
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
        with admin_connection(self.pool) as db:
            extra = db.execute("select name from storage.objects where bucket_id=%s and starts_with(name,%s)",
                               (self.blobs.bucket, f"users/{owner}/")).fetchall()
        keys = set(row["blob_keys"]) | {item["name"] for item in extra}
        blobs_deleted = True
        for key in keys:
            if not key.startswith(f"users/{owner}/"):
                raise Unauthorized("invalid_blob_owner")
            if not self.blobs.delete(key):
                blobs_deleted = False
        with admin_connection(self.pool) as db, db.transaction():
            db.execute("select pg_advisory_xact_lock(hashtextextended(%s,190))", (str(owner),))
            # Each explicit predicate uses only the owner authenticated before revocation.
            for table in _present_tables(db, PRIVATE_TABLES):
                db.execute(f"delete from app.{table} where owner_id=%s", (owner,))
            # A retained financial row contains opaque IDs/numbers, no private prompt/data.
            db.execute("update app.payment_orders set checkout_url=null where owner_id=%s", (owner,))
        self.identity.delete_user(owner)
        if not (checkouts_closed and blobs_deleted):
            return "deleting"
        with admin_connection(self.pool) as db:
            db.execute("""update app.account_deletions set status='deleted',blob_keys='{}',completed_at=now()
                where owner_id=%s""", (owner,))
        return "deleted"

    def delete(self, owner: UUID) -> str:
        self.begin(owner)
        return self.finish(owner)
