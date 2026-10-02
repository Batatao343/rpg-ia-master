"""Independent exact-match oracle used as the first evaluator calibration case."""

from __future__ import annotations

from datetime import UTC, datetime
from time import perf_counter
from typing import Any

from evals.core.schemas import EVALUATOR_VERSION, EvalCase, EvalCaseResult


def strict_equal(actual: Any, expected: Any) -> bool:
    """Compare JSON-shaped values without Python's bool/int coercion."""

    if type(actual) is not type(expected):
        return False
    if isinstance(expected, dict):
        return actual.keys() == expected.keys() and all(
            strict_equal(actual[key], value) for key, value in expected.items()
        )
    if isinstance(expected, list):
        return len(actual) == len(expected) and all(
            strict_equal(actual_value, expected_value)
            for actual_value, expected_value in zip(actual, expected, strict=True)
        )
    return bool(actual == expected)


class ExactEvaluator:
    """Compare candidate output to fixture-authored expected data."""

    evaluator_id = "exact"
    evaluator_version = EVALUATOR_VERSION

    def evaluate(
        self,
        case: EvalCase,
        actual: Any,
        *,
        product_sha: str,
        dataset_hash: str,
        seed: int,
    ) -> EvalCaseResult:
        if case.oracle != "exact":
            raise ValueError(f"exact evaluator cannot evaluate oracle {case.oracle!r}")
        started_at = datetime.now(UTC)
        started = perf_counter()
        passed = strict_equal(actual, case.expected)
        return EvalCaseResult(
            case_id=case.id,
            suite=case.suite,
            passed=passed,
            actual=actual,
            expected=case.expected,
            metric_values={"exact_match": 1.0 if passed else 0.0},
            diagnostics=[] if passed else ["actual != fixture-authored expected"],
            evaluator_id=self.evaluator_id,
            evaluator_version=self.evaluator_version,
            product_sha=product_sha,
            dataset_hash=dataset_hash,
            seed=seed,
            started_at=started_at,
            duration_ms=(perf_counter() - started) * 1000,
        )
