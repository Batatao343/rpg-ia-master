"""Complete automated suite for agents/nodes/end-to-end behaviors."""

import json
import os
from unittest import mock

import pytest
from langchain_core.messages import AIMessage, HumanMessage

from agents.archivist import archive_narrative
from agents.bestiary import (
    _infer_tier_from_name as infer_enemy_tier,
    generate_new_enemy,
    get_enemy_template,
)
from agents.combat import _tree_of_thoughts_strategy, combat_node
from agents.npc import _infer_tier_from_name as infer_npc_tier, generate_new_npc, npc_actor_node
from agents.router import dm_router_node
from agents.rules import rules_node
from agents.storyteller import storyteller_node
from character_creator import create_player_character
from engine_utils import DamageTarget, EngineUpdate
from persistence import load_game, save_game
from prologue_manager import generate_prologue
from state import GameState


HAS_API_KEY = bool(os.getenv("GOOGLE_API_KEY"))

# === STATE FACTORIES ===
def create_base_state() -> GameState:
    return {
        "messages": [],
        "player": {
            "name": "Valerius",
            "class_name": "Knight",
            "race": "Human",
            "hp": 30,
            "max_hp": 30,
            "mana": 10,
            "max_mana": 10,
            "stamina": 20,
            "max_stamina": 20,
            "gold": 50,
            "level": 1,
            "xp": 0,
            "alignment": "NG",
            "attributes": {
                "strength": 12,
                "dexterity": 10,
                "constitution": 12,
                "intelligence": 10,
                "wisdom": 10,
                "charisma": 10,
            },
            "inventory": ["Espada"],
            "known_abilities": [],
            "defense": 12,
            "attack_bonus": 1,
            "active_conditions": [],
        },
        "world": {
            "current_location": "Sala de Testes",
            "time_of_day": "Dia",
            "turn_count": 0,
            "weather": "Claro",
            "quest_plan": [],
            "quest_plan_origin": None,
        },
        "enemies": [],
        "party": [],
        "npcs": {},
        "active_npc_name": None,
        "next": None,
    }


def create_combat_state(boss: bool = False) -> GameState:
    state = create_base_state()
    enemy_name = "Test Goblin" if not boss else "Ancient Void Dragon Boss"
    state["enemies"] = [
        {
            "id": "enemy_1",
            "name": enemy_name,
            "type": "BOSS" if boss else "MINION",
            "hp": 25 if boss else 12,
            "max_hp": 25 if boss else 12,
            "stamina": 10,
            "mana": 5,
            "defense": 12,
            "attack_mod": 3,
            "attributes": {
                "strength": 14,
                "dexterity": 12,
                "constitution": 12,
                "intelligence": 10,
                "wisdom": 10,
                "charisma": 8,
            },
            "abilities": ["Garras", "Sopro"],
            "active_conditions": [],
            "status": "ativo",
        }
    ]
    return state


def create_social_state() -> GameState:
    state = create_base_state()
    state["npcs"] = {
        "King": {
            "name": "King",
            "role": "Sovereign",
            "persona": "Authoritative but fair",
            "location": state["world"]["current_location"],
            "relationship": 5,
            "memory": [],
            "last_interaction": "",
        },
        "Bob": {
            "name": "Bob",
            "role": "Vendor",
            "persona": "Jovial merchant",
            "location": state["world"]["current_location"],
            "relationship": 6,
            "memory": [],
            "last_interaction": "",
        },
    }
    state["active_npc_name"] = "Bob"
    return state


# === TEST SCENARIOS ===
def test_engine_contracts_validation():
    # Dano absurdo deve explodir
    with pytest.raises(ValueError):
        EngineUpdate(
            reasoning_trace="Spike damage overflow",
            narrative_reason="",
            hp_updates=[DamageTarget(target_name="Jogador", damage_amount=999)],
        )

    corrected = EngineUpdate(
        reasoning_trace="Negative damage clamp",
        narrative_reason="",
        hp_updates=[DamageTarget(target_name="Jogador", damage_amount=-50)],
    )
    assert corrected.hp_updates[0].damage_amount == 0

    with pytest.raises(ValueError):
        EngineUpdate(
            reasoning_trace="Stamina too low",
            narrative_reason="",
            player_stamina_change=-50,
        )


def test_persistence_roundtrip(tmp_path):
    state = create_base_state()
    state["messages"].append(HumanMessage(content="Salvar jogo!"))
    fname = tmp_path / "test_save.json"
    save_msg = save_game(state, fname.with_suffix("").name)
    assert "sucesso" in save_msg.lower()
    restored = load_game(fname.with_suffix("").name)
    assert state["player"] == restored["player"]
    assert state["world"] == restored["world"]


@pytest.mark.skipif(not HAS_API_KEY, reason="GOOGLE_API_KEY não configurada")
def test_bestiary_spawner_and_cache():
    for name in ["Rat", "Ancient Void Dragon Boss"]:
        tier = infer_enemy_tier(name)
        enemy = generate_new_enemy(name, context="Arena de testes")
        assert enemy and enemy.get("hp") is not None
        cached = get_enemy_template(name)
        assert cached is not None or enemy.get("name") == name
        assert tier is not None


@pytest.mark.skipif(not HAS_API_KEY, reason="GOOGLE_API_KEY não configurada")
def test_npc_designer_outputs_fields():
    for name in ["Beggar", "King of Shadows"]:
        tier = infer_npc_tier(name)
        npc = generate_new_npc(name, context="Cidade portuária")
        assert npc and "persona" in npc
        assert tier is not None


@pytest.mark.skipif(not HAS_API_KEY, reason="GOOGLE_API_KEY não configurada")
def test_character_pipeline_fields():
    hero = create_player_character(
        {
            "name": "TestHero",
            "class_name": "Warrior",
            "race": "Human",
        }
    )
    assert hero.get("hp") is not None
    assert hero.get("attributes") is not None
    assert isinstance(hero.get("inventory"), list)


@pytest.mark.skipif(not HAS_API_KEY, reason="GOOGLE_API_KEY não configurada")
def test_prologue_generation_fields():
    hero = {
        "name": "TestHero",
        "class_name": "Warrior",
        "race": "Human",
    }
    prologue = generate_prologue(hero)
    assert all(key in prologue for key in ["starting_location", "intro_narrative", "quest_plan"])


@pytest.mark.skipif(not HAS_API_KEY, reason="GOOGLE_API_KEY não configurada")
def test_archivist_invokes_lore_index():
    sample_fact = "The Sword of Zorg was forged in the fires of Mount Doom."
    with mock.patch("rag.add_to_lore_index") as mock_add:
        archive_narrative(sample_fact)
        assert mock_add.called, "add_to_lore_index deve ser invocado mesmo sem LLM/RAG"


@pytest.mark.skipif(not HAS_API_KEY, reason="GOOGLE_API_KEY não configurada")
def test_router_paths_with_context():
    combat_state = create_combat_state()
    combat_state["messages"].append(HumanMessage(content="Attack goblin"))
    assert dm_router_node(combat_state)["next"] == "combat_agent"

    social_state = create_social_state()
    social_state["messages"].append(HumanMessage(content="Talk to King"))
    res_social = dm_router_node(social_state)
    assert res_social["next"] in {"npc_actor", "storyteller"}

    rules_state = create_base_state()
    rules_state["messages"].append(HumanMessage(content="Climb wall"))
    res_rules = dm_router_node(rules_state)
    assert res_rules["next"] in {"rules_agent", "storyteller"}


@pytest.mark.skipif(not HAS_API_KEY, reason="GOOGLE_API_KEY não configurada")
def test_storyteller_plan_and_message():
    state = create_base_state()
    state["world"]["quest_plan"] = ["Find key", "Open door"]
    state["world"]["quest_plan_origin"] = state["world"]["current_location"]
    state["messages"].append(HumanMessage(content="I search the desk for clues."))
    result = storyteller_node(state)
    assert "messages" in result and isinstance(result["messages"][0], AIMessage)


@pytest.mark.skipif(not HAS_API_KEY, reason="GOOGLE_API_KEY não configurada")
def test_combat_agents_minion_and_boss():
    # Minion flow
    minion_state = create_combat_state()
    minion_state["messages"].append(HumanMessage(content="Strike the goblin"))
    minion_result = combat_node(minion_state)
    assert "messages" in minion_result

    # Boss ToT flow
    boss_state = create_combat_state(boss=True)
    boss_state["messages"].append(HumanMessage(content="Face the dragon"))
    boss_strategy = _tree_of_thoughts_strategy(
        boss_state["player"],
        boss_state["enemies"],
        "",
        boss_state["messages"][-1].content,
        "\n".join([f"{e['name']} (HP {e['hp']})" for e in boss_state["enemies"]]),
    )
    assert isinstance(boss_strategy, str) and boss_strategy
    boss_result = combat_node(boss_state)
    assert "messages" in boss_result


def test_rules_agent_physics_response():
    state = create_base_state()
    state["messages"].append(HumanMessage(content="I jump off a 30m cliff"))
    result = rules_node(state)
    assert "messages" in result


@pytest.mark.skipif(not HAS_API_KEY, reason="GOOGLE_API_KEY não configurada")
def test_npc_actor_memory_updates():
    state = create_social_state()
    state["active_npc_name"] = "Bob"
    state["messages"].append(HumanMessage(content="How are the sales today?"))
    result = npc_actor_node(state)
    updated_npc = result.get("npcs", {}).get("Bob")
    assert updated_npc and updated_npc.get("memory")


if __name__ == "__main__":
    # Execução direta: roda todos os testes sequencialmente
    for fn in [
        test_engine_contracts_validation,
        test_persistence_roundtrip,
        test_bestiary_spawner_and_cache,
        test_npc_designer_outputs_fields,
        test_character_pipeline_fields,
        test_prologue_generation_fields,
        test_archivist_invokes_lore_index,
        test_router_paths_with_context,
        test_storyteller_plan_and_message,
        test_combat_agents_minion_and_boss,
        test_rules_agent_physics_response,
        test_npc_actor_memory_updates,
    ]:
        fn()
    print("✅ test_suite_complete: todos os cenários executados.")
