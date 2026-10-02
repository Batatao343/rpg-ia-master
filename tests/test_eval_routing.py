"""Routing and structured action eval contracts (SPEC-169)."""

from __future__ import annotations

from collections import defaultdict
from pathlib import Path

from evals.core.adapters import AdapterCase, AdapterOutput, AdapterRegistry
from evals.core.governance import load_cases
from evals.core.runner import run_eval


ROOT = Path(__file__).resolve().parents[1]
DATASET = "datasets/regression/routing_actions.jsonl"
ROUTING_KEYS = {
    "route",
    "target",
    "loot_context",
    "combat_origin_hint",
    "flee_attempt",
    "flee_destination",
}


def test_routing_corpus_is_closed_sourced_and_covers_required_classes() -> None:
    cases = load_cases(ROOT / "evals" / DATASET)
    classification = [case for case in cases if case.oracle == "classification"]
    exact = [case for case in cases if case.oracle == "exact"]
    routes = {case.expected["route"] for case in classification}
    tags = {tag for case in cases for tag in case.tags}

    assert len(cases) == 25
    assert len(classification) == 21
    assert len(exact) == 4
    assert routes == {"storyteller", "combat_agent", "npc_actor", "loot"}
    assert {"negative", "structured-output", "normalization", "flee"}.issubset(tags)
    assert all(case.description and case.created_from for case in cases)
    assert all(case.source == "regression" for case in cases)
    assert all(case.oracle != "judge" for case in cases)


def test_metamorphic_variants_preserve_fixture_authored_expected() -> None:
    cases = load_cases(ROOT / "evals" / DATASET)
    groups: dict[str, list[object]] = defaultdict(list)
    for case in cases:
        for tag in case.tags:
            if tag.startswith("metamorphic:"):
                groups[tag].append(case.expected)

    assert set(groups) == {
        "metamorphic:story-travel",
        "metamorphic:combat-attack",
        "metamorphic:npc-corvo",
        "metamorphic:loot-treasure",
    }
    assert all(len(values) >= 2 for values in groups.values())
    assert all(all(value == values[0] for value in values) for values in groups.values())


def test_routing_dataset_emits_accuracy_and_confusion_matrix() -> None:
    result = run_eval(ROOT, datasets=[DATASET], run_id="routing-actions")

    assert result.passed is True
    assert len(result.results) == 25
    assert result.metric_values == {
        "exact_match": 1.0,
        "route_accuracy": 1.0,
        "target_accuracy": 1.0,
    }
    assert result.aggregates == {
        "route_confusion_matrix": {
            "combat_agent": {"combat_agent": 5},
            "loot": {"loot": 7},
            "npc_actor": {"npc_actor": 3},
            "storyteller": {"storyteller": 6},
        }
    }
    assert result.metadata.provider is None
    assert result.metadata.model is None


def test_routing_score_contains_only_pre_narration_structured_fields() -> None:
    result = run_eval(
        ROOT,
        datasets=[DATASET],
        suites={"routing"},
        run_id="routing-shape",
    )

    assert result.passed is True
    assert len(result.results) == 21
    assert all(set(case.actual) == ROUTING_KEYS for case in result.results)
    assert all(
        not ({"messages", "narrative", "reasoning", "confidence"} & set(case.actual))
        for case in result.results
    )


def test_invalid_structured_output_has_deterministic_diagnostic() -> None:
    result = run_eval(
        ROOT,
        datasets=[DATASET],
        case_ids={"action.decision.invalid-context"},
        run_id="invalid-router-decision",
    )

    assert result.passed is True
    assert result.results[0].actual == {
        "valid": False,
        "error_types": ["literal_error"],
    }
    assert result.case_diagnostics == {
        "action.decision.invalid-context": [
            "structured RouterDecision validation failed as expected"
        ]
    }


def test_known_bad_candidate_route_fails_without_oracle_access() -> None:
    class BrokenRoutingAdapter:
        adapter_id = "broken-routing"

        def execute(self, case: AdapterCase) -> AdapterOutput:
            assert not hasattr(case, "expected")
            assert not hasattr(case, "oracle")
            return AdapterOutput(
                actual={
                    "route": "loot",
                    "target": None,
                    "loot_context": None,
                    "combat_origin_hint": None,
                    "flee_attempt": False,
                    "flee_destination": None,
                }
            )

    result = run_eval(
        ROOT,
        datasets=[DATASET],
        case_ids={"routing.story.travel.base"},
        registry=AdapterRegistry({"routing": BrokenRoutingAdapter()}),
        run_id="known-bad-routing",
    )

    assert result.passed is False
    assert result.metric_values == {"route_accuracy": 0.0, "target_accuracy": 1.0}
    assert result.aggregates == {
        "route_confusion_matrix": {"storyteller": {"loot": 1}}
    }
    assert result.results[0].diagnostics == [
        "route mismatch: expected 'storyteller', got 'loot'"
    ]
    assert result.hard_failures == ["case failed: routing.story.travel.base"]
