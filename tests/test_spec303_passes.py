"""SPEC-303 Etapa 4: passos de montanha sazonais (R10, R11, R11b, P6)."""

from __future__ import annotations

import pytest

import gamedata
import world_utils as wu
from services import economy
from services import world_calendar as wc
from services import world_perception as wperc
from tests.spec303_helpers import cal_for, cal_state, run, step


@pytest.fixture(autouse=True)
def _mode_on(monkeypatch):
    monkeypatch.setenv("RPG_WORLD_ENGINE", "on")
    monkeypatch.setenv("RPG_CALENDAR", "on")


def _world(loc_id: str, season: str | None, **extra) -> dict:
    w = {
        "current_location_id": loc_id,
        "current_location": loc_id,
        "world_clock": {"day": 5, "period": "Manhã"},
        "visited": [loc_id],
        **extra,
    }
    if season:
        w["season"] = {"id": season, "label": season, "day_in_season": 1}
    return w


def test_pass_pairs_are_real_connections():
    for p in wc._cfg()["passes"]:
        assert p["b"] in (gamedata.get_location(p["a"]) or {}).get("connections", [])
        assert p["a"] in (gamedata.get_location(p["b"]) or {}).get("connections", [])
        assert set(p["closed_in"]) <= set(wc.SEASONS)


def test_pass_closed_only_in_listed_seasons():
    for season in wc.SEASONS:
        closed = wc.pass_closed(_world("skallgard", season), "montanhas_afiadas", "skallgard")
        assert closed == (season == "inverno")
    assert not wc.pass_closed(_world("skallgard", "inverno"), "skallgard", "sk_salao_do_jarl")
    assert wc.pass_between("skallgard", "montanhas_afiadas")["id"] == "passo_skallgard"


@pytest.mark.parametrize(
    ("src", "dst"), [("montanhas_afiadas", "skallgard"), ("skallgard", "montanhas_afiadas")]
)
def test_winter_crossing_costs_extra_periods(src, dst):
    dest = gamedata.get_location(dst)
    base = wu.travel_cost(_world(src, "verao"), dest)
    assert wu.travel_cost(_world(src, "inverno"), dest) == base + wc.pass_extra_periods()
    assert wu.travel_cost(_world(src, None), dest) == base


def test_winter_crossing_forces_snow_on_arrival():
    dest = gamedata.get_location("skallgard")
    w = wu.apply_travel(_world("montanhas_afiadas", "inverno", weather_state="limpo"), dest)
    assert w["weather_state"] == "nevasca" and w["current_location_id"] == "skallgard"
    summer = wu.apply_travel(_world("montanhas_afiadas", "verao", weather_state="limpo"), dest)
    assert summer["world_clock"]["day"] >= 5
    cost_w = wu.travel_cost(_world("montanhas_afiadas", "inverno"), dest)
    cost_s = wu.travel_cost(_world("montanhas_afiadas", "verao"), dest)
    assert cost_w - cost_s == wc.pass_extra_periods()


def test_winter_crossing_never_refused():
    w = _world("skallgard", "inverno")
    dest = wu.find_travel_destination(w, "viajar para Montanhas Afiadas")
    assert dest and dest["id"] == "montanhas_afiadas"
    assert wu.invalid_travel_message(w, "viajar para Montanhas Afiadas") == ""
    assert wu.travel_cost(w, dest) >= wc.pass_extra_periods()


def test_crossing_note_is_deterministic_fact():
    assert "fechado pela neve" in wc.CROSSING_NOTE and "dia inteiro" in wc.CROSSING_NOTE
    import inspect

    from agents import storyteller

    assert "world_calendar.CROSSING_NOTE" in inspect.getsource(storyteller)


def test_closed_pass_counts_as_blocked_for_trade():
    winter = _world("skallgard", "inverno")
    pairs = wc.seasonal_closed_pairs(winter)
    assert frozenset(("montanhas_afiadas", "skallgard")) in pairs
    assert wc.seasonal_closed_pairs(_world("skallgard", "verao")) == set()
    assert economy.supply_factor("pocao_cura", "skallgard", {}) == 1.0
    assert economy.supply_factor("pocao_cura", "skallgard", {}, pairs) == economy.SCARCE_MULT
    st = {"world": winter, "world_projection": {}, "factions": []}
    summer_st = {**st, "world": _world("skallgard", "verao")}
    assert economy.price("pocao_cura", mode="buy", state=st) > economy.price(
        "pocao_cura", mode="buy", state=summer_st
    )


def test_route_events_untouched_by_season():
    st = cal_state(cal_for("outono", 3))
    results = run(st, 2, 40)
    types = {e["type"] for r in results for e in r.pending_events}
    assert not (types & {"route_blocked", "route_cleared"})
    assert not [e for e in st["event_log"] if (e.get("payload") or {}).get("cause") == "x"]
    assert not (st["world_projection"].get("blocked_routes") or [])


def test_pass_digest_regional_on_close_and_open():
    # inverno comeca no dia 7 e termina no dia 21 (primavera)
    st = cal_state(cal_for("inverno", 7))
    st["world"]["current_location_id"] = "skallgard"
    closes, opens = [], []
    for d in range(2, 23):
        for it in step(st, d).digest:
            if it["kind"] == "passo":
                (closes if it["template_id"] == "passo.fechou" else opens).append(it)
    assert {i["region_id"] for i in closes} == {"montanhas_afiadas", "skallgard"}
    assert {i["region_id"] for i in opens} == {"montanhas_afiadas", "skallgard"}
    tpl = wperc._templates()["templates"]
    assert tpl["passo.fechou"]["visibility"] == tpl["passo.abriu"]["visibility"] == "regional"
    seen = wperc.perceivable(st, closes)
    assert [i["region_id"] for i in seen] == ["skallgard"]
    assert "Montanhas Afiadas" in wperc.render(st, seen[0])
