"""Fixture compartilhada da SPEC-309: heroi em Skallgard, cerco nao percebido em Brekmar."""

from __future__ import annotations

from services import world_director as wd

FACT_B = "Há sinais de fome em"


def world_state_two_regions(*, perceive_siege: bool = False, season: str | None = None) -> dict:
    siege = wd._ev(
        "g",
        4,
        "location_state_changed",
        "brekmar",
        {
            "state": "cerco",
            "previous": "",
            "severity": 2,
            "crisis_id": "c-siege",
            "cause": "guerra",
            "day": 4,
        },
    )
    siege["turn"] = 8
    warn = wd._ev(
        "g",
        5,
        "world_crisis_warning",
        "skallgard",
        {"kind": "fome", "region_id": "skallgard", "crisis_id": "c-fome", "earliest_day": 9},
    )
    warn["turn"] = 10
    fate = wd._ev(
        "g", 5, "companion_fate", "comp-zed", {"name": "Zedrik", "fate": "morto", "day": 5}
    )
    fate["turn"] = 10
    ledger = [warn["event_id"]] + ([siege["event_id"]] if perceive_siege else [])
    world = {
        "current_location_id": "skallgard",
        "current_location": "Skallgard",
        "world_clock": {"day": 5, "period": "Manhã"},
        "turn_count": 11,
        "visited": ["skallgard"],
    }
    if season:
        world["season"] = {"id": season}
    return {
        "game_id": "g",
        "event_log": [siege, warn, fate],
        "world_projection": {
            "location_states": {
                "brekmar": {"state": "cerco", "severity": 2, "since_day": 4, "crisis_id": "c-siege"}
            }
        },
        "world_sim": {"perceived_ids": ledger, "festivals": []},
        "world": world,
        "chronicle": [],
    }
