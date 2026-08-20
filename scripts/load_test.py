"""Carga local multi-processo para commits, receipts, leases e jobs Postgres."""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
import sys
import time
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path
from statistics import mean
from uuid import UUID, uuid4

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from infrastructure.contracts import Conflict, JobRequest, LeaseHeld, Principal
from infrastructure.postgres import PostgresGameStore, PostgresPool
from infrastructure.postgres_jobs import PostgresJobQueue
from infrastructure.postgres_turns import PostgresTurnCoordinator


DEFAULT_DSN = "postgresql://postgres:postgres@127.0.0.1:55322/postgres"


def _state(game_id: UUID, name: str = "Carga") -> dict:
    return {
        "game_id": str(game_id), "messages": [], "event_log": [],
        "player": {"name": name, "class_name": "Devoto", "level": 1},
        "world": {
            "current_location": "Laboratório", "turn_count": 0,
            "world_clock": {"day": 1},
        },
    }


def _p95(values: list[float]) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    return ordered[max(0, int(len(ordered) * 0.95 + 0.999999) - 1)]


def _commit_task(dsn: str, owner: str, game: str, operation: str) -> dict:
    pool = PostgresPool(dsn, max_size=1)
    try:
        principal = Principal(UUID(owner), "load", owner, local=True)
        game_id, operation_id = UUID(game), UUID(operation)
        store = PostgresGameStore(pool)
        coordinator = PostgresTurnCoordinator(pool, lease_seconds=10)
        started = time.perf_counter()
        stored = store.get(principal, game_id)
        if not stored:
            raise RuntimeError("jogo de carga não encontrado")
        claim = coordinator.claim(
            principal, operation_id, game_id=game_id, kind="turn",
            request_hash=hashlib.sha256(str(operation_id).encode()).hexdigest(),
            base_version=stored.version,
        )
        changed = copy.deepcopy(stored.state)
        changed.setdefault("world", {})["turn_count"] = (
            int(changed.get("world", {}).get("turn_count", 0)) + 1
        )
        commit_started = time.perf_counter()
        version, _ = coordinator.commit_game(
            principal, claim, changed,
            receipt={"ok": True, "operation_id": str(operation_id)},
            input_sha256=hashlib.sha256(b"load").hexdigest(),
            latency_ms=0, llm_cost_usd=0.0,
        )
        return {
            "status": "committed", "version": version,
            "commit_latency_ms": (time.perf_counter() - commit_started) * 1000,
            "end_to_end_latency_ms": (time.perf_counter() - started) * 1000,
        }
    finally:
        pool.close()


def _idempotent_task(dsn: str, owner: str, game: str, operation: str) -> dict:
    try:
        return _commit_task(dsn, owner, game, operation)
    except (Conflict, LeaseHeld) as exc:
        pool = PostgresPool(dsn, max_size=1)
        try:
            principal = Principal(UUID(owner), "load", owner, local=True)
            coordinator = PostgresTurnCoordinator(pool)
            deadline = time.monotonic() + 10
            receipt = None
            while time.monotonic() < deadline and receipt is None:
                receipt = coordinator.receipt(principal, UUID(operation))
                if receipt is None:
                    time.sleep(0.05)
            if receipt is None:
                raise RuntimeError("duplicate não convergiu para receipt") from exc
            return {"status": "duplicate", "version": receipt["committed_version"]}
        finally:
            pool.close()


def _job_worker(dsn: str, worker_id: str, kind: str) -> dict:
    pool = PostgresPool(dsn, max_size=1)
    completed: list[str] = []
    try:
        queue = PostgresJobQueue(pool, lease_seconds=10)
        while True:
            leased = queue.lease(worker_id, {kind}, 4)
            if not leased:
                break
            for job in leased:
                queue.complete(job.job_id, job.lease_token, {"worker": worker_id})
                completed.append(str(job.job_id))
        return {"worker": worker_id, "completed": completed}
    finally:
        pool.close()


def run(dsn: str = DEFAULT_DSN, *, workers: int = 2, operations: int = 12,
        output: Path | None = None) -> dict:
    if workers < 2 or operations < workers:
        raise ValueError("carga exige ao menos 2 workers e operações >= workers")
    pool = PostgresPool(dsn, max_size=4)
    store = PostgresGameStore(pool)
    games: list[tuple[Principal, UUID]] = []
    started = time.perf_counter()
    kind = f"load-{uuid4()}"
    try:
        owners = [uuid4(), uuid4()]
        for index in range(operations + 1):
            owner = owners[index % 2]
            principal = Principal(owner, "load", str(owner), local=True)
            game_id = uuid4()
            store.create(principal, _state(game_id, f"Carga {index}"))
            games.append((principal, game_id))
        tasks = [
            (dsn, str(principal.user_id), str(game_id), str(uuid4()))
            for principal, game_id in games[:operations]
        ]
        with ProcessPoolExecutor(max_workers=workers) as executor:
            commit_results = list(executor.map(
                _commit_task,
                [row[0] for row in tasks], [row[1] for row in tasks],
                [row[2] for row in tasks], [row[3] for row in tasks],
            ))

        duplicate_principal, duplicate_game = games[-1]
        duplicate_operation = uuid4()
        duplicate_args = (
            dsn, str(duplicate_principal.user_id), str(duplicate_game),
            str(duplicate_operation),
        )
        with ProcessPoolExecutor(max_workers=2) as executor:
            duplicate_results = list(executor.map(
                _idempotent_task,
                [duplicate_args[0]] * 2, [duplicate_args[1]] * 2,
                [duplicate_args[2]] * 2, [duplicate_args[3]] * 2,
            ))

        queue = PostgresJobQueue(pool)
        job_ids = [queue.enqueue(JobRequest(
            kind, f"{kind}-{index}", {"index": index},
            owner_id=games[index % len(games)][0].user_id,
            game_id=games[index % len(games)][1],
        )) for index in range(operations)]
        with ProcessPoolExecutor(max_workers=workers) as executor:
            job_results = list(executor.map(
                _job_worker, [dsn] * workers,
                [f"worker-{index}" for index in range(workers)], [kind] * workers,
            ))

        commit_latencies = [float(row["commit_latency_ms"]) for row in commit_results]
        end_to_end_latencies = [
            float(row["end_to_end_latency_ms"]) for row in commit_results
        ]
        with pool.connection() as connection:
            succeeded = int(connection.execute(
                "select count(*) as n from app.jobs where id=any(%s) and status='succeeded'",
                (job_ids,),
            ).fetchone()["n"])
            duplicate_turns = int(connection.execute(
                "select count(*) as n from app.turns where operation_id=%s",
                (duplicate_operation,),
            ).fetchone()["n"])
        statuses = sorted(row["status"] for row in duplicate_results)
        errors = []
        if any(row["status"] != "committed" for row in commit_results):
            errors.append("distinct_commit_failed")
        if statuses != ["committed", "duplicate"] or duplicate_turns != 1:
            errors.append("idempotency_failed")
        if succeeded != operations:
            errors.append("job_loss_or_duplicate")
        if _p95(commit_latencies) >= 250:
            errors.append("commit_p95_slo_exceeded")
        result = {
            "status": "passed" if not errors else "failed",
            "workers": workers,
            "operations": operations,
            "owners": 2,
            "commits": len(commit_results),
            "duplicate_statuses": statuses,
            "duplicate_turn_rows": duplicate_turns,
            "jobs_succeeded": succeeded,
            "job_worker_distribution": [len(row["completed"]) for row in job_results],
            "commit_latency_ms": {
                "mean": round(mean(commit_latencies), 3),
                "p95": round(_p95(commit_latencies), 3),
                "max": round(max(commit_latencies, default=0.0), 3),
            },
            "end_to_end_latency_ms": {
                "mean": round(mean(end_to_end_latencies), 3),
                "p95": round(_p95(end_to_end_latencies), 3),
                "max": round(max(end_to_end_latencies, default=0.0), 3),
            },
            "elapsed_seconds": round(time.perf_counter() - started, 3),
            "errors": errors,
        }
        if output:
            output.parent.mkdir(parents=True, exist_ok=True)
            output.write_text(json.dumps(result, indent=2), encoding="utf-8")
        if errors:
            raise RuntimeError(json.dumps(result))
        return result
    finally:
        for principal, game_id in games:
            try:
                store.delete(principal, game_id)
            except Exception:
                pass
        pool.close()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dsn", default=DEFAULT_DSN)
    parser.add_argument("--workers", type=int, default=2)
    parser.add_argument("--operations", type=int, default=12)
    parser.add_argument(
        "--output", type=Path, default=Path("readiness_artifacts/load_test.json"),
    )
    args = parser.parse_args()
    print(json.dumps(run(
        args.dsn, workers=args.workers, operations=args.operations, output=args.output,
    ), ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
