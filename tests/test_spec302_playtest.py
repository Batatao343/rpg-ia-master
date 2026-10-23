"""SPEC-302 Etapa 7: invariantes, relatorio, cenario `mundo` e calibracao rapida."""

from __future__ import annotations

import importlib.util
import pathlib

import pytest

from playtest import invariants, report


@pytest.fixture(autouse=True)
def _mode_on(monkeypatch):
    monkeypatch.setenv("RPG_WORLD_ENGINE", "on")


def _sim(**over):
    sim = {
        "crises": [],
        "pressures": {"nova_arcadia": {"guerra": 10}},
        "tick_log": [{"day": 2}, {"day": 3}],
    }
    sim.update(over)
    return {"world_sim": sim}


def _ids(state):
    return {v.check_id for v in invariants.check_world_engine(state, None, 1)}


def _crisis(start=10, warned=8, end=None):
    return {
        "crisis_id": str(start),
        "kind": "fome",
        "region_id": "brekmar",
        "start_day": start,
        "warned_day": warned,
        "end_day": end,
    }


def test_invariants_detect_cap_and_unwarned():
    assert _ids(_sim()) == set()
    cap = _sim(crises=[_crisis(10), _crisis(11), _crisis(12)])
    assert "world.crisis_cap_exceeded" in _ids(cap)
    assert "world.crisis_without_warning" in _ids(_sim(crises=[_crisis(10, warned=9)]))
    assert "world.pressure_out_of_range" in _ids(_sim(pressures={"x": {"guerra": 120}}))
    assert "world.day_ticked_twice" in _ids(_sim(tick_log=[{"day": 4}, {"day": 4}]))


def test_report_has_world_section():
    summaries = [
        {
            "profile": "explorador",
            "world": {
                "enabled": True,
                "days_elapsed": 7,
                "crises_started": 2,
                "crises_perceived": 1,
                "signals_perceived": 4,
            },
        }
    ]
    rep = report.RunReport(
        run_id="r", campaigns=summaries, top_violations=[], top_errors=[], deltas=None
    )
    md = report.render_markdown(rep)
    assert "## Mundo" in md and "| explorador | 7 | 2 | 1 | 4 |" in md


def test_scenario_mundo_forces_crisis_within_5_days():
    from playtest.runner import run_campaign

    result = run_campaign("explorador", turns=14, seed=21, scenario="mundo")
    assert not [v for v in result.violations if str(v.get("check_id", "")).startswith("smoke.")]
    sim = result.final_state["world_sim"]
    assert any(c["region_id"] == "nova_arcadia" and c["start_day"] for c in sim["crises"])
    assert any(e["type"] == "location_state_changed" for e in result.final_state["event_log"]), (
        "crise deve virar location_state"
    )


def _sim_module():
    path = pathlib.Path(__file__).resolve().parents[1] / "docs" / "spec302" / "world_engine_sim.py"
    spec = importlib.util.spec_from_file_location("world_engine_sim_cal", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_calibration_fast_c3_c5_always_hold():
    out = _sim_module().evaluate(seeds=3, days=30)
    assert out["C3"] is True and out["C5"] is True
    assert out["invalid_events"] == []
    assert out["max_sim_bytes"] < 60_000
