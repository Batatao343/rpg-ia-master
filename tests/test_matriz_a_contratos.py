from __future__ import annotations

import random

import pytest
from langchain_core.messages import AIMessage, HumanMessage

import party
from agents.action_guard import action_guard_node
from playtest import invariants
from playtest.profiles import Recrutador
from services.actor_lifecycle import ActorPhase, classify_actor, evaluate_action
from services.prose_guard import semantic_opening
from services.turn_outcome import capture_baseline, finalize_outcome, player_facing_message


def test_vitalidade_zero_consciente_e_ativo_mas_inconsciente_bloqueia_viagem():
    active = {"player": {"vitalidade": 0, "conscious": True}, "combat": {"active": False}}
    assert classify_actor(active) == ActorPhase.ACTIVE
    assert evaluate_action(active, "Viajo para o norte")["allowed"] is True

    down = {"player": {"vitalidade": 0, "conscious": False}, "combat": {"active": False}}
    decision = evaluate_action(down, "Viajo para o norte")
    assert decision["allowed"] is False
    assert decision["code"] == "blocked_unconscious"
    assert evaluate_action(down, "Descanso e aguardo socorro")["allowed"] is True


def test_guard_bloqueia_sem_consumir_turno_e_sem_chamar_llm():
    state = {
        "player": {"vitalidade": 0, "conscious": False, "gold": 2, "xp": 0,
                   "level": 1, "inventory": []},
        "world": {"turn_count": 71, "current_location_id": "vorr"},
        "messages": [HumanMessage(content="Viajo para outra região")],
        "combat": {"active": False}, "quests": [], "event_log": [],
    }
    update = action_guard_node(state)
    assert update["action_guard_blocked"] is True
    assert "world" not in update and "player" not in update
    assert "inconsciente" in update["messages"][0].content


def test_grafo_universal_encerra_viagem_inconsciente_antes_do_router():
    from main import app
    from playtest.runner import _build_initial_state

    state = _build_initial_state("lifecycle-graph", 9)
    state["player"]["vitalidade"] = 0
    state["player"]["conscious"] = False
    state["player"]["post_combat_state"] = "inconsciente"
    state["messages"] = [HumanMessage(content="Viajo para muito longe")]
    before_turn = state["world"]["turn_count"]
    before_location = state["world"]["current_location_id"]

    nodes = []
    final = state
    for mode, chunk in app.stream(state, stream_mode=["updates", "values"]):
        if mode == "updates":
            nodes.extend(chunk.keys())
        else:
            final = chunk

    assert nodes == ["action_guard"]
    assert final["world"]["turn_count"] == before_turn
    assert final["world"]["current_location_id"] == before_location
    assert final["last_action_outcome"]["code"] == "blocked_unconscious"


@pytest.mark.parametrize("turn", [39, 42, 80, 94])
def test_recompensa_tardia_de_quest_reconcilia_a_mesma_resposta(turn):
    before = {
        "game_id": "quester", "world": {"turn_count": turn - 1},
        "player": {"gold": 602, "xp": 400, "level": 11, "inventory": []},
        "quests": [{"id": "q1", "status": "active"}], "event_log": [],
        "messages": [],
    }
    baseline = capture_baseline(before)
    after = {
        **before, "turn_baseline": baseline, "world": {"turn_count": turn},
        "player": {"gold": 622, "xp": 500, "level": 11, "inventory": []},
        "quests": [{"id": "q1", "status": "completed"}],
        "event_log": [{"event_id": "ev-q1", "type": "quest_completed"}],
        "messages": [AIMessage(content=(
            "A missão chega ao fim. Ao conferir seus pertences, você percebe que nada novo foi obtido."
        ))],
    }
    outcome = finalize_outcome(after)
    message = outcome["player_message"]
    assert "nada novo" not in message.casefold()
    assert "+20 ouro" in message and "+100 XP" in message
    assert outcome["quests_completed"] == ["q1"]
    assert player_facing_message({**after, "last_turn_outcome": outcome}) == message
    assert finalize_outcome({**after, "last_turn_outcome": outcome})["receipt_id"] == outcome["receipt_id"]


def test_decisao_recrutamento_trait_aware_e_hint_nao_vaza_trait():
    state = {
        "npcs": {"Kess": {"name": "Kess", "relationship": 7,
                            "hidden_traits": ["desconfiado"], "revealed_traits": [],
                            "in_scene": True}},
        "party": [], "factions": [], "world": {"current_location_id": "brekmar"},
    }
    decision = party.recruitment_decision(state, "Kess")
    assert decision["ok"] is False
    assert decision["code"] == "relationship_too_low"
    assert decision["required_relationship"] == 10
    assert "desconfiado" not in decision["public_hint"].casefold()

    profile = Recrutador()
    actions = [profile._next_action(state, random.Random(7)) for _ in range(5)]
    assert all("se junte" not in action for action in actions)
    assert len(set(actions[1:4])) == 3
    assert "Viajo" in actions[4] or "tarefa concreta" in actions[4]


def test_repeticao_de_interacao_vira_um_episodio_curto():
    assert semantic_opening("🗣️ Kess: Ainda não confio em você.") == "ainda não confio em você"
    state = {"last_interaction_outcome": {
        "code": "relationship_too_low", "subject_id": "kess",
        "progressed": False, "repeat_count": 3,
    }}
    got = invariants.check_interaction_no_progress(state, None, 3)
    assert len(got) == 1 and got[0].check_id == "interaction.no_progress"
    state["last_interaction_outcome"]["repeat_count"] = 5
    assert invariants.check_interaction_no_progress(state, None, 5) == []


def test_resultado_e_progresso_de_interacao_sobrevivem_save_load():
    from persistence import _raw_to_state, _state_to_save_data

    state = {
        "game_id": "persist-contract", "player": {}, "party": [], "enemies": [],
        "world": {}, "messages": [], "continuity": {},
        "last_turn_outcome": {
            "turn": 39, "receipt_id": "receipt-q1",
            "player_message": "Missão concluída.\n\n[RESULTADO] +20 ouro",
        },
        "last_interaction_outcome": {
            "kind": "recruit", "subject_id": "kess",
            "code": "relationship_too_low", "repeat_count": 3,
            "progressed": False,
        },
    }
    raw = _state_to_save_data(state, state["game_id"])
    loaded = _raw_to_state(raw)

    assert loaded["last_turn_outcome"] == state["last_turn_outcome"]
    assert loaded["last_interaction_outcome"] == state["last_interaction_outcome"]
    assert player_facing_message(loaded).endswith("+20 ouro")
    legacy = _raw_to_state({**raw, "last_turn_outcome": None,
                            "last_interaction_outcome": None})
    assert legacy["last_turn_outcome"] == {}
    assert legacy["last_interaction_outcome"] == {}
