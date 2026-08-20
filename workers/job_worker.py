"""Loop síncrono de jobs tipados com shutdown gracioso."""

from __future__ import annotations

import threading
from collections.abc import Callable
from typing import Any

from infrastructure.contracts import JobQueue, LeasedJob


JobHandler = Callable[[dict[str, Any]], dict[str, Any]]


class JobWorker:
    def __init__(self, queue: JobQueue, handlers: dict[str, JobHandler], *, worker_id: str) -> None:
        self.queue = queue
        self.handlers = dict(handlers)
        self.worker_id = worker_id
        self.stop_event = threading.Event()

    def run_once(self, *, limit: int = 10) -> int:
        jobs = self.queue.lease(self.worker_id, set(self.handlers), limit)
        for job in jobs:
            self._run(job)
        return len(jobs)

    def _run(self, job: LeasedJob) -> None:
        from observability.telemetry import span

        handler = self.handlers.get(job.request.kind)
        if handler is None:
            self.queue.fail(job.job_id, job.lease_token, "unknown_job_kind")
            return
        try:
            with span("job.run", kind=job.request.kind, attempt=job.attempt):
                result = handler(job.request.payload)
        except Exception as exc:
            code = getattr(exc, "error_code", "handler_error")
            self.queue.fail(job.job_id, job.lease_token, str(code)[:100])
            return
        self.queue.complete(job.job_id, job.lease_token, result)

    def request_stop(self) -> None:
        self.stop_event.set()
