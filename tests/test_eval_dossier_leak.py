"""Deterministic dossier leak eval contracts (SPEC-211 §5/R10)."""

from __future__ import annotations

import json
import os
from pathlib import Path

import pytest

from evals.core.adapters import AdapterCase, AdapterOutput, AdapterRegistry
from evals.core.governance import load_cases, load_metrics_registry
from evals.core.runner import run_eval
from evals.evaluators.dossier_leak import _MISSING, resolve_path


ROOT = Path(__file__).resolve().parents[1]
DATASET = "datasets/regression/dossier_leak.jsonl"
METRICS = (
    "dossier_leak_count",
    "dossier_tier_key_accuracy",
    "dossier_indistinguishability",
    "dossier_oracle_detection",
)


def test_corpus_covers_the_spec_211_evidence_list() -> None:
    cases = load_cases(ROOT / "evals" / DATASET)

    assert len(cases) == 28
    assert {case.oracle for case in cases} == {"dossier_leak"}
    assert {case.suite for case in cases} == {"dossier_leak"}
    assert {case.input["operation"] for case in cases} == {
        "project", "paired_project", "oracle_mutation",
    }
    tags = {tag for case in cases for tag in case.tags}
    assert {
        "hidden", "npc", "private", "bestiary", "tier", "overlay", "profile", "faction",
        "stale", "chronicle", "paired", "reveal", "oracle", "mutation", "art", "count",
        "known-good", "known-bad",
    } <= tags
    tiers = {
        spec["tier"]
        for case in cases
        for spec in (case.expected.get("creatures") or {}).values()
    }
    assert tiers == {1, 2, 3, 4}
    assert all(case.description and case.created_from for case in cases)


def test_corpus_passes_with_zero_leak() -> None:
    result = run_eval(ROOT, datasets=[DATASET], run_id="dossier-leak")

    assert result.passed is True
    assert result.error_case_ids == []
    assert len(result.results) == 28
    assert result.metric_values == {
        "dossier_leak_count": 0.0,
        "dossier_tier_key_accuracy": 1.0,
        "dossier_indistinguishability": 1.0,
        "dossier_oracle_detection": 1.0,
    }
    assert result.metadata.provider is None and result.metadata.model is None


def test_metrics_are_registered_as_blocking_hard_gates() -> None:
    registry = load_metrics_registry(ROOT / "evals" / "metrics-registry.yaml")
    for name in METRICS:
        definition = registry.metrics[name]
        assert definition.kind == "deterministic" and definition.blocking is True
    assert registry.metrics["dossier_leak_count"].hard_limit == 0.0
    for name in METRICS[1:]:
        assert registry.metrics[name].hard_limit == 1.0


def test_unfiltered_projection_is_a_hard_leak(monkeypatch) -> None:
    from services import player_knowledge as pk

    monkeypatch.setattr(pk, "entity_is_player_visible", lambda _eid, _state: True)
    monkeypatch.setattr(pk, "_mentions_hidden", lambda _text, _hidden: None)
    monkeypatch.setattr(pk, "_strict_unrevealed", lambda _text, _state: None)
    # Blind the product SPEC-206 oracle too: the evaluator's own fold must still catch it.
    monkeypatch.setattr(pk, "assert_no_player_leak", lambda _codex, _state: [])

    result = run_eval(
        ROOT,
        datasets=[DATASET],
        case_ids={"dl.hidden.visited_location_absent", "dl.hidden.npc_named_after_hidden_entity"},
        run_id="unfiltered-dossier",
    )

    assert result.passed is False
    assert result.metric_values["dossier_leak_count"] >= 1.0
    assert any("metric dossier_leak_count" in item for item in result.hard_failures)


def test_null_padded_tier_keys_fail_tier_accuracy(monkeypatch) -> None:
    from services import dossiers

    real = dossiers.creature_dossier

    def padded(entry, state):
        out = real(entry, state)
        for key in ("max_hp", "loot", "behavior"):
            out.setdefault(key, None)
        return out

    monkeypatch.setattr(dossiers, "creature_dossier", padded)
    result = run_eval(
        ROOT,
        datasets=[DATASET],
        case_ids={"dl.bestiary.tier1_keys_absent_not_null"},
        run_id="padded-tier",
    )

    assert result.passed is False
    assert result.metric_values["dossier_tier_key_accuracy"] == 0.0


def test_shared_overlay_in_db_profile_is_a_leak(monkeypatch) -> None:
    from services import dossiers

    real_getenv = os.getenv

    def legacy_always(key, default=None):
        return "legacy" if key == "RPG_RUNTIME_PROFILE" else real_getenv(key, default)

    monkeypatch.setattr(dossiers.os, "getenv", legacy_always)
    result = run_eval(
        ROOT,
        datasets=[DATASET],
        case_ids={"dl.bestiary.db_profile_overlay_not_shared"},
        run_id="shared-overlay",
    )

    assert result.passed is False
    assert result.metric_values["dossier_tier_key_accuracy"] == 0.0


def test_hidden_entity_changing_the_payload_fails_indistinguishability() -> None:
    class Drift:
        adapter_id = "drift"

        def execute(self, case: AdapterCase) -> AdapterOutput:
            from evals.core.adapters import DossierLeakAdapter

            actual = dict(DossierLeakAdapter().execute(case).actual)
            if case.input["operation"] == "paired_project":
                first = json.loads(actual["payload_jsons"][0])
                first["version"] = first["version"] + 1
                actual["payload_jsons"] = [json.dumps(first, sort_keys=True),
                                           actual["payload_jsons"][1]]
            return AdapterOutput(actual=actual)

    result = run_eval(
        ROOT,
        datasets=[DATASET],
        case_ids={"dl.paired.hidden_location_equals_nonexistent"},
        registry=AdapterRegistry({"dossier_leak": Drift()}),
        run_id="paired-drift",
    )

    assert result.passed is False
    assert result.metric_values["dossier_indistinguishability"] == 0.0


def test_blind_product_oracles_fail_detection(monkeypatch) -> None:
    monkeypatch.setattr(
        "services.dossier_visibility.assert_no_private_fields", lambda _payload: []
    )
    monkeypatch.setattr(
        "services.player_knowledge.assert_no_player_leak", lambda _codex, _state: []
    )
    result = run_eval(
        ROOT,
        datasets=[DATASET],
        case_ids={
            "dl.mutation.hidden_trait_key_flagged",
            "dl.mutation.hidden_name_in_prose_flagged",
            "dl.mutation.clean_payload_not_flagged",
        },
        run_id="blind-oracles",
    )

    assert result.passed is False
    assert result.metric_values["dossier_oracle_detection"] == pytest.approx(1 / 3)


def test_adapter_error_counts_as_a_leak_not_a_pass() -> None:
    class Broken:
        adapter_id = "broken"

        def execute(self, _case: AdapterCase) -> AdapterOutput:
            raise RuntimeError("boom")

    result = run_eval(
        ROOT,
        datasets=[DATASET],
        case_ids={"dl.hidden.visited_location_absent"},
        registry=AdapterRegistry({"dossier_leak": Broken()}),
        run_id="broken-adapter",
    )

    assert result.passed is False
    assert result.error_case_ids == ["dl.hidden.visited_location_absent"]
    assert result.metric_values["dossier_leak_count"] == 1.0


def test_resolve_path_walks_dicts_and_lists() -> None:
    value = {"a": [{"b": 1}]}
    assert resolve_path(value, "a.0.b") == 1
    assert resolve_path(value, "a.1.b") is _MISSING
    assert resolve_path(value, "a.x") is _MISSING
