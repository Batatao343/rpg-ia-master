"""Append-only usage ledger writer, called inside the operation transaction."""

from __future__ import annotations

from collections.abc import Sequence
from hashlib import sha256
import json
from uuid import UUID

from infrastructure.contracts import Conflict
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
    for event in events:
        if event.operation_id != operation_id:
            raise Conflict("usage operation_id divergiu")
        digest = _event_digest(event)
        row = connection.execute(
            """insert into app.usage_events
              (event_id,operation_id,owner_id,game_id,component,attempt_ordinal,
               category,provider,model,outcome,input_units,output_units,cached_units,
               audio_units,image_units,cost_usd,cost_basis,pricing_version,
               billing_exact,event_sha256)
            values (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
            on conflict (operation_id,component,attempt_ordinal) do nothing
            returning event_sha256""",
            (
                event.event_id, event.operation_id, owner_id, game_id,
                event.component, event.attempt_ordinal, event.category,
                event.provider, event.model, event.outcome, event.input_units,
                event.output_units, event.cached_units, event.audio_units,
                event.image_units, event.cost_usd, event.cost_basis,
                event.pricing_version, event.billing_exact, digest,
            ),
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


def _append_job_attempt(pool, job, attempts: Sequence[dict], *, job_kind: str,
                        operation_kind: str, category: str) -> None:
    if not attempts:
        return
    from infrastructure.postgres_jobs import PostgresJobQueue
    from services.usage_metering import normalize_attempts

    with pool.connection() as connection, connection.transaction():
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
