"""SPEC-307 Etapa 3: migracao v1 -> v2 sem salto de estacao (R19-R21)."""

from __future__ import annotations

import copy

import pytest

from services import world_calendar as wc
from services import world_engine as we
from tests.spec302_helpers import make_state
from tests.spec303_helpers import cal_state, run, step, v1_cal, zero_cal


@pytest.fixture(autouse=True)
def _mode_on(monkeypatch):
    monkeypatch.setenv("RPG_WORLD_ENGINE", "on")
    monkeypatch.setenv("RPG_CALENDAR", "on")


@pytest.mark.parametrize("offset", [0, 17, 40])
def test_migrate_v1_preserves_season_and_year_on_day(offset):
    v1 = {**v1_cal("primavera", 1), "epoch_offset": offset}
    for day in range(1, 57):
        v2 = wc.migrate_calendar(v1, "g", day)
        old, new = wc.season_at(v1, day), wc.season_at(v2, day)
        assert new["season"] == old["season"], (offset, day)
        assert new["year"] == old["year"], (offset, day)
        assert v2["version"] == 2 and v2["migrated_from"] == 1
        assert v2["anchor_day"] == v1["anchor_day"] and v2["first_turn_day"] == v1["first_turn_day"]
    # dia 30 em inverno d=5 -> 12o dia de Vorrnak (exemplo da spec)
    inv = v1_cal("inverno", 26)
    v2 = wc.migrate_calendar(inv, "g", 30)
    d = wc.date_at(v2, 30)
    assert (d["month_id"], d["day_of_month"]) == ("vorrnak", 12)


def test_hook_migrates_instead_of_recreating():
    v1 = v1_cal("inverno", 3)
    st = cal_state(v1)
    step(st, 5)
    cal = st["world_sim"]["calendar"]
    assert cal["version"] == 2 and cal["migrated_from"] == 1
    assert cal["anchor_day"] == v1["anchor_day"]
    assert st["world"]["season"]["id"] == wc.season_at(v1, 5)["season"] == "inverno"
    assert st["world"]["date"]["day"] == 5
    frozen = copy.deepcopy(cal)
    run(st, 6, 20)
    assert st["world_sim"]["calendar"] == frozen  # migra 1x; depois congelado


def test_active_festa_kept_announced_rescheduled():
    gid = "g-303"
    st = cal_state(zero_cal(), game_id=gid)
    st["world_sim"]["calendar"] = v1_cal("verao", 7)
    st["world_sim"]["festivals"] = [
        {
            "festa_id": "ativa-1",
            "festival_id": "dia_da_fundacao",
            "year": 1,
            "start_day": 4,
            "end_day": 9,
            "status": "ativa",
            "location_ids": ["nova_arcadia"],
        },
        {
            "festa_id": "anun-1",
            "festival_id": "noite_dos_nomes",
            "year": 1,
            "start_day": 40,
            "end_day": 41,
            "status": "anunciada",
            "location_ids": [],
        },
    ]
    step(st, 5)
    ids = {r["festa_id"]: r for r in st["world_sim"]["festivals"]}
    assert ids["ativa-1"]["end_day"] == 9 and ids["ativa-1"]["status"] == "ativa"
    assert "anun-1" not in ids  # descartada; o agendamento v2 recalcula o ano


def test_no_festival_twice_same_year_after_migration():
    gid = "g-twice"
    st = cal_state(v1_cal("verao", 1), game_id=gid)
    ran = wc.festa_id(gid, "dia_da_fundacao", 1)
    st["world_sim"]["festivals"] = [
        {
            "festa_id": ran,
            "festival_id": "dia_da_fundacao",
            "year": 1,
            "start_day": 1,
            "end_day": 3,
            "status": "encerrada",
            "location_ids": ["nova_arcadia"],
        }
    ]
    for d in range(2, 160):
        step(st, d)
    mine = [r for r in st["world_sim"]["festivals"] if r["festival_id"] == "dia_da_fundacao"]
    assert [r for r in mine if r["year"] == 1] == [mine[0]] and mine[0]["status"] == "encerrada"
    assert len({r["festa_id"] for r in mine}) == len(mine)


def test_save_without_calendar_creates_v2_next_tick():
    st = make_state("legacy", 80)
    sim = we.ensure_world_sim(st, 80, st["factions"])
    st["world_sim"] = sim
    assert "calendar" not in sim
    assert "date" not in st["world"]  # ate o 1o dia virado: rotulo legado
    step(st, 81)
    cal = st["world_sim"]["calendar"]
    assert cal["version"] == 2 and cal["anchor_day"] == 80 and "migrated_from" not in cal
    assert st["world"]["date"]["day"] == 81


def test_save_load_roundtrip_v1_v2_none(tmp_path, monkeypatch):
    import persistence

    monkeypatch.setenv("RPG_RUNTIME_PROFILE", "legacy")
    monkeypatch.setattr(persistence, "SAVES_DIR", str(tmp_path))
    for n, cal in enumerate((v1_cal("verao", 5), zero_cal(), None)):
        gid = f"00000000-0000-4000-8000-00000000030{n}"
        sim = we.ensure_world_sim({"game_id": gid}, 1, [])
        if cal:
            sim["calendar"] = cal
        state = {
            "game_id": gid,
            "messages": [],
            "player": {},
            "world": {"world_clock": {"day": 6, "period": "Manhã"}},
            "world_sim": sim,
        }
        assert persistence.save_game_state(state)
        loaded = persistence.load_game_state(persistence.save_path(gid))
        assert loaded["world_sim"].get("calendar") == cal
        read = wc.calendar_for_read(loaded["world_sim"], 6)
        if cal is None:
            assert read is None
        else:
            assert read and read["version"] == 2
            assert wc.date_label(read, 6)
