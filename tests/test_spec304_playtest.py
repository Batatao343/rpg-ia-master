"""SPEC-304 Etapa 7: invariantes, relatório, cenários dirigidos e calibração rápida (R30-R32)."""

from __future__ import annotations

import importlib.util
import pathlib

import pytest

from playtest import invariants, report
from tests.spec304_helpers import BRUNNA_ID, setup_env

LEADER = "npc_durgrim_ultimo_martelo"


@pytest.fixture(autouse=True)
def _on(monkeypatch):
    setup_env(monkeypatch, "on")


def _peril(**over) -> dict:
    base = {
        "peril_id": "p1",
        "npc_id": "npc_zed",
        "major": False,
        "kind": "emboscada",
        "location_id": "ma_saidas_baixas",
        "opened_day": 3,
        "earliest_day": 5,
        "deadline_day": 6,
        "perceived_day": None,
        "resolution": "ferido",
        "resolved_day": 6,
        "warning_event_id": "w1",
    }
    return {**base, **over}


def _state(perils=(), roster=(), npcs=None, projection=None, day=10, loc="nova_arcadia", **extra):
    return {
        "npc_sim": {"version": 1, "roster": list(roster), "perils": list(perils), "npcs": {}},
        "npcs": npcs or {},
        "world": {"current_location_id": loc, "world_clock": {"day": day}},
        "world_projection": projection or {},
        "event_log": [{"event_id": "w1", "type": "npc_peril_warning"}],
        "pending_world_events": [],
        **extra,
    }


def _ids(state) -> set[str]:
    return {v.check_id for v in invariants.check_npc_world(state, None, 1)}


def test_invariants_detect_each_violation(monkeypatch):
    assert _ids(_state()) == set()
    assert _ids(_state(perils=[_peril()])) == set()  # telegrama de 3 dias, tudo certo
    assert "npc.roster_cap_exceeded" in _ids(_state(roster=[f"n{i}" for i in range(61)]))
    no_warn = _state(perils=[_peril(warning_event_id="")])
    assert "npc.fate_without_warning" in _ids(no_warn)
    same_day = _state(perils=[_peril(resolved_day=4)])
    assert "npc.fate_without_warning" in _ids(same_day)  # menos de TELEGRAPH_MIN_DAYS
    missing = _state(perils=[_peril(warning_event_id="ausente")])
    assert "npc.fate_without_warning" in _ids(missing)  # telegrama nunca foi aplicado
    unperceived = _state(perils=[_peril(major=True, resolution="morto")])
    assert "npc.major_death_unperceived" in _ids(unperceived)
    perceived = _state(perils=[_peril(major=True, resolution="morto", perceived_day=4)])
    assert "npc.major_death_unperceived" not in _ids(perceived)
    present = _state(
        perils=[_peril(resolution="morto", resolved_day=10)], loc="ma_saidas_baixas", day=10
    )
    assert "npc.fate_while_player_present" in _ids(present)
    dead = _state(npcs={"Zed": {"name": "Zed", "status": "morto", "in_scene": True}})
    assert "npc.dead_in_scene" in _ids(dead)
    lead = _state(projection={"npc_affiliations": {LEADER: "legiao_ferro"}})
    assert "npc.leader_defected" in _ids(lead)
    # belief_leak: a API mostra "morto" enquanto a crenca nao sabe
    import api

    st = _state(
        npcs={"Zed": {"id": "npc_zed", "name": "Zed", "status": "morto", "known_by_player": True}},
    )
    st["npc_sim"]["npcs"]["npc_zed"] = {"fate": "morto", "fate_event_id": "k1"}
    assert "npc.belief_leak" not in _ids(st)
    monkeypatch.setattr(
        api, "_npcs_block", lambda npcs, state=None: [{"name": "Zed", "status": "morto"}]
    )
    assert "npc.belief_leak" in _ids(st)


def test_report_has_npc_section():
    summaries = [
        {
            "profile": "explorador",
            "world": {
                "enabled": True,
                "npcs": {
                    "enabled": True,
                    "roster": 54,
                    "opened": 3,
                    "perceived": 2,
                    "by_fate": {"morto": 1, "intervencao": 1, "ferido": 1},
                    "interventions": 1,
                    "deaths_major": 0,
                    "deaths_minor": 1,
                    "defections": 1,
                },
            },
        }
    ]
    rep = report.RunReport(
        run_id="r", campaigns=summaries, top_violations=[], top_errors=[], deltas=None
    )
    md = report.render_markdown(rep)
    assert "### NPCs" in md
    assert "| explorador | 54 | 3 | 2 | 1 | 0/1 | ferido=1, intervencao=1, morto=1 | 1 |" in md


def test_scenario_companheiro_exposto():
    from playtest.runner import run_campaign

    result = run_campaign("explorador", turns=14, seed=21, scenario="companheiro_exposto")
    assert not [v for v in result.violations if v.get("severity") == "error"], result.violations
    state = result.final_state
    warn = next(
        e
        for e in state["event_log"]
        if e["type"] == "npc_peril_warning" and e["target_id"] == BRUNNA_ID
    )
    assert warn["payload"]["channel"] == "pedido_de_ajuda"
    assert warn["event_id"] in state["world_sim"]["perceived_ids"]  # o mensageiro chegou
    peril = next(p for p in state["npc_sim"]["perils"] if p["npc_id"] == BRUNNA_ID)
    assert peril["perceived_day"] is not None and peril["resolution"] in (
        "morto",
        "ferido",
        "capturado",
        "escapou",
    )
    assert peril["resolved_day"] >= peril["opened_day"] + 2  # nunca antes do telegrama minimo
    assert warn["payload"]["opened_day"] <= 5 + state["npc_sim"]["enabled_from_day"]


def test_scenario_npc_perigo_minor():
    from playtest.runner import run_campaign

    result = run_campaign("explorador", turns=14, seed=21, scenario="npc_perigo")
    assert not [v for v in result.violations if v.get("severity") == "error"], result.violations
    types = [e["type"] for e in result.final_state["event_log"]]
    assert "npc_peril_warning" in types


def _sim_module():
    path = pathlib.Path(__file__).resolve().parents[1] / "docs" / "spec304" / "npc_world_sim.py"
    spec = importlib.util.spec_from_file_location("npc_world_sim_cal", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_calibration_fast_n5_n6_always_hold():
    sim = _sim_module()
    sts = [sim.run_seed(s, 30) for s in range(3)]
    out = sim._stats(sts, 30)
    assert out["N5_deaths_danger_le2"] == 0 and out["N6_deaths_without_telegraph"] == 0
    assert out["N7_max_active_crises"] <= out["N7_cap"] and out["N3_gap_30d_ok"]
