"""SPEC-302 Etapa 1: tick diario, seed, idempotencia, migracao."""

from __future__ import annotations

import ast
import json
import pathlib

import pytest

from services import world_engine as we
from tests.spec302_helpers import make_state, tick, world_at


@pytest.fixture(autouse=True)
def _mode_on(monkeypatch):
    monkeypatch.setenv("RPG_WORLD_ENGINE", "on")


def test_no_tick_when_day_unchanged():
    st = make_state()
    res = tick(st, 1, 1)
    assert res.days_ticked == 0


def test_one_tick_per_day_turned():
    st = make_state()
    tick(st, 1, 1)  # ancora o sim no dia 1
    res = tick(st, 1, 2)  # descanso que vira 1 dia
    assert res.days_ticked == 1
    res2 = we.advance_days(st, world_at(2, "Tarde"), world_at(3, "Amanhecer"), st["factions"], {})
    assert res2.days_ticked == 1  # viagem de 3 periodos cruzando a noite


def test_multi_day_ticks_in_order():
    st = make_state()
    res = tick(st, 1, 4)
    assert res.days_ticked == 3
    assert [e["day"] for e in res.world_sim["tick_log"]] == [2, 3, 4]
    assert res.world_sim["last_ticked_day"] == 4


def test_idempotent_replay():
    st = make_state()
    first = tick(st, 1, 4)
    snapshot = json.dumps(st["world_sim"], sort_keys=True)
    again = we.advance_days(st, world_at(1), world_at(4), st["factions"], {})
    assert again.days_ticked == 0
    assert json.dumps(again.world_sim, sort_keys=True) == snapshot
    assert first.days_ticked == 3


def test_cap_max_days_per_action():
    st = make_state()
    res = tick(st, 1, 40)
    assert res.days_ticked == 10
    assert res.world_sim["last_ticked_day"] == 40
    assert any(e.get("capped") for e in res.world_sim["tick_log"])


def test_same_seed_same_world_sim():
    a, b = make_state("same"), make_state("same")
    ra, rb = tick(a, 1, 30), tick(b, 1, 30)
    assert json.dumps(ra.world_sim, sort_keys=True) == json.dumps(rb.world_sim, sort_keys=True)
    assert ra.pending_events == rb.pending_events
    other = tick(make_state("other"), 1, 30)
    assert json.dumps(other.world_sim["pressures"]) != json.dumps(ra.world_sim["pressures"])


def test_independent_of_player():
    a = make_state("p", player={"level": 1, "gold": 0, "inventory": []})
    b = make_state("p", player={"level": 20, "gold": 99999, "inventory": ["x"] * 30})
    ra, rb = tick(a, 1, 20), tick(b, 1, 20)
    assert json.dumps(ra.world_sim, sort_keys=True) == json.dumps(rb.world_sim, sort_keys=True)
    assert ra.pending_events == rb.pending_events


def test_no_global_random_in_world_modules():
    root = pathlib.Path(__file__).resolve().parents[1] / "services"
    for name in (
        "world_engine",
        "world_pressures",
        "world_director",
        "location_states",
        "faction_relations",
        "world_perception",
    ):
        path = root / f"{name}.py"
        if not path.exists():
            continue
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if (
                isinstance(node, ast.Attribute)
                and isinstance(node.value, ast.Name)
                and node.value.id == "random"
            ):
                assert node.attr == "Random", f"{name}: random.{node.attr}"


def test_legacy_save_without_world_sim_initializes_at_current_day():
    st = make_state(day=40)
    assert "world_sim" not in st
    res = tick(st, 40, 41)
    sim = res.world_sim
    assert sim["enabled_from_day"] == 40
    assert res.days_ticked == 1  # sem simulacao retroativa dos 39 dias anteriores
    assert sim["calm_until_day"] == 45
    assert sim["phase"] == "calmo"


def test_save_load_roundtrip_world_sim():
    import persistence

    st = make_state("11111111-1111-4111-8111-111111111111")
    tick(st, 1, 12)
    st.update({"player": {"name": "T", "class_name": "x"}, "messages": []})
    st["world_projection"] = {
        "location_states": {"nova_arcadia": {"state": "cerco", "severity": 1}}
    }
    assert persistence.save_game_state(st)
    loaded = persistence.load_game_state(persistence._safe_save_path(st["game_id"]))
    assert loaded["world_sim"] == json.loads(json.dumps(st["world_sim"]))
    assert loaded["world_projection"]["location_states"]["nova_arcadia"]["state"] == "cerco"


def test_world_sim_size_bound():
    st = make_state("size")
    for d in range(1, 121, 10):
        tick(st, d, d + 10)
    assert len(json.dumps(st["world_sim"])) < 40_000


def test_mode_off_is_legacy_path(monkeypatch):
    from agents import storyteller

    monkeypatch.setenv("RPG_WORLD_ENGINE", "off")
    assert storyteller._engine_owns_factions() is False
    st = make_state()
    res = tick(st, 1, 5)
    assert res.days_ticked == 0 and res.world_sim is None and res.pending_events == []
    monkeypatch.setenv("RPG_WORLD_ENGINE", "on")
    assert storyteller._engine_owns_factions() is True


def test_shadow_mode_emits_nothing_and_writes_shadow_key(monkeypatch):
    monkeypatch.setenv("RPG_WORLD_ENGINE", "shadow")
    st = make_state()
    res = tick(st, 1, 40)
    assert res.sim_key == "world_sim_shadow"
    assert res.pending_events == []
    assert "world_sim" not in st and st["world_sim_shadow"]["last_ticked_day"] == 40
    assert res.factions == st["factions"] or res.factions
