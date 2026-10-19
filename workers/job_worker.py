"""Loop síncrono de jobs tipados com shutdown gracioso."""

from __future__ import annotations

import threading
import time
from collections import Counter
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
        self.stats: Counter[str] = Counter()     # SPEC-255 R4: completed/failed/dead/deferred/lease_lost

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
        """SPEC-255 R2: o job roda dentro da correlacao do request que o criou."""
        from observability.telemetry import correlation_scope, pseudonym
        trace = job.request.trace or {}
        with correlation_scope(job_ref=pseudonym(job.job_id), job_kind=job.request.kind,
                               request_id=trace.get("request_id"),
                               action_ref=trace.get("action_ref")):
            self._run_scoped(job)

    def _run_scoped(self, job: LeasedJob) -> None:
        from observability.telemetry import log_event, span

        kind, attempt = job.request.kind, int(job.attempt)
        started = time.monotonic()
        log_event("job", "started", level="debug", kind=kind, attempt=attempt)
        handler = self.handlers.get(kind)
        try:
            renew = getattr(self.queue, "heartbeat", None)
            with keep_lease_alive(
                (lambda: renew(job.job_id, job.lease_token)) if renew else None,
                interval_seconds=float(getattr(self.queue, "lease_seconds", 90)) / 4,
            ) as lease:
                if handler is None:
                    raise ValueError("unknown_job_kind")
                with job_scope(job), span("job.run", kind=kind, attempt=attempt):
                    result = handler(job.request.payload)
                lease.check()
            self.queue.complete(job.job_id, job.lease_token, result)
            self.stats["completed"] += 1
            log_event("job", "completed", kind=kind, attempt=attempt,
                      duration_ms=int((time.monotonic() - started) * 1000))
        except LeaseHeld:
            self.stats["lease_lost"] += 1
            log_event("job", "lease_lost", level="warning", kind=kind, attempt=attempt)
            return  # New owner's fence controls publication, never fail its job.
        except JobDeferred as exc:
            defer = getattr(self.queue, "defer", None)
            try:
                if defer is not None:
                    defer(job.job_id, job.lease_token, exc.delay_seconds, str(exc.reason))
                else:
                    self.queue.fail(job.job_id, job.lease_token, str(exc.reason)[:100])
                self.stats["deferred"] += 1
                log_event("job", "deferred", kind=kind, attempt=attempt, reason=str(exc.reason)[:60],
                          delay_s=int(exc.delay_seconds))
            except LeaseHeld:
                self.stats["lease_lost"] += 1
                log_event("job", "lease_lost", level="warning", kind=kind, attempt=attempt)
            return
        except Exception as exc:
            # SPEC-255 R3: nunca so "handler_error" — a classe da excecao vai no codigo.
            code = str(getattr(exc, "error_code", None) or f"exc:{type(exc).__name__}")[:100]
            outcome: Any = None
            try:
                outcome = self.queue.fail(job.job_id, job.lease_token, code)
            except LeaseHeld:
                self.stats["lease_lost"] += 1
                log_event("job", "lease_lost", level="warning", kind=kind, attempt=attempt)
                return
            status = (outcome or {}).get("status") if isinstance(outcome, dict) else None
            if status is None:
                status = "dead" if attempt >= int(job.request.max_attempts) else "retry"
            self.stats["failed"] += 1
            log_event("job", "failed", level="warning", kind=kind, attempt=attempt,
                      error_type=type(exc).__name__, error_code=code, will_retry=status == "retry",
                      next_run_in_s=int((outcome or {}).get("next_run_in_s", 0)) if isinstance(outcome, dict) else 0)
            if status == "dead":
                self.stats["dead"] += 1
                log_event("job", "dead", level="error", kind=kind, attempt=attempt,
                          reason="max_attempts", error_code=code)
            return

    def request_stop(self) -> None:
        self.stop_event.set()
