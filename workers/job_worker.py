"""Loop síncrono de jobs tipados com shutdown gracioso."""

from __future__ import annotations

import threading
from collections.abc import Callable
from typing import Any

from infrastructure.contracts import JobDeferred, JobQueue, LeasedJob, LeaseHeld
from services.lease_heartbeat import keep_lease_alive
from services.job_fence import job_scope


JobHandler = Callable[[dict[str, Any]], dict[str, Any]]


class JobWorker:
    def __init__(self, queue: JobQueue, handlers: dict[str, JobHandler], *, worker_id: str) -> None:
        self.queue = queue
        self.handlers = dict(handlers)
        self.worker_id = worker_id
        self.stop_event = threading.Event()

    def run_once(self, *, limit: int = 10) -> int:
        if self.stop_event.is_set() or limit <= 0:
            return 0
        jobs = self.queue.lease(self.worker_id, set(self.handlers), 1)
        for job in jobs:
            self._run(job)
        return len(jobs)

    def run_leased(self, job: LeasedJob) -> None:
        """Executa um job já arrendado por quem chama (SPEC-213: o dono do turno
        roda o próprio outbox logo após responder), com o mesmo ciclo de fence."""
        self._run(job)

    def _run(self, job: LeasedJob) -> None:
        from observability.telemetry import span

        handler = self.handlers.get(job.request.kind)
        try:
            renew = getattr(self.queue, "heartbeat", None)
            with keep_lease_alive(
                (lambda: renew(job.job_id, job.lease_token)) if renew else None,
                interval_seconds=float(getattr(self.queue, "lease_seconds", 90)) / 4,
            ) as lease:
                if handler is None:
                    raise ValueError("unknown_job_kind")
                with job_scope(job), span("job.run", kind=job.request.kind, attempt=job.attempt):
                    result = handler(job.request.payload)
                lease.check()
            self.queue.complete(job.job_id, job.lease_token, result)
        except LeaseHeld:
            return  # New owner's fence controls publication, never fail its job.
        except JobDeferred as exc:
            defer = getattr(self.queue, "defer", None)
            try:
                if defer is not None:
                    defer(job.job_id, job.lease_token, exc.delay_seconds, str(exc.reason))
                else:
                    self.queue.fail(job.job_id, job.lease_token, str(exc.reason)[:100])
            except LeaseHeld:
                pass
            return
        except Exception as exc:
            code = getattr(exc, "error_code", "handler_error")
            try:
                self.queue.fail(job.job_id, job.lease_token, str(code)[:100])
            except LeaseHeld:
                pass
            return

    def request_stop(self) -> None:
        self.stop_event.set()
