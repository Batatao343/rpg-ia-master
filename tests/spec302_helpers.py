"""Helpers compartilhados dos testes da SPEC-302 (motor de mundo)."""

from __future__ import annotations

import copy

from services import world_engine as we
from services import world_pressures as wp


def world_at(day: int, period: str = "Manhã", **extra) -> dict:
    return {"world_clock": {"day": day, "period": period}, "turn_count": day, **extra}


def make_state(game_id: str = "g-302", day: int = 1, **extra) -> dict:
    import gamedata

    return {
        "game_id": game_id,
        "event_log": [],
        "world_projection": {},
        "factions": gamedata.seed_factions(),
        "world": world_at(day),
        **extra,
    }


def tick(state: dict, day_from: int, day_to: int, factions=None):
    """Roda advance_days e grava o sim de volta no estado (como o storyteller faria)."""
    before, after = world_at(day_from), world_at(day_to)
    res = we.advance_days(
        state, before, after, factions if factions is not None else state["factions"], {}
    )
    if res.world_sim is not None:
        state[res.sim_key] = res.world_sim
    state["world"] = res.world
    return res


def fresh_sim(day: int = 1, factions=None, calm: int = 0) -> dict:
    sim = we._new_sim("g-302", day, factions or [], "on")
    sim["calm_until_day"] = day + calm
    return sim


def set_pressure(sim: dict, region: str, kind: str, value: int) -> None:
    sim["pressures"][region][kind] = value
    sim["bands"], _ = wp.update_bands(sim["bands"], sim["pressures"])


def quiet(cfg_fixture_dict: dict | None = None):
    """Copia da config sem ruido/surtos (dinamica deterministica por causas)."""
    cfg = copy.deepcopy(wp.get_config())
    cfg["constants"]["noise"] = 0
    cfg["constants"]["surge_p"] = 0.0
    return cfg
