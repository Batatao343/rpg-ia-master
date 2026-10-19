"""SPEC-255: logs do worker de jobs, correlacao com o request de origem e contagem no drain."""

import json
import uuid
from contextlib import contextmanager

import pytest

from infrastructure.contracts import JobDeferred, JobRequest, LeasedJob, LeaseHeld
from observability import logging_setup
from observability.telemetry import correlation_scope
from workers.job_worker import JobWorker

SENT = "PAYLOADSENTINELA255"


@pytest.fixture(autouse=True)
def _logs():
    logging_setup.configure_logging({"RPG_LOG_LEVEL": "debug"})


def _lines(capsys):
    out = []
    for raw in capsys.readouterr().out.splitlines():
        try:
            out.append(json.loads(raw))
        except ValueError:
            pass
    return [x for x in out if str(x.get("event", "")).startswith("job.")]


class _Queue:
    lease_seconds = 90

    def __init__(self, fail_result=None, fail_exc=None):
        self.completed, self.failed, self.deferred = [], [], []
        self._fail_result, self._fail_exc = fail_result, fail_exc
        self.leased: list[LeasedJob] = []

    def lease(self, worker_id, kinds, limit):
        jobs, self.leased = self.leased[:limit], self.leased[limit:]
        return jobs

    def heartbeat(self, job_id, token):
        return None

    def complete(self, job_id, token, result):
        self.completed.append(result)

    def fail(self, job_id, token, code):
        if self._fail_exc:
            raise self._fail_exc
        self.failed.append(code)
        return self._fail_result

    def defer(self, job_id, token, delay, reason):
        self.deferred.append(reason)


def _job(kind="project_archive", trace=None, attempt=1, max_attempts=3):
    return LeasedJob(
        job_id=uuid.uuid4(),
        lease_token=uuid.uuid4(),
        attempt=attempt,
        request=JobRequest(
            kind=kind,
            dedupe_key="k",
            payload={"texto": SENT},
            max_attempts=max_attempts,
            trace=trace,
        ),
    )


def _worker(queue, handler):
    return JobWorker(queue, {"project_archive": handler}, worker_id="w1")


def test_job_failure_logs_class_and_retry(capsys):
    queue = _Queue(fail_result={"status": "retry", "next_run_in_s": 4})

    def boom(_payload):
        raise ValueError(f"segredo {SENT}")

    _worker(queue, boom)._run(_job())
    assert queue.failed == ["exc:ValueError"]  # nunca so "handler_error"
    (failed,) = [x for x in _lines(capsys) if x["event"] == "job.failed"]
    assert failed["error_type"] == "ValueError" and failed["error_code"] == "exc:ValueError"
    assert failed["will_retry"] is True and failed["next_run_in_s"] == 4 and failed["attempt"] == 1
    assert failed["level"] == "warning" and failed["job_kind"] == "project_archive"


def test_handler_error_code_attribute_is_kept(capsys):
    queue = _Queue(fail_result={"status": "retry", "next_run_in_s": 2})

    class Coded(Exception):
        error_code = "provider_down"

    def boom(_payload):
        raise Coded("x")

    _worker(queue, boom)._run(_job())
    assert queue.failed == ["provider_down"]


def test_dead_job_logged_as_error(capsys):
    queue = _Queue(fail_result={"status": "dead", "next_run_in_s": 0})

    def boom(_payload):
        raise RuntimeError("x")

    _worker(queue, boom)._run(_job(attempt=3))
    events = {x["event"]: x for x in _lines(capsys)}
    assert events["job.failed"]["will_retry"] is False
    assert events["job.dead"]["level"] == "error" and events["job.dead"]["reason"] == "max_attempts"


def test_job_inherits_request_id_from_enqueue(capsys):
    trace = {"request_id": "turn-req-0001", "action_ref": "abcd1234abcd1234"}
    queue = _Queue()
    _worker(queue, lambda payload: {"ok": True})._run(_job(trace=trace))
    lines = _lines(capsys)
    assert [x["event"] for x in lines] == ["job.started", "job.completed"]
    assert all(
        x["request_id"] == "turn-req-0001" and x["action_ref"] == "abcd1234abcd1234" for x in lines
    )
    done = lines[1]
    assert done["level"] == "info" and done["duration_ms"] >= 0 and done["attempt"] == 1
    assert SENT not in json.dumps(lines)


def test_deferred_and_lease_lost_logged(capsys):
    queue = _Queue()

    def defer(_payload):
        raise JobDeferred("image_generation_disabled", 60.0)

    _worker(queue, defer)._run(_job())
    lost = _Queue(fail_exc=LeaseHeld("x"))

    def boom(_payload):
        raise RuntimeError("x")

    _worker(lost, boom)._run(_job())
    events = [x["event"] for x in _lines(capsys)]
    assert "job.deferred" in events and "job.lease_lost" in events


def test_drain_counts_failures(capsys):
    from workers.drain import drain_jobs

    queue = _Queue(fail_result={"status": "dead", "next_run_in_s": 0})
    queue.leased = [_job(), _job(), _job()]
    calls = {"n": 0}

    def sometimes(_payload):
        calls["n"] += 1
        if calls["n"] == 1:
            return {"ok": True}
        raise RuntimeError("x")

    result = drain_jobs(100.0, 10, "w1", worker=_worker(queue, sometimes))
    assert result["processed"] == 3 and result["failed"] == 2 and result["dead"] == 2
    assert result["deferred"] == 0


def test_old_payload_without_trace_ok():
    from infrastructure.postgres_jobs import _split_trace

    payload, trace = _split_trace({"a": 1})
    assert payload == {"a": 1} and trace is None
    payload, trace = _split_trace({"a": 1, "_trace": {"request_id": "r1234567", "x": "no"}})
    assert payload == {"a": 1} and trace == {"request_id": "r1234567"}


class _Cursor:
    def __init__(self, rows):
        self._rows = rows

    def fetchall(self):
        return self._rows

    def fetchone(self):
        return self._rows[0] if self._rows else None


class _Conn:
    def __init__(self, results):
        self._results, self.calls = list(results), []

    def execute(self, sql, params=None):
        self.calls.append((sql, params))
        return _Cursor(self._results.pop(0) if self._results else [])

    @contextmanager
    def transaction(self):
        yield


def test_lease_expiry_dead_logged(capsys, monkeypatch):
    from infrastructure import postgres_jobs

    dead_id = uuid.uuid4()
    conn = _Conn([[{"id": dead_id}], []])

    @contextmanager
    def fake_admin(_pool):
        yield conn

    monkeypatch.setattr(postgres_jobs, "admin_connection", fake_admin)
    queue = postgres_jobs.PostgresJobQueue(pool=object(), lease_seconds=90)
    assert queue.lease("w1", {"project_archive"}, 1) == []
    out = capsys.readouterr().out
    (line,) = [json.loads(x) for x in out.splitlines() if "job.dead" in x]
    assert line["reason"] == "lease_expired_max_attempts" and line["level"] == "error"
    assert str(dead_id) not in out


def test_enqueue_stores_trace_inside_payload(monkeypatch):
    from infrastructure import postgres_jobs

    conn = _Conn([[{"id": uuid.uuid4()}]])
    queue = postgres_jobs.PostgresJobQueue(pool=object(), lease_seconds=90)
    with correlation_scope(request_id="origin-req-0001", action_id=str(uuid.uuid4())):
        queue.enqueue(
            JobRequest(kind="project_archive", dedupe_key="k", payload={"a": 1}), connection=conn
        )
    stored = conn.calls[0][1][5].obj
    assert stored["a"] == 1 and stored["_trace"]["request_id"] == "origin-req-0001"
    assert stored["_trace"]["action_ref"]
