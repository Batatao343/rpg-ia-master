"""Time-boxed job drain for serverless schedulers (SPEC-192).

Reuses JobWorker/JobQueue unchanged, so Postgres leases, heartbeat and fencing
keep guarding every job; this only bounds *how long* we keep leasing.
"""

from __future__ import annotations

import time
from collections.abc import Callable
from typing import Any

# A job may take up to a lease window; never start one without this much time left.
MIN_JOB_WINDOW_S = 15.0
SAFETY_MARGIN_S = 3.0


def drain_jobs(
    deadline_s: float,
    max_jobs: int,
    worker_id: str,
    *,
    worker: Any | None = None,
    clock: Callable[[], float] = time.monotonic,
    min_job_window_s: float = MIN_JOB_WINDOW_S,
    safety_margin_s: float = SAFETY_MARGIN_S,
) -> dict[str, Any]:
    """Run jobs until the queue is empty, ``max_jobs`` reached or time budget exhausted.

    ``deadline_s`` is the total budget in seconds from now.
    """
    started = clock()
    stop_at = started + deadline_s - safety_margin_s
    if worker is None:
        from infrastructure.runtime import get_runtime
        from workers.job_worker import JobWorker
        from workers.run_worker import build_handlers

        worker = JobWorker(get_runtime().job_queue, build_handlers(), worker_id=worker_id)
    processed = 0
    reason = "empty"
    before = dict(getattr(worker, "stats", None) or {})
    while True:
        if processed >= max_jobs:
            reason = "max_jobs"
            break
        if stop_at - clock() < min_job_window_s:
            reason = "deadline"
            break
        if worker.run_once(limit=1) == 0:
            reason = "empty"
            break
        processed += 1
    after = dict(getattr(worker, "stats", None) or {})

    def delta(key: str) -> int:  # SPEC-255 R4: o cron deriva o outcome daqui
        return int(after.get(key, 0)) - int(before.get(key, 0))

    return {
        "processed": processed,
        "stopped_reason": reason,
        "elapsed_s": round(clock() - started, 3),
        "failed": delta("failed"),
        "dead": delta("dead"),
        "deferred": delta("deferred"),
    }
