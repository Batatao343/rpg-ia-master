"""Append-only usage ledger writer, called inside the operation transaction."""

from __future__ import annotations

import json
from collections.abc import Sequence
from decimal import Decimal
from hashlib import sha256
from uuid import UUID

from infrastructure.contracts import Conflict
from infrastructure.db_roles import admin_connection
from services.usage_metering import UsageEvent


def _event_digest(event: UsageEvent) -> str:
    fields = {
        "event_id": str(event.event_id),
        "operation_id": str(event.operation_id),
        "component": event.component,
        "attempt_ordinal": event.attempt_ordinal,
        "category": event.category,
        "provider": event.provider,
        "model": event.model,
        "outcome": event.outcome,
        "input_units": event.input_units,
        "output_units": event.output_units,
        "cached_units": event.cached_units,
        "audio_units": event.audio_units,
        "image_units": event.image_units,
        "cost_usd": str(event.cost_usd),
        "cost_basis": event.cost_basis,
        "pricing_version": event.pricing_version,
        "billing_exact": event.billing_exact,
    }
    encoded = json.dumps(fields, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return sha256(encoded).hexdigest()


# SPEC-236 (Sol review): this code may be deployed before migration 20261017100000. Writers
# and readers probe the catalog and degrade to the legacy schema instead of failing every turn.
# A present column is cached for the process lifetime; absence is re-probed on each call.
_COLUMNS_SEEN: set[tuple[str, str]] = set()


def has_column(connection, table: str, column: str) -> bool:
    key = (table, column)
    if key in _COLUMNS_SEEN:
        return True
    row = connection.execute(
        "select 1 as present from pg_catalog.pg_attribute where attrelid=to_regclass(%s) "
        "and attname=%s and attnum>0 and not attisdropped", (table, column),
    ).fetchone()
    if row is not None:
        _COLUMNS_SEEN.add(key)
    return row is not None


def spend_schema_ready(connection) -> bool:
    return has_column(connection, "app.usage_events", "counts_as_spend")


def _legacy_shape(event: UsageEvent) -> UsageEvent:
    """Pre-migration CHECK only knows four bases: a no-spend fact becomes a zero-cost,
    non-exact estimate (never US$ 1, never settleable)."""
    from dataclasses import replace
    if event.counts_as_spend:
        return event
    return replace(event, cost_usd=Decimal("0"), cost_basis="estimated", billing_exact=False)


def append_usage_events(connection, *, owner_id: UUID, operation_id: UUID,
                        game_id: UUID | None, events: Sequence[UsageEvent]) -> None:
    """Insert facts exactly once; reject same logical attempt with changed facts."""
    if not events:
        return
    operation = connection.execute(
        "select owner_id,game_id from app.operations where id=%s for update",
        (operation_id,),
    ).fetchone()
    if (operation is None or operation["owner_id"] != owner_id
            or operation["game_id"] != game_id):
        raise Conflict("usage attribution divergiu")
    ready = spend_schema_ready(connection)
    for event in events:
        if event.operation_id != operation_id:
            raise Conflict("usage operation_id divergiu")
        digest = _event_digest(event)
        # Pre-migration: legacy column list and CHECK. The digest stays the canonical event's
        # so replays across the migration boundary agree.
        stored = event if ready else _legacy_shape(event)
        spend_column = ",counts_as_spend" if ready else ""
        values = ",".join(["%s"] * (21 if ready else 20))
        params = [
            stored.event_id, stored.operation_id, owner_id, game_id,
            stored.component, stored.attempt_ordinal, stored.category,
            stored.provider, stored.model, stored.outcome, stored.input_units,
            stored.output_units, stored.cached_units, stored.audio_units,
            stored.image_units, stored.cost_usd, stored.cost_basis,
            stored.pricing_version, stored.billing_exact, digest,
        ]
        if ready:
            params.append(stored.counts_as_spend)
        row = connection.execute(
            f"""insert into app.usage_events
              (event_id,operation_id,owner_id,game_id,component,attempt_ordinal,
               category,provider,model,outcome,input_units,output_units,cached_units,
               audio_units,image_units,cost_usd,cost_basis,pricing_version,
               billing_exact,event_sha256{spend_column})
            values ({values})
            on conflict (operation_id,component,attempt_ordinal) do nothing
            returning event_sha256""",
            tuple(params),
        ).fetchone()
        if row is not None:
            continue
        existing = connection.execute(
            """select event_sha256 from app.usage_events
            where operation_id=%s and component=%s and attempt_ordinal=%s""",
            (operation_id, event.component, event.attempt_ordinal),
        ).fetchone()
        if not existing or existing["event_sha256"] != digest:
            raise Conflict("usage replay divergiu")


def append_embedding_job_attempt(pool, job, attempts: Sequence[dict]) -> None:
    """Record each provider response under a fenced embedding job operation."""
    _append_job_attempt(pool, job, attempts, job_kind="embed_memory",
                        operation_kind="embedding", category="embedding")


def append_chronicle_job_attempt(pool, job, attempts: Sequence[dict]) -> None:
    """Record SMART compression calls, including fallback and retry attempts."""
    _append_job_attempt(pool, job, attempts, job_kind="compress_chronicle",
                        operation_kind="chronicle_compress", category="llm")


def append_projection_job_attempt(pool, job, attempts: Sequence[dict]) -> None:
    """SPEC-213: chamadas SMART da projeção adiada do arquivista (modo B/A-DB)."""
    _append_job_attempt(pool, job, attempts, job_kind="project_archive",
                        operation_kind="archive_projection", category="llm")


def _append_job_attempt(pool, job, attempts: Sequence[dict], *, job_kind: str,
                        operation_kind: str, category: str) -> None:
    if not attempts:
        return
    from infrastructure.postgres_jobs import PostgresJobQueue
    from services.usage_metering import normalize_attempts

    with admin_connection(pool) as connection, connection.transaction():
        row = PostgresJobQueue._require_running(
            connection, job.job_id, job.lease_token)
        if row["kind"] != job_kind or row["owner_id"] is None:
            raise Conflict("job de usage sem owner")
        request_hash = sha256(
            f"{operation_kind}:{job.job_id}:{row['dedupe_key']}".encode("utf-8")
        ).hexdigest()
        connection.execute(
            """insert into app.operations
              (id,owner_id,game_id,kind,status,request_sha256,finished_at)
            values (%s,%s,%s,%s,'completed',%s,now())
            on conflict (id) do nothing""",
            (job.job_id, row["owner_id"], row["game_id"], operation_kind, request_hash),
        )
        operation = connection.execute(
            """select kind,request_sha256 from app.operations
            where id=%s and owner_id=%s and game_id is not distinct from %s""",
            (job.job_id, row["owner_id"], row["game_id"]),
        ).fetchone()
        if (not operation or operation["kind"] != operation_kind
                or operation["request_sha256"] != request_hash):
            raise Conflict("operação de usage divergiu")
        events = normalize_attempts(
            attempts, operation_id=job.job_id,
            component=f"{category}:{job.attempt}", category=category,
        )
        append_usage_events(
            connection, owner_id=row["owner_id"],
            operation_id=job.job_id, game_id=row["game_id"],
            events=events[-1:],
        )
