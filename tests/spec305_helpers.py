"""Helpers compartilhados dos testes da SPEC-305 (quests de mundo com prazo)."""

from __future__ import annotations

from services import location_states as ls
from services import world_director as wd
from tests.spec302_helpers import fresh_sim, make_state

GID = "g-302"


def base_state(day: int = 17, loc: str = "brekmar", **extra) -> dict:
    """Estado com motor `on`, sim fresco e o jogador em `loc` (ids reais do mapa)."""
    import gamedata

    state = make_state(GID, day=day)
    place = gamedata.get_location(loc)
    state["world"] = {
        **state["world"],
        "current_location_id": loc,
        "current_location": place["name"],
        "turn_count": day,
    }
    state["world_sim"] = fresh_sim(day)
    state.update({"quests": [], "location_heard": {}, "npcs": {}, "pending_world_events": []})
    state.update(extra)
    return state


def add_crisis(
    state: dict,
    kind: str = "praga",
    region: str = "brekmar",
    *,
    warned: int = 14,
    start: int | None = 17,
    escalation: int | None = 23,
    loc: str = "brekmar",
    faction_id: str = "",
    cid: str = "crise-1",
    route: list[str] | None = None,
) -> dict:
    rec = {
        "crisis_id": cid,
        "kind": kind,
        "region_id": region,
        "location_id": loc if start is not None else "",
        "loc_state": ls.CRISIS_STATE.get(kind, ""),
        "faction_id": faction_id,
        "warned_day": warned,
        "start_day": start,
        "escalation_day": escalation if start is not None else None,
        "severity": 1 if start is not None else 0,
        "end_day": None,
        "resolution": "",
    }
    if route:
        rec["route"] = route
    state["world_sim"]["crises"].append(rec)
    return rec


def crisis_item(
    kind: str = "praga",
    region: str = "brekmar",
    loc: str = "brekmar",
    day: int = 17,
    tpl: str = "crise.inicio",
    item_kind: str = "crise",
    subject: str = "ev-open-1",
    **params,
) -> dict:
    """Item de digest como o diretor da 302 emite (`digest_item`)."""
    return wd.digest_item(
        GID, day, item_kind, region, loc, f"{kind}.{tpl}", {"local": loc, **params}, subject
    )
