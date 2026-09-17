from scripts.benchmark_turn_pipeline import modelled_reduction
from scripts.benchmark_turn_pipeline_real import evaluate_real_gate


def test_controlled_fanout_reduces_wall_time_without_provider_calls():
    reduction = modelled_reduction(plan_ms=60, route_ms=50)
    assert round(reduction * 100, 1) == 45.5
    assert reduction >= 0.30


def _real_samples(*, concurrent_latency: int = 80,
                  concurrent_requests: int = 2) -> list[dict]:
    samples = []
    for cohort in ("replan", "travel", "archive_due"):
        for mode, latency, requests in (
            ("sequential", 100, 2),
            ("concurrent", concurrent_latency, concurrent_requests),
        ):
            for repetition in range(3):
                samples.append({
                    "mode": mode,
                    "cohort": cohort,
                    "repetition": repetition + 1,
                    "latency_ms": latency,
                    "requests": requests,
                    "cost_usd": requests * 0.001,
                    "successes": 2,
                    "terminal_invocations": 0,
                    "error_violations": 0,
                    "contract_ok": True,
                })
    return samples


def test_real_gate_requires_latency_correctness_and_no_request_increase():
    passed = evaluate_real_gate(_real_samples())
    assert passed["gate_passed"] is True
    assert all(row["reduction_pct"] == 20.0
               for row in passed["cohorts"].values())

    too_slow = evaluate_real_gate(_real_samples(concurrent_latency=90))
    assert too_slow["gate_passed"] is False

    extra_calls = evaluate_real_gate(_real_samples(concurrent_requests=3))
    assert extra_calls["gate_passed"] is False
