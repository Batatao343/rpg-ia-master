"""SPEC-299 — fixtures compartilhadas (lei e crime por região)."""

from __future__ import annotations

from langchain_core.messages import HumanMessage

from services import law


def base_state(loc: str = "nova_arcadia", *, day: int = 2, period: str = "Tarde", **over) -> dict:
    import gamedata

    name = (gamedata.get_location(loc) or {}).get("name", loc)
    state = {
        "game_id": "spec299-game",
        "world": {
            "turn_count": 5,
            "current_location": name,
            "current_location_id": loc,
            "visited": [loc],
            "world_clock": {"day": day, "period": period},
        },
        "player": {"name": "Heroi", "gold": 500, "virtudes": {"agilidade": 2, "mente": 2}},
        "npcs": {
            "Mercador": {
                "name": "Mercador",
                "id": "npc_mercador",
                "role": "mercador",
                "persona": "falante",
                "in_scene": True,
                "home_location_id": loc,
                "relationship": 5,
                "memory": [],
            }
        },
        "party": [],
        "event_log": [],
        "pending_world_events": [],
        "messages": [HumanMessage(content="olho a banca")],
    }
    state.update(over)
    return state


def with_clock(state: dict, clock: int) -> dict:
    day, idx = divmod(clock, 5)
    from world_utils import PERIODS

    world = {**state["world"], "world_clock": {"day": day, "period": PERIODS[idx]}}
    return {**state, "world": world}


def clock_where(state: dict, loc: str, *, patrol: bool) -> int:
    """Primeiro clock (dia 2+) em que a patrulha de `loc` está (ou não) presente."""
    for clock in range(10, 400):
        if law.patrol_present(state, loc, clock) is patrol:
            return clock
    raise AssertionError("sem clock com a patrulha pedida")


def merge(state: dict, updates: dict) -> dict:
    return {**state, **updates}


def commit(state: dict, cand_type="furto", **kw) -> tuple[dict, dict | None, str]:
    cand = {
        "crime_type": cand_type,
        "victim_ref": kw.pop("victim_ref", "local"),
        "covert": kw.pop("covert", False),
        "source": kw.pop("source", "engine"),
        "location_id": state["world"]["current_location_id"],
        "turn": state["world"]["turn_count"],
        "player_text": kw.pop("player_text", ""),
        **kw,
    }
    upd, rec, why = law.register_crime(state, cand)
    return {**state, **upd}, rec, why
