"""SPEC-307 Etapa 1: calendario de Valoria v2 puro (R1-R8, R12-R14, R23)."""

from __future__ import annotations

import ast
import pathlib

import pytest

from services import world_calendar as wc
from tests.spec303_helpers import cal_for

_SRC = pathlib.Path(wc.__file__)


@pytest.fixture(autouse=True)
def _mode_on(monkeypatch):
    monkeypatch.setenv("RPG_WORLD_ENGINE", "on")
    monkeypatch.setenv("RPG_CALENDAR", "on")


def test_year_is_7_months_of_20_days_week_of_5():
    c = wc.constants()
    assert (c["MONTH_DAYS"], c["WEEK_DAYS"]) == (20, 5)
    assert len(wc.months()) == 7 and len(wc.weekdays()) == 5
    assert c["MONTH_DAYS"] % c["WEEK_DAYS"] == 0 and c["MONTH_DAYS"] // c["WEEK_DAYS"] == 4
    assert "SEASON_DAYS" not in c
    assert len(wc.months()) * c["MONTH_DAYS"] == 140
    assert [m["name"] for m in wc.months()] == [
        "Morrakh",
        "Vaelith",
        "Malagor",
        "Solveth",
        "Orrakh",
        "Vorrnak",
        "Thessrak",
    ]
    assert [w["name"] for w in wc.weekdays()] == [
        "Sino de Ferro",
        "Sino de Bronze",
        "Sino de Cobre",
        "Sino de Estanho",
        "Sino Mudo",
    ]


def test_months_climate_two_cold_two_hot_three_transition():
    ms = wc.months()
    kinds = [m["climate"] for m in ms]
    assert kinds.count("frio") == 2 and kinds.count("calor") == 2 and kinds.count("transicao") == 3
    assert all({"id", "name", "of", "climate", "season", "lore_ref"} <= set(m) for m in ms)
    assert [m["season"] for m in ms if m["climate"] == "frio"] == ["inverno", "inverno"]


def test_season_months_contiguous_cyclic_order():
    seasons = [m["season"] for m in wc.months()]
    assert set(seasons) == set(wc.SEASONS)
    order = [s for i, s in enumerate(seasons) if i == 0 or s != seasons[i - 1]]
    assert order == list(wc.SEASONS)  # cada estacao num bloco so, na ordem ciclica
    assert seasons.count("primavera") == 1 and seasons.count("outono") == 2


def test_first_of_every_month_same_weekday():
    cal = wc.create_calendar("wk", 1)
    firsts = {
        wc.date_at(cal, d)["weekday_index"]
        for d in range(1, 300)
        if wc.date_at(cal, d)["day_of_month"] == 1
    }
    assert firsts == {0}
    d = [wc.date_at(cal, x)["weekday_index"] for x in range(1, 30)]
    assert set(d) == {0, 1, 2, 3, 4}


def test_date_at_pure_deterministic_and_no_global_random():
    cal = wc.create_calendar("g", 1)
    a = [wc.date_at(cal, d) for d in range(1, 300)]
    assert a == [wc.date_at(dict(cal), d) for d in range(1, 300)]
    assert all(1 <= x["day_in_season"] <= x["season_len"] <= 40 for x in a)
    tree = ast.parse(_SRC.read_text(encoding="utf-8"))
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            assert all(alias.name != "random" for alias in node.names)
        if isinstance(node, ast.ImportFrom):
            assert node.module != "random"
        if isinstance(node, ast.Name):
            assert node.id != "random"


def test_season_at_compat_shape_unchanged():
    cal = cal_for("verao", 5)
    info = wc.season_at(cal, 5)
    assert set(info) == {"season", "day_in_season", "year", "day_of_year"}
    assert info["season"] == "verao" and info["day_in_season"] == 1
    assert wc.season_at(cal, 44)["day_in_season"] == 40
    assert wc.season_at(cal, 45)["season"] == "outono"


@pytest.mark.parametrize("anchor", [1, 7, 33])
def test_first_turn_month_and_season_between_4_and_8_days(anchor):
    for n in range(200):
        cal = wc.create_calendar(f"game-{n}", anchor)
        k = cal["first_turn_day"] - anchor
        assert 4 <= k <= 8
        first = wc.date_at(cal, anchor)
        assert all(
            wc.date_at(cal, d)["month_id"] == first["month_id"] for d in range(anchor, anchor + k)
        )
        after = wc.date_at(cal, anchor + k)
        assert after["month_id"] != first["month_id"] and after["season"] != first["season"]
        assert after["day_of_month"] == 1


def test_same_game_id_same_start_season_as_v1():
    for n in range(60):
        gid = f"same-{n}"
        v1 = wc._v1_season_at(_v1_create(gid, 1), 1)["season"]
        v2 = wc.season_at(wc.create_calendar(gid, 1), 1)["season"]
        assert v1 == v2


def _v1_create(game_id: str, anchor_day: int) -> dict:
    """Reproduz `create_calendar` da SPEC-303 (mesma ordem de chamadas do rng)."""
    from services.world_engine import day_rng

    sd = 14
    rng = day_rng(game_id, anchor_day, "calendar")
    s0 = rng.randrange(4)
    k = rng.randint(4, 8)
    return {"season_days": sd, "epoch_offset": (s0 * sd + (sd - k) - (anchor_day - 1)) % (4 * sd)}


def test_params_frozen_when_month_days_changes(monkeypatch):
    cal = wc.create_calendar("frozen", 1)
    before = [wc.date_at(cal, d) for d in range(1, 200)]
    cfg = {**wc._cfg(), "constants": {**wc._cfg()["constants"], "MONTH_DAYS": 25}}
    monkeypatch.setattr(wc, "_cfg", lambda: cfg)
    assert [wc.date_at(cal, d) for d in range(1, 200)] == before
    assert wc.create_calendar("frozen", 1)["month_days"] == 25


def test_unknown_version_neutral_never_recreated():
    from tests.spec303_helpers import cal_state, step

    weird = {**cal_for("verao", 2), "version": 9}
    st = cal_state(weird)
    step(st, 2)
    assert st["world_sim"]["calendar"] == weird  # nunca recriado
    assert "season" not in st["world"] and "date" not in st["world"]
    assert wc.active_season(st["world"]) is None
    assert wc.calendar_for_read(st["world_sim"], 2) is None


def test_skallgard_noite_longa_months_4_to_7():
    cal = cal_for("primavera", 1)
    noite = {
        m["id"] for m in wc.months() if wc.label_for(m["season"], "skallgard") == "Noite Longa"
    }
    assert noite == {"solveth", "orrakh", "vorrnak", "thessrak"}
    dia = {m["id"] for m in wc.months() if wc.label_for(m["season"], "skallgard") == "Dia Longo"}
    assert dia == {"morrakh", "vaelith", "malagor"}
    assert sum(20 for m in wc.months() if m["id"] in noite) == 80
    assert wc.season_label(cal, 61, "skallgard") == "Noite Longa"
    vidro = {
        m["id"]
        for m in wc.months()
        if wc.label_for(m["season"], "deserto_zhur") == "Estação do Vidro"
    }
    assert vidro == {"vaelith", "malagor"}


@pytest.mark.parametrize(
    ("day", "label"),
    [
        (1, "1º dia de Morrakh, Sino de Ferro — Ano 112 da Era 7"),
        (3, "3º dia de Morrakh, Sino de Cobre — Ano 112 da Era 7"),
        (20, "20º dia de Morrakh, Sino Mudo — Ano 112 da Era 7"),
        (21, "1º dia de Vaelith, Sino de Ferro — Ano 112 da Era 7"),
        (113, "13º dia de Vorrnak, Sino de Cobre — Ano 112 da Era 7"),
        (141, "1º dia de Morrakh, Sino de Ferro — Ano 113 da Era 7"),
    ],
)
def test_date_label_format_table(day, label):
    cal = {**cal_for("primavera", 1), "epoch_offset": 0}
    assert wc.date_label(cal, day) == label


def test_date_label_preposition_comes_from_month_of(monkeypatch):
    cfg = wc._cfg()
    ms = [dict(m) for m in cfg["months"]]
    ms[2]["of"] = "do Céu Vermelho"
    monkeypatch.setattr(wc, "_cfg", lambda: {**cfg, "months": ms})
    cal = {**cal_for("primavera", 1), "epoch_offset": 0}
    assert wc.date_label(cal, 52).startswith("12º dia do Céu Vermelho, Sino de Bronze")


def test_year_monotonic_and_year_base():
    cal = {**cal_for("primavera", 1), "epoch_offset": 33}
    years = [wc.date_at(cal, d)["year"] for d in range(1, 700)]
    assert years == sorted(years) and years[0] == 112
    assert years[-1] >= 112 + 4
    assert wc.constants()["YEAR_BASE"] == 112 and wc._cfg().get("year_review") == "dono"
    assert {wc.season_at(cal, d)["year"] for d in range(1, 140)} <= {1, 2}  # ano interno


def test_calendar_independent_of_player():
    banned = {"player", "inventory", "gold", "level", "party", "equipment", "xp"}
    tree = ast.parse(_SRC.read_text(encoding="utf-8"))
    doc_ids = {
        id(n.value)
        for n in ast.walk(tree)
        if isinstance(n, ast.Expr) and isinstance(n.value, ast.Constant)
    }
    for node in ast.walk(tree):
        if isinstance(node, ast.Name):
            assert node.id not in banned
        if isinstance(node, ast.Attribute):
            assert node.attr not in banned
        if isinstance(node, ast.Constant) and isinstance(node.value, str):
            if id(node) not in doc_ids:
                assert node.value not in banned
