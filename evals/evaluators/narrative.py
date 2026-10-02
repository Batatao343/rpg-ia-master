"""Deterministic narrative-claim evaluator backed by canonical product state."""

from __future__ import annotations

from datetime import UTC, datetime
from time import perf_counter
from typing import Any

from evals.core.schemas import EVALUATOR_VERSION, EvalCase, EvalCaseResult
from evals.evaluators.exact import strict_equal


class NarrativeClaimEvaluator:
    """Score only labelled hard claims; subjective prose stays outside the gate."""

    evaluator_id = "narrative_claim_contract"
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
        if case.oracle != "narrative_claim":
            raise ValueError(f"narrative claim evaluator cannot evaluate {case.oracle!r}")
        started_at = datetime.now(UTC)
        started = perf_counter()
        if not isinstance(case.expected, dict):
            raise ValueError("narrative claim expected must be an object")
        required = {"accepted", "rejection_reasons"}
        allowed = required | {"sanitized_text", "forbidden_output_fragments"}
        if not required.issubset(case.expected) or not set(case.expected).issubset(allowed):
            raise ValueError("narrative claim expected has an invalid contract")
        expected_reasons = case.expected["rejection_reasons"]
        if not isinstance(case.expected["accepted"], bool):
            raise ValueError("expected accepted must be boolean")
        if not isinstance(expected_reasons, list) or any(
            not isinstance(reason, str) for reason in expected_reasons
        ):
            raise ValueError("expected rejection_reasons must be a string list")
        if len(expected_reasons) != len(set(expected_reasons)):
            raise ValueError("expected rejection_reasons must be unique")
        forbidden_fragments = case.expected.get("forbidden_output_fragments") or []
        if not isinstance(forbidden_fragments, list) or any(
            not isinstance(fragment, str) or not fragment.strip()
            for fragment in forbidden_fragments
        ):
            raise ValueError("forbidden_output_fragments must be non-empty strings")
        if len(forbidden_fragments) != len(set(forbidden_fragments)):
            raise ValueError("forbidden_output_fragments must be unique")
        if not isinstance(actual, dict):
            raise ValueError("narrative claim actual must be an object")
        reasons = actual.get("rejection_reasons")
        if not isinstance(actual.get("accepted"), bool) or not isinstance(reasons, list):
            raise ValueError("narrative claim actual requires accepted and rejection_reasons")
        if any(not isinstance(reason, str) for reason in reasons):
            raise ValueError("narrative rejection reasons must be strings")
        if len(reasons) != len(set(reasons)):
            raise ValueError("narrative rejection reasons must be unique")

        contract = {
            "accepted": actual["accepted"],
            "rejection_reasons": sorted(set(reasons)),
        }
        expected = {
            "accepted": case.expected["accepted"],
            "rejection_reasons": sorted(expected_reasons),
        }
        if "sanitized_text" in case.expected:
            if not isinstance(case.expected["sanitized_text"], str):
                raise ValueError("expected sanitized_text must be a string")
            if not isinstance(actual.get("sanitized_text"), str):
                raise ValueError("narrative guard actual requires sanitized_text")
            contract["sanitized_text"] = actual["sanitized_text"]
            expected["sanitized_text"] = case.expected["sanitized_text"]
        passed = strict_equal(contract, expected)
        sanitized = str(contract.get("sanitized_text", "")).casefold()
        forbidden_survived = any(
            fragment.casefold() in sanitized for fragment in forbidden_fragments
        )
        leaked_contradiction = float(
            expected["accepted"] is False
            and (
                contract["accepted"] is True
                or forbidden_survived
            )
        )
        metrics = {
            "narrative_claim_accuracy": 1.0 if passed else 0.0,
            "narrative_hard_contradictions": leaked_contradiction,
        }
        if "identity" in case.tags:
            metrics["npc_identity_errors"] = leaked_contradiction
        diagnostics: list[str] = []
        if leaked_contradiction:
            diagnostics.append("fixture-labelled hard contradiction crossed the product guard")
        elif not passed:
            diagnostics.append("hard claim decision or reason differs from fixture label")
        return EvalCaseResult(
            case_id=case.id,
            suite=case.suite,
            passed=passed,
            actual=actual,
            expected=case.expected,
            metric_values=metrics,
            diagnostics=diagnostics,
            evaluator_id=self.evaluator_id,
            evaluator_version=self.evaluator_version,
            product_sha=product_sha,
            dataset_hash=dataset_hash,
            seed=seed,
            started_at=started_at,
            duration_ms=(perf_counter() - started) * 1000,
        )
