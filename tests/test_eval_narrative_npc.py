"""Deterministic-first narrative and NPC eval contracts (SPEC-171)."""

from __future__ import annotations

from pathlib import Path

import pytest

from evals.core.adapters import AdapterCase, AdapterOutput, AdapterRegistry
from evals.core.governance import load_cases, load_metrics_registry
from evals.core.runner import run_eval


ROOT = Path(__file__).resolve().parents[1]
DATASET = "datasets/regression/narrative_npc.jsonl"


def test_narrative_corpus_covers_all_deterministic_contracts() -> None:
    cases = load_cases(ROOT / "evals" / DATASET)

    assert len(cases) == 27
    assert {case.oracle for case in cases} == {"narrative_claim"}
    assert {case.input["operation"] for case in cases} == {
        "narrative_guard",
        "scene_presence",
        "action_eligibility",
        "conflict_lifecycle",
    }
    all_tags = {tag for case in cases for tag in case.tags}
    assert {
        "death",
        "inventory",
        "location",
        "identity",
        "secret",
        "reward",
        "outcome",
        "lifecycle",
        "action",
        "scene",
        "npc",
        "known-good",
        "known-bad",
    } <= all_tags
    assert all(case.description and case.created_from for case in cases)


def test_narrative_dataset_uses_canonical_contracts_without_judge() -> None:
    result = run_eval(ROOT, datasets=[DATASET], run_id="narrative-npc")

    assert result.passed is True
    assert len(result.results) == 27
    assert result.metric_values == {
        "narrative_claim_accuracy": 1.0,
        "narrative_hard_contradictions": 0.0,
        "npc_identity_errors": 0.0,
    }
    assert "npc_persona_score" not in result.metric_values
    assert result.metadata.provider is None
    assert result.metadata.model is None
    matrix = result.aggregates["narrative_reason_matrix"]
    assert all(set(row) == {expected} for expected, row in matrix.items())
    assert all("input" not in case.actual and "story_text" not in case.actual
               for case in result.results)


def test_subjective_judge_remains_explicitly_non_blocking_and_uncalibrated() -> None:
    registry = load_metrics_registry(ROOT / "evals" / "metrics-registry.yaml")
    persona = registry.metrics["npc_persona_score"]

    assert persona.kind == "llm_judge"
    assert persona.blocking is False
    assert persona.calibration is None


@pytest.mark.parametrize(
    ("case_id", "patch_target", "replacement"),
    [
        (
            "narrative.death.false",
            "services.narrative_evidence.validate_narrative",
            lambda text, _evidence, *, channel: __import__(
                "services.narrative_evidence", fromlist=["NarrativeCheck"]
            ).NarrativeCheck(text, [], []),
        ),
        (
            "narrative.scene.absent-npc",
            "services.npc_layers.npcs_in_scene",
            lambda _state: ["Borin"],
        ),
        (
            "narrative.action.unconscious-attack",
            "services.actor_lifecycle.evaluate_action",
            lambda _state, _action: {
                "phase": "active",
                "allowed": True,
                "code": "ok",
                "action_kind": "normal",
                "message": "",
            },
        ),
        (
            "narrative.lifecycle.dead-revived",
            "services.conflict_summary.validate_narrative_text",
            lambda _summary, _text: {"ok": True, "violations": []},
        ),
    ],
)
def test_product_contract_mutations_leak_hard_claims(
    monkeypatch, case_id: str, patch_target: str, replacement
) -> None:
    monkeypatch.setattr(patch_target, replacement)

    result = run_eval(
        ROOT,
        datasets=[DATASET],
        case_ids={case_id},
        run_id=f"mutated-{case_id}",
    )

    assert result.passed is False
    assert result.metric_values["narrative_claim_accuracy"] == 0.0
    assert result.metric_values["narrative_hard_contradictions"] == 1.0


def test_wrong_rejection_reason_fails_without_counting_an_accepted_contradiction() -> None:
    class WrongReasonAdapter:
        adapter_id = "wrong_reason"

        def execute(self, _case: AdapterCase) -> AdapterOutput:
            return AdapterOutput(actual={
                "accepted": False,
                "rejection_reasons": ["wrong_reason"],
                "sanitized_text": "",
                "trace": {},
            })

    result = run_eval(
        ROOT,
        datasets=[DATASET],
        case_ids={"narrative.death.false"},
        registry=AdapterRegistry({"narrative_claims": WrongReasonAdapter()}),
        run_id="wrong-narrative-reason",
    )

    assert result.passed is False
    assert result.error_case_ids == []
    assert result.metric_values["narrative_claim_accuracy"] == 0.0
    assert result.metric_values["narrative_hard_contradictions"] == 0.0


def test_logging_a_rejection_without_sanitizing_the_claim_is_a_hard_leak(
    monkeypatch,
) -> None:
    from services import narrative_evidence

    monkeypatch.setattr(
        narrative_evidence,
        "validate_narrative",
        lambda text, _evidence, *, channel: narrative_evidence.NarrativeCheck(
            text,
            [{"channel": channel, "reason": "player_death", "turn": "3"}],
            [],
        ),
    )

    result = run_eval(
        ROOT,
        datasets=[DATASET],
        case_ids={"narrative.death.false"},
        run_id="logging-only-narrative-guard",
    )

    assert result.passed is False
    assert result.results[0].actual["accepted"] is False
    assert result.results[0].actual["sanitized_text"] == "Ari morreu."
    assert result.metric_values["narrative_claim_accuracy"] == 0.0
    assert result.metric_values["narrative_hard_contradictions"] == 1.0


def test_suppressing_valid_text_fails_accuracy_without_inventing_a_leak(monkeypatch) -> None:
    from services import narrative_evidence

    monkeypatch.setattr(
        narrative_evidence,
        "validate_narrative",
        lambda _text, _evidence, *, channel: narrative_evidence.NarrativeCheck("", [], []),
    )

    result = run_eval(
        ROOT,
        datasets=[DATASET],
        case_ids={"narrative.death.negated"},
        run_id="over-sanitized-valid-claim",
    )

    assert result.passed is False
    assert result.metric_values["narrative_claim_accuracy"] == 0.0
    assert result.metric_values["narrative_hard_contradictions"] == 0.0


def test_neutral_replacement_mismatch_is_not_counted_as_a_contradiction(monkeypatch) -> None:
    from services import narrative_evidence

    monkeypatch.setattr(
        narrative_evidence,
        "validate_narrative",
        lambda _text, _evidence, *, channel: narrative_evidence.NarrativeCheck(
            "O vento sopra.",
            [{"channel": channel, "reason": "player_death", "turn": "3"}],
            [],
        ),
    )

    result = run_eval(
        ROOT,
        datasets=[DATASET],
        case_ids={"narrative.death.false"},
        run_id="neutral-replacement-mismatch",
    )

    assert result.passed is False
    assert result.error_case_ids == []
    assert result.metric_values["narrative_claim_accuracy"] == 0.0
    assert result.metric_values["narrative_hard_contradictions"] == 0.0


def test_adapter_error_remains_in_narrative_accuracy_denominator() -> None:
    class OneErrorAdapter:
        adapter_id = "one_error"

        def execute(self, case: AdapterCase) -> AdapterOutput:
            if case.id == "narrative.death.false":
                raise RuntimeError("synthetic adapter error")
            return AdapterOutput(actual={
                "accepted": True,
                "rejection_reasons": [],
                "sanitized_text": "Ari morreu.",
                "trace": {},
            })

    result = run_eval(
        ROOT,
        datasets=[DATASET],
        case_ids={"narrative.death.false", "narrative.death.canonical"},
        registry=AdapterRegistry({"narrative_claims": OneErrorAdapter()}),
        run_id="narrative-error-denominator",
    )

    assert result.passed is False
    assert result.error_case_ids == ["narrative.death.false"]
    assert result.metric_values["narrative_claim_accuracy"] == 0.5
