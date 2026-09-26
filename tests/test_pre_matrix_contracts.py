"""Independent regression oracles from the pre-matrix audit; no provider calls."""
from __future__ import annotations

import copy
import itertools
from types import SimpleNamespace

import pytest
from langchain_core.messages import AIMessage, HumanMessage
from pydantic import BaseModel

from services.actor_lifecycle import evaluate_action
from services.entity_identity import coalesce_runtime_npcs, find_runtime_npc_key
from services.memory_provenance import (
    canonical_location_contradiction, inventory_possession_contradiction,
    make_memory_fact, validate_memory_fact,
)
from services.turn_outcome import render_player_message


@pytest.mark.parametrize("action", [
    "Viajo para a Pradaria das Ruínas para pedir ajuda",
    "Descanso e depois ataco o guarda", "Peço ajuda e saqueio o baú",
])
def test_recovery_does_not_authorize_mixed_physical_actions(action: str) -> None:
    assert evaluate_action({"player": {"conscious": False}}, action)["allowed"] is False


@pytest.mark.parametrize("incapacitated", [False, True])
def test_recovery_graph_and_reload(incapacitated: bool) -> None:
    from main import app
    from playtest.runner import _build_initial_state
    from persistence import _raw_to_state, _state_to_save_data

    state = _build_initial_state("normal", 9)
    state["player"].update(conscious=False, incapacitated=incapacitated, vitalidade=0, hp=0)
    state["messages"] = [HumanMessage(content="Aguardo socorro")]
    location = state["world"]["current_location_id"]
    clock = copy.deepcopy(state["world"]["world_clock"])
    out = app.invoke(state)
    assert out["world"]["current_location_id"] == location
    assert out["world"]["world_clock"] != clock
    assert out["player"]["conscious"] is True
    assert not out["player"].get("incapacitated")
    assert out["last_turn_outcome"]["transition_readiness"]["phase"] == "active"
    loaded = _raw_to_state(_state_to_save_data(out, out["game_id"]))
    assert loaded["player"]["conscious"] is True
    assert not loaded["player"].get("incapacitated")
    assert loaded["last_turn_outcome"] == out["last_turn_outcome"]


def test_blocked_weather_does_not_magically_restore_consciousness(monkeypatch) -> None:
    import world_utils

    monkeypatch.setattr(world_utils, "weather_effects", lambda _: {"rest_block": True})
    monkeypatch.setattr(world_utils, "advance_weather", lambda _: None)
    before = {"vitalidade": 0, "max_vitalidade": 10, "conscious": False, "incapacitated": True}
    after, world = world_utils.apply_rest(before, {"world_clock": {"day": 1, "period": "Manhã"}})
    assert after["vitalidade"] == 0 and after["conscious"] is False
    assert after["incapacitated"] is True
    assert world["world_clock"] == {"day": 1, "period": "Tarde"}


def test_lifecycle_oracle_does_not_trust_the_guard_decision() -> None:
    from playtest.invariants import check_actor_lifecycle

    before = {"player": {"conscious": False}, "world": {"current_location_id": "nova_arcadia"}}
    after = {**before, "world": {"current_location_id": "pradaria_ruinas"},
             "last_action_outcome": {"allowed": True, "action_kind": "recovery"}}
    assert [v.check_id for v in check_actor_lifecycle(after, before, 1)] == [
        "player.action_while_incapacitated"]


def test_receipt_marker_is_not_authority_and_render_is_idempotent() -> None:
    outcome = {"gold_delta": 20}
    text = render_player_message("Uma pista surgiu.\n[RESULTADO] Nada mudou.", outcome)
    assert "+20 ouro" in text and "Nada mudou" not in text
    assert "Uma pista surgiu" in text
    assert text.count("[RESULTADO]") == 1
    assert render_player_message(text, outcome) == text


def test_gold_gain_does_not_contradict_no_item_gain() -> None:
    text = render_player_message("Nenhum item foi obtido.", {"gold_delta": 20})
    assert "Nenhum item foi obtido." in text
    assert "+20 ouro" in text


@pytest.mark.parametrize("text", [
    "O viajante não carrega o Diário de Vesper.",
    "O viajante conta que Kess carrega o Diário de Vesper.",
    "O viajante carrega uma tocha e Kess possui o Diário de Vesper.",
])
def test_inventory_rejects_neither_negation_nor_npc_possession(text: str) -> None:
    state = {"player": {"name": "Ari", "inventory": []},
             "npcs": {"Kess": {"name": "Kess"}},
             "rejected_item_claims": ["Diário de Vesper"]}
    assert inventory_possession_contradiction(text, state) is None


def test_inventory_still_rejects_direct_positive_claim() -> None:
    state = {"player": {"name": "Ari", "inventory": []},
             "rejected_item_claims": ["Diário de Vesper"]}
    assert inventory_possession_contradiction("Ari carrega o Diário de Vesper.", state)


@pytest.mark.parametrize("text", ["Ari morreu no conflito.", "O herói morreu no conflito."])
def test_quest_event_cannot_prove_player_death(text: str) -> None:
    state = {"player": {"name": "Ari"},
             "event_log": [{"event_id": "quest1", "type": "quest_completed"}]}
    fact = make_memory_fact(text, provenance="canonical_event", source_id="quest1", source_turn=1)
    assert validate_memory_fact(fact, state)[0] is None


@pytest.mark.parametrize("text", [
    "Ari não morreu no conflito.", "Ari nunca esteve morto.",
])
def test_negated_death_remains_valid(text: str) -> None:
    state = {"player": {"name": "Ari"},
             "event_log": [{"event_id": "down", "type": "player_downed"}]}
    fact = make_memory_fact(text, provenance="canonical_event", source_id="down", source_turn=1)
    assert validate_memory_fact(fact, state)[0] is not None


@pytest.mark.parametrize("target, epoch, accepted", [
    ("player", 1, True), ("npc_kess", 1, False), ("player", 0, False),
])
def test_terminal_evidence_belongs_to_player_and_current_timeline(target, epoch, accepted) -> None:
    state = {"player": {"name": "Ari"}, "continuity": {"timeline_epoch": 1},
             "event_log": [{"event_id": "death", "type": "player_died",
                            "target_id": target, "timeline_epoch": epoch}]}
    fact = make_memory_fact("Ari morreu no conflito.", provenance="canonical_event",
                            source_id="death", source_turn=1)
    assert (validate_memory_fact(fact, state)[0] is not None) is accepted


def test_death_invariant_does_not_require_a_downed_event() -> None:
    from playtest.invariants import check_false_player_death

    state = {"player": {"name": "Ari"}, "memory_facts": [
        {"memory_id": "bad", "text": "Ari morreu no conflito."}]}
    assert [v.check_id for v in check_false_player_death(state, {}, 1)] == [
        "narrative.false_player_death"]


@pytest.mark.parametrize("order", list(itertools.permutations(range(3))))
def test_alias_components_are_transitive_and_survive_reload(order: tuple[int, ...]) -> None:
    from persistence import _raw_to_state, _state_to_save_data

    rows = [
        ("Kess", {"id": "npc_kess", "name": "Kess", "created_turn": 1, "last_seen_turn": 1}),
        ("Máscara", {"id": "npc_kess", "name": "Máscara", "created_turn": 2, "last_seen_turn": 2}),
        ("Capuz", {"id": "npc_capuz", "name": "Máscara", "created_turn": 3, "last_seen_turn": 3}),
    ]
    original = dict(rows[i] for i in order)
    merged = coalesce_runtime_npcs(original)
    assert len(merged) == 1
    assert next(iter(merged.values()))["name"] == "Kess"
    assert next(iter(merged.values()))["last_seen_turn"] == 3
    assert coalesce_runtime_npcs(merged) == merged
    raw = _state_to_save_data({"npcs": merged, "player": {}, "world": {}}, "alias-audit")
    loaded = _raw_to_state(raw)["npcs"]
    for alias in ("Kess", "Máscara", "Capuz", "npc_kess", "npc_capuz"):
        assert find_runtime_npc_key(loaded, alias) is not None


def test_cosmetic_prefix_does_not_hide_repeated_dialogue() -> None:
    from playtest.invariants import check_repeated_opening
    from services.prose_guard import semantic_opening, vary_repeated_opening

    dialogue = "Não tenho nada novo para contar sobre essa missão."
    previous = semantic_opening(dialogue, words=12)
    rendered = vary_repeated_opening(dialogue, [previous], salt="audit")
    state = {"messages": [AIMessage(content=f'**Kess:** "{text}"')
                           for text in (dialogue, dialogue, rendered)]}
    assert [v.check_id for v in check_repeated_opening(state, None, 3)] == [
        "narrative.repeated_opening"]


class _Expected(BaseModel):
    value: str


@pytest.mark.parametrize("raw, expected", [
    (AIMessage(content="", tool_calls=[{"id": "1", "name": "WrongSchema", "args": {}}]), "wrong_tool"),
    (AIMessage(content='{"other": 1}'), "schema_validation"),
    (AIMessage(content=""), "no_tool_call"),
])
def test_structured_failures_have_distinct_causes(raw: AIMessage, expected: str) -> None:
    from llm_setup import ModelTier, RoutedLLM

    llm = RoutedLLM(ModelTier.SMART, 0.0, []).with_structured_output(_Expected)
    _, code, _ = llm._normalize_internal_structured_result(
        {"raw": raw, "parsed": None, "parsing_error": None})
    assert code == expected


@pytest.mark.parametrize("failure", ["invariant", "turn", "incomplete", "observability"])
def test_matrix_stops_before_next_campaign_on_failure(monkeypatch, failure: str) -> None:
    from playtest import __main__ as cli, matrix, telemetry

    cases = matrix.select_matrix_cases(1)[:2]
    calls = []
    finished = []
    monkeypatch.setattr(matrix, "select_matrix_cases", lambda *_: cases)
    for name in ("begin_run", "touch_run"):
        monkeypatch.setattr(telemetry, name, lambda *a, **k: None)
    monkeypatch.setattr(telemetry, "finish_run", lambda *a, **k: finished.append(k))
    monkeypatch.setattr(telemetry, "new_run_id", lambda: "no-files")
    monkeypatch.setattr(telemetry, "run_dir", lambda *_: "no-files")
    monkeypatch.setattr(cli, "_print_resumo", lambda *_: None)

    def campaign(profile, **kwargs):
        assert kwargs["stop_on_error"] is True
        calls.append(profile)
        return SimpleNamespace(profile=profile, errors=["bad"] if failure == "turn" else [],
                               aborted_reason=None, turns_completed=1 if failure == "incomplete" else 200)

    monkeypatch.setattr(cli, "run_campaign", campaign)
    monkeypatch.setattr(telemetry, "persist_campaign", lambda *a, **k: {
        "error_violations": int(failure == "invariant"),
        "observability_errors": int(failure == "observability"),
    })
    args = SimpleNamespace(real=False, max_cost=.25, max_requests=800, start_index=1,
                           turns=200, routes_profile=None, groq_min_interval=0,
                           label="B", turn_timeout=None)
    assert cli._run_matrix_suite(args) == 1
    assert len(calls) == 1
    assert finished[0]["status"] == "failed"


def test_matrix_campaign_stops_at_first_bad_turn(monkeypatch) -> None:
    from playtest import runner

    monkeypatch.setattr(runner, "_run_invariants", lambda *a, **k: [{
        "check_id": "audit.injected", "severity": "error", "turn": 1,
        "message": "synthetic violation", "details": {},
    }])
    result = runner.run_campaign("normal", turns=3, seed=9, stop_on_error=True)
    assert result.turns_completed == 1
    assert result.aborted_reason == "contract_failure (turno 1)"
    assert result.history[0].violation_details[0]["check_id"] == "audit.injected"


@pytest.mark.parametrize("text, invalid", [
    ("Anel Dourado, bairro alto de Brekmar.", True),
    ("Anel Dourado fica em Nova Arcádia.", False),
    ("Viajo do Anel Dourado para Brekmar.", False),
    ("Anel Dourado não fica em Brekmar.", False),
])
def test_location_corpus_has_independent_expected_results(text: str, invalid: bool) -> None:
    assert bool(canonical_location_contradiction(text)) is invalid
