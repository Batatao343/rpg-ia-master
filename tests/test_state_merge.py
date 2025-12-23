import copy

import pytest
from langchain_core.messages import HumanMessage, SystemMessage

from engine_utils import (
    EngineUpdate,
    DamageTarget,
    apply_state_update,
    execute_engine,
)


def base_state():
    return {
        "messages": [],
        "next": None,
        "player": {
            "name": "Tester",
            "class_name": "Debug",
            "race": "Humano",
            "hp": 30,
            "max_hp": 30,
            "mana": 10,
            "max_mana": 10,
            "stamina": 10,
            "max_stamina": 10,
            "gold": 0,
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
            "inventory": [],
            "known_abilities": [],
            "defense": 10,
            "attack_bonus": 0,
            "active_conditions": [],
        },
        "world": {
            "current_location": "Lab",
            "time_of_day": "Dia",
            "turn_count": 0,
            "weather": "Neutro",
            "quest_plan": [],
            "quest_plan_origin": None,
        },
        "campaign_plan": None,
        "needs_replan": False,
        "enemies": [],
        "party": [],
        "npcs": {},
        "active_npc_name": None,
        "active_plan_step": None,
        "router_confidence": None,
        "last_routed_intent": None,
    }


class FakeTool:
    def __init__(self):
        self.tool_calls = []

    def invoke(self, _input):
        return self  # tool_calls permanece vazio


class FakeLLM:
    is_fallback = False

    def __init__(self, update: EngineUpdate):
        self.update = update

    def bind_tools(self, *_args, **_kwargs):
        return FakeTool()

    def with_structured_output(self, *_args, **_kwargs):
        return self

    def with_retry(self, **_kwargs):
        return self

    def invoke(self, _input):
        return self.update


def test_preserves_world_and_next_without_mutation():
    state = base_state()
    state["world"]["quest_plan"] = ["a", "b"]
    state["next"] = "storyteller"
    state["campaign_plan"] = {"location": "Lab", "beats": []}
    state["needs_replan"] = True
    snapshot = copy.deepcopy(state)

    update = EngineUpdate(reasoning_trace="t", narrative_reason="nada")
    new_state = apply_state_update(update, state)

    assert new_state["world"]["quest_plan"] == ["a", "b"]
    assert new_state["next"] == "storyteller"
    assert new_state["campaign_plan"]["location"] == "Lab"
    assert new_state["needs_replan"] is True
    assert state == snapshot  # estado original intacto


def test_enemy_damage_does_not_hit_player():
    state = base_state()
    state["enemies"] = [{"id": "e1", "name": "Goblin", "hp": 10, "status": "ativo", "active_conditions": []}]
    update = EngineUpdate(
        reasoning_trace="dano em goblin",
        narrative_reason="golpe",
        hp_updates=[DamageTarget(target_name="Goblin", damage_amount=5)],
    )
    new_state = apply_state_update(update, state)

    assert new_state["enemies"][0]["hp"] == 5
    assert new_state["player"]["hp"] == state["player"]["hp"]


def test_spawn_enemy_preserves_world_and_next():
    state = base_state()
    state["world"]["turn_count"] = 5
    state["next"] = "rules_agent"
    update = EngineUpdate(reasoning_trace="spawn", narrative_reason="um inimigo surge", spawn_enemy_type="Goblin Batedor")

    new_state = apply_state_update(update, state)

    assert new_state["world"]["turn_count"] == 5
    assert new_state["next"] == "rules_agent"
    assert len(new_state["enemies"]) == 1
    assert new_state["enemies"][0]["status"] == "ativo"


def test_resource_clamp_respects_max():
    state = base_state()
    state["player"]["mana"] = 9
    state["player"]["stamina"] = 9
    update = EngineUpdate(
        reasoning_trace="buff",
        narrative_reason="recupera",
        player_mana_change=5,
        player_stamina_change=5,
    )
    new_state = apply_state_update(update, state)

    assert new_state["player"]["mana"] == 10  # clamp em max_mana
    assert new_state["player"]["stamina"] == 10  # clamp em max_stamina


def test_execute_engine_blocks_damage_without_tool():
    state = base_state()
    messages = [HumanMessage(content="Ataco o alvo.")]
    update = EngineUpdate(
        reasoning_trace="dano sem dado",
        narrative_reason="golpe direto",
        hp_updates=[DamageTarget(target_name="Valerius", damage_amount=6)],
    )
    fake_llm = FakeLLM(update)

    result = execute_engine(fake_llm, SystemMessage(content="sys"), messages, state, "Teste")

    assert result["player"]["hp"] == state["player"]["hp"]  # dano bloqueado
    last_msg = result["messages"][-1].content
    assert "dano foi ignorado" in last_msg

