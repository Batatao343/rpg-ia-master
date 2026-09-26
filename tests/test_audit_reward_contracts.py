"""Independent regressions from the September audit; no provider or disk writes."""
from __future__ import annotations

from copy import deepcopy
from types import SimpleNamespace

import pytest
from langchain_core.messages import HumanMessage

from agents import storyteller
from inventory import add_item, get_qty
from services.turn_outcome import capture_baseline, finalize_outcome


def _state() -> dict:
    return {
        "game_id": "audit-rewards", "messages": [HumanMessage(content="Observo a rua.")],
        "player": {"name": "Ari", "class_name": "Devoto do Abismo", "level": 1,
                   "xp": 0, "inventory": [], "vitalidade": 8, "max_vitalidade": 8},
        "world": {"current_location_id": "nova_arcadia", "current_location": "Nova Arcádia",
                  "turn_count": 4, "danger_level": 1,
                  "world_clock": {"day": 1, "period": "Manhã"}, "visited": ["nova_arcadia"]},
        "npcs": {}, "factions": [], "faction_intel": {}, "quests": [],
        "campaign_plan": {}, "event_log": [], "world_projection": {},
    }


@pytest.fixture
def story(monkeypatch):
    monkeypatch.setattr(storyteller, "build_context_pack", lambda *a, **k: SimpleNamespace(
        lore_block="", memory_block="", world_state_block=""))
    monkeypatch.setattr(storyteller, "simulate_world", lambda s, w, *a: (w, ""))
    monkeypatch.setattr(storyteller, "check_encounter", lambda *a, **k: None)

    def run(state: dict, **fields) -> dict:
        update = storyteller.StoryUpdate(narrative="A cena permanece tranquila.", **fields)
        llm = SimpleNamespace(with_structured_output=lambda _: SimpleNamespace(invoke=lambda _: update))
        monkeypatch.setattr(storyteller, "get_llm", lambda **k: llm)
        return storyteller.storyteller_node(state)
    return run


@pytest.mark.parametrize("plan", [
    {}, {"beats": [], "current_step": 0},
    {"beats": [{"description": "Investigar", "status": "pending"}], "current_step": 1},
    {"beats": [{"description": "Investigar", "status": "done"}], "current_step": 0},
    {"beats": [{"description": "Investigar", "status": "pending"}], "current_step": -1},
    {"beats": [{"description": "Investigar", "status": "pending"}], "current_step": None},
    {"beats": [{"description": "Investigar", "status": "pending"}], "current_step": "0"},
])
def test_invalid_or_completed_beat_cannot_grant_xp(story, plan: dict) -> None:
    state = _state()
    state["campaign_plan"] = deepcopy(plan)
    out = story(state, beat_completed=True)
    assert out.get("player", state["player"])["xp"] == 0
    assert out["campaign_plan"] == plan
    assert state["campaign_plan"] == plan


def test_valid_beat_rewards_once_and_does_not_mutate_input(story) -> None:
    state = _state()
    state["campaign_plan"] = {"beats": [{"description": "Investigar", "status": "pending"}],
                              "current_step": 0}
    before = deepcopy(state)
    out = story(state, beat_completed=True)
    assert out["player"]["xp"] == 150
    assert out["campaign_plan"]["current_step"] == 1
    assert out["campaign_plan"]["beats"][0]["status"] == "done"
    assert state == before
    repeated = story({**state, **out}, beat_completed=True)
    assert repeated.get("player", out["player"])["xp"] == 150


def test_prologue_beat_never_grants_xp(story) -> None:
    state = _state()
    state["world"]["turn_count"] = 1
    state["campaign_plan"] = {"beats": [{"description": "Chegar", "status": "pending"}],
                              "current_step": 0}
    out = story(state, beat_completed=True)
    assert out.get("player", state["player"])["xp"] == 0


@pytest.mark.parametrize("already_owned", [False, True])
def test_unique_aliases_granted_once_even_before_projection_updates(story, already_owned: bool) -> None:
    from gamedata import ARTIFACTS_DB
    item_id = "art_adaga_vidro_dragao"
    state = _state()
    if already_owned:
        state["player"]["inventory"] = add_item([], item_id)
    before = deepcopy(state)
    out = story(state, items_gained=[ARTIFACTS_DB[item_id]["name"], item_id])
    player = out.get("player", state["player"])
    assert get_qty(player["inventory"], item_id) == 1
    events = [e for e in out.get("pending_world_events", []) if e["type"] == "unique_item_claimed"]
    assert len(events) == (0 if already_owned else 1)
    assert state == before
    if not already_owned:
        assert not out.get("rejected_item_claims")
        assert not out.get("narrative_rejections")


@pytest.mark.parametrize("quantities,expected", [([1, 1], 2), ([2, 3], 5), ([1, 0, -2], 1)])
def test_receipt_sums_repeated_rows_and_ignores_nonpositive_quantities(quantities, expected) -> None:
    state = _state()
    state["player"]["inventory"] = [{"id": "art_adaga_vidro_dragao", "qty": q} for q in quantities]
    assert capture_baseline(state)["inventory"] == {"art_adaga_vidro_dragao": expected}


def test_second_nonstackable_item_appears_in_receipt_and_survives_serialization() -> None:
    import uuid
    import persistence
    state = _state()
    state["game_id"] = str(uuid.uuid4())
    state["player"]["inventory"] = add_item([], "Espada Gasta")
    item_id = state["player"]["inventory"][0]["id"]
    state["turn_baseline"] = capture_baseline(state)
    state["player"]["inventory"] = add_item(state["player"]["inventory"], item_id)
    outcome = finalize_outcome(state)
    assert outcome["items_gained"] == {item_id: 1}
    assert finalize_outcome(state) == outcome
    state["last_turn_outcome"] = outcome
    loaded = persistence._raw_to_state(persistence._state_to_save_data(state, state["game_id"]))
    assert loaded["last_turn_outcome"] == outcome
