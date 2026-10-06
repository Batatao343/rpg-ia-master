"""SPEC-178: paired, live routing experiment over the locked regression corpus.

Run explicitly with ``uv run python -m evals.experiments.jev_router_ab``.
This module does not change the product router or the protected eval ruler.
"""

from __future__ import annotations

import argparse
import copy
from contextlib import contextmanager
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import time
from typing import Any, Iterator
from uuid import uuid4

from dotenv import load_dotenv

from evals.core.adapters import AdapterCase, RoutingAdapter
from evals.core.governance import load_cases, validate_repository
from evals.core.hashing import repository_identity, sha256_file
from services.jev_decision import (
    ChoiceAnswer, ChoiceQuestion, DecisionRequest, DecisionState,
    JevDecisionBackend, JevError,
)


ROOT = Path(__file__).resolve().parents[2]
DATASET = ROOT / "evals/datasets/regression/routing_actions.jsonl"
ROUTES = ("storyteller", "combat_agent", "npc_actor", "loot", "none")
QUESTION = ChoiceQuestion(
    instructions=(
        "Classifique a intenção da última ação do jogador de RPG. Escolha uma rota. "
        "COMBAT para atacar, sacar arma ou reagir a ameaça; NPC para conversa social; "
        "LOOT para vasculhar, pegar, comprar, vender ou criar; STORY para movimento, "
        "exploração e observação. Escolha none se não houver intenção clara."
    ),
    criteria={
        "storyteller": "Movimentação, exploração ou observar o cenário",
        "combat_agent": "Atacar, sacar arma ou reagir a ameaça",
        "npc_actor": "Conversa social ou diplomacia",
        "loot": "Vasculhar, pegar item, comprar, vender ou criar",
        "none": "Nenhuma intenção clara",
    },
)


class ExperimentBlocked(RuntimeError):
    """A run cannot complete within provider/configuration/budget constraints."""

    def __init__(self, message: str, record: dict[str, Any] | None = None) -> None:
        super().__init__(message)
        self.record = record


class _ClassifierReached(BaseException):
    """Probe sentinel bypasses the product router's broad Exception fallback."""


@dataclass
class Budget:
    max_calls: int = 100
    max_cost_usd: float = 1.0
    calls: int = 0
    reported_cost_usd: float | None = None
    # A reservation is a stop rule, not a claim of actual provider cost.
    reserved_per_call_usd: float = 0.01
    exhausted: bool = False

    def consume(self) -> None:
        if (self.calls >= self.max_calls or
                (self.reported_cost_usd is not None and
                 self.reported_cost_usd + self.reserved_per_call_usd > self.max_cost_usd) or
                (self.calls + 1) * self.reserved_per_call_usd > self.max_cost_usd):
            self.exhausted = True
            raise ExperimentBlocked("external call or reserved spending cap reached")
        self.calls += 1

    def record_cost(self, cost_usd: float | None) -> None:
        if cost_usd is None:
            return
        if cost_usd < 0:
            raise ExperimentBlocked("provider reported negative cost")
        self.reported_cost_usd = (self.reported_cost_usd or 0.0) + cost_usd
        if self.reported_cost_usd > self.max_cost_usd:
            self.exhausted = True
            raise ExperimentBlocked("reported spending cap exceeded")


def _candidate(case: Any) -> AdapterCase:
    """Only input and opaque case id enter a product candidate; no labels or hints."""
    return AdapterCase(
        id=hashlib.sha256(case.id.encode("utf-8")).hexdigest()[:16],
        suite="routing", description="", fixture=None,
        input=copy.deepcopy(case.input), tags=(), source="", created_from=None,
    )


def _cases() -> tuple[list[Any], str]:
    manifest = validate_repository(ROOT / "evals")
    digest = sha256_file(DATASET)
    if manifest["datasets"]["datasets/regression/routing_actions.jsonl"] != digest:
        raise ExperimentBlocked("locked routing dataset hash mismatch")
    cases = [
        case for case in load_cases(DATASET)
        if case.oracle == "classification" and case.input.get("operation") == "route"
    ]
    if len(cases) != 21:
        raise ExperimentBlocked(f"expected 21 classification route cases; got {len(cases)}")
    return cases, digest


def _eligible(case: Any) -> tuple[bool, str | None]:
    import agents.router as router

    original = router.get_llm

    def reached(*_args: Any, **_kwargs: Any) -> Any:
        raise _ClassifierReached

    try:
        router.get_llm = reached
        try:
            actual = RoutingAdapter().execute(_candidate(case)).actual
        except _ClassifierReached:
            return True, None
        return False, actual["route"]
    finally:
        router.get_llm = original


def preflight() -> dict[str, Any]:
    cases, digest = _cases()
    gates = {case.id: _eligible(case) for case in cases}
    return {
        "dataset_hash": digest,
        "case_ids": [case.id for case in cases],
        "eligible_ids": [case.id for case in cases if gates[case.id][0]],
        "gated_routes": {case.id: gates[case.id][1] for case in cases if not gates[case.id][0]},
    }


@contextmanager
def _capture_classify(budget: Budget) -> Iterator[dict[str, Any]]:
    """Capture each actual provider attempt and enforce the cap before network I/O."""
    import agents.router as router
    import llm_setup
    from agents.router import RouterDecision

    original_get = router.get_llm
    original_invoke = llm_setup.RoutedLLM.invoke
    original_normalize = llm_setup.RoutedLLM._normalize_internal_structured_result
    original_slot = llm_setup._provider_slot
    original_hook = llm_setup._ATTEMPT_TELEMETRY_HOOK
    capture: dict[str, Any] = {
        "attempts": [], "confidence": None, "fatal_sanity_error": False, "usage_rows": [],
    }

    def real_only(*args: Any, **kwargs: Any) -> Any:
        llm = original_get(*args, **kwargs)
        if not isinstance(llm, llm_setup.RoutedLLM) or not llm.candidates:
            raise ExperimentBlocked("CLASSIFY has no real routed provider")
        return llm

    def invoke(self: Any, value: Any) -> Any:
        result = original_invoke(self, value)
        if isinstance(result, RouterDecision):
            capture["confidence"] = result.confidence
        return result

    def normalize(self: Any, result: Any) -> Any:
        raw = result.get("raw") if isinstance(result, dict) else result
        usage = getattr(raw, "usage_metadata", None) or (
            (getattr(raw, "response_metadata", None) or {}).get("token_usage")
        )
        if isinstance(usage, dict):
            input_tokens = usage.get("input_tokens", usage.get("prompt_tokens"))
            output_tokens = usage.get("output_tokens", usage.get("completion_tokens"))
            if isinstance(input_tokens, int) and isinstance(output_tokens, int):
                capture["usage_rows"].append({
                    "input_tokens": input_tokens, "output_tokens": output_tokens,
                })
        return original_normalize(self, result)

    @contextmanager
    def slot(provider: str) -> Iterator[None]:
        budget.consume()
        with original_slot(provider):
            yield

    def attempt(event: Any) -> None:
        error_text = str(event.error or "").lower()
        if event.outcome == "build_error" or (
            event.outcome != "success" and any(
                marker in error_text for marker in
                ("401", "402", "429", "api key", "api_key", "authentication",
                 "unauthorized", "quota", "insufficient credit", "configuration")
            )
        ):
            capture["fatal_sanity_error"] = True
        capture["attempts"].append({
            "provider": event.provider, "model": event.model,
            "attempt_index": event.attempt_index, "latency_ms": event.latency_ms,
            "fell_back": event.fell_back, "outcome": event.outcome,
            "failure_code": event.structured_failure_code,
        })

    try:
        router.get_llm = real_only
        llm_setup.RoutedLLM.invoke = invoke
        llm_setup.RoutedLLM._normalize_internal_structured_result = normalize
        llm_setup._provider_slot = slot
        llm_setup.set_llm_attempt_telemetry_hook(attempt)
        yield capture
    finally:
        router.get_llm = original_get
        llm_setup.RoutedLLM.invoke = original_invoke
        llm_setup.RoutedLLM._normalize_internal_structured_result = original_normalize
        llm_setup._provider_slot = original_slot
        llm_setup.set_llm_attempt_telemetry_hook(original_hook)


def _arm_a(case: Any, budget: Budget) -> dict[str, Any]:
    start = time.perf_counter()
    with _capture_classify(budget) as capture:
        try:
            actual = RoutingAdapter().execute(_candidate(case)).actual
        except Exception as exc:
            raise ExperimentBlocked(
                f"CLASSIFY failed for {case.id}: {type(exc).__name__}",
                _error_result(str(exc), round((time.perf_counter() - start) * 1000), capture["attempts"]),
            ) from exc
    if budget.exhausted:
        message = "CLASSIFY exhausted external call cap"
        raise ExperimentBlocked(
            message,
            _error_result(message, round((time.perf_counter() - start) * 1000), capture["attempts"]),
        )
    attempts = capture["attempts"]
    if not any(row["outcome"] == "success" for row in attempts):
        message = f"CLASSIFY did not return a real structured decision: {case.id}"
        raise ExperimentBlocked(
            message, _error_result(message, round((time.perf_counter() - start) * 1000), attempts),
        )
    return {
        "route": actual["route"], "confidence": capture["confidence"],
        "probabilities": "unavailable", "latency_ms": round((time.perf_counter() - start) * 1000),
        "attempts": attempts, "provider": next(row["provider"] for row in attempts if row["outcome"] == "success"),
        "model": next(row["model"] for row in attempts if row["outcome"] == "success"),
        "usage": capture["usage_rows"] or "unavailable",
        "cost_usd": "unavailable", "error": None,
        "fatal_sanity_error": capture["fatal_sanity_error"],
    }


def _arm_b(case: Any, backend: JevDecisionBackend, budget: Budget, run_id: str) -> dict[str, Any]:
    start = time.perf_counter()
    value = _candidate(case).input
    state = value.get("state") or {}
    world = state.get("world") or {"current_location": "Aethelgard"}
    request = DecisionRequest(
        state=DecisionState(
            action=str(value.get("action") or ""),
            location_id=str(world.get("current_location") or "Aethelgard"),
            in_combat=bool((state.get("combat") or {}).get("active")),
            active_npc=state.get("active_npc_name"),
        ),
        questions={"route": QUESTION},
    )
    budget.consume()
    try:
        result = backend.decide(request, idempotency_key=f"{run_id}-{case.id}".replace("_", "-"))
    except JevError as exc:
        message = f"Jev {exc.code} for {case.id}"
        raise ExperimentBlocked(
            message,
            _error_result(message, round((time.perf_counter() - start) * 1000),
                          [{"provider": "jev", "model": request.model, "outcome": exc.code}]),
        ) from exc
    answer = result.answers["route"]
    if not isinstance(answer, ChoiceAnswer):
        raise ExperimentBlocked(f"Jev returned non-choice answer for {case.id}")
    record = {
        "route": "storyteller" if answer.choice == "none" else answer.choice,
        "raw_choice": answer.choice, "confidence": answer.confidence,
        "probabilities": answer.probabilities,
        "latency_ms": round((time.perf_counter() - start) * 1000),
        "provider_latency_ms": result.latency_ms,
        "attempts": [{"provider": "jev", "model": result.model, "outcome": "success"}],
        "provider": "jev", "model": result.model,
        "usage": result.usage.model_dump() if result.usage else "unavailable",
        "cost_usd": result.cost_usd if result.cost_usd is not None else "unavailable",
        "error": None,
    }
    try:
        budget.record_cost(result.cost_usd)
    except ExperimentBlocked as exc:
        record["error"] = str(exc)
        raise ExperimentBlocked(str(exc), record) from exc
    return record


def _error_result(message: str, latency_ms: int, attempts: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "route": None, "confidence": "unavailable", "probabilities": "unavailable",
        "latency_ms": latency_ms, "attempts": attempts,
        "provider": "unavailable", "model": "unavailable",
        "usage": "unavailable", "cost_usd": "unavailable", "error": message,
    }


def _write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    temporary.replace(path)


def _percentile(values: list[int], fraction: float) -> float | str:
    if not values:
        return "unavailable"
    ordered = sorted(values)
    rank = (len(ordered) - 1) * fraction
    lower = int(rank)
    return round(ordered[lower] + (ordered[min(lower + 1, len(ordered) - 1)] - ordered[lower]) * (rank - lower), 2)


def score(raw: dict[str, Any], cases: list[Any]) -> dict[str, Any]:
    """Only this post-persistence function reads the expected labels."""
    expected = {case.id: case.expected["route"] for case in cases}
    summary: dict[str, Any] = {"evidence_type": "development/regression", "promotion": False}
    for cohort in ("pipeline_full", "classifier_eligible"):
        rows = [
            row for replica in raw["replicas"] for row in replica["rows"]
            if (cohort == "pipeline_full" and row["replica"] == 1)
            or (cohort == "classifier_eligible" and row["eligible"])
        ]
        paired = [row for row in rows if row.get("a") and row.get("b")]
        cohort_summary: dict[str, Any] = {"paired_count": len(paired), "divergences": []}
        for arm in ("a", "b"):
            valid = [row for row in paired if row[arm]["route"] in ROUTES]
            confusion: dict[str, dict[str, int]] = {}
            for row in valid:
                truth = expected[row["case_id"]]
                route = row[arm]["route"]
                confusion.setdefault(truth, {})[route] = confusion.setdefault(truth, {}).get(route, 0) + 1
            latencies = [row[arm]["latency_ms"] for row in valid if row["eligible"]]
            cohort_summary[arm] = {
                "route_accuracy": (sum(row[arm]["route"] == expected[row["case_id"]] for row in valid) / len(valid)) if valid else "unavailable",
                "confusion_matrix": confusion,
                "backend_latency_ms_p50": _percentile(latencies, 0.5),
                "backend_latency_ms_p95": _percentile(latencies, 0.95),
                "failure_unavailable_rate": (len(paired) - len(valid)) / len(paired) if paired else "unavailable",
            }
        cohort_summary["divergences"] = [
            {"replica": row["replica"], "case_id": row["case_id"],
             "expected": expected[row["case_id"]], "a": row["a"]["route"], "b": row["b"]["route"]}
            for row in paired if row["a"]["route"] != row["b"]["route"]
        ]
        summary[cohort] = cohort_summary
    return summary


def run(output_dir: Path, budget: Budget | None = None) -> dict[str, Any]:
    local_env = ROOT / ".env"
    # The isolated checkout lives at <workspace>/.tmp/spec176-clone.
    checkout_env = ROOT.parent.parent / ".env" if ROOT.parent.name == ".tmp" else local_env
    load_dotenv(local_env if local_env.exists() else checkout_env, override=False)
    if os.getenv("RPG_FORCE_MOCK") or os.getenv("RPG_NO_MOCK") or os.getenv("LLM_PROVIDER"):
        raise ExperimentBlocked("mock/no-mock/provider override invalidates current CLASSIFY cascade")
    budget = budget or Budget()
    cases, dataset_hash = _cases()
    pre = preflight()
    eligible = set(pre["eligible_ids"])
    # Reserve 2 sanity requests plus 3 paired passes before any external call.
    minimum = 2 + 3 * 2 * len(eligible)
    if minimum > budget.max_calls or minimum * budget.reserved_per_call_usd > budget.max_cost_usd:
        raise ExperimentBlocked(f"minimum {minimum} calls exceed approved cap")
    output_dir.mkdir(parents=True, exist_ok=False)
    run_id = datetime.now(timezone.utc).strftime("SPEC-178-%Y%m%dT%H%M%SZ") + "-" + uuid4().hex[:8]
    product_sha, product_tree_hash, product_dirty = repository_identity(ROOT)
    raw: dict[str, Any] = {
        "run_id": run_id, "product_sha": product_sha,
        "product_tree_hash": product_tree_hash, "product_dirty": product_dirty,
        "dataset_hash": dataset_hash,
        "started_at": datetime.now(timezone.utc).isoformat(),
        "case_order": pre["case_ids"], "eligible_ids": pre["eligible_ids"],
        "gated_routes": pre["gated_routes"], "budget": asdict(budget),
        "sanity": {}, "replicas": [], "status": "in_progress",
    }
    raw_path = output_dir / "raw.json"
    _write_json(raw_path, raw)
    try:
        with JevDecisionBackend(max_retries=0) as backend:
            first = next(case for case in cases if case.id in eligible)
            try:
                raw["sanity"]["a"] = _arm_a(first, budget)
            except ExperimentBlocked as exc:
                raw["sanity"]["a"] = {"case_id": first.id, **(exc.record or _error_result(str(exc), 0, []))}
                raise
            _write_json(raw_path, raw)
            if raw["sanity"]["a"]["fatal_sanity_error"]:
                raise ExperimentBlocked("CLASSIFY sanity hit auth/quota/config failure")
            try:
                raw["sanity"]["b"] = _arm_b(first, backend, budget, run_id + "-sanity")
            except ExperimentBlocked as exc:
                raw["sanity"]["b"] = {"case_id": first.id, **(exc.record or _error_result(str(exc), 0, []))}
                raise
            _write_json(raw_path, raw)
            for number in range(1, 4):
                replica = {"run_id": f"{run_id}-replica-{number}", "rows": []}
                raw["replicas"].append(replica)
                for case in cases:
                    gate = case.id not in eligible
                    if gate and number > 1:
                        continue
                    row = {"replica": number, "case_id": case.id, "eligible": not gate}
                    replica["rows"].append(row)
                    if gate:
                        route = pre["gated_routes"][case.id]
                        row["a"] = row["b"] = {
                            "route": route, "confidence": "unavailable", "probabilities": "unavailable",
                            "latency_ms": 0, "attempts": [], "provider": "python_gate", "model": "unavailable",
                            "usage": "unavailable", "cost_usd": "unavailable", "error": None,
                        }
                    else:
                        try:
                            row["a"] = _arm_a(case, budget)
                        except ExperimentBlocked as exc:
                            row["a"] = exc.record or _error_result(str(exc), 0, [])
                            raise
                        _write_json(raw_path, raw)
                        try:
                            row["b"] = _arm_b(case, backend, budget, replica["run_id"])
                        except ExperimentBlocked as exc:
                            row["b"] = exc.record or _error_result(str(exc), 0, [])
                            raise
                    _write_json(raw_path, raw)
        raw["status"] = "complete"
    except (ExperimentBlocked, JevError) as exc:
        raw["status"] = "blocked-by-provider"
        raw["blocker"] = str(exc)
    finally:
        raw["budget"] = asdict(budget)
        _write_json(raw_path, raw)
    if raw["status"] == "complete":
        # The raw artifact is already durable when the scorer sees any oracle.
        _write_json(output_dir / "summary.json", score(raw, cases))
    return raw


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--preflight", action="store_true")
    parser.add_argument("--output-dir", type=Path)
    parser.add_argument("--max-calls", type=int, default=100)
    parser.add_argument("--max-cost-usd", type=float, default=1.0)
    args = parser.parse_args()
    if args.preflight:
        print(json.dumps(preflight(), ensure_ascii=False, indent=2))
        return
    if args.output_dir is None:
        parser.error("--output-dir is required for live execution")
    if args.max_calls <= 0 or args.max_cost_usd <= 0:
        parser.error("call and spending caps must be positive")
    result = run(args.output_dir, Budget(max_calls=args.max_calls, max_cost_usd=args.max_cost_usd))
    print(json.dumps({"run_id": result["run_id"], "status": result["status"], "calls": result["budget"]["calls"]}))


if __name__ == "__main__":
    main()
