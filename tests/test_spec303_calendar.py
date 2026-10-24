"""SPEC-303 Etapa 1: calendario puro (R1-R6, R26)."""

from __future__ import annotations

import ast
import pathlib

import pytest

from services import world_calendar as wc
from services import world_engine as we
from tests.spec302_helpers import make_state, world_at
from tests.spec303_helpers import cal_for, cal_state, step

_SRC = pathlib.Path(wc.__file__)


@pytest.fixture(autouse=True)
def _mode_on(monkeypatch):
    monkeypatch.setenv("RPG_WORLD_ENGINE", "on")
    monkeypatch.setenv("RPG_CALENDAR", "on")


def test_four_seasons_fixed_order_canonical_keys():
    # SPEC-307 (decisao do dono de 24/10 substitui a 303 R1): ha semana de 5 dias e mes;
    # as 4 estacoes seguem como chave canonica das tabelas de modulacao.
    assert wc.SEASONS == ("primavera", "verao", "outono", "inverno")
    cal = cal_for("primavera", 1)
    seen = [wc.season_at(cal, d)["season"] for d in range(1, 141)]
    assert seen[0] == "primavera" and seen[19] == "primavera" and seen[20] == "verao"
    assert seen[59] == "verao" and seen[60] == "outono" and seen[100] == "inverno"
    assert seen[139] == "inverno"
    assert wc.season_at(cal, 141)["season"] == "primavera" and wc.season_at(cal, 141)["year"] == 2


def test_season_at_is_pure_and_deterministic():
    cal = wc.create_calendar("g", 1)
    a = [wc.season_at(cal, d) for d in range(1, 80)]
    assert a == [wc.season_at(dict(cal), d) for d in range(1, 80)]
    assert all(1 <= x["day_in_season"] <= 40 for x in a)


def test_no_global_random_in_calendar_module():
    tree = ast.parse(_SRC.read_text(encoding="utf-8"))
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            assert all(alias.name != "random" for alias in node.names)
        if isinstance(node, ast.ImportFrom):
            assert node.module != "random"
        if isinstance(node, ast.Name):
            assert node.id != "random"


@pytest.mark.parametrize("anchor", [1, 7, 33])
def test_first_turn_between_4_and_8_days_after_anchor(anchor):
    for n in range(200):
        cal = wc.create_calendar(f"game-{n}", anchor)
        k = cal["first_turn_day"] - anchor
        assert 4 <= k <= 8
        first = wc.season_at(cal, anchor)["season"]
        assert all(wc.season_at(cal, d)["season"] == first for d in range(anchor, anchor + k))
        assert wc.season_at(cal, anchor + k)["season"] != first


def test_start_season_distribution_covers_all_four():
    starts = {wc.season_at(wc.create_calendar(f"g{n}", 1), 1)["season"] for n in range(80)}
    assert starts == set(wc.SEASONS)


def test_params_frozen_when_constant_changes(monkeypatch):
    cal = wc.create_calendar("frozen", 1)
    before = [wc.season_at(cal, d) for d in range(1, 120)]
    cfg = {**wc._cfg(), "constants": {**wc._cfg()["constants"], "MONTH_DAYS": 25}}
    monkeypatch.setattr(wc, "_cfg", lambda: cfg)
    assert [wc.season_at(cal, d) for d in range(1, 120)] == before
    assert wc.create_calendar("frozen", 1)["month_days"] == 25  # so jogos novos mudam


def test_new_game_anchor_is_day_1():
    import world_utils as wu

    st = {"game_id": "g-new", "factions": [], "world": wu.starting_world("Nova Arcádia", 1)}
    wc.init_new_game(st)
    cal = st["world_sim"]["calendar"]
    assert cal["anchor_day"] == 1
    assert st["world"]["season"]["id"] == wc.season_at(cal, 1)["season"]


def test_legacy_save_anchor_is_enabled_from_day_no_retroactive():
    st = make_state("legacy", 80)
    sim = we.ensure_world_sim(st, 80, st["factions"])
    st["world_sim"] = sim
    assert "calendar" not in sim
    step(st, 81)
    cal = st["world_sim"]["calendar"]
    assert cal["anchor_day"] == 80 and st["world_sim"]["enabled_from_day"] == 80
    assert st["world"]["season"]["id"] == wc.season_at(cal, 81)["season"]
    assert not [e for e in st["event_log"] if (e.get("payload") or {}).get("cause") == "calendario"]


def test_season_none_before_calendar_exists():
    assert wc.active_season({}) is None
    assert wc.active_season({"season": None}) is None
    assert wc.weather_multipliers("skallgard", None) == {}
    assert wc.encounter_multipliers("skallgard", None) == {}
    assert wc.baseline_offsets(None) == {}
    assert wc.seasonal_closed_pairs({}) == set()


def test_regional_labels_skallgard_noite_longa():
    assert wc.label_for("inverno", "skallgard") == "Noite Longa"
    assert wc.label_for("outono", "skallgard") == "Noite Longa"
    assert wc.label_for("verao", "skallgard") == "Dia Longo"
    assert wc.label_for("verao", "deserto_zhur") == "Estação do Vidro"
    assert wc.label_for("inverno", "deserto_zhur") == "Inverno"
    assert wc.label_for("outono", "nova_arcadia") == "Outono"
    cal = cal_for("inverno", 5)
    assert wc.season_label(cal, 5, "skallgard") == "Noite Longa"
    assert wc.season_view(cal, 5, "brekmar") == {
        "id": "inverno",
        "label": "Inverno",
        "day_in_season": 1,
    }
    assert wc.has_regional_label("inverno", "skallgard")
    assert not wc.has_regional_label("inverno", "brekmar")


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
    # o resultado do hook nao muda com a ficha do heroi no estado
    a = cal_state(cal_for("verao", 2), player={"level": 1, "gold": 0})
    b = cal_state(cal_for("verao", 2), player={"level": 20, "gold": 9999})
    step(a, 2)
    step(b, 2)
    assert a["world_sim"]["calendar"] == b["world_sim"]["calendar"]
    assert a["world"]["season"] == b["world"]["season"]
    assert world_at(2)["world_clock"]["day"] == 2
