"""SPEC-325 Etapa 8: capability_counts (R4), bots/cenarios (R18, §6) e invariantes (R19)."""

from __future__ import annotations

import pytest

from playtest import capabilities, invariants, report, scenarios, telemetry
from playtest.profiles import PROFILES
from services import combat_flags

ALL_ON = {cap: "on" for cap in combat_flags.CAPS}
ENV = combat_flags.ENV_VARS


def _set_flags(monkeypatch, mode):
    for var in ENV.values():
        monkeypatch.setenv(var, mode)
    monkeypatch.setenv("RPG_COMPANION_SOUL", "on")


# --- R4: contagem -----------------------------------------------------------
def test_counter_maps_on_and_shadow_events():
    c = capabilities.CapabilityCounter()
    for ev in (
        "combat.reveal_resist",
        "combat.reveal_resist_shadow",
        "combat.chase_attack_refused",
        "combat.chase_attack_reengage",
        "combat.chase_sacrifice",
        "combat.chase_abandon_shadow",
        "combat.nao_existe",
    ):
        c(ev)
    snap = c.snapshot()
    assert snap["reveal_resist"] == 1 and snap["reveal_resist_shadow"] == 1
    assert snap["chase_attack"] == 2 and snap["chase_abandon"] == 1
    assert snap["chase_abandon_shadow"] == 1
    assert set(snap) == {k for cap in combat_flags.CAPS for k in (cap, f"{cap}_shadow")}
    assert len(snap) == 16


def test_counting_listens_to_log_event_and_detaches():
    from observability import telemetry as obs

    with capabilities.counting() as counter:
        obs.log_event("combat", "object_used")
        obs.log_event("combat", "objects_shadow")
        obs.log_event("law", "gate_failed")
    obs.log_event("combat", "object_used")  # fora do bloco: ninguem escuta
    snap = counter.snapshot()
    assert snap["objects"] == 1 and snap["objects_shadow"] == 1
    assert obs._event_sink is None


def test_summary_and_report_have_capability_counts():
    class R:
        capability_counts = {"nonlethal": 2, "ruido": 9}

    got = telemetry._capability_counts(R())
    assert got["nonlethal"] == 2 and "ruido" not in got and len(got) == 16
    rep = report.RunReport(
        run_id="x",
        campaigns=[
            {"profile": "combate", "scenario": "combate_nao_letal", "capability_counts": got}
        ],
        top_violations=[],
        top_errors=[],
        deltas=None,
    )
    md = report.render_markdown(rep)
    assert "## Capacidades de conflito" in md and "combate_nao_letal" in md


# --- R18: perfis intactos, cenarios novos ------------------------------------
def test_new_bots_do_not_enter_profiles_or_all():
    for name in scenarios.names():
        if name in capabilities_scenarios():
            assert name not in PROFILES
    assert set(capabilities_scenarios()) <= set(scenarios.names())
    assert len(capabilities_scenarios()) == 7


def capabilities_scenarios():
    from playtest import capability_bots

    return capability_bots.NAMES


# --- R19: invariantes ----------------------------------------------------------
def _ids(state, prev=None):
    return {v.check_id for v in invariants.check_conflict_capabilities_state(state, prev, 1)}


def test_state_invariants_clean_and_each_violation():
    assert _ids({"enemies": [{"id": "a_1", "status": "ativo"}]}) == set()
    dup = {"enemies": [{"id": "a_r1"}, {"id": "a_r1"}]}
    assert _ids(dup) == {"conflict.enemy_id_repeated"}
    killed = {
        "enemies": [{"id": "soldado_1", "status": "incapacitado"}],
        "event_log": [{"type": "npc_killed", "target_id": "soldado"}],
    }
    assert _ids(killed) == {"conflict.incapacitated_in_deaths"}
    # evento antigo (ja no estado anterior) nao conta
    assert _ids(killed, prev={"event_log": killed["event_log"]}) == set()
    fate = {"party": [{"name": "B", "active": True, "pending_fate": {"seed": "s"}}]}
    assert _ids(fate) == {"conflict.sealed_fate_active"}
    assert _ids({"party": [{"name": "B", "active": False, "pending_fate": {"seed": "s"}}]}) == set()
    neg = {"combat": {"scene": {"objects": [{"id": "o", "uses_remaining": -1}]}}}
    assert _ids(neg) == {"conflict.object_uses_negative"}


def test_resistance_format_invariant_still_there():
    bad = {"enemies": [{"name": "C", "revealed_resistances": ["igneo:talvez"]}]}
    ids = {v.check_id for v in invariants.check_conflict_capabilities(bad, None, 1)}
    assert ids == {"conflict.resistance_format"}


def test_golden_rule_flags_leaks(monkeypatch):
    _set_flags(monkeypatch, "on")
    base = {
        "player": {"name": "H", "vitalidade": 10, "max_vitalidade": 10, "ferimentos": {}},
        "combat": {"active": True, "round": 2, "scene": {"objects": []}},
        "enemies": [
            {
                "id": "e1",
                "name": "Iniciado",
                "status": "ativo",
                "vitalidade": 5,
                "max_vitalidade": 5,
                "immunities": ["igneo"],
                "revealed_resistances": [],
            }
        ],
    }
    assert invariants.check_conflict_golden_rule(base, None, 1) == []
    # aviso de reforco sem aviso registrado = vazamento
    leaky = {**base, "combat": {**base["combat"], "reinforcement": {"warned_round": None}}}
    assert invariants.check_conflict_golden_rule(leaky, None, 1) == []  # a API nao o publica
    # estado vazio de combate nao dispara a view
    assert invariants.check_conflict_golden_rule({"player": {}}, None, 1) == []


def test_new_checks_are_registered():
    assert invariants.check_conflict_capabilities_state in invariants.CHECKS
    assert invariants.check_conflict_golden_rule in invariants.CHECKS


# --- §6: cenarios por capacidade, via grafo real (MockLLM) -------------------
SCENARIOS = {
    "combate_resistencia": "reveal_resist",
    "combate_nao_letal": "nonlethal",
    "fuga_escolhas": "chase_approach",
    "fuga_abandono": "chase_abandon",
    "combate_objeto": "objects",
    "combate_ordem": "companion_orders",
    "combate_reforco": "reinforcements",
}


def _run(name, turns):
    from playtest.runner import run_campaign

    return run_campaign(scenarios.profile_for(name), turns=turns, seed=0, scenario=name)


@pytest.mark.parametrize(("name", "cap"), sorted(SCENARIOS.items()))
def test_scenario_on_fires_capability_without_errors(monkeypatch, name, cap):
    _set_flags(monkeypatch, "on")
    result = _run(name, 12)
    errors = [v for v in result.violations if v.get("severity") == "error"]
    assert not errors and not result.errors, (errors, result.errors)
    assert result.capability_counts[cap] >= 1
    summary = telemetry.build_summary(result, [])
    assert summary["capability_counts"][cap] >= 1


def test_scenario_shadow_counts_only_shadow_keys(monkeypatch):
    _set_flags(monkeypatch, "shadow")
    result = _run("combate_nao_letal", 6)
    assert not [v for v in result.violations if v.get("severity") == "error"]
    counts = result.capability_counts
    assert counts["nonlethal"] == 0 and counts["nonlethal_shadow"] >= 1


def test_oracle_requires_capability_only_when_on(monkeypatch):
    class R:
        final_state: dict = {}
        turns_completed = 3
        capability_counts = {"nonlethal": 0}

    monkeypatch.setenv(ENV["nonlethal"], "shadow")
    assert scenarios.oracle_violations("combate_nao_letal", R()) == []
    monkeypatch.setenv(ENV["nonlethal"], "on")
    out = scenarios.oracle_violations("combate_nao_letal", R())
    assert [v["check_id"] for v in out] == ["smoke.combate_nao_letal_not_observed"]
