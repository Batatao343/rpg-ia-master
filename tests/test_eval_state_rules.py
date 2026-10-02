"""Structured state/rules/persistence eval corpus contracts (SPEC-168)."""

from __future__ import annotations

from pathlib import Path

from evals.core.adapters import AdapterCase, AdapterOutput, AdapterRegistry
from evals.core.governance import load_cases
from evals.core.runner import run_eval


ROOT = Path(__file__).resolve().parents[1]
DATASET = "datasets/regression/state_rules.jsonl"


def test_state_rules_corpus_covers_declared_domains_without_judge() -> None:
    cases = load_cases(ROOT / "evals" / DATASET)
    tags = {tag for case in cases for tag in case.tags}

    assert len(cases) == 12
    assert {
        "state",
        "rules",
        "gold",
        "inventory",
        "unique-item",
        "lifecycle",
        "downed",
        "death",
        "quest",
        "reward",
        "combat",
        "persistence",
        "save-load",
        "restore",
        "idempotency",
        "replay",
        "invariants",
    }.issubset(tags)
    assert all(case.oracle in {"projection", "exact"} for case in cases)
    assert all(case.source == "regression" for case in cases)


def test_state_rules_dataset_passes_as_structured_projections() -> None:
    result = run_eval(ROOT, datasets=[DATASET], run_id="state-rules")

    assert result.passed is True
    assert len(result.results) == 12
    assert result.metric_values == {
        "exact_match": 1.0,
        "state_transition_pass_rate": 1.0,
    }
    assert result.metadata.provider is None
    assert result.metadata.model is None
    assert {case.evaluator_id for case in result.results} == {
        "exact",
        "state_projection",
    }


def test_projection_cases_emit_only_declared_contract_shapes() -> None:
    result = run_eval(
        ROOT,
        datasets=[DATASET],
        case_ids={"state.event.npc-killed", "state.persistence.save-load"},
        run_id="projection-shapes",
    )
    by_id = {case.case_id: case.actual for case in result.results}

    assert by_id["state.event.npc-killed"] == {
        "projection": {"entities.npc_grum.alive": False},
        "input_unchanged": True,
        "idempotent": None,
    }
    assert set(by_id["state.persistence.save-load"]["state"]) == {
        "game_id",
        "player.gold",
        "world.current_location",
        "world_projection.unique_items.artefato_unico.holder",
        "processed_action_ids",
    }


def test_known_bad_candidate_projection_fails_without_oracle_access() -> None:
    class BrokenStateAdapter:
        adapter_id = "broken-state"

        def execute(self, case: AdapterCase) -> AdapterOutput:
            assert not hasattr(case, "expected")
            return AdapterOutput(
                actual={"projection": {}, "input_unchanged": True, "idempotent": None}
            )

    result = run_eval(
        ROOT,
        datasets=[DATASET],
        case_ids={"state.event.npc-killed"},
        registry=AdapterRegistry({"state_rules": BrokenStateAdapter()}),
        run_id="known-bad-state",
    )

    assert result.passed is False
    assert result.metric_values == {"state_transition_pass_rate": 0.0}
    assert result.results[0].diagnostics == [
        "actual projection != fixture-authored expected"
    ]
    assert result.hard_failures == ["case failed: state.event.npc-killed"]
