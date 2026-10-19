"""Deterministic NPC-knowledge eval contracts (SPEC-215 §5)."""

from __future__ import annotations

from pathlib import Path

import pytest

from evals.core.adapters import AdapterCase, AdapterError, default_registry
from evals.core.governance import load_cases
from evals.core.runner import run_eval

ROOT = Path(__file__).resolve().parents[1]
DATASET = "datasets/regression/npc_knowledge.jsonl"


def _cases() -> dict:
    return {case.id.split(".", 1)[1]: case for case in load_cases(ROOT / "evals" / DATASET)}


def test_corpus_covers_the_spec_215_handoff_list() -> None:
    cases = load_cases(ROOT / "evals" / DATASET)

    assert len(cases) == 39
    assert {case.suite for case in cases} == {"npc_knowledge"}
    assert {case.oracle for case in cases} == {"projection"}
    assert {case.input["operation"] for case in cases} == {
        "scenario",
        "off_identity",
        "api_private",
    }
    tags = {tag for case in cases for tag in case.tags}
    assert {
        "witness",
        "delay",
        "distance",
        "messenger",
        "reload",
        "checkpoint",
        "rumor",
        "secret",
        "inheritance",
        "graph",
        "player",
        "dead",
        "prompt",
        "identity",
        "flag-off",
        "legacy",
        "api",
        "oracle",
        "teleport",
        "baseline-off",
        "known-good",
        "known-bad",
    } <= tags
    assert all(case.description and case.created_from for case in cases)


def test_expected_pins_the_hard_properties_independently() -> None:
    """The fixture-authored expectations assert the SPEC-215 invariants by value."""
    cases = _cases()
    exp = {name: case.expected for name, case in cases.items()}

    osric = "npc_osric"
    assert exp["messenger-before-due"]["observations"][osric]["knows"] == {
        "npc_halveth_fixture": False,
        "morto": False,
    }
    assert exp["messenger-at-due"]["observations"][osric]["labels"] == [
        "[OUVIU DE viajantes de Brekmar]"
    ]
    assert exp["delivery-delayed-by-distance"]["queue_due_after_travel"] is True
    assert exp["delivery-delayed-by-distance"]["queue_len"] > 0
    assert exp["oracle-queue-early-delivery-detected"]["queue_due_after_travel"] is False
    assert exp["witness-sees-death"]["observations"]["npc_lyra"]["labels"] == ["[VIU]"]
    for name in ("rumor-believed-stays-rumor", "rumor-delivered-distant-stays-rumor"):
        assert exp[name]["memory_facts_unchanged"] is True
        assert exp[name]["event_log_unchanged"] is True
        assert exp[name]["violations"] == []
    for name in ("secret-revealed-witness-only", "secret-revealed-not-inherited"):
        assert exp[name]["watch_in_heard"] == [] and exp[name]["watch_in_queue"] == []
    assert exp["secret-revealed-tampered-heard-not-inherited"]["links_total"] == 0
    assert exp["remote-control-edge-hidden-on"]["observations"]["npc_guarda"]["knows"] == {
        "faction_fixture_215": False
    }
    assert exp["remote-control-edge-visible-off"]["observations"]["npc_guarda"]["knows"] == {
        "faction_fixture_215": True
    }
    assert exp["player-tells-rel5-only-heard"]["observations"]["npc_lyra"]["relations"] == [
        "ev_kill_1:told_to"
    ]
    assert exp["player-invents-event-no-link"]["links_total"] == 0
    assert exp["dead-npc-witnesses-nothing"]["links_total"] == 0
    assert exp["flag-off-has-no-ledger-effect"] == {
        "pack_identical": True,
        "turn_updates": {},
        "state_untouched": True,
        "context_gate_is_none": True,
    }
    assert (
        exp["prompt-limited-to-eight-lines"]["observations"]["npc_lyra"]["labels"] == ["[VIU]"] * 8
    )
    assert exp["legacy-save-loads-with-legacy-knowledge"]["legacy_knowledge"] is True
    assert exp["oracle-teleport-detected"]["violations"] == ["knowledge.teleport"]
    assert exp["oracle-rumor-promoted-detected"]["violations"] == ["knowledge.rumor_promoted"]
    assert exp["ledger-never-in-public-api"] == {"observations": {}, "leaked": []} or exp[
        "ledger-never-in-public-api"
    ] == {"leaked": []}


def test_corpus_passes_fully() -> None:
    result = run_eval(ROOT, datasets=[DATASET], run_id="npc-knowledge")

    assert result.passed is True
    assert result.error_case_ids == []
    assert len(result.results) == 39
    assert result.metric_values == {"state_transition_pass_rate": 1.0}


def test_flag_off_regresses_distance_cases_only_in_baseline() -> None:
    """`off` is the documented omniscient baseline: same scenario, opposite answer."""
    adapter = default_registry().resolve("npc_knowledge")
    on = _cases()["distant-unaware-before-any-news"].input
    off = {**on, "mode": "off"}

    def run(inp):
        case = AdapterCase(
            id="probe",
            suite="npc_knowledge",
            description="probe",
            fixture=None,
            input=inp,
            tags=(),
            source="synthetic",
            created_from=None,
        )
        return adapter.execute(case).actual["observations"]["npc_osric"]["knows"]

    assert run(on)["npc_halveth_fixture"] is False
    assert run(off)["npc_halveth_fixture"] is True


def test_adapter_fails_closed_on_unknown_operation_and_step() -> None:
    adapter = default_registry().resolve("npc_knowledge")
    for inp in ({"operation": "nope"}, {"operation": "scenario", "steps": [{"do": "teleport"}]}):
        case = AdapterCase(
            id="probe",
            suite="npc_knowledge",
            description="probe",
            fixture=None,
            input=inp,
            tags=(),
            source="synthetic",
            created_from=None,
        )
        with pytest.raises(AdapterError):
            adapter.execute(case)
