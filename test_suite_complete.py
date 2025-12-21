"""
Complete V8 test suite with interactive menu and modular state factories.
Each scenario mirrors architecture features: governance, RAG generation, routing, and tactical AI.
"""

import json
import os
from unittest import mock

from langchain_core.messages import HumanMessage

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
from agents.archivist import archive_narrative
from engine_utils import DamageTarget, EngineUpdate
from persistence import load_game, save_game
from state import GameState
from character_creator import create_player_character
from prologue_manager import generate_prologue


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


# === HELPERS ===
def print_header(title: str):
    print(f"\n{'=' * 12} {title} {'=' * 12}")


def clone_state(state: GameState) -> GameState:
    return json.loads(json.dumps(state))


# === TEST SCENARIOS ===
def test_agent_contracts():
    print_header("Test A: Agent Contracts (Validation)")
    try:
        EngineUpdate(
            reasoning_trace="Spike damage overflow",
            narrative_reason="",
            hp_updates=[DamageTarget(target_name="Jogador", damage_amount=999)],
        )
    except ValueError as exc:
        print(f"✅ High damage rejected: {exc}")

    corrected = EngineUpdate(
        reasoning_trace="Negative damage clamp",
        narrative_reason="",
        hp_updates=[DamageTarget(target_name="Jogador", damage_amount=-50)],
    )
    print(f"🔧 Negative damage clamped to: {corrected.hp_updates[0].damage_amount}")

    try:
        EngineUpdate(
            reasoning_trace="Stamina too low",
            narrative_reason="",
            player_stamina_change=-50,
        )
    except ValueError as exc:
        print(f"✅ Stamina guard triggered: {exc}")


def test_persistence():
    print_header("Test B: Persistence Roundtrip")
    state = create_base_state()
    state["messages"].append(HumanMessage(content="Salvar jogo!"))
    fname = "test_save"
    save_msg = save_game(state, fname)
    print(save_msg)
    restored = load_game(fname)
    os.remove(os.path.join("saves", f"{fname}.json"))
    identical = state["player"] == restored["player"] and state["world"] == restored["world"]
    print(f"Restored state matches: {identical}")


def test_bestiary_spawner():
    print_header("Test C: Bestiary Spawner")
    for name in ["Rat", "Ancient Void Dragon Boss"]:
        tier = infer_enemy_tier(name)
        print(f"Name: {name} -> Tier: {tier.name}")
        enemy = generate_new_enemy(name, context="Arena de testes")
        print(f"Generated enemy: {json.dumps(enemy, ensure_ascii=False, indent=2)}")
        cached = get_enemy_template(name)
        print(f"Cache available: {cached is not None}")


def test_npc_designer():
    print_header("Test D: NPC Designer")
    for name in ["Beggar", "King of Shadows"]:
        tier = infer_npc_tier(name)
        print(f"Name: {name} -> Tier: {tier.name}")
        npc = generate_new_npc(name, context="Cidade portuária")
        print(f"Generated NPC: {npc}")


def test_character_pipeline():
    print_header("Test J: Character Pipeline")
    hero = create_player_character(
        {
            "name": "TestHero",
            "class_name": "Warrior",
            "race": "Human",
        }
    )
    required_keys = ["hp", "attributes", "inventory"]
    missing = [k for k in required_keys if k not in hero]
    print(f"Hero generated: {hero}")
    if missing:
        print(f"⚠️ Missing keys: {missing}")
    else:
        print("✅ Character includes HP, attributes, and inventory")


def test_prologue_generation():
    print_header("Test K: Prologue Generation")
    hero = {
        "name": "TestHero",
        "class_name": "Warrior",
        "race": "Human",
    }
    prologue = generate_prologue(hero)
    print(f"Prologue: {json.dumps(prologue, ensure_ascii=False, indent=2)}")
    has_fields = all(
        key in prologue for key in ["starting_location", "intro_narrative", "quest_plan"]
    )
    print(f"Field presence OK: {has_fields}")


def test_archivist_memory():
    print_header("Test L: Archivist (Dynamic Memory)")
    sample_fact = "The Sword of Zorg was forged in the fires of Mount Doom."
    with mock.patch("rag.add_to_lore_index") as mock_add:
        archive_narrative(sample_fact)
        if mock_add.called:
            print("✅ RAG index updated via archivist.")
        else:
            print("⚠️ Archivist returned NONE or skipped update.")


def test_router_navigation():
    print_header("Test E: Router (Navigation)")

    combat_state = create_combat_state()
    combat_state["messages"].append(HumanMessage(content="Attack goblin"))
    print("Attack goblin ->", dm_router_node(combat_state))

    social_state = create_social_state()
    social_state["messages"].append(HumanMessage(content="Talk to King"))
    print("Talk to King ->", dm_router_node(social_state))

    missing_npc_state = create_social_state()
    missing_npc_state["messages"].append(HumanMessage(content="Talk to Ghost"))
    print("Talk to Ghost ->", dm_router_node(missing_npc_state))

    rules_state = create_base_state()
    rules_state["messages"].append(HumanMessage(content="Climb wall"))
    print("Climb wall ->", dm_router_node(rules_state))


def test_storyteller_plan_execute():
    print_header("Test F: Storyteller (Plan & Execute)")
    state = create_base_state()
    state["world"]["quest_plan"] = ["Find key", "Open door"]
    state["world"]["quest_plan_origin"] = state["world"]["current_location"]
    state["messages"].append(HumanMessage(content="I search the desk for clues."))
    result = storyteller_node(state)
    updated_plan = result.get("world", {}).get("quest_plan", [])
    print(f"Narrative: {result['messages'][0].content if 'messages' in result else ''}")
    print(f"Updated quest plan: {updated_plan}")


def test_combat_agents():
    print_header("Test G: Combat Agent (Tactics)")

    # Minion flow
    minion_state = create_combat_state()
    minion_state["messages"].append(HumanMessage(content="Strike the goblin"))
    minion_result = combat_node(minion_state)
    print("Minion combat response:", minion_result.get("messages", []))

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
    print("Boss strategy directive:", boss_strategy)
    boss_result = combat_node(boss_state)
    print("Boss combat response:", boss_result.get("messages", []))


def test_rules_agent():
    print_header("Test H: Rules Agent (Physics/RAG)")
    state = create_base_state()
    state["messages"].append(HumanMessage(content="I jump off a 30m cliff"))
    result = rules_node(state)
    print("Rules agent response:", result.get("messages", []))


def test_npc_actor_memory():
    print_header("Test I: NPC Actor (Memory)")
    state = create_social_state()
    state["active_npc_name"] = "Bob"
    state["messages"].append(HumanMessage(content="How are the sales today?"))
    result = npc_actor_node(state)
    print("NPC reply:", result.get("messages", []))
    updated_npc = result.get("npcs", {}).get("Bob")
    if updated_npc:
        print("Updated relationship:", updated_npc.get("relationship"))
        print("Memory log tail:", updated_npc.get("memory", [])[-1:])


# === CLI MENU ===
def run_menu():
    options = {
        "1": ("Core & Governance", [test_agent_contracts, test_persistence]),
        "2": ("AI Services (Generation & RAG)", [test_bestiary_spawner, test_npc_designer]),
        "3": ("Agent Routing & Logic", [test_router_navigation]),
        "4": ("Node Execution (Brains)", [
            test_storyteller_plan_execute,
            test_combat_agents,
            test_rules_agent,
            test_npc_actor_memory,
        ]),
        "5": (
            "Dynamic Start & Archivist",
            [test_character_pipeline, test_prologue_generation, test_archivist_memory],
        ),
        "0": ("Exit", []),
    }

    while True:
        print("\n=== 🧪 COMPLETE V8 ENGINE TEST SUITE ===")
        for key, (label, _) in options.items():
            print(f"{key}. {label}")
        choice = input("Select option: ")

        if choice == "0":
            break
        if choice in options:
            _, funcs = options[choice]
            for func in funcs:
                func()
        else:
            print("Invalid option. Try again.")


if __name__ == "__main__":
    run_menu()
