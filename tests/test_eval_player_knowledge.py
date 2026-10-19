"""Deterministic player-knowledge Codex eval contracts (SPEC-206 §5/§9)."""

from __future__ import annotations

from pathlib import Path

import pytest

from evals.core.adapters import AdapterCase, AdapterOutput, AdapterRegistry
from evals.core.governance import load_cases, load_metrics_registry
from evals.core.runner import run_eval
from evals.evaluators.player_knowledge import fold_text

ROOT = Path(__file__).resolve().parents[1]
DATASET = "datasets/regression/player_knowledge.jsonl"
METRICS = (
    "player_knowledge_leak_count",
    "player_knowledge_kind_accuracy",
    "player_knowledge_count_consistency",
    "player_knowledge_oracle_detection",
)


def test_corpus_covers_the_spec_206_evidence_list() -> None:
    cases = load_cases(ROOT / "evals" / DATASET)

    assert len(cases) == 29
    assert {case.oracle for case in cases} == {"player_knowledge"}
    assert {case.suite for case in cases} == {"player_knowledge"}
    assert {case.input["operation"] for case in cases} == {"project", "oracle_mutation"}
    tags = {tag for case in cases for tag in case.tags}
    assert {
        "hidden",
        "reveal",
        "payload",
        "prose",
        "rumor",
        "repeat",
        "legacy",
        "bestiary",
        "npc",
        "faction",
        "note",
        "signature",
        "normalization",
        "count",
        "oracle",
        "known-good",
        "known-bad",
    } <= tags
    oracle_classes = {
        item
        for case in cases
        if case.input["operation"] == "oracle_mutation"
        for item in case.expected["oracle_problem_classes"]
    }
    assert {
        "a:hidden_entity",
        "b:secret_signature",
        "c:count_mismatch",
        "c:meta_counts_missing",
        "d:fact_without_source",
        "d:kind_outside_taxonomy",
    } <= oracle_classes
    assert all(case.description and case.created_from for case in cases)


def test_corpus_passes_with_zero_leak_and_full_consistency() -> None:
    result = run_eval(ROOT, datasets=[DATASET], run_id="player-knowledge")

    assert result.passed is True
    assert result.error_case_ids == []
    assert len(result.results) == 29
    assert result.metric_values == {
        "player_knowledge_leak_count": 0.0,
        "player_knowledge_kind_accuracy": 1.0,
        "player_knowledge_count_consistency": 1.0,
        "player_knowledge_oracle_detection": 1.0,
    }
    assert result.metadata.provider is None and result.metadata.model is None


def test_metrics_are_registered_as_blocking_hard_gates() -> None:
    registry = load_metrics_registry(ROOT / "evals" / "metrics-registry.yaml")
    for name in METRICS:
        definition = registry.metrics[name]
        assert definition.kind == "deterministic" and definition.blocking is True
    assert registry.metrics["player_knowledge_leak_count"].hard_limit == 0.0
    assert registry.metrics["player_knowledge_count_consistency"].hard_limit == 1.0


def test_projection_without_visibility_filters_is_a_hard_leak(monkeypatch) -> None:
    from services import player_knowledge as pk

    monkeypatch.setattr(pk, "entity_is_player_visible", lambda _eid, _state: True)
    monkeypatch.setattr(pk, "_mentions_hidden", lambda _text, _hidden: None)
    monkeypatch.setattr(pk, "_strict_unrevealed", lambda _text, _state: None)
    # The product oracle is blinded too: the evaluator's own fold must still catch it.
    monkeypatch.setattr(pk, "assert_no_player_leak", lambda _codex, _state: [])

    result = run_eval(
        ROOT,
        datasets=[DATASET],
        case_ids={"pk.hidden.visited_location_omitted", "pk.signature.goal_omits_entry"},
        run_id="unfiltered-projection",
    )

    assert result.passed is False
    assert result.metric_values["player_knowledge_leak_count"] == 2.0
    assert any("metric player_knowledge_leak_count" in item for item in result.hard_failures)


def test_llm_payload_ids_releasing_a_secret_is_caught(monkeypatch) -> None:
    from services import memory_provenance

    real = memory_provenance.accepted_secret_ids

    def trusting_payload(state):
        revealed = set(real(state))
        for event in state.get("event_log") or []:
            payload = event.get("payload") or {}
            revealed.update(str(v) for v in payload.values())
        return revealed

    monkeypatch.setattr(memory_provenance, "accepted_secret_ids", trusting_payload)
    monkeypatch.setattr("services.player_knowledge.accepted_secret_ids", trusting_payload)

    result = run_eval(
        ROOT,
        datasets=[DATASET],
        case_ids={"pk.reveal.llm_payload_id_does_not_release"},
        run_id="payload-reveal",
    )

    assert result.passed is False
    assert result.metric_values["player_knowledge_leak_count"] == 1.0


def test_rumor_promoted_to_fact_fails_kind_accuracy(monkeypatch) -> None:
    from services import player_knowledge as pk

    real = pk.derive_stamp

    def promote(origin, record, state):
        stamp = real(origin, record, state)
        if stamp["knowledge_kind"] in {"rumor", "report"}:
            stamp = {**stamp, "knowledge_kind": "fact"}
        return stamp

    monkeypatch.setattr(pk, "derive_stamp", promote)
    result = run_eval(
        ROOT,
        datasets=[DATASET],
        case_ids={"pk.rumor.repeated_npc_claim_never_fact", "pk.rumor.bestiary_seen_only"},
        run_id="promoted-rumor",
    )

    assert result.passed is False
    assert result.metric_values["player_knowledge_kind_accuracy"] < 1.0


def test_count_drift_fails_consistency() -> None:
    class DriftAdapter:
        adapter_id = "drift"

        def execute(self, case: AdapterCase) -> AdapterOutput:
            from evals.core.adapters import PlayerKnowledgeAdapter

            actual = dict(PlayerKnowledgeAdapter().execute(case).actual)
            actual["counts"] = {**actual["counts"], "locations": 7}
            return AdapterOutput(actual=actual)

    result = run_eval(
        ROOT,
        datasets=[DATASET],
        case_ids={"pk.hidden.visited_location_omitted"},
        registry=AdapterRegistry({"player_knowledge": DriftAdapter()}),
        run_id="count-drift",
    )

    assert result.passed is False
    assert result.metric_values["player_knowledge_count_consistency"] == 0.0


def test_blind_oracle_fails_detection(monkeypatch) -> None:
    monkeypatch.setattr(
        "services.player_knowledge.assert_no_player_leak", lambda _codex, _state: []
    )
    result = run_eval(
        ROOT,
        datasets=[DATASET],
        case_ids={"pk.oracle.hidden_art_url", "pk.oracle.clean_projection_passes"},
        run_id="blind-oracle",
    )

    assert result.passed is False
    assert result.metric_values["player_knowledge_oracle_detection"] == 0.5


def test_adapter_error_counts_as_a_leak_not_a_pass() -> None:
    class Broken:
        adapter_id = "broken"

        def execute(self, _case: AdapterCase) -> AdapterOutput:
            raise RuntimeError("boom")

    result = run_eval(
        ROOT,
        datasets=[DATASET],
        case_ids={"pk.hidden.visited_location_omitted"},
        registry=AdapterRegistry({"player_knowledge": Broken()}),
        run_id="broken-adapter",
    )

    assert result.passed is False
    assert result.error_case_ids == ["pk.hidden.visited_location_omitted"]
    assert result.metric_values["player_knowledge_leak_count"] == 1.0


@pytest.mark.parametrize(
    ("raw", "folded"),
    [
        ("Verme-Primordial das Raízes\n do  Mundo", "verme-primordial das raizes do mundo"),
        ("ASCENSÃO", "ascensao"),
    ],
)
def test_evaluator_fold_is_accent_and_whitespace_insensitive(raw: str, folded: str) -> None:
    assert fold_text(raw) == folded
