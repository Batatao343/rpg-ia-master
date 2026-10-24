"""SPEC-303 Etapa 2: hook diario, estacao e baseline de pressao (R7, R12-R14, R25)."""

from __future__ import annotations

import copy
import pathlib

import pytest

from services import world_calendar as wc
from services import world_director as wd
from services import world_engine as we
from services import world_pressures as wp
from tests.spec303_helpers import cal_for, cal_state, run, step


@pytest.fixture(autouse=True)
def _mode_on(monkeypatch):
    monkeypatch.setenv("RPG_WORLD_ENGINE", "on")
    monkeypatch.setenv("RPG_CALENDAR", "on")


def test_hook_registered_pre_order_10():
    row = next(h for h in we._HOOKS if h[0] == "calendar")
    assert row[1] == "pre" and row[2] == 10 and row[3] is wc.calendar_day_hook


def test_world_season_updated_each_tick():
    cal = cal_for("primavera", 3)
    st = cal_state(cal)
    for d in range(2, 20):
        step(st, d)
        assert st["world"]["season"]["id"] == wc.season_at(cal, d)["season"]
        assert st["world"]["season"]["day_in_season"] == wc.season_at(cal, d)["day_in_season"]


def test_season_change_emits_one_digest_item():
    cal = cal_for("verao", 7)  # vira para verao no dia 7
    st = cal_state(cal)
    per_day = {d: [i for i in step(st, d).digest if i["kind"] == "estacao"] for d in range(2, 21)}
    assert [d for d, items in per_day.items() if items] == [7]
    assert len(per_day[7]) == 1 and per_day[7][0]["template_id"] == "estacao.inicio.verao"


def test_replay_same_day_no_duplicate_items():
    cal = cal_for("verao", 4)
    st = cal_state(cal)
    run(st, 2, 3)
    snap = copy.deepcopy(st)
    first = step(st, 4)
    again = step(snap, 4)
    assert [i["item_id"] for i in first.digest] == [i["item_id"] for i in again.digest]
    # re-tick do mesmo dia sobre o estado ja avancado: last_ticked_day barra
    res = we.advance_days(st, st["world"], st["world"], st["factions"], {})
    assert res.digest == [] and res.days_ticked == 0


def test_baseline_offset_moves_equilibrium_not_accumulates(monkeypatch):
    cfg = wp.get_config()
    monkeypatch.setitem(cfg["constants"], "noise", 0)
    monkeypatch.setitem(cfg["constants"], "surge_p", 0.0)
    cal = cal_for("inverno", 1)  # inverno de 40 dias corridos (SPEC-307)
    st = cal_state(cal)
    for d in range(2, 41):
        step(st, d)
        assert st["world_sim"]["pressures"]["skallgard"]["fome"] <= 40
    assert st["world_sim"]["pressures"]["skallgard"]["fome"] == 40  # 25 baseline + 15
    assert st["world_sim"]["pressures"]["nova_arcadia"]["fome"] == 20  # 15 + 5


def test_offsets_never_exceed_sinal():
    sinal = int(wp.constants()["SINAL"])
    base = wp.baseline()
    for season in wc.SEASONS:
        for region, row in wc.baseline_offsets(season).items():
            assert region in base
            for kind, off in row.items():
                assert kind in wp.KINDS
                assert base[region][kind] + off <= sinal, (season, region, kind)


def test_calendar_never_requests_crisis_slot(monkeypatch):
    src = pathlib.Path(wc.__file__).read_text(encoding="utf-8")
    assert "request_crisis_slot" not in src

    def boom(*a, **k):
        raise AssertionError("o calendario nao pode pedir slot de crise")

    monkeypatch.setattr(wd, "request_crisis_slot", boom)
    st = cal_state(cal_for("primavera", 1))
    run(st, 2, 30)


def test_shadow_writes_only_shadow_key(monkeypatch):
    monkeypatch.setenv("RPG_CALENDAR", "shadow")
    st = cal_state(cal_for("primavera", 1))
    st["world_sim"].pop("calendar")
    res = step(st, 2)
    sim = st["world_sim"]
    assert "calendar" not in sim and sim["calendar_shadow"]["anchor_day"] == 1
    assert "season" not in st["world"] and not res.pending_events
    assert not [i for i in res.digest if i["kind"] in ("estacao", "passo", "festa")]
    assert wc.active_season(st["world"]) is None


def test_off_writes_nothing(monkeypatch):
    monkeypatch.setenv("RPG_CALENDAR", "off")
    st = cal_state(cal_for("primavera", 1))
    st["world_sim"].pop("calendar")
    step(st, 2)
    assert "calendar" not in st["world_sim"] and "calendar_shadow" not in st["world_sim"]
    assert "season" not in st["world"]
    assert wc.mode() == "off"
    monkeypatch.setenv("RPG_CALENDAR", "on")
    monkeypatch.setenv("RPG_WORLD_ENGINE", "shadow")
    assert wc.mode() == "shadow"
    monkeypatch.setenv("RPG_WORLD_ENGINE", "off")
    assert wc.mode() == "off"
