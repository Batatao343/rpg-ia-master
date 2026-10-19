"""Fila Postgres com dedupe, SKIP LOCKED, fencing e retry/dead-letter."""

from __future__ import annotations

import hashlib
from contextlib import nullcontext
from datetime import timedelta
from typing import Any
from uuid import UUID, uuid4

from psycopg.types.json import Jsonb

from infrastructure.contracts import JobRequest, LeasedJob, LeaseHeld, NotFound
from infrastructure.db_log import conflict as _db_conflict
from infrastructure.db_log import timed_call as _timed
from infrastructure.db_roles import admin_connection
from infrastructure.postgres import PostgresPool

# SPEC-236 R9: a dead/cancelled job for a document that is still pending is revived on the next
# enqueue of the same (kind, dedupe_key), but at most once per cooldown so an automatic
# re-enqueue on every turn cannot turn a persistent failure back into a paid retry loop.
# Sol review: the wait is max(cooldown, age the job had when it died), so it doubles per revival
# (~15 min, 30 min, 1 h, 2 h, ...) instead of buying max_attempts paid calls every 15 min forever.
DEAD_JOB_REVIVE_COOLDOWN = timedelta(minutes=15)


def revive_dead_job(
    connection, kind: str, dedupe_key: str, cooldown: timedelta = DEAD_JOB_REVIVE_COOLDOWN
) -> bool:
    """Requeue a dead/cancelled job with fresh attempts; True when one was revived."""
    result = connection.execute(
        """
        update app.jobs set status='queued', attempts=0, available_at=now(),
          last_error_code=null, lease_token=null, lease_owner=null, lease_until=null,
          updated_at=now()
        where kind=%s and dedupe_key=%s and status in ('dead','cancelled')
          and updated_at <= now() - greatest(%s::interval, updated_at - created_at)
        """,
        (kind, dedupe_key, cooldown),
    )
    return result.rowcount == 1


_TRACE_KEYS = ("request_id", "action_ref")


def _current_trace() -> dict[str, str] | None:
    """SPEC-255 R1: correlacao do request atual (somente ids; nunca conteudo)."""
    from observability.telemetry import correlation

    current = correlation()
    trace = {key: current[key] for key in _TRACE_KEYS if current.get(key)}
    return trace or None


def _split_trace(payload: dict[str, Any] | None) -> tuple[dict[str, Any], dict[str, str] | None]:
    """Separa ``_trace`` do payload do handler (jobs antigos nao o tem)."""
    data = dict(payload or {})
    raw = data.pop("_trace", None)
    trace = (
        {key: str(raw[key])[:128] for key in _TRACE_KEYS if isinstance(raw, dict) and raw.get(key)}
        if isinstance(raw, dict)
        else None
    )
    return data, (trace or None)


def _job_ref(job_id: Any) -> str:
    from observability.telemetry import pseudonym

    return pseudonym(job_id)


def _request_from_row(row: dict[str, Any]) -> JobRequest:
    payload, trace = _split_trace(row["payload"])
    return JobRequest(
        kind=row["kind"],
        dedupe_key=row["dedupe_key"],
        payload=payload,
        owner_id=row["owner_id"],
        game_id=row["game_id"],
        max_attempts=row["max_attempts"],
        trace=trace,
    )


def _log_dead(job_id: Any, reason: str) -> None:
    from observability.telemetry import log_event

    log_event("job", "dead", level="error", job_ref=_job_ref(job_id), reason=reason)


class PostgresJobQueue:
    def __init__(self, pool: PostgresPool, *, lease_seconds: int = 90) -> None:
        if lease_seconds <= 0:
            raise ValueError("lease_seconds precisa ser positivo")
        self.pool = pool
        self.lease_seconds = lease_seconds

    @_timed("job.enqueue")
    def enqueue(self, job: JobRequest, connection=None) -> UUID:
        job_id = uuid4()
        trace = job.trace or _current_trace()
        stored_payload = {**job.payload, "_trace": trace} if trace else job.payload
        scope = self.pool.connection() if connection is None else nullcontext(connection)
        with scope as connection, connection.transaction():
            row = connection.execute(
                """
                insert into app.jobs
                  (id,owner_id,game_id,kind,dedupe_key,status,payload,max_attempts)
                values (%s,%s,%s,%s,%s,'queued',%s,%s)
                on conflict (kind,dedupe_key) do update
                  set dedupe_key=excluded.dedupe_key
                returning id
                """,
                (
                    job_id,
                    job.owner_id,
                    job.game_id,
                    job.kind,
                    job.dedupe_key,
                    Jsonb(stored_payload),
                    job.max_attempts,
                ),
            ).fetchone()
            return row["id"]

    @_timed("job.lease")
    def lease(self, worker_id: str, kinds: set[str], limit: int) -> list[LeasedJob]:
        if not worker_id or not kinds or limit <= 0:
            return []
        lease_token = uuid4()
        interval = timedelta(seconds=self.lease_seconds)
        with admin_connection(self.pool) as connection, connection.transaction():
            # SPEC-236 R9: a handler that keeps killing its process (timeout/OOM) used to be
            # re-leased forever. Expired leases that already spent max_attempts go dead instead.
            dead_rows = connection.execute(
                """
                with poisoned as (
                  select id from app.jobs
                  where kind = any(%s) and status='running' and lease_until < now()
                    and attempts >= max_attempts
                  for update skip locked
                )
                update app.jobs j set status='dead',
                  last_error_code='lease_expired_max_attempts', lease_token=null,
                  lease_owner=null, lease_until=null, updated_at=now()
                from poisoned where j.id=poisoned.id
                returning j.id
                """,
                (list(kinds),),
            ).fetchall()
            for dead_row in dead_rows:  # SPEC-255 R5: antes so existia em SQL
                _log_dead(dead_row["id"], "lease_expired_max_attempts")
            rows = connection.execute(
                """
                with picked as (
                  select id from app.jobs
                  where kind = any(%s)
                    and (
                      (status in ('queued','retry') and available_at <= now()) or
                      (status='running' and lease_until < now() and attempts < max_attempts)
                    )
                  order by available_at, created_at, id
                  limit %s
                  for update skip locked
                )
                update app.jobs j set
                  status='running', attempts=j.attempts+1, lease_token=%s,
                  lease_owner=%s, lease_until=now()+%s,
                  updated_at=now()
                from picked where j.id=picked.id
                returning j.*
                """,
                (list(kinds), limit, lease_token, worker_id, interval),
            ).fetchall()
        return [
            LeasedJob(
                job_id=row["id"],
                lease_token=row["lease_token"],
                request=_request_from_row(row),
                attempt=row["attempts"],
            )
            for row in rows
        ]

    @_timed("job.lease_key")
    def lease_key(self, worker_id: str, kind: str, dedupe_key: str) -> LeasedJob | None:
        """SPEC-213: o dono do turno executa o PRÓPRIO job do outbox logo após a
        resposta (modo A em perfil DB), sob o mesmo lease/fencing da fila."""
        lease_token = uuid4()
        interval = timedelta(seconds=self.lease_seconds)
        with admin_connection(self.pool) as connection, connection.transaction():
            row = connection.execute(
                """
                update app.jobs j set
                  status='running', attempts=j.attempts+1, lease_token=%s,
                  lease_owner=%s, lease_until=now()+%s, updated_at=now()
                where j.id = (
                  select id from app.jobs where kind=%s and dedupe_key=%s
                    and status in ('queued','retry')
                  for update skip locked)
                returning j.*
                """,
                (lease_token, worker_id, interval, kind, dedupe_key),
            ).fetchone()
        if not row:
            return None
        return LeasedJob(
            job_id=row["id"],
            lease_token=row["lease_token"],
            request=_request_from_row(row),
            attempt=row["attempts"],
        )

    def status(self, kind: str, dedupe_key: str) -> dict[str, Any] | None:
        with admin_connection(self.pool) as connection:
            return connection.execute(
                """select status, coalesce(lease_until > now(), false) as leased
                from app.jobs where kind=%s and dedupe_key=%s""",
                (kind, dedupe_key),
            ).fetchone()

    @staticmethod
    def _require_running(connection, job_id: UUID, lease_token: UUID) -> dict[str, Any]:
        row = connection.execute(
            "select * from app.jobs where id=%s for update",
            (job_id,),
        ).fetchone()
        if not row:
            raise NotFound("job não encontrado")
        if row["status"] != "running" or row["lease_token"] != lease_token:
            _db_conflict("lease_conflict", "job_fence_invalid", op_kind="job", operation_id=job_id)
            raise LeaseHeld("fencing token do job divergiu")
        return row

    @_timed("job.heartbeat")
    def heartbeat(self, job_id: UUID, lease_token: UUID) -> None:
        interval = timedelta(seconds=self.lease_seconds)
        with admin_connection(self.pool) as connection, connection.transaction():
            self._require_running(connection, job_id, lease_token)
            connection.execute(
                "update app.jobs set lease_until=now()+%s,updated_at=now() where id=%s",
                (interval, job_id),
            )

    @_timed("job.complete")
    def complete(self, job_id: UUID, lease_token: UUID, result: dict[str, Any]) -> None:
        with admin_connection(self.pool) as connection, connection.transaction():
            self._require_running(connection, job_id, lease_token)
            connection.execute(
                """
                update app.jobs set status='succeeded',result=%s,lease_token=null,
                  lease_owner=null,lease_until=null,updated_at=now() where id=%s
                """,
                (Jsonb(result), job_id),
            )

    @_timed("job.fail")
    def fail(self, job_id: UUID, lease_token: UUID, error_code: str) -> dict[str, Any]:
        """Devolve ``{status: retry|dead, next_run_in_s}`` (SPEC-255: o worker loga o resultado)."""
        with admin_connection(self.pool) as connection, connection.transaction():
            row = self._require_running(connection, job_id, lease_token)
            terminal = int(row["attempts"]) >= int(row["max_attempts"])
            status = "dead" if terminal else "retry"
            seconds = min(300, 2 ** min(int(row["attempts"]), 8))
            jitter = int(hashlib.sha256(str(job_id).encode()).hexdigest()[:2], 16) % 4
            connection.execute(
                """
                update app.jobs set status=%s,last_error_code=%s,lease_token=null,
                  lease_owner=null,lease_until=null,available_at=now()+%s,
                  updated_at=now() where id=%s
                """,
                (status, error_code[:100], timedelta(seconds=seconds + jitter), job_id),
            )
        return {"status": status, "next_run_in_s": 0 if terminal else seconds + jitter}

    @_timed("job.defer")
    def defer(self, job_id: UUID, lease_token: UUID, delay_seconds: float, reason: str) -> None:
        """Back to 'queued' for later WITHOUT burning the attempt (kill-switch pause, not failure)."""
        with admin_connection(self.pool) as connection, connection.transaction():
            self._require_running(connection, job_id, lease_token)
            connection.execute(
                """
                update app.jobs set status='queued',attempts=greatest(attempts-1,0),
                  last_error_code=%s,lease_token=null,lease_owner=null,lease_until=null,
                  available_at=now()+%s,updated_at=now() where id=%s
                """,
                (reason[:100], timedelta(seconds=max(1.0, delay_seconds)), job_id),
            )

    @_timed("job.cancel")
    def cancel(self, job_id: UUID) -> bool:
        with admin_connection(self.pool) as connection, connection.transaction():
            result = connection.execute(
                """
                update app.jobs set status='cancelled',updated_at=now()
                where id=%s and status in ('queued','retry')
                """,
                (job_id,),
            )
            return result.rowcount == 1
