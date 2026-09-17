"""Deterministic, provider-free benchmark for the turn fan-out contract."""
from __future__ import annotations

import argparse
import json
import statistics
import time
from concurrent.futures import ThreadPoolExecutor


def _branch(delay_ms: int) -> None:
    time.sleep(max(0, delay_ms) / 1000)


def sample(*, concurrent: bool, plan_ms: int, route_ms: int) -> float:
    started = time.perf_counter()
    if concurrent:
        with ThreadPoolExecutor(max_workers=2) as executor:
            futures = [
                executor.submit(_branch, plan_ms),
                executor.submit(_branch, route_ms),
            ]
            for future in futures:
                future.result()
    else:
        _branch(plan_ms)
        _branch(route_ms)
    return (time.perf_counter() - started) * 1000


def benchmark(*, repetitions: int = 5, plan_ms: int = 80,
              route_ms: int = 60) -> dict:
    serial = [sample(concurrent=False, plan_ms=plan_ms, route_ms=route_ms)
              for _ in range(repetitions)]
    parallel = [sample(concurrent=True, plan_ms=plan_ms, route_ms=route_ms)
                for _ in range(repetitions)]
    serial_median = statistics.median(serial)
    parallel_median = statistics.median(parallel)
    reduction = 1 - (parallel_median / serial_median)
    return {
        "schema_version": 1,
        "provider_calls": 0,
        "repetitions": repetitions,
        "serial_median_ms": round(serial_median, 2),
        "concurrent_median_ms": round(parallel_median, 2),
        "reduction_pct": round(reduction * 100, 1),
        "gate_min_reduction_pct": 30.0,
        "gate_passed": reduction >= 0.30,
    }


def modelled_reduction(*, plan_ms: int, route_ms: int) -> float:
    """Exact lower-bound model used by unit tests; no scheduler timing involved."""
    total = max(0, plan_ms) + max(0, route_ms)
    if total == 0:
        return 0.0
    return 1 - (max(plan_ms, route_ms) / total)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repetitions", type=int, default=5)
    args = parser.parse_args()
    result = benchmark(repetitions=max(3, args.repetitions))
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    return 0 if result["gate_passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
