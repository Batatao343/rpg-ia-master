"""Suíte da spec balanceamento-classes-pos-playtest — instrumentação (Etapa 1).

`--class` no harness + telemetria de Entropia/Carga por turno + seção Classes
no relatório. Offline/determinístico. Ver specs/balanceamento-classes-pos-playtest.md.
"""
import pytest

from playtest import report as rp
from playtest import telemetry as tm
from playtest.runner import (CampaignResult, TurnRecord, resolve_class_name,
                             run_campaign)


# --- R1: --class ------------------------------------------------------------

def test_resolve_class_name_slug_e_exato():
    assert resolve_class_name("devoto_do_abismo") == "Devoto do Abismo"
    assert resolve_class_name("Sangromante") == "Sangromante"
    assert resolve_class_name("medico_de_campo") == "Médico de Campo"  # sem acento
    assert resolve_class_name("ARCANISTA CINZENTO") == "Arcanista Cinzento"
    with pytest.raises(KeyError):
        resolve_class_name("bardo")


def test_run_aceita_class():
    res = run_campaign("explorador", turns=2, seed=1, class_name="sangromante")
    assert res.final_state["player"]["class_name"] == "Sangromante"
    assert res.turns_completed >= 1


# --- R2: telemetria de Entropia/Carga ---------------------------------------

def _rec(**over):
    r = TurnRecord(turn=1, action="a", route="combat_agent", latency_ms=1)
    for k, v in over.items():
        setattr(r, k, v)
    return r


def test_turn_record_tem_entropia():
    rec = _rec(entropy=4, max_entropy=16, abyss_charge=7, abyss_tier="moderado")
    row = tm.turn_to_record(rec)
    assert row["entropy"] == 4
    assert row["max_entropy"] == 16
    assert row["abyss_charge"] == 7
    assert row["abyss_tier"] == "moderado"


def test_fill_state_metrics_le_entropia_do_estado():
    from playtest.runner import _fill_state_metrics
    rec = _rec()
    state = {"player": {"hp": 20, "max_hp": 30, "class_name": "Devoto do Abismo",
                        "entropy": 5, "max_entropy": 16, "abyss_charge": 2},
             "world": {"current_location_id": "nova_arcadia"}}
    _fill_state_metrics(rec, state)
    assert rec.entropy == 5 and rec.max_entropy == 16
    assert rec.abyss_charge == 2
    assert rec.abyss_tier == "leve"          # thresholds do Devoto (leve=1)


def _result(profile="combate", turns=3, player=None):
    return CampaignResult(
        profile=profile, seed=1, turns_completed=turns, errors=[],
        history=[], final_state={"player": player or {}, "world": {}},
        save_path="", violations=[], mock=True)


def test_summary_agrega_starvation_flooding_carga():
    player = {"class_name": "Sangromante", "level": 2, "gold": 0,
              "entropy": 0, "max_entropy": 16, "abyss_charge": 5}
    rows = [
        {"turn": 1, "combat_active": True, "entropy": 0, "max_entropy": 16,
         "abyss_charge": 1, "latency_ms": 1},
        {"turn": 2, "combat_active": True, "entropy": 16, "max_entropy": 16,
         "abyss_charge": 3, "latency_ms": 1},
        {"turn": 3, "combat_active": False, "entropy": 2, "max_entropy": 16,
         "abyss_charge": 5, "latency_ms": 1},
    ]
    s = tm.build_summary(_result(player=player), rows)
    assert s["class_name"] == "Sangromante"
    ent = s["entropy"]
    assert ent["starvation_pct_combat"] == 50.0   # 1 de 2 turnos de combate
    assert ent["flooding_pct_combat"] == 50.0     # 1 de 2 turnos de combate
    assert ent["peak_abyss_charge"] == 5
    assert ent["final_abyss_charge"] == 5
    assert ent["final_abyss_tier"] == "moderado"  # Sangromante: moderado=4


def test_summary_sem_combate_nao_divide_por_zero():
    s = tm.build_summary(_result(player={"class_name": "Corruptor"}),
                         [{"turn": 1, "combat_active": False, "entropy": 1,
                           "max_entropy": 10, "abyss_charge": 0, "latency_ms": 1}])
    assert s["entropy"]["starvation_pct_combat"] is None
    assert s["entropy"]["flooding_pct_combat"] is None


# --- R3: seção Classes no relatório -----------------------------------------

def test_report_secao_classes():
    summaries = [{
        "profile": "combate", "seed": 42, "turns_completed": 50, "errors": 0,
        "violations": {}, "routes": {}, "latency_ms": {"p50": 1, "p95": 2},
        "deaths": 1, "first_death_turn": 30, "downed_count": 1,
        "final_level": 3, "final_gold": 10, "locations_visited": 2,
        "quests": {"created": 0, "completed": 0},
        "llm_requests_by_provider": {}, "cost_usd_total": 0.0,
        "cost_usd_by_tier": {}, "fell_back_turns": 0, "mock": True,
        "aborted_reason": None, "replan_count": 0,
        "avg_hp_pct_after_combat": 55.0,
        "class_name": "Devoto do Abismo",
        "entropy": {"starvation_pct_combat": 20.0, "flooding_pct_combat": 10.0,
                    "peak_abyss_charge": 6, "final_abyss_charge": 4,
                    "final_abyss_tier": "moderado"},
    }]
    rep = rp.RunReport(run_id="t", campaigns=summaries, top_violations=[],
                       top_errors=[], deltas=None, mock_any=True)
    md = rp.render_markdown(rep)
    assert "## Classes" in md
    assert "Devoto do Abismo" in md
    assert "moderado" in md
