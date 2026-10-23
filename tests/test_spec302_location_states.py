"""SPEC-302 Etapa 4: estados de local e eventos do motor."""

from __future__ import annotations

import collections
import importlib.util
import pathlib

import pytest

import gamedata
from services import location_states as ls
from services import world_director as wd
from services import world_engine as we
from services import world_pressures as wp
from services.event_processor import apply_event, process_pending_events
from services.world_validators import validate_proposal
from tests.spec302_helpers import fresh_sim, make_state, set_pressure


@pytest.fixture(autouse=True)
def _mode_on(monkeypatch):
    monkeypatch.setenv("RPG_WORLD_ENGINE", "on")


def _state_event(loc="nova_arcadia", state="cerco", source="engine", sev=1):
    return {
        "type": "location_state_changed",
        "actor_id": "engine",
        "target_id": loc,
        "payload": {
            "state": state,
            "previous": "",
            "severity": sev,
            "crisis_id": "c1",
            "cause": "guerra",
        },
        "source": source,
    }


def test_event_types_engine_only():
    st = make_state()
    assert validate_proposal(_state_event(source="engine"), st).ok
    for src in ("storyteller", "", "system", "combat"):
        res = validate_proposal(_state_event(source=src), st)
        assert not res.ok and "motor" in res.reason
    warn = {
        "type": "world_crisis_warning",
        "target_id": "nova_arcadia",
        "payload": {"kind": "guerra", "region_id": "nova_arcadia"},
    }
    assert not validate_proposal(warn, st).ok
    assert validate_proposal({**warn, "source": "engine"}, st).ok


def test_apply_event_sets_and_clears_location_state():
    proj = apply_event({**_state_event(), "event_id": "e1", "turn": 5}, {})
    row = proj["location_states"]["nova_arcadia"]
    assert row["state"] == "cerco" and row["severity"] == 1 and row["crisis_id"] == "c1"
    cleared = apply_event(
        {
            **_state_event(state=""),
            "event_id": "e2",
            "turn": 9,
            "payload": {"state": "", "previous": "cerco"},
        },
        proj,
    )
    assert "nova_arcadia" not in cleared["location_states"]


def test_interior_inherits_parent_state():
    interior = next(loc for loc in gamedata.WORLD_MAP["locations"] if loc.get("kind") == "interior")
    state = {
        "world_projection": {
            "location_states": {interior["parent_id"]: {"state": "escassez", "severity": 2}}
        }
    }
    assert ls.location_state(state, interior["id"])["state"] == "escassez"
    assert ls.public_label(ls.location_state(state, interior["id"])) == "em escassez"


def test_pick_target_never_interior():
    interiors = {
        loc["id"] for loc in gamedata.WORLD_MAP["locations"] if loc.get("kind") == "interior"
    }
    for region in wp.region_ids():
        for kind in wp.KINDS:
            for d in range(20):
                t = ls.pick_crisis_target(region, kind, {}, we.day_rng("g", d, "t"))
                assert t is None or (t not in interiors and wp.region_of(t) == region)


def test_pick_target_by_tags():
    counts = collections.Counter(
        ls.pick_crisis_target("nova_arcadia", "guerra", {}, we.day_rng("g", d, "t")) for d in range(400)
    )
    # cidades pesam 3x: o conjunto nao e uniforme e nunca inclui o interior (taverna)
    assert "na_taverna_javali" not in counts
    assert counts["nova_arcadia"] > 0
    ab = collections.Counter(
        ls.pick_crisis_target("pantano_melancolia", "abismo", {}, we.day_rng("g", d, "t"))
        for d in range(100)
    )
    assert ab and all(wp.region_of(k) == "pantano_melancolia" for k in ab)
    taken = {"location_states": {"pantano_melancolia": {"state": "praga"}}}
    assert (
        ls.pick_crisis_target("pantano_melancolia", "praga", taken, we.day_rng("g", 1, "t"))
        != "pantano_melancolia"
    )


def _load_sim_module():
    path = pathlib.Path(__file__).resolve().parents[1] / "docs" / "spec302" / "world_engine_sim.py"
    spec = importlib.util.spec_from_file_location("world_engine_sim", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_every_engine_event_passes_validator():
    sim_mod = _load_sim_module()
    for seed in range(1, 11):
        out = sim_mod.run_campaign(seed, 120)
        assert out["invalid_events"] == [], (seed, out["invalid_events"][:3])


def test_local_projection_converges_with_archivist():
    """O motor aplica os proprios eventos a uma copia local; o arquivista aplica o mesmo
    lote na projection real: as `location_states` convergem."""
    st = make_state("conv")
    st["world"] = {"world_clock": {"day": 1, "period": "Manhã"}, "turn_count": 1}
    local: dict = {}
    for day in range(1, 90, 3):
        before = {"world_clock": {"day": day, "period": "Manhã"}, "turn_count": day}
        after = {"world_clock": {"day": day + 3, "period": "Manhã"}, "turn_count": day + 3}
        st["world"] = after
        res = we.advance_days(st, before, after, st["factions"], {})
        st[res.sim_key] = res.world_sim
        st["factions"] = res.factions
        for ev in res.pending_events:
            local = apply_event({**ev, "turn": day}, local)
        st["pending_world_events"] = res.pending_events
        upd = process_pending_events(st)
        if upd:
            st.update(upd)
    assert st["world_projection"].get("location_states", {}) == local.get("location_states", {})
    assert not st.get("event_rejections")


def _announced_siege_sim():
    sim = fresh_sim()
    set_pressure(sim, "nova_arcadia", "guerra", 90)
    sim["bands"]["nova_arcadia"]["guerra"] = "crise"
    return sim


def test_siege_blocks_one_route_and_clears_on_end():
    sim = _announced_siege_sim()
    proj: dict = {}
    legiao = {"id": "legiao_ferro", "region": "Nova Arcádia", "disposition": "hostil"}
    allev = []
    for day in (10, 12):
        _, ev, _ = wd.step_crises(
            sim,
            day,
            proj,
            we.day_rng("g", day, "d"),
            game_id="g",
            factions=[legiao],
            faction_region=we.faction_region_id,
        )
        for e in ev:
            proj.update(apply_event({**e, "turn": day}, proj))
        allev += ev
    blocked = [e for e in allev if e["type"] == "route_blocked"]
    assert len(blocked) == 1 and len(proj["blocked_routes"]) == 1
    set_pressure(sim, "nova_arcadia", "guerra", 5)
    _, ev, _ = wd.step_crises(
        sim,
        16,
        proj,
        we.day_rng("g", 16, "d"),
        game_id="g",
        factions=[legiao],
        faction_region=we.faction_region_id,
    )
    assert any(e["type"] == "route_cleared" for e in ev)


def test_ruin_recovers_after_quiet_days():
    sim = fresh_sim()
    proj = {"location_states": {"pr_vaelorn": {"state": "ruina", "severity": 1, "since_day": 1}}}
    ev, _ = wd.recovery_step(sim, 20, proj, we.day_rng("g", 20, "r"), game_id="g")
    assert not ev  # ainda cedo
    ev, _ = wd.recovery_step(sim, 45, proj, we.day_rng("g", 45, "r"), game_id="g")
    assert [e["payload"]["state"] for e in ev] == ["escassez"]
    proj = {
        "location_states": {
            "pr_vaelorn": {"state": "escassez", "since_day": 45, "cause": "recuperacao"}
        }
    }
    ev, _ = wd.recovery_step(sim, 51, proj, we.day_rng("g", 51, "r"), game_id="g")
    assert [e["payload"]["state"] for e in ev] == [""]


def test_ruin_does_not_recover_while_pressure_sustains():
    sim = fresh_sim()
    sim["pressures"]["pradaria_ruinas"]["guerra"] = 60
    proj = {"location_states": {"pr_vaelorn": {"state": "ruina", "severity": 1, "since_day": 1}}}
    ev, _ = wd.recovery_step(sim, 80, proj, we.day_rng("g", 80, "r"), game_id="g")
    assert not ev


def test_occupation_ends_when_occupier_defeated():
    sim = fresh_sim()
    proj = {
        "location_states": {
            "na_anel_lama": {
                "state": "ocupado",
                "since_day": 3,
                "faction_id": "legiao_ferro",
                "prev_controller": "mao_sombria",
            }
        }
    }
    facs = [
        {"id": "legiao_ferro", "defeated": True},
        {"id": "mao_sombria"},
    ]
    ev, _ = wd.recovery_step(sim, 10, proj, we.day_rng("g", 10, "r"), game_id="g", factions=facs)
    types = [e["type"] for e in ev]
    assert types == ["location_state_changed", "location_control_changed"]
    assert ev[1]["payload"]["new_controller_id"] == "mao_sombria"


def test_shadow_mode_emits_nothing_and_writes_shadow_key(monkeypatch):
    monkeypatch.setenv("RPG_WORLD_ENGINE", "shadow")
    st = make_state("shadow")
    for d in range(1, 100, 10):
        before = {"world_clock": {"day": d, "period": "Manhã"}}
        after = {"world_clock": {"day": d + 10, "period": "Manhã"}}
        res = we.advance_days(st, before, after, st["factions"], {})
        st[res.sim_key] = res.world_sim
        assert res.pending_events == []
    assert "world_sim" not in st and st["world_sim_shadow"]["crises"] is not None


def test_npc_knowledge_subject_params_include_new_types():
    from services.npc_knowledge import SUBJECT_PARAMS

    assert SUBJECT_PARAMS["location_state_changed"] == (0.9, 20, 2)
    assert SUBJECT_PARAMS["world_crisis_warning"] == (0.8, 20, 2)
    assert SUBJECT_PARAMS["faction_relation_changed"] == (0.7, 20, 2)
