"""Routing evaluator independent from the product router implementation."""

from __future__ import annotations

from datetime import UTC, datetime
from time import perf_counter
from typing import Any

from evals.core.schemas import EVALUATOR_VERSION, EvalCase, EvalCaseResult
from evals.evaluators.exact import strict_equal


class RoutingEvaluator:
    evaluator_id = "routing_contract"
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
        if case.oracle != "classification":
            raise ValueError(f"routing evaluator cannot evaluate oracle {case.oracle!r}")
        started_at = datetime.now(UTC)
        started = perf_counter()
        expected = case.expected
        diagnostics: list[str] = []
        if not isinstance(expected, dict) or "route" not in expected:
            raise ValueError("classification expected must be an object with route")
        if not isinstance(actual, dict):
            diagnostics.append("actual routing decision is not an object")
            actual = {}

        route_ok = strict_equal(actual.get("route"), expected["route"])
        if not route_ok:
            diagnostics.append(
                f"route mismatch: expected {expected['route']!r}, got {actual.get('route')!r}"
            )
        target_ok = True
        metric_values = {"route_accuracy": 1.0 if route_ok else 0.0}
        for field, expected_value in expected.items():
            if field == "route":
                continue
            actual_value = actual.get(field)
            if field == "target" and isinstance(expected_value, list):
                field_ok = any(strict_equal(actual_value, value) for value in expected_value)
            else:
                field_ok = strict_equal(actual_value, expected_value)
            if field == "target":
                target_ok = field_ok
                metric_values["target_accuracy"] = 1.0 if field_ok else 0.0
            if not field_ok:
                diagnostics.append(
                    f"{field} mismatch: expected {expected_value!r}, got {actual_value!r}"
                )

        return EvalCaseResult(
            case_id=case.id,
            suite=case.suite,
            passed=route_ok and target_ok and not diagnostics,
            actual=actual,
            expected=expected,
            metric_values=metric_values,
            diagnostics=diagnostics,
            evaluator_id=self.evaluator_id,
            evaluator_version=self.evaluator_version,
            product_sha=product_sha,
            dataset_hash=dataset_hash,
            seed=seed,
            started_at=started_at,
            duration_ms=(perf_counter() - started) * 1000,
        )
