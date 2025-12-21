import unittest
from langchain_core.messages import AIMessage, SystemMessage

from agents.router import dm_router_node
from agents.storyteller import storyteller_node
from engine_utils import execute_engine
from llm_setup import FallbackLLM


def build_base_state(messages):
    return {
        "messages": messages,
        "next": None,
        "player": {
            "name": "Valerius",
            "class_name": "Guerreiro",
            "hp": 10,
            "max_hp": 10,
            "mana": 5,
            "max_mana": 5,
            "stamina": 5,
            "max_stamina": 5,
            "gold": 0,
            "level": 1,
            "xp": 0,
            "alignment": "CN",
            "attributes": {
                "strength": 10,
                "dexterity": 10,
                "constitution": 10,
                "intelligence": 10,
                "wisdom": 10,
                "charisma": 10,
            },
            "inventory": [],
            "known_abilities": [],
            "defense": 10,
            "attack_bonus": 0,
            "active_conditions": [],
        },
        "world": {
            "current_location": "Teste",
            "time_of_day": "dia",
            "turn_count": 0,
            "weather": "claro",
            "quest_plan": [],
            "quest_plan_origin": None,
        },
        "enemies": [],
        "party": [],
        "npcs": {},
        "active_npc_name": None,
    }


class SafetyGuardsTest(unittest.TestCase):
    def test_execute_engine_handles_empty_history(self):
        state = build_base_state([])
        result = execute_engine(
            FallbackLLM("LLM indisponível"),
            SystemMessage(content="contexto"),
            [],
            state,
            "TEST",
        )
        self.assertIn("messages", result)
        self.assertIsInstance(result["messages"][0], AIMessage)

    def test_storyteller_returns_prompt_when_history_missing(self):
        state = build_base_state([])
        result = storyteller_node(state)
        self.assertIsInstance(result["messages"][0], AIMessage)

    def test_dm_router_defaults_to_storyteller_on_empty_history(self):
        state = build_base_state([])
        decision = dm_router_node(state)
        self.assertEqual(decision["next"], "storyteller")

    def test_execute_engine_requires_human_message(self):
        state = build_base_state([AIMessage(content="oi")])
        result = execute_engine(
            FallbackLLM("LLM indisponível"),
            SystemMessage(content="contexto"),
            state["messages"],
            state,
            "TEST",
        )
        self.assertIn("Envie sua próxima ação", result["messages"][0].content)


if __name__ == "__main__":
    unittest.main()
