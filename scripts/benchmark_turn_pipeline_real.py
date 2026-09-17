"""Paired real-provider gate for the concurrent turn pipeline.

The benchmark builds one deterministic offline snapshot, clones it for every
sample and changes only the execution mode.  Player-facing prose is allowed to
vary; the gate compares the mechanical contract, provider attempts, cost and
wall-clock latency without persisting normal game saves.
"""
from __future__ import annotations

import argparse
import contextlib
import copy
import json
import os
import random
import statistics
import sys
import tempfile
import time
import uuid
from collections import defaultdict
from pathlib import Path
from typing import Iterator


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


COHORTS = ("replan", "travel", "archive_due")


@contextlib.contextmanager
def _temporary_env(**updates: str | None) -> Iterator[None]:
    previous = {key: os.environ.get(key) for key in updates}
    for key, value in updates.items():
        if value is None:
            os.environ.pop(key, None)
        else:
            os.environ[key] = value
    try:
        yield
    finally:
        for key, value in previous.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value


def _percentile(values: list[float], pct: float) -> float:
    if not values:
        return 0.0
    rows = sorted(values)
    index = min(len(rows) - 1, int(round((pct / 100.0) * (len(rows) - 1))))
    return float(rows[index])


def evaluate_real_gate(samples: list[dict]) -> dict:
    """Evaluate R29 without weakening its thresholds."""
    grouped: dict[tuple[str, str], list[dict]] = defaultdict(list)
    for sample in samples:
        grouped[(str(sample["mode"]), str(sample["cohort"]))].append(sample)

    cohorts: dict[str, dict] = {}
    all_sequential: list[float] = []
    all_concurrent: list[float] = []
    medians_pass = True
    for cohort in COHORTS:
        serial = grouped[("sequential", cohort)]
        parallel = grouped[("concurrent", cohort)]
        serial_latencies = [float(row["latency_ms"]) for row in serial]
        parallel_latencies = [float(row["latency_ms"]) for row in parallel]
        serial_median = statistics.median(serial_latencies) if serial_latencies else 0.0
        parallel_median = statistics.median(parallel_latencies) if parallel_latencies else 0.0
        reduction = (
            1.0 - parallel_median / serial_median if serial_median > 0 else 0.0
        )
        cohort_passed = bool(serial and parallel and reduction >= 0.15)
        medians_pass = medians_pass and cohort_passed
        all_sequential.extend(serial_latencies)
        all_concurrent.extend(parallel_latencies)
        cohorts[cohort] = {
            "sequential_median_ms": round(serial_median, 2),
            "concurrent_median_ms": round(parallel_median, 2),
            "reduction_pct": round(reduction * 100, 1),
            "gate_passed": cohort_passed,
        }

    sequential_p95 = _percentile(all_sequential, 95)
    concurrent_p95 = _percentile(all_concurrent, 95)
    p95_passed = bool(
        all_sequential
        and all_concurrent
        and concurrent_p95 <= sequential_p95 * 1.05
    )
    totals = {}
    for mode in ("sequential", "concurrent"):
        rows = [row for row in samples if row["mode"] == mode]
        totals[mode] = {
            "requests": sum(int(row.get("requests", 0)) for row in rows),
            "cost_usd": round(sum(float(row.get("cost_usd", 0.0)) for row in rows), 6),
        }
    calls_passed = (
        totals["concurrent"]["requests"] <= totals["sequential"]["requests"]
        and totals["concurrent"]["cost_usd"] <= totals["sequential"]["cost_usd"]
    )
    correctness_passed = all(
        bool(row.get("contract_ok"))
        and int(row.get("terminal_invocations", 0)) == 0
        and int(row.get("error_violations", 0)) == 0
        and int(row.get("successes", 0)) > 0
        for row in samples
    )
    complete = all(grouped[(mode, cohort)] for mode in ("sequential", "concurrent")
                   for cohort in COHORTS)
    return {
        "schema_version": 1,
        "samples": len(samples),
        "cohorts": cohorts,
        "aggregate_p95": {
            "sequential_ms": round(sequential_p95, 2),
            "concurrent_ms": round(concurrent_p95, 2),
            "gate_passed": p95_passed,
        },
        "totals": totals,
        "calls_cost_gate_passed": calls_passed,
        "correctness_gate_passed": correctness_passed,
        "gate_passed": bool(
            complete and medians_pass and p95_passed and calls_passed
            and correctness_passed
        ),
    }


def _build_offline_snapshot() -> dict:
    from playtest.runner import _build_initial_state, _force_mock, _offline_embeddings

    with _force_mock(True), _offline_embeddings(True), _temporary_env(
        RPG_TURN_EXECUTION="sequential",
    ):
        from main import build_game_graph

        state = _build_initial_state("latency-gate", seed=8128, start_level=9)
        state = build_game_graph().invoke(state)
    state["game_over"] = False
    state["death_pending"] = False
    state["archive_due"] = False
    state["needs_replan"] = False
    return state


def _cohort_snapshot(base: dict, cohort: str, repetition: int) -> tuple[dict, str, dict]:
    from gamedata import get_connections

    state = copy.deepcopy(base)
    state["game_id"] = str(uuid.uuid4())
    state["turn_prepared"] = False
    state["archive_due"] = cohort == "archive_due"
    state["needs_replan"] = cohort == "replan"
    expected: dict = {
        "turn": int((state.get("world") or {}).get("turn_count", 0) or 0) + 1,
        "session_actions": int(
            (state.get("continuity") or {}).get("session_action_count", 0) or 0
        ) + 1,
    }
    if cohort == "travel":
        exits = get_connections((state.get("world") or {}).get("current_location_id", ""))
        if not exits:
            raise RuntimeError("snapshot de benchmark não possui saída de viagem")
        destination = exits[repetition % len(exits)]
        action = f"Viajo agora para {destination['name']}."
        expected["location_id"] = destination["id"]
    elif cohort == "replan":
        action = "Investigo os rumores locais e procuro o próximo objetivo concreto."
        expected["replanned"] = True
    else:
        action = "Examino cuidadosamente os sinais ao meu redor antes de prosseguir."
        expected["archived"] = True
    return state, action, expected


def _contract_ok(result: dict, expected: dict) -> bool:
    world = result.get("world") or {}
    continuity = result.get("continuity") or {}
    if int(world.get("turn_count", 0) or 0) != expected["turn"]:
        return False
    if int(continuity.get("session_action_count", 0) or 0) != expected["session_actions"]:
        return False
    if expected.get("location_id") and world.get("current_location_id") != expected["location_id"]:
        return False
    if expected.get("replanned") and bool(result.get("needs_replan")):
        return False
    if expected.get("archived") and int(result.get("archivist_last_run", -1)) != expected["turn"]:
        return False
    return not bool(result.get("game_over") or result.get("death_pending"))


def run_real_benchmark(*, repetitions: int, max_requests: int, max_cost: float,
                       timeout_seconds: float, routes_profile: str) -> dict:
    from langchain_core.messages import HumanMessage
    import llm_setup
    import rag
    from playtest import pricing
    from playtest.invariants import check_all
    from playtest.provider_profiles import activated_routes_profile, preflight_real_routes
    from playtest.runner import (
        _normalize_llm_event,
        _run_with_watchdog,
        terminal_llm_invocation_count,
    )
    from main import build_game_graph

    base = _build_offline_snapshot()
    samples: list[dict] = []
    aggregate_requests = 0
    aggregate_cost = 0.0
    with tempfile.TemporaryDirectory(prefix="valoria-latency-") as temporary:
        previous_rag_dir = rag.SAVES_DIR
        rag.SAVES_DIR = str(Path(temporary) / "memory")
        try:
            with activated_routes_profile(routes_profile), _temporary_env(
                RPG_FORCE_MOCK=None,
                RPG_NO_MOCK="1",
                RPG_RUNTIME_CACHE_DIR=str(Path(temporary) / "runtime"),
            ):
                preflight = preflight_real_routes()
                graphs = {}
                for mode in ("sequential", "concurrent"):
                    with _temporary_env(RPG_TURN_EXECUTION=mode):
                        graphs[mode] = build_game_graph()

                # Alternate modes per repetition to reduce provider drift bias.
                for cohort in COHORTS:
                    for repetition in range(repetitions):
                        modes = (
                            ("sequential", "concurrent")
                            if repetition % 2 == 0
                            else ("concurrent", "sequential")
                        )
                        for mode in modes:
                            if aggregate_requests >= max_requests or aggregate_cost >= max_cost:
                                raise RuntimeError(
                                    "teto do benchmark atingido antes de completar R29"
                                )
                            state, action, expected = _cohort_snapshot(
                                base, cohort, repetition,
                            )
                            state["messages"].append(HumanMessage(content=action))
                            attempts: list[dict] = []

                            def hook(event: object) -> None:
                                attempts.append(_normalize_llm_event(event))

                            llm_setup.reset_llm_circuit_breakers()
                            llm_setup.set_llm_attempt_telemetry_hook(hook)
                            random.seed(8128 + repetition)
                            started = time.perf_counter()
                            try:
                                with _temporary_env(
                                    RPG_CONTEXT_MAX_CONCURRENCY=("1" if mode == "sequential" else "3"),
                                ):
                                    result = _run_with_watchdog(
                                        lambda: graphs[mode].invoke(state),
                                        timeout_seconds=timeout_seconds,
                                        phase=f"latency-{cohort}-{mode}-{repetition + 1}",
                                    )
                                error_violations = len([
                                    violation for violation in check_all(
                                        result, state, repetition + 1,
                                    )
                                    if violation.severity == "error"
                                ])
                                exception = None
                            except Exception as exc:
                                result = state
                                error_violations = 1
                                exception = f"{type(exc).__name__}: {str(exc)[:240]}"
                            finally:
                                llm_setup.set_llm_attempt_telemetry_hook(None)
                            elapsed_ms = (time.perf_counter() - started) * 1000
                            network = [row for row in attempts if row["network_attempted"]]
                            sample_cost = pricing.turn_cost(network)
                            aggregate_requests += len(network)
                            aggregate_cost += sample_cost
                            samples.append({
                                "mode": mode,
                                "cohort": cohort,
                                "repetition": repetition + 1,
                                "latency_ms": round(elapsed_ms, 2),
                                "requests": len(network),
                                "cost_usd": round(sample_cost, 6),
                                "successes": len([
                                    row for row in attempts if row["status"] == "success"
                                ]),
                                "terminal_invocations": terminal_llm_invocation_count(attempts),
                                "error_violations": error_violations,
                                "contract_ok": bool(
                                    exception is None and _contract_ok(result, expected)
                                ),
                                "exception": exception,
                                "providers": sorted({
                                    row["provider"] for row in attempts
                                    if row["status"] == "success"
                                }),
                            })
        finally:
            llm_setup.set_llm_attempt_telemetry_hook(None)
            rag.SAVES_DIR = previous_rag_dir

    gate = evaluate_real_gate(samples)
    return {
        **gate,
        "kind": "real-paired-turn-latency",
        "routes_profile": routes_profile,
        "repetitions_per_mode_cohort": repetitions,
        "preflight": preflight,
        "budget": {
            "requests": aggregate_requests,
            "max_requests": max_requests,
            "cost_usd": round(aggregate_cost, 6),
            "max_cost_usd": max_cost,
        },
        "raw_samples": samples,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repetitions", type=int, default=3)
    parser.add_argument("--max-requests", type=int, default=180)
    parser.add_argument("--max-cost", type=float, default=0.10)
    parser.add_argument("--turn-timeout", type=float, default=120.0)
    parser.add_argument("--routes-profile", default="deepseek-paid")
    parser.add_argument("--output")
    args = parser.parse_args()
    if args.repetitions < 3 or args.max_requests <= 0 or args.max_cost <= 0:
        parser.error("repetitions >= 3 e tetos positivos são obrigatórios")

    result = run_real_benchmark(
        repetitions=args.repetitions,
        max_requests=args.max_requests,
        max_cost=args.max_cost,
        timeout_seconds=args.turn_timeout,
        routes_profile=args.routes_profile,
    )
    output = Path(args.output) if args.output else Path(
        "playtest_runs", f"latency-r29-{time.strftime('%Y%m%d-%H%M%S')}.json",
    )
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True),
        encoding="utf-8",
    )
    print(json.dumps({
        "output": str(output),
        "gate_passed": result["gate_passed"],
        "cohorts": result["cohorts"],
        "aggregate_p95": result["aggregate_p95"],
        "budget": result["budget"],
    }, ensure_ascii=False, sort_keys=True))
    return 0 if result["gate_passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
