"""Automated sanity tests for core flow (router -> nodes -> spawn)."""

import os
import random
from typing import Dict, Any

import pytest
from langchain_core.messages import HumanMessage, AIMessage

from state import GameState
from agents.router import dm_router_node
from agents.combat import combat_node
from agents.rules import rules_node
from agents.npc import npc_actor_node, generate_new_npc
from agents.storyteller import storyteller_node
from engine_utils import apply_state_update, EngineUpdate


HAS_API_KEY = bool(os.getenv("GOOGLE_API_KEY"))


def create_base_state() -> GameState:
    return {
        "messages": [],
        "player": {
            "name": "Tester",
            "class_name": "Debug",
            "race": "Humano",
            "hp": 30,
            "max_hp": 30,
            "stamina": 20,
            "max_stamina": 20,
            "mana": 10,
            "max_mana": 10,
            "gold": 100,
            "xp": 0,
            "level": 1,
            "alignment": "N",
            "attributes": {
                "strength": 10,
                "dexterity": 10,
                "constitution": 10,
                "intelligence": 10,
                "wisdom": 10,
                "charisma": 10,
            },
            "inventory": ["Espada"],
            "known_abilities": [],
            "defense": 10,
            "attack_bonus": 0,
            "active_conditions": [],
        },
        "world": {
            "current_location": "Lab de Testes",
            "time_of_day": "Dia",
            "turn_count": 0,
            "weather": "Neutro",
            "quest_plan": [],
            "quest_plan_origin": None,
        },
        "enemies": [],
        "party": [],
        "npcs": {},
        "active_npc_name": None,
        "next": None,
    }


def create_combat_state() -> GameState:
    state = create_base_state()
    state["enemies"] = [
        {
            "id": "enemy_1",
            "name": "Boneco de Teste",
            "hp": 10,
            "max_hp": 10,
            "stamina": 5,
            "mana": 0,
            "defense": 10,
            "attack_mod": 2,
            "attributes": {k: 10 for k in ["strength", "dexterity", "constitution", "intelligence", "wisdom", "charisma"]},
            "abilities": [],
            "active_conditions": [],
            "status": "ativo",
        }
    ]
    return state


def create_social_state() -> GameState:
    state = create_base_state()
    state["npcs"] = {
        "Bob": {
            "name": "Bob",
            "role": "Vendor",
            "persona": "Jovial merchant",
            "location": state["world"]["current_location"],
            "relationship": 5,
            "memory": [],
            "last_interaction": "",
        }
    }
    state["active_npc_name"] = "Bob"
    return state


def test_router_storyteller_on_empty():
    state = create_base_state()
    res = dm_router_node(state)
    assert res["next"] == "storyteller"


@pytest.mark.skipif(not HAS_API_KEY, reason="GOOGLE_API_KEY não configurada")
def test_router_combat_when_enemy_and_attack():
    state = create_combat_state()
    state["messages"].append(HumanMessage(content="Ataco o inimigo."))
    res = dm_router_node(state)
    assert res["next"] == "combat_agent"


def test_storyteller_produces_narrative():
    state = create_base_state()
    state["world"]["quest_plan"] = ["Find clue"]
    state["messages"].append(HumanMessage(content="Olho ao redor."))
    res = storyteller_node(state)
    assert "messages" in res and isinstance(res["messages"][0], AIMessage)


def test_combat_returns_message_and_not_empty():
    state = create_combat_state()
    state["messages"].append(HumanMessage(content="Atacar com espada."))
    res = combat_node(state)
    assert "messages" in res and res["messages"]


def test_rules_agent_returns_response():
    state = create_base_state()
    state["messages"].append(HumanMessage(content="Pulo de um muro alto."))
    res = rules_node(state)
    assert "messages" in res and res["messages"]


@pytest.mark.skipif(not HAS_API_KEY, reason="GOOGLE_API_KEY não configurada")
def test_npc_actor_updates_memory():
    state = create_social_state()
    state["messages"].append(HumanMessage(content="Como estão as vendas?"))
    res = npc_actor_node(state)
    assert "npcs" in res
    bob = res["npcs"].get("Bob")
    assert bob and bob.get("memory") is not None


def test_spawn_enemy_via_engine_update():
    state = create_base_state()
    update = EngineUpdate(reasoning_trace="spawn", narrative_reason="aparece", spawn_enemy_type="Goblin Batedor")
    new_state = apply_state_update(update, state)
    assert new_state.get("enemies")


@pytest.mark.skipif(not HAS_API_KEY, reason="GOOGLE_API_KEY não configurada")
def test_generate_new_npc_template():
    npc_name = f"Conde Drácula Tech {random.randint(100,999)}"
    tpl = generate_new_npc(npc_name, context="Teste de loja")
    assert tpl and "name" in tpl and "persona" in tpl


if __name__ == "__main__":
    # Facilita rodar direto: pytest.main não é usado para evitar depender da CLI
    for fn in [
        test_router_storyteller_on_empty,
        test_router_combat_when_enemy_and_attack,
        test_storyteller_produces_narrative,
        test_combat_returns_message_and_not_empty,
        test_rules_agent_returns_response,
        test_npc_actor_updates_memory,
        test_spawn_enemy_via_engine_update,
        test_generate_new_npc_template,
    ]:
        fn()
    print("✅ test_runner: todos os cenários básicos executados.")