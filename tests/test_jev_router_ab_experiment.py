"""Offline checks for the opt-in SPEC-178 experiment protocol."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from evals.experiments import jev_router_ab as experiment
from services.jev_decision import ChoiceAnswer, DecisionResult, Usage


def test_preflight_proves_classifier_eligibility_without_calling_provider(monkeypatch: pytest.MonkeyPatch) -> None:
    import agents.router as router

    def forbidden(*_args: object, **_kwargs: object) -> object:
        raise AssertionError("real provider reached during preflight")

    monkeypatch.setattr(router, "get_llm", forbidden)
    preflight = experiment.preflight()
    assert len(preflight["case_ids"]) == 21
    assert len(preflight["eligible_ids"]) == 16
    assert len(preflight["gated_routes"]) == 5
    assert router.get_llm is forbidden


def test_candidate_never_contains_expected_or_oracle() -> None:
    cases, _digest = experiment._cases()
    candidate = experiment._candidate(cases[0])
    assert candidate.input == cases[0].input
    assert candidate.input is not cases[0].input
    assert candidate.description == ""
    assert candidate.tags == ()
    assert "expected" not in vars(candidate)
    assert "oracle" not in vars(candidate)


def test_budget_stops_before_next_external_call() -> None:
    budget = experiment.Budget(max_calls=2, max_cost_usd=0.02)
    budget.consume()
    budget.consume()
    with pytest.raises(experiment.ExperimentBlocked):
        budget.consume()
    assert budget.calls == 2
    assert budget.exhausted


def test_raw_write_retries_transient_windows_replace_lock(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    path = tmp_path / "raw.json"
    experiment._write_json(path, {"status": "in_progress"})
    original_replace = Path.replace
    attempts = 0

    def locked_once(source: Path, target: Path) -> Path:
        nonlocal attempts
        attempts += 1
        if attempts == 1:
            raise PermissionError("transient sync lock")
        return original_replace(source, target)

    monkeypatch.setattr(Path, "replace", locked_once)
    experiment._write_json(path, {"status": "blocked-by-provider", "calls": 2})
    assert attempts == 2
    assert json.loads(path.read_text(encoding="utf-8")) == {
        "status": "blocked-by-provider", "calls": 2,
    }
    assert not path.with_suffix(".json.tmp").exists()


def test_reported_cost_is_not_treated_as_zero() -> None:
    budget = experiment.Budget(max_calls=100, max_cost_usd=0.02)
    assert budget.reported_cost_usd is None
    budget.record_cost(0.015)
    with pytest.raises(experiment.ExperimentBlocked):
        budget.consume()
    assert budget.calls == 0


def test_capture_marks_build_failure_fatal_and_keeps_raw_usage() -> None:
    import llm_setup
    from agents.router import RouterDecision
    from langchain_core.messages import AIMessage

    budget = experiment.Budget()
    with experiment._capture_classify(budget) as capture:
        llm_setup._emit_attempt_telemetry(llm_setup.LLMAttemptEvent(
            provider="missing", model="missing", tier=llm_setup.ModelTier.CLASSIFY,
            attempt_index=0, latency_ms=0, fell_back=False,
            outcome="build_error", error="No module named provider", structured=True,
        ))
        routed = llm_setup.RoutedLLM(llm_setup.ModelTier.CLASSIFY, 0.0, [])
        routed = routed.with_structured_output(RouterDecision)
        routed._normalize_internal_structured_result({
            "raw": AIMessage(content="", usage_metadata={"input_tokens": 12, "output_tokens": 3, "total_tokens": 15}),
            "parsed": RouterDecision(route="storyteller", loot_context=None, target=None,
                                     reasoning="test", confidence=0.9),
            "parsing_error": None,
        })
    assert capture["fatal_sanity_error"]
    assert capture["usage_rows"] == [{"input_tokens": 12, "output_tokens": 3}]


def test_jev_over_budget_keeps_observed_response() -> None:
    case = next(case for case in experiment._cases()[0] if case.id == experiment.preflight()["eligible_ids"][0])

    class Backend:
        def decide(self, *_args: object, **_kwargs: object) -> DecisionResult:
            return DecisionResult(
                model="fixture-model",
                answers={"route": ChoiceAnswer(
                    type="choice", choice="storyteller",
                    probabilities={route: (1.0 if route == "storyteller" else 0.0)
                                   for route in experiment.ROUTES},
                    confidence=1.0,
                )},
                usage=Usage(input_tokens=12, output_tokens=3),
                correlation_id="fixture", latency_ms=5, cost_usd=2.0,
            )

    budget = experiment.Budget(max_cost_usd=1.0)
    with pytest.raises(experiment.ExperimentBlocked) as error:
        experiment._arm_b(case, Backend(), budget, "fixture")
    assert error.value.record is not None
    assert error.value.record["model"] == "fixture-model"
    assert error.value.record["usage"] == {"input_tokens": 12, "output_tokens": 3}
    assert error.value.record["cost_usd"] == 2.0
    assert budget.reported_cost_usd == 2.0


def test_raw_is_durable_before_scoring_and_all_pairs_keep_order(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("RPG_FORCE_MOCK", raising=False)
    monkeypatch.delenv("RPG_NO_MOCK", raising=False)
    monkeypatch.delenv("LLM_PROVIDER", raising=False)
    cases, _digest = experiment._cases()
    expected_order = [case.id for case in cases]

    class OfflineBackend:
        def __init__(self, **_kwargs: object) -> None:
            pass

        def __enter__(self) -> OfflineBackend:
            return self

        def __exit__(self, *_args: object) -> None:
            pass

    def actual(case: object, _budget: object, *_args: object) -> dict[str, object]:
        assert getattr(case, "id") in expected_order
        return {
            "route": "storyteller", "confidence": 0.5, "probabilities": "unavailable",
            "latency_ms": 10, "attempts": [{"provider": "offline", "outcome": "success"}],
            "provider": "offline", "model": "fake", "usage": "unavailable",
            "cost_usd": "unavailable", "error": None, "fatal_sanity_error": False,
        }

    monkeypatch.setattr(experiment, "JevDecisionBackend", OfflineBackend)
    monkeypatch.setattr(experiment, "_arm_a", actual)
    monkeypatch.setattr(experiment, "_arm_b", actual)
    original_score = experiment.score
    output_dir = tmp_path / "experiment"

    def checked_score(raw: dict, loaded_cases: list) -> dict:
        assert (output_dir / "raw.json").exists()
        persisted = json.loads((output_dir / "raw.json").read_text(encoding="utf-8"))
        assert persisted["status"] == "complete"
        assert persisted["replicas"] == raw["replicas"]
        return original_score(raw, loaded_cases)

    monkeypatch.setattr(experiment, "score", checked_score)
    raw = experiment.run(output_dir)
    assert raw["status"] == "complete"
    assert len(raw["replicas"]) == 3
    assert [row["case_id"] for row in raw["replicas"][0]["rows"]] == expected_order
    for replica in raw["replicas"][1:]:
        assert [row["case_id"] for row in replica["rows"]] == raw["eligible_ids"]
    summary = json.loads((output_dir / "summary.json").read_text(encoding="utf-8"))
    assert summary["pipeline_full"]["paired_count"] == 21
    assert summary["classifier_eligible"]["paired_count"] == 48


def test_incomplete_run_has_no_score(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("RPG_FORCE_MOCK", raising=False)
    monkeypatch.delenv("RPG_NO_MOCK", raising=False)
    monkeypatch.delenv("LLM_PROVIDER", raising=False)

    class OfflineBackend:
        def __init__(self, **_kwargs: object) -> None:
            pass

        def __enter__(self) -> OfflineBackend:
            return self

        def __exit__(self, *_args: object) -> None:
            pass

    def rejected(*_args: object, **_kwargs: object) -> dict:
        raise experiment.ExperimentBlocked("authentication")

    monkeypatch.setattr(experiment, "JevDecisionBackend", OfflineBackend)
    monkeypatch.setattr(experiment, "_arm_a", rejected)
    output_dir = tmp_path / "experiment"
    raw = experiment.run(output_dir)
    assert raw["status"] == "blocked-by-provider"
    assert json.loads((output_dir / "raw.json").read_text(encoding="utf-8"))["status"] == "blocked-by-provider"
    assert not (output_dir / "summary.json").exists()
