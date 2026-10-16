"""Deterministic encounter-manifest eval contracts (SPEC-203 §5/§9)."""

from __future__ import annotations

from pathlib import Path

from evals.core.adapters import AdapterCase, AdapterError, default_registry
from evals.core.governance import load_cases
from evals.core.runner import run_eval

import pytest


ROOT = Path(__file__).resolve().parents[1]
DATASET = "datasets/regression/encounter_manifest.jsonl"


def test_corpus_covers_the_spec_203_handoff_list() -> None:
    cases = load_cases(ROOT / "evals" / DATASET)

    assert len(cases) == 31
    assert {case.suite for case in cases} == {"encounter_manifest"}
    assert {case.oracle for case in cases} == {"projection"}
    assert {case.input["operation"] for case in cases} == {
        "roster_rounds", "reload_phase", "router_resume", "legacy_load",
        "phase_cycle", "build_result", "species_drift",
    }
    phases = {
        case.input["phase"] for case in cases if case.input["operation"] == "reload_phase"
    }
    assert phases == {"entering", "active", "resolving", "ended"}
    tags = {tag for case in cases for tag in case.tags}
    assert {"roster", "identity", "reload", "router", "death", "legacy", "phase",
            "result", "xp", "species-drift", "narrative", "oracle",
            "known-good", "known-bad"} <= tags
    assert all(case.description and case.created_from for case in cases)


def test_corpus_passes_fully() -> None:
    result = run_eval(ROOT, datasets=[DATASET], run_id="encounter-manifest")

    assert result.passed is True
    assert result.error_case_ids == []
    assert len(result.results) == 31
    assert result.metric_values == {"state_transition_pass_rate": 1.0}


def test_adapter_reports_a_regression_instead_of_hiding_it() -> None:
    adapter = default_registry().resolve("encounter_manifest")
    case = AdapterCase(
        id="probe.drift", suite="encounter_manifest", description="probe", fixture=None,
        input={"operation": "species_drift",
               "manifest_enemies": [{"id": "enemy_bandido_1", "name": "Bandido"}],
               "text": "O corvo mergulha e bica seu ombro."},
        tags=(), source="synthetic", created_from=None,
    )
    actual = adapter.execute(case).actual
    assert actual["neutralized"] is True and actual["flagged_species"] == ["corvo"]


def test_adapter_fails_closed_on_unknown_operation() -> None:
    adapter = default_registry().resolve("encounter_manifest")
    case = AdapterCase(
        id="probe.unknown", suite="encounter_manifest", description="probe", fixture=None,
        input={"operation": "nope"}, tags=(), source="synthetic", created_from=None,
    )
    with pytest.raises(AdapterError):
        adapter.execute(case)
