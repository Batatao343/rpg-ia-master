"""Autonomous AI-vs-AI simulation with verbose chain-of-thought logging."""

import random
from typing import Tuple

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage

from character_creator import create_player_character
from llm_setup import ModelTier, get_llm
from main import app as dm_graph
from prologue_manager import generate_prologue
from test_runner import create_base_state


TURN_LIMIT = 10


def get_last_ai_narrative(state) -> str:
    """Return the most recent AI narrative in the message stack."""
    for msg in reversed(state.get("messages", [])):
        if isinstance(msg, AIMessage):
            return msg.content
    return "The adventure awaits..."


def get_ai_player_action(state) -> Tuple[str, str]:
    """Use a SMART-tier LLM to propose the player's thought and next action."""
    narrative = get_last_ai_narrative(state)
    quest_plan = state.get("world", {}).get("quest_plan", [])
    player = state.get("player", {})

    system_msg = SystemMessage(
        content=(
            "You are the Player. Read the narrative and game state, think privately, "
            "then output a concise action command the engine can execute."
        )
    )
    human_msg = HumanMessage(
        content=(
            "Format exactly two lines:\n"
            "Thought: <short internal reasoning>\n"
            "Action: <one actionable command>\n"
            f"Narrative: {narrative}\n"
            f"Quest plan: {quest_plan}\n"
            f"HP: {player.get('hp', '?')}/{player.get('max_hp', '?')} | "
            f"Stamina: {player.get('stamina', '?')} | Mana: {player.get('mana', '?')}\n"
            f"Inventory: {player.get('inventory', [])}"
        )
    )

    llm = get_llm(temperature=0.4, tier=ModelTier.SMART)
    result = llm.invoke([system_msg, human_msg])
    content = result.content if hasattr(result, "content") else str(result)

    thought, action = "", ""
    for line in content.splitlines():
        if line.lower().startswith("thought"):
            thought = line.split(":", 1)[-1].strip()
        if line.lower().startswith("action"):
            action = line.split(":", 1)[-1].strip()
    return thought or content.strip(), action or "Wait and observe"


def bootstrap_state():
    """Generate a random hero, prologue, and initial state."""
    seed_names = ["Aerin", "Corvin", "Lyra", "Thorne"]
    seed_classes = ["Ranger", "Wizard", "Warrior", "Bard"]
    seed_races = ["Human", "Elf", "Dwarf", "Tiefling"]
    manual_args = {
        "name": random.choice(seed_names),
        "class_name": random.choice(seed_classes),
        "race": random.choice(seed_races),
    }
    player_data = create_player_character(manual_args)
    prologue_data = generate_prologue(player_data)

    state = create_base_state()
    state["player"] = player_data
    state["world"].update(
        {
            "current_location": prologue_data.get(
                "starting_location", state["world"].get("current_location", "Unknown")
            ),
            "quest_plan": prologue_data.get("quest_plan", []),
            "quest_plan_origin": prologue_data.get("quest_plan_origin"),
        }
    )
    intro_text = prologue_data.get("intro_narrative", "The adventure begins...")
    state["messages"] = [AIMessage(content=intro_text)]
    return state, intro_text


def run_simulation(turns: int = TURN_LIMIT):
    print("=== 🤖 AI vs. AI Simulation (Verbose) ===")
    state, intro_text = bootstrap_state()
    print(f"Intro: {intro_text}\n")

    for turn in range(1, turns + 1):
        narrative = get_last_ai_narrative(state)
        thought, action = get_ai_player_action(state)

        print("--- TURN", turn, "---")
        print(f"📝 [NARRATIVE (Storyteller)]: {narrative}")
        print(f"🧠 [PLAYER THOUGHT]: {thought}")
        print(f"⚔️ [PLAYER ACTION]: {action}")

        state["messages"].append(HumanMessage(content=action))
        result = dm_graph.invoke(state)
        state = result

        engine_msg = get_last_ai_narrative(state)
        print(f"⚙️ [ENGINE RESULT]: {engine_msg}")
        print("📜 [ARCHIVIST]: Check runtime logs for saved lore entries")
        print("----------------")

    print("Simulation complete.")


if __name__ == "__main__":
    run_simulation()
