"""Real local database fences, with no provider calls."""
from threading import Event, Thread
from uuid import uuid4

import pytest

from infrastructure.contracts import JobRequest, LeaseHeld
from services.job_fence import job_scope, require_job_fence
from tests.test_postgres_jobs_local import infra  # noqa: F401
from workers.job_worker import JobWorker

pytestmark = pytest.mark.infra_local


def test_old_worker_cannot_publish_after_takeover(infra):
    _, queue, _, _ = infra
    kind = f'fence-{uuid4()}'
    job_id = queue.enqueue(JobRequest(kind, kind, {}))
    old = queue.lease('old', {kind}, 1)[0]
    with queue.pool.connection() as connection, connection.transaction():
        connection.execute("update app.jobs set lease_until=now()-interval '1 second' where id=%s", (job_id,))
    new = queue.lease('new', {kind}, 1)[0]
    with job_scope(old), pytest.raises(LeaseHeld):
        with queue.pool.connection() as connection, connection.transaction():
            require_job_fence(connection)
    with job_scope(new):
        with queue.pool.connection() as connection, connection.transaction():
            require_job_fence(connection)
    queue.complete(new.job_id, new.lease_token, {'ok': True})


def test_heartbeat_retains_job_beyond_ttl_against_second_worker(infra):
    _, queue, _, _ = infra
    queue.lease_seconds = 0.3
    kind = f'heartbeat-{uuid4()}'
    job_id = queue.enqueue(JobRequest(kind, kind, {}))
    started, release = Event(), Event()
    def handler(_):
        started.set()
        assert release.wait(3)
        return {'ok': True}
    worker = JobWorker(queue, {kind: handler}, worker_id='first')
    thread = Thread(target=worker.run_once)
    thread.start()
    try:
        assert started.wait(2)
        # This integration gate deliberately spans more than two lease periods.
        assert not release.wait(0.7)
        assert queue.lease('second', {kind}, 1) == []
    finally:
        release.set()
        thread.join(3)
    assert not thread.is_alive()
    with queue.pool.connection() as connection:
        assert connection.execute('select status from app.jobs where id=%s', (job_id,)).fetchone()['status'] == 'succeeded'
