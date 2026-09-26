"""Fila Postgres com dedupe, SKIP LOCKED, fencing e retry/dead-letter."""

from __future__ import annotations

from contextlib import nullcontext

import hashlib
from datetime import timedelta
from typing import Any
from uuid import UUID, uuid4

from psycopg.types.json import Jsonb

from infrastructure.contracts import JobRequest, LeaseHeld, LeasedJob, NotFound
from infrastructure.postgres import PostgresPool


class PostgresJobQueue:
    def __init__(self, pool: PostgresPool, *, lease_seconds: int = 90) -> None:
        if lease_seconds <= 0:
            raise ValueError("lease_seconds precisa ser positivo")
        self.pool = pool
        self.lease_seconds = lease_seconds

    def enqueue(self, job: JobRequest, connection=None) -> UUID:
        job_id = uuid4()
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
                    job_id, job.owner_id, job.game_id, job.kind, job.dedupe_key,
                    Jsonb(job.payload), job.max_attempts,
                ),
            ).fetchone()
            return row["id"]

    def lease(self, worker_id: str, kinds: set[str], limit: int) -> list[LeasedJob]:
        if not worker_id or not kinds or limit <= 0:
            return []
        lease_token = uuid4()
        interval = timedelta(seconds=self.lease_seconds)
        with self.pool.connection() as connection, connection.transaction():
            rows = connection.execute(
                """
                with picked as (
                  select id from app.jobs
                  where kind = any(%s)
                    and (
                      (status in ('queued','retry') and available_at <= now()) or
                      (status='running' and lease_until < now())
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
                request=JobRequest(
                    kind=row["kind"], dedupe_key=row["dedupe_key"],
                    payload=row["payload"], owner_id=row["owner_id"],
                    game_id=row["game_id"], max_attempts=row["max_attempts"],
                ),
                attempt=row["attempts"],
            )
            for row in rows
        ]

    @staticmethod
    def _require_running(connection, job_id: UUID, lease_token: UUID) -> dict[str, Any]:
        row = connection.execute(
            "select * from app.jobs where id=%s for update", (job_id,),
        ).fetchone()
        if not row:
            raise NotFound("job não encontrado")
        if row["status"] != "running" or row["lease_token"] != lease_token:
            raise LeaseHeld("fencing token do job divergiu")
        return row

    def heartbeat(self, job_id: UUID, lease_token: UUID) -> None:
        interval = timedelta(seconds=self.lease_seconds)
        with self.pool.connection() as connection, connection.transaction():
            self._require_running(connection, job_id, lease_token)
            connection.execute(
                "update app.jobs set lease_until=now()+%s,updated_at=now() where id=%s",
                (interval, job_id),
            )

    def complete(self, job_id: UUID, lease_token: UUID, result: dict[str, Any]) -> None:
        with self.pool.connection() as connection, connection.transaction():
            self._require_running(connection, job_id, lease_token)
            connection.execute(
                """
                update app.jobs set status='succeeded',result=%s,lease_token=null,
                  lease_owner=null,lease_until=null,updated_at=now() where id=%s
                """,
                (Jsonb(result), job_id),
            )

    def fail(self, job_id: UUID, lease_token: UUID, error_code: str) -> None:
        with self.pool.connection() as connection, connection.transaction():
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

    def cancel(self, job_id: UUID) -> bool:
        with self.pool.connection() as connection, connection.transaction():
            result = connection.execute(
                """
                update app.jobs set status='cancelled',updated_at=now()
                where id=%s and status in ('queued','retry')
                """,
                (job_id,),
            )
            return result.rowcount == 1
