"""SPEC-302 Etapa 3: diretor de tensao."""

from __future__ import annotations

import copy

import pytest

from services import world_director as wd
from services import world_engine as we
from tests.spec302_helpers import fresh_sim, set_pressure

LEGIAO = {
    "id": "legiao_ferro",
    "name": "A Legião de Ferro",
    "region": "Nova Arcádia",
    "disposition": "hostil",
}


@pytest.fixture(autouse=True)
def _mode_on(monkeypatch):
    monkeypatch.setenv("RPG_WORLD_ENGINE", "on")


_PROJ: dict = {}


def step(sim, day, projection=None, factions=None):
    """Um dia do diretor; os eventos do motor sao aplicados a projection (como o arquivista)."""
    from services.event_processor import apply_event

    proj = _PROJ.setdefault(id(sim), {})
    out = wd.step_crises(
        sim,
        day,
        proj,
        we.day_rng("g", day, "director"),
        game_id="g",
        factions=factions or [],
        faction_region=we.faction_region_id,
    )
    for ev in out[1]:
        proj.update(apply_event({**ev, "turn": day}, proj))
    return out


def hot(sim, region="nova_arcadia", kind="guerra", value=85):
    set_pressure(sim, region, kind, value)


def test_initial_calm_blocks_announcements():
    sim = fresh_sim(1, calm=5)
    hot(sim)
    _, ev, _ = step(sim, 3)
    assert not sim["crises"] and not ev


def test_crisis_requires_prior_warning_min_days():
    sim = fresh_sim()
    hot(sim)
    _, ev, _ = step(sim, 10)
    assert [e["type"] for e in ev] == ["world_crisis_warning"]
    assert not wd.request_crisis_slot(sim, 10, "nova_arcadia", "guerra")  # mesmo dia
    assert not wd.request_crisis_slot(sim, 11, "nova_arcadia", "guerra")
    assert not wd.request_crisis_slot(sim, 12, "pantano_melancolia", "guerra")  # sem aviso
    assert wd.request_crisis_slot(sim, 12, "nova_arcadia", "guerra")


def test_warning_then_open_after_delay():
    sim = fresh_sim()
    hot(sim)
    step(sim, 10)
    _, ev11, _ = step(sim, 11)
    assert not wd.active_crises(sim) and not ev11
    _, ev12, dg = step(sim, 12)
    assert len(wd.active_crises(sim)) == 1
    assert any(e["type"] == "location_state_changed" for e in ev12)
    assert any(d["kind"] == "crise" for d in dg)


def test_max_active_crises():
    sim = fresh_sim()
    regs = [
        ("nova_arcadia", "guerra"),
        ("pantano_melancolia", "praga"),
        ("pradaria_ruinas", "fome"),
        ("brekmar", "abismo"),
    ]
    peak = 0
    for d in range(1, 30):
        for r, k in regs:
            hot(sim, r, k, 90)
        step(sim, d)
        peak = max(peak, len(wd.active_crises(sim)))
    assert peak == 2


def test_region_cooldown():
    sim = fresh_sim()
    sim["region_last_crisis_end"] = {"nova_arcadia": 8}
    hot(sim)
    step(sim, 10)  # 10 + 2 - 8 < 12: nem anuncia
    assert not sim["crises"]
    step(sim, 18)
    assert sim["crises"]


def test_global_gap():
    sim = fresh_sim()
    hot(sim, "nova_arcadia", "guerra")
    hot(sim, "pradaria_ruinas", "fome")
    step(sim, 10)
    step(sim, 12)
    starts = sorted(c["start_day"] for c in sim["crises"] if c["start_day"])
    assert starts == [12]  # a segunda so abre >= 3 dias depois
    step(sim, 13)
    step(sim, 14)
    step(sim, 15)
    starts = sorted(c["start_day"] for c in sim["crises"] if c["start_day"])
    assert starts == [12, 15]


def test_no_crisis_during_recuperacao():
    sim = fresh_sim()
    hot(sim)
    step(sim, 10)
    sim["recovery_until_day"] = 30
    assert not wd.request_crisis_slot(sim, 12, "nova_arcadia", "guerra")
    wd.update_phase(sim, 12)
    assert sim["phase"] == "recuperacao"
    assert wd.request_crisis_slot(sim, 30, "nova_arcadia", "guerra")


def test_crisis_ends_below_recupera_after_min_days():
    sim = fresh_sim()
    hot(sim)
    step(sim, 10)
    step(sim, 12)
    assert wd.active_crises(sim)
    set_pressure(sim, "nova_arcadia", "guerra", 10)
    step(sim, 13)
    assert wd.active_crises(sim)  # < MIN_CRISIS_DAYS
    _, ev, _ = step(sim, 15)
    assert not wd.active_crises(sim)
    assert any(e["type"] == "location_state_changed" and not e["payload"]["state"] for e in ev)
    assert sim["region_last_crisis_end"]["nova_arcadia"] == 15
    assert sim["crises"][-1]["resolution"] == "recuperou"


def _open_guerra(factions):
    sim = fresh_sim()
    hot(sim)
    step(sim, 10, factions=factions)
    step(sim, 12, factions=factions)
    return sim


def test_escalation_on_escalation_day():
    sim = _open_guerra([LEGIAO])
    rec = wd.active_crises(sim)[0]
    esc = rec["escalation_day"]
    hot(sim, value=95)
    _, ev, _ = step(sim, esc, factions=[LEGIAO])
    assert rec["severity"] == 2
    assert any(e["payload"].get("severity") == 2 for e in ev)
    rec["severity"] = 3
    rec["escalation_day"] = esc + 1
    _, ev, _ = step(sim, esc + 1, factions=[LEGIAO])
    states = [e["payload"]["state"] for e in ev if e["type"] == "location_state_changed"]
    assert states == ["ocupado"]
    assert any(e["type"] == "location_control_changed" for e in ev)
    assert rec["resolution"] == "escalou"


def test_escalation_without_faction_becomes_ruina():
    sim = _open_guerra([])
    rec = wd.active_crises(sim)[0]
    rec["severity"], rec["escalation_day"] = 3, 13
    hot(sim, value=95)
    _, ev, _ = step(sim, 13)
    states = [e["payload"]["state"] for e in ev if e["type"] == "location_state_changed"]
    assert states == ["ruina"]
    assert not any(e["type"] == "location_control_changed" for e in ev)


def test_phase_transitions():
    sim = fresh_sim()
    wd.update_phase(sim, 1)
    assert sim["phase"] == "calmo"
    hot(sim)
    step(sim, 10)
    wd.update_phase(sim, 10)
    assert sim["phase"] == "tensao"
    step(sim, 12)
    wd.update_phase(sim, 12)
    assert sim["phase"] == "crise"
    set_pressure(sim, "nova_arcadia", "guerra", 5)
    step(sim, 16)
    wd.update_phase(sim, 16)
    assert sim["phase"] == "recuperacao"
    wd.update_phase(sim, 16 + 5)
    assert sim["phase"] == "calmo"


def test_announce_respects_shared_budget():
    sim = fresh_sim()
    for r, k in (("nova_arcadia", "guerra"), ("brekmar", "fome"), ("pradaria_ruinas", "praga")):
        wd.announce(sim, 1, r, k, game_id="g")
    # announce respeita o teto de avisos+ativas: so 2 avisos cabem
    assert len(wd.announced_crises(sim)) + len(wd.active_crises(sim)) == 2


def test_external_slot_consumes_same_budget():
    sim = fresh_sim()
    wd.announce(sim, 1, "nova_arcadia", "guerra", game_id="g")
    wd.announce(sim, 1, "brekmar", "fome", game_id="g")
    assert wd.request_crisis_slot(sim, 4, "nova_arcadia", "guerra")
    assert not wd.request_crisis_slot(sim, 5, "brekmar", "fome")  # gap global
    assert wd.request_crisis_slot(sim, 8, "brekmar", "fome")
    assert len(wd.active_crises(sim)) == 2
    # o diretor interno ve as duas ativas: nao abre uma terceira
    wd.announce(sim, 8, "pradaria_ruinas", "praga", game_id="g")
    assert wd.announce(sim, 8, "pradaria_ruinas", "praga", game_id="g") is None


def test_tiebreak_deterministic():
    def run():
        sim = fresh_sim()
        hot(sim, "nova_arcadia", "guerra")
        hot(sim, "pradaria_ruinas", "fome")
        step(sim, 10)
        step(sim, 12)
        return copy.deepcopy(sim["crises"])

    assert run() == run()
