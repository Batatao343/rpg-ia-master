"""SPEC-286 — herói inconsciente: perfil escolhe recuperação; guard grava rota."""

import random

from playtest.profiles import PROFILES
from playtest.runner import _run_turn
from services.actor_lifecycle import evaluate_action


def _unconscious_state(danger: int = 4) -> dict:
    return {
        "player": {"conscious": False, "vitalidade": 0, "max_vitalidade": 18},
        "world": {"danger_level": danger, "current_location_id": "pm_profundezas"},
        "combat": {"active": False},
    }


def test_profiles_never_travel_when_unconscious():
    for name, factory in PROFILES.items():
        state = _unconscious_state()
        decision = factory.decide(state, random.Random(1))
        assert evaluate_action(state, decision.text)["allowed"], (name, decision.text)
        assert evaluate_action(state, decision.text)["action_kind"] == "recovery"


def test_incapacitated_is_recovery_too():
    state = _unconscious_state()
    state["player"] = {"incapacitated": True, "vitalidade": 0, "max_vitalidade": 18}
    decision = PROFILES["combate"].decide(state, random.Random(1))
    assert evaluate_action(state, decision.text)["allowed"]


class _GuardGraph:
    def invoke(self, state):
        return state

    def stream(self, state, stream_mode=None):
        yield ("updates", {"action_guard": {"action_guard_blocked": True}})
        yield ("values", dict(state))


def test_guard_refusal_gets_route_not_empty():
    nodes: list[str] = []
    _final, route = _run_turn(_GuardGraph(), {"combat": None}, nodes_executed=nodes)
    assert route == "action_guard"
