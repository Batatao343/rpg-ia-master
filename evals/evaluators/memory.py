"""Deterministic memory-write and evidence-ranking evaluators."""

from __future__ import annotations

from datetime import UTC, datetime
from time import perf_counter
from typing import Any

from evals.core.schemas import EVALUATOR_VERSION, EvalCase, EvalCaseResult
from evals.evaluators.exact import strict_equal


class MemoryWriteEvaluator:
    evaluator_id = "memory_write_contract"
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
        if case.oracle != "memory_write":
            raise ValueError(f"memory write evaluator cannot evaluate {case.oracle!r}")
        started_at = datetime.now(UTC)
        started = perf_counter()
        passed = strict_equal(actual, case.expected)
        return EvalCaseResult(
            case_id=case.id,
            suite=case.suite,
            passed=passed,
            actual=actual,
            expected=case.expected,
            metric_values={"memory_write_precision": 1.0 if passed else 0.0},
            diagnostics=[] if passed else ["memory write decisions != fixture labels"],
            evaluator_id=self.evaluator_id,
            evaluator_version=self.evaluator_version,
            product_sha=product_sha,
            dataset_hash=dataset_hash,
            seed=seed,
            started_at=started_at,
            duration_ms=(perf_counter() - started) * 1000,
        )


class RetrievalEvaluator:
    """Score evidence IDs without looking at generated prose."""

    evaluator_id = "evidence_ranking"
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
        if case.oracle != "ranking":
            raise ValueError(f"retrieval evaluator cannot evaluate {case.oracle!r}")
        started_at = datetime.now(UTC)
        started = perf_counter()
        expected = case.expected
        if not isinstance(expected, dict):
            raise ValueError("ranking expected must be an object")
        if not isinstance(actual, dict) or not isinstance(actual.get("ranked_ids"), list):
            raise ValueError("ranking actual must contain ranked_ids")

        ranked = [str(value) for value in actual["ranked_ids"]]
        if len(ranked) != len(set(ranked)):
            raise ValueError("ranking actual contains duplicate evidence IDs")

        labelled: dict[str, list[str]] = {}
        for field in ("required_ids", "acceptable_ids", "forbidden_ids", "secret_ids"):
            raw = expected.get(field) or []
            if not isinstance(raw, list) or any(not isinstance(value, str) for value in raw):
                raise ValueError(f"ranking expected.{field} must be a string list")
            if len(raw) != len(set(raw)):
                raise ValueError(f"ranking expected.{field} contains duplicate IDs")
            labelled[field] = list(raw)
        required = labelled["required_ids"]
        acceptable = set(labelled["acceptable_ids"])
        forbidden = set(labelled["forbidden_ids"])
        secret = set(labelled["secret_ids"])
        if set(required) & acceptable or set(required) & forbidden or acceptable & forbidden:
            raise ValueError("required, acceptable and forbidden evidence IDs must be disjoint")
        if not secret.issubset(forbidden):
            raise ValueError("secret_ids must be a subset of forbidden_ids")
        diagnostics: list[str] = []
        metrics: dict[str, float] = {}

        if required:
            required_set = set(required)
            recalls = {
                cutoff: len(required_set.intersection(ranked[:cutoff])) / len(required_set)
                for cutoff in (1, 3, 5)
            }
            reciprocal_rank = next(
                (1.0 / rank for rank, evidence_id in enumerate(ranked, start=1)
                 if evidence_id in required_set),
                0.0,
            )
            if case.suite == "memory_retrieval":
                metrics.update({
                    "memory_recall_at_1": recalls[1],
                    "memory_recall_at_3": recalls[3],
                    "memory_recall_at_5": recalls[5],
                    "memory_mrr": reciprocal_rank,
                })
            elif case.suite == "context_grounding":
                metrics["context_recall_at_5"] = recalls[5]
            missing = [evidence_id for evidence_id in required if evidence_id not in ranked[:5]]
            if missing:
                diagnostics.append("required evidence absent from top 5: " + ", ".join(missing))

        leaked = [evidence_id for evidence_id in ranked if evidence_id in forbidden]
        secret_leaks = [evidence_id for evidence_id in ranked if evidence_id in secret]
        metrics["context_forbidden_leak_rate"] = len(leaked) / max(1, len(ranked))
        metrics["secret_leak_count"] = float(len(secret_leaks))
        within_budget = bool(actual.get("within_budget", True))
        if case.suite == "context_grounding":
            metrics["context_token_budget_violation"] = 0.0 if within_budget else 1.0
        if leaked:
            diagnostics.append("forbidden evidence leaked: " + ", ".join(leaked))
        if secret_leaks:
            diagnostics.append("secret evidence leaked: " + ", ".join(secret_leaks))
        if not within_budget:
            diagnostics.append("context token budget exceeded")

        hard_failure = bool(leaked or secret_leaks or not within_budget)
        return EvalCaseResult(
            case_id=case.id,
            suite=case.suite,
            passed=not hard_failure,
            actual=actual,
            expected=expected,
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
