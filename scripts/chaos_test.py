"""Falhas locais controladas: fencing, lease recovery e atomicidade."""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
import sys
from pathlib import Path
from uuid import uuid4

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from infrastructure.contracts import Conflict, JobRequest, LeaseHeld, Principal
from infrastructure.postgres import PostgresGameStore, PostgresPool
from infrastructure.postgres_jobs import PostgresJobQueue
from infrastructure.postgres_turns import PostgresTurnCoordinator
from scripts.load_test import DEFAULT_DSN, _state


def run(dsn: str = DEFAULT_DSN, *, output: Path | None = None) -> dict:
    pool = PostgresPool(dsn, max_size=4)
    store = PostgresGameStore(pool)
    owner, game_id = uuid4(), uuid4()
    principal = Principal(owner, "chaos", str(owner), local=True)
    scenarios: dict[str, bool] = {}
    try:
        initial = _state(game_id, "Caos")
        initial["event_log"] = [{
            "event_id": "chaos-event", "type": "quest_completed", "turn": 0,
            "payload": {"value": "original"}, "source": "chaos",
        }]
        created = store.create(principal, initial)

        coordinator = PostgresTurnCoordinator(pool, lease_seconds=1)
        operation = uuid4()
        old = coordinator.claim(
            principal, operation, game_id=game_id, kind="turn",
            request_hash="a" * 64, base_version=created.version,
        )
        with pool.connection() as connection, connection.transaction():
            connection.execute(
                "update app.operations set lease_until=now()-interval '1 second' where id=%s",
                (operation,),
            )
            connection.execute(
                "update app.games set active_lease_until=now()-interval '1 second' where id=%s",
                (game_id,),
            )
        fresh = coordinator.claim(
            principal, operation, game_id=game_id, kind="turn",
            request_hash="a" * 64, base_version=created.version,
        )
        try:
            coordinator.complete(old, committed_version=created.version, receipt={"old": True})
            scenarios["turn_fencing"] = False
        except LeaseHeld:
            scenarios["turn_fencing"] = True
        coordinator.complete(fresh, committed_version=created.version, receipt={"fresh": True})
        scenarios["expired_turn_converges"] = coordinator.receipt(principal, operation) == {
            "fresh": True,
        }

        queue = PostgresJobQueue(pool, lease_seconds=1)
        job_id = queue.enqueue(JobRequest(
            "chaos_job", f"chaos-{uuid4()}", {}, owner_id=owner, game_id=game_id,
        ))
        old_job = queue.lease("old-worker", {"chaos_job"}, 1)[0]
        with pool.connection() as connection, connection.transaction():
            connection.execute(
                "update app.jobs set lease_until=now()-interval '1 second' where id=%s",
                (job_id,),
            )
        fresh_job = queue.lease("new-worker", {"chaos_job"}, 1)[0]
        try:
            queue.complete(old_job.job_id, old_job.lease_token, {"old": True})
            scenarios["job_fencing"] = False
        except LeaseHeld:
            scenarios["job_fencing"] = True
        queue.complete(fresh_job.job_id, fresh_job.lease_token, {"fresh": True})
        with pool.connection() as connection:
            scenarios["expired_job_converges"] = connection.execute(
                "select status='succeeded' and attempts=2 as ok from app.jobs where id=%s",
                (job_id,),
            ).fetchone()["ok"]

        stored = store.get(principal, game_id)
        assert stored is not None
        atomic_operation = uuid4()
        claim = coordinator.claim(
            principal, atomic_operation, game_id=game_id, kind="turn",
            request_hash="b" * 64, base_version=stored.version,
        )
        corrupted = copy.deepcopy(stored.state)
        corrupted["event_log"][0]["payload"] = {"value": "divergent"}
        try:
            coordinator.commit_game(
                principal, claim, corrupted, receipt={"bad": True},
                input_sha256=hashlib.sha256(b"chaos").hexdigest(),
                latency_ms=1, llm_cost_usd=0,
            )
            scenarios["atomic_rollback"] = False
        except Conflict:
            after = store.get(principal, game_id)
            with pool.connection() as connection:
                turn_rows = connection.execute(
                    "select count(*) as n from app.turns where operation_id=%s",
                    (atomic_operation,),
                ).fetchone()["n"]
            scenarios["atomic_rollback"] = bool(
                after and after.version == stored.version and turn_rows == 0
            )
            coordinator.fail(claim, "injected_event_conflict")

        errors = [name for name, passed in scenarios.items() if not passed]
        result = {
            "status": "passed" if not errors else "failed",
            "scenarios": scenarios,
            "errors": errors,
        }
        if output:
            output.parent.mkdir(parents=True, exist_ok=True)
            output.write_text(json.dumps(result, indent=2), encoding="utf-8")
        if errors:
            raise RuntimeError(json.dumps(result))
        return result
    finally:
        try:
            store.delete(principal, game_id)
        except Exception:
            pass
        pool.close()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dsn", default=DEFAULT_DSN)
    parser.add_argument(
        "--output", type=Path, default=Path("readiness_artifacts/chaos_test.json"),
    )
    args = parser.parse_args()
    print(json.dumps(run(args.dsn, output=args.output), ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
