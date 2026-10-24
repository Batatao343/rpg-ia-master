"""SPEC-303 Etapa 3: clima e encontros modulados pela estacao (R8, R9, R14b)."""

from __future__ import annotations

import random

import pytest

import gamedata
import world_utils as wu
from services import world_calendar as wc


@pytest.fixture(autouse=True)
def _mode_on(monkeypatch):
    monkeypatch.setenv("RPG_WORLD_ENGINE", "on")
    monkeypatch.setenv("RPG_CALENDAR", "on")


def _freq(location_id: str, season: str | None, n: int = 2000) -> dict[str, int]:
    rng = random.Random(7)
    counts: dict[str, int] = {}
    for _ in range(n):
        w = {"current_location_id": location_id, "weather_state": "nublado"}
        if season:
            w["season"] = {"id": season}
        wu._advance_weather_once(w, rng)
        counts[w["weather_state"]] = counts.get(w["weather_state"], 0) + 1
    return counts


def test_weather_mult_applied_with_injected_rng():
    winter = _freq("skallgard", "inverno")
    summer = _freq("skallgard", "verao")
    assert winter.get("nevasca", 0) > summer.get("nevasca", 0)


def test_weather_zero_sum_falls_back_to_raw(monkeypatch):
    monkeypatch.setattr(
        wc, "weather_multipliers", lambda r, s: {"limpo": 0, "nublado": 0, "nevasca": 0}
    )
    raw = _freq("skallgard", None, 300)
    zero = _freq("skallgard", "inverno", 300)
    assert raw == zero  # soma 0 -> pesos crus (mesmo rng, mesmo resultado)


def test_default_profile_for_regions_without_table():
    assert wc.weather_multipliers("costa_negra", "inverno") == {"chuva": 1.3, "nublado": 1.3}
    assert wc.weather_multipliers("skallgard", "inverno") == {"nevasca": 2.0}
    assert _freq("costa_negra", "verao")["chuva"] < _freq("costa_negra", "outono")["chuva"]


def test_weather_neutral_when_season_none_or_mode_off(monkeypatch):
    base = _freq("skallgard", None, 500)
    assert _freq("skallgard", None, 500) == base
    monkeypatch.setenv("RPG_CALENDAR", "off")
    assert _freq("skallgard", "inverno", 500) == base


def test_no_new_weather_states():
    weather = gamedata.load_json_data("weather.json")
    for region, table in wc._cfg()["weather_mult"].items():
        states = set((weather.get(region) or weather["default"])["states"])
        for season_row in table.values():
            assert set(season_row) <= states


def _loc(region_id: str) -> dict:
    return next(
        loc
        for loc in gamedata.WORLD_MAP["locations"]
        if loc.get("region_id") == region_id and loc.get("kind") != "interior"
    )


def _picks(loc: dict, danger: int, season: str | None, n: int = 400) -> list[str]:
    return [
        (
            wu.pick_encounter_enemy(
                loc,
                danger,
                t,
                projection={},
                bestiary_knowledge={},
                rng=random.Random(t),
                season=season,
            )
            or {}
        ).get("id", "")
        for t in range(n)
    ]


def test_encounter_mult_only_in_weighted_path():
    loc = _loc("skallgard")
    for turn in range(12):  # legado (sem projection/knowledge): identico com ou sem estacao
        assert wu.pick_encounter_enemy(loc, 3, turn) == wu.pick_encounter_enemy(
            loc, 3, turn, season="inverno"
        )
    winter, plain = _picks(loc, 3, "inverno"), _picks(loc, 3, None)
    cold = ("enemy_lobo_invernal", "enemy_yeti")
    assert sum(winter.count(c) for c in cold) > sum(plain.count(c) for c in cold)


def test_encounter_mult_never_changes_tier_or_trigger():
    loc = _loc("skallgard")

    def tiers(ids):
        return {
            "elite" if "elite" in str(gamedata.BESTIARY[i].get("type", "")).lower() else "minion"
            for i in ids
            if i
        }

    for danger in (1, 2, 4):
        assert tiers(_picks(loc, danger, "inverno", 200)) == tiers(_picks(loc, danger, None, 200))
        assert set(_picks(loc, danger, "inverno", 200)) <= set(_picks(loc, danger, None, 200)) | {
            c for c in ("enemy_lobo_invernal", "enemy_yeti")
        }
    # o gatilho (check_encounter) nao le a estacao
    w = {"current_location_id": "skallgard", "turn_count": 5, "danger_level": 4}
    plain = wu.check_encounter(dict(w), [], {}, 50)
    seasoned = wu.check_encounter({**w, "season": {"id": "inverno"}}, [], {}, 50)
    assert (plain is None) == (seasoned is None)


def test_encounter_ids_exist_have_region_not_boss():
    from encounter_budget import is_boss

    for region, by_season in wc._cfg()["encounter_mult"].items():
        for season, row in by_season.items():
            assert season in wc.SEASONS
            for eid in row:
                entry = gamedata.BESTIARY[eid]
                assert region in entry["regions"] and not is_boss(entry)
