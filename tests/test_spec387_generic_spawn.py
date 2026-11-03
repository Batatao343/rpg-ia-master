"""SPEC-387 R10-R12: nome genérico do scanner vira criatura da região, nunca `fallback_*`."""

from __future__ import annotations

import pytest

import agents.combat as combat
import gamedata
from services import fauna
from services import generic_spawn as gs
from tests.test_encounter_identity_repro import (
    _BANDIT,
    _install_llm,
    _scan,
    _start_state,
    _world,
)


def _state(loc: str, gid: str):
    st = _start_state(hint="a criatura hostil")
    st["game_id"] = gid
    st["world"] = {**_world(), "current_location_id": loc, "current_location": loc}
    return st


@pytest.mark.parametrize("loc", ["pantano_melancolia", "floresta_sussurros"])
def test_generic_name_picks_regional(monkeypatch, loc):
    monkeypatch.setenv("RPG_CREATURE_GEN", "off")
    region = loc
    for i in range(20):
        _install_llm(monkeypatch, scan=_scan(("Criatura hostil", 1)))
        state = _state(loc, f"g{i}")
        enemies, flavor = combat._spawn_v4_enemies(
            state["messages"], "a criatura hostil", state, meta := {}
        )
        assert enemies and not any(str(e["id"]).startswith("fallback_") for e in enemies)
        base = enemies[0].get("archetype_id")
        assert region in (gamedata.BESTIARY[base].get("regions") or [])
        assert meta["source"] == "regional_generic"
        assert enemies[0]["name"] in flavor


def test_generic_pick_is_deterministic_and_varies():
    st = _state("pantano_melancolia", "g1")
    assert gs.regional_pick(st, "x") == gs.regional_pick(st, "x")
    picks = {gs.regional_pick(_state("pantano_melancolia", f"g{i}"), "x") for i in range(20)}
    assert len(picks) > 1
    assert all(fauna._bestiary(p) for p in picks)


def test_specific_hint_unchanged(monkeypatch):
    _install_llm(monkeypatch, scan=_scan(("Bandido", 1)))
    state = _start_state(hint="Bandido")
    enemies, _ = combat._spawn_v4_enemies(state["messages"], "Bandido", state, meta := {})
    assert meta["source"] != "regional_generic"
    assert gs.regional_template("Bandido", state, "Bandido", 1) is None
    assert any(_BANDIT in str(e["id"]) for e in enemies)


def test_no_fallback_from_contentless_name(monkeypatch):
    # região sem candidato -> caminho de hoje, mas o evento é `spawn_generic_name`
    events: list[str] = []
    monkeypatch.setattr(combat, "_log_event", lambda a, b, **k: events.append(b))
    monkeypatch.setattr(gs, "regional_pick", lambda *_a: None)
    monkeypatch.setenv("RPG_CREATURE_GEN", "off")
    _install_llm(monkeypatch, scan=_scan(("Criatura hostil", 1)))
    state = _state("pantano_melancolia", "g1")
    combat._spawn_v4_enemies(state["messages"], "a criatura hostil", state, {})
    assert "spawn_identity_mismatch" not in events
