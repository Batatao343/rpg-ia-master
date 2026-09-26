from threading import Event, enumerate as threads
from uuid import uuid4

from infrastructure.contracts import JobRequest, LeasedJob, LeaseHeld
from workers.job_worker import JobWorker


class Queue:
    lease_seconds = 0.12

    def __init__(self):
        self.renewed = Event()
        self.renewals = 0
        self.limits = []
        self.completed = []
        self.failed = []
        self.lost = False

    def lease(self, worker, kinds, limit):
        self.limits.append(limit)
        return [LeasedJob(uuid4(), uuid4(), JobRequest('work', 'test', {}), 1)]

    def heartbeat(self, *args):
        self.renewals += 1
        if self.renewals >= 3:
            self.renewed.set()
        if self.lost:
            raise LeaseHeld('lost')

    def complete(self, *args):
        if self.lost:
            raise LeaseHeld('lost')
        self.completed.append(args)

    def fail(self, *args):
        if self.lost:
            raise LeaseHeld('lost')
        self.failed.append(args)


def test_serial_worker_only_reserves_capacity_and_renews():
    queue = Queue()
    def handle(payload):
        assert queue.renewed.wait(1)
        return {'ok': True}
    worker = JobWorker(queue, {'work': handle}, worker_id='test')
    assert worker.run_once(limit=10) == 1
    assert queue.limits == [1]
    assert len(queue.completed) == 1
    assert queue.renewals >= 3
    assert not any(t.name == 'lease-heartbeat' for t in threads())


def test_lost_lease_does_not_publish_or_crash_worker():
    queue = Queue()
    queue.lost = True
    worker = JobWorker(queue, {'work': lambda _: {}}, worker_id='test')
    worker.run_once()
    assert queue.completed == []
    assert queue.failed == []


def test_stopped_worker_does_not_reserve():
    queue = Queue()
    worker = JobWorker(queue, {'work': lambda _: {}}, worker_id='test')
    worker.request_stop()
    assert worker.run_once() == 0
    assert queue.limits == []
