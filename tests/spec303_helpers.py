"""Helpers compartilhados dos testes da SPEC-303 (calendario, estacoes, festas)."""

from __future__ import annotations

from services import world_calendar as wc
from services import world_engine as we
from services.event_processor import _build_event, apply_event
from tests.spec302_helpers import make_state, world_at


def cal_for(season: str, day: int = 1, *, season_days: int = 14, anchor: int = 1) -> dict:
    """Calendario cujo `day` e o 1o dia de `season` (`first_turn_day` irrelevante)."""
    year = 4 * season_days
    doy = wc.SEASONS.index(season) * season_days
    return {
        "version": 1,
        "season_days": season_days,
        "epoch_offset": (doy - (day - 1)) % year,
        "anchor_day": anchor,
        "first_turn_day": anchor + 6,
    }


def zero_cal(season_days: int = 14) -> dict:
    """Ano comeca no dia 1 (epoch_offset 0): verao d7 = dia 21, outono d1 = dia 29."""
    return {
        "version": 1,
        "season_days": season_days,
        "epoch_offset": 0,
        "anchor_day": 1,
        "first_turn_day": 7,
    }


def cal_state(cal: dict, game_id: str = "g-303", day: int = 1, **extra) -> dict:
    st = make_state(game_id, day, **extra)
    sim = we.ensure_world_sim(st, day, st["factions"])
    sim["calm_until_day"] = 10_000  # sem avisos de crise (testes isolam o calendario)
    sim["calendar"] = cal
    st["world_sim"] = sim
    return st


def step(st: dict, day: int):
    """Um tick (day-1 -> day) aplicando os eventos do motor na projection, como o arquivista."""
    before, after = world_at(day - 1), world_at(day)
    after["current_location_id"] = st["world"].get("current_location_id", "")
    before["current_location_id"] = after["current_location_id"]
    res = we.advance_days(st, before, after, st["factions"], {})
    st[res.sim_key] = res.world_sim
    st["world"] = res.world
    for ev in res.pending_events:
        built = _build_event(ev, day)
        st["event_log"].append(built)
        st["world_projection"] = apply_event(built, st["world_projection"])
    return res


def run(st: dict, first: int, last: int) -> list:
    return [step(st, d) for d in range(first, last + 1)]
