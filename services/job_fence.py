"""Bind derived writes to the worker's current database fencing token."""
from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from contextvars import ContextVar
from typing import Any

from infrastructure.contracts import LeasedJob

_current: ContextVar[LeasedJob | None] = ContextVar("current_job_fence", default=None)


@contextmanager
def job_scope(job: LeasedJob) -> Iterator[None]:
    token = _current.set(job)
    try:
        yield
    finally:
        _current.reset(token)


def require_job_fence(connection: Any) -> None:
    """Lock the job through publication; direct maintenance calls have no job."""
    job = _current.get()
    if job is not None:
        from infrastructure.postgres_jobs import PostgresJobQueue

        PostgresJobQueue._require_running(connection, job.job_id, job.lease_token)
