"""Structured state projection evaluator with fixture-authored expected values."""

from __future__ import annotations

from datetime import UTC, datetime
from time import perf_counter
from typing import Any

from evals.core.schemas import EVALUATOR_VERSION, EvalCase, EvalCaseResult
from evals.evaluators.exact import strict_equal


class ProjectionEvaluator:
    evaluator_id = "state_projection"
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
        if case.oracle != "projection":
            raise ValueError(f"projection evaluator cannot evaluate oracle {case.oracle!r}")
        started_at = datetime.now(UTC)
        started = perf_counter()
        passed = strict_equal(actual, case.expected)
        return EvalCaseResult(
            case_id=case.id,
            suite=case.suite,
            passed=passed,
            actual=actual,
            expected=case.expected,
            metric_values={"state_transition_pass_rate": 1.0 if passed else 0.0},
            diagnostics=[] if passed else ["actual projection != fixture-authored expected"],
            evaluator_id=self.evaluator_id,
            evaluator_version=self.evaluator_version,
            product_sha=product_sha,
            dataset_hash=dataset_hash,
            seed=seed,
            started_at=started_at,
            duration_ms=(perf_counter() - started) * 1000,
        )
