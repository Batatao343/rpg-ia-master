"""SPEC-350 Etapa 5 — elenco da trama no roster da SPEC-304 (R24, R28)."""

from __future__ import annotations

import pytest

from services import npc_world
from services import plot_threads as pt
from tests.spec304_helpers import known_npc, setup_env, waiting_state


@pytest.fixture(autouse=True)
def _env(monkeypatch):
    setup_env(monkeypatch, "on")
    monkeypatch.setenv("RPG_PLOT_THREADS", "on")
    pt.clear_cache()
    yield
    pt.clear_cache()


def _state(loc="na_anel_lama"):
    st = waiting_state(player_at=loc)
    st["world"] = {**st["world"], "current_location_id": loc}
    return st


def test_roster_includes_region_cast_before_key_npcs():
    r = npc_world.roster(_state())
    anchors = {d.anchor_npc_id for d in pt.plot_doors("nova_arcadia")}
    assert anchors <= set(r)
    key = next(k for k in npc_world._cfg()["key_npcs"] if k in r and k not in pt.catalog().cast)
    non_leader_cast = [c for c in pt.region_cast("nova_arcadia") if not npc_world.is_leader(c)]
    assert max(r.index(c) for c in non_leader_cast) < r.index(key)


def test_roster_cap_unchanged_and_freezes_overflow():
    st = _state()
    st["npcs"] = {
        **st["npcs"],
        **{f"N{i}": known_npc(f"npc_g{i:03d}", f"N{i}", rel=5) for i in range(120)},
    }
    r = npc_world.roster(st)
    assert len(r) == 60
    assert not [k for k in npc_world._cfg()["key_npcs"] if k in r and k not in pt.catalog().cast][
        1:
    ]


def test_roster_other_region_has_no_nova_arcadia_boost():
    r_here = npc_world.roster(_state("na_anel_lama"))
    r_far = npc_world.roster(_state("brekmar"))
    extra = set(r_here) - set(r_far)
    assert extra and extra <= set(pt.catalog().cast)


def test_roster_flag_off_identical(monkeypatch):
    monkeypatch.setenv("RPG_PLOT_THREADS", "off")
    off = npc_world.roster(_state())
    monkeypatch.setattr(pt, "region_cast", lambda region: [])
    monkeypatch.setenv("RPG_PLOT_THREADS", "on")
    assert npc_world.roster(_state()) == off
