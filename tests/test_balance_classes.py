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
    rec = _rec(
        entropy=4, max_entropy=16, abyss_charge=7, abyss_tier="moderado",
        class_mechanics=[{"kind": "special:blood_leak"}],
    )
    row = tm.turn_to_record(rec)
    assert row["entropy"] == 4
    assert row["max_entropy"] == 16
    assert row["abyss_charge"] == 7
    assert row["abyss_tier"] == "moderado"
    assert row["class_mechanics"] == [{"kind": "special:blood_leak"}]


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


def test_summary_mede_gasto_de_entropia():
    # spec playtest-agente-curioso-entropia (R4): economia medida por GASTO, não
    # snapshot. Turno de combate = rota combat_agent.
    player = {"class_name": "Devoto do Abismo", "level": 2, "gold": 0,
              "known_abilities": ["ataque_basico", "provocacao_do_abismo"],
              "entropy": 0, "max_entropy": 16, "abyss_charge": 5}
    rows = [
        # combate: usou ativa, gastou 5
        {"turn": 1, "route": "combat_agent", "combat_active": True,
         "used_active_ability": True, "entropy_spent": 5, "ability_id": "x",
         "resolved_action": {"kind": "card"},
         "entropy": 11, "max_entropy": 16, "abyss_charge": 1, "latency_ms": 1,
         "class_mechanics": [{"kind": "special:taunt"}]},
        # combate: ataque básico com Entropia cheia → flooding
        {"turn": 2, "route": "combat_agent", "combat_active": True,
         "used_active_ability": False, "entropy_spent": 0,
         "resolved_action": {"kind": "attack"},
         "entropy": 16, "max_entropy": 16, "abyss_charge": 3, "latency_ms": 1},
        # fora de combate: ignorado no cálculo de economia
        {"turn": 3, "route": "storyteller", "combat_active": False,
         "entropy": 2, "max_entropy": 16, "abyss_charge": 5, "latency_ms": 1},
    ]
    s = tm.build_summary(_result(player=player), rows)
    assert s["class_name"] == "Devoto do Abismo"
    ent = s["entropy"]
    assert ent["spent_total"] == 5
    assert ent["spent_per_combat_turn"] == 2.5           # 5 gasto / 2 turnos combate
    assert ent["pct_combat_turns_ability_used"] == 50.0  # 1 de 2
    assert ent["pct_combat_turns_basic_only"] == 50.0
    assert ent["flooding_pct_combat"] == 50.0            # turno 2: básico + cheio
    assert ent["peak_abyss_charge"] == 5
    assert ent["final_abyss_tier"] == "moderado"         # Devoto: moderado=4
    assert ent["mechanic_activations"] == {"special:taunt": 1}


def test_summary_starvation_quando_recurso_falta():
    # básico com Entropia < menor custo de ativa conhecida → starvation.
    player = {"class_name": "Devoto do Abismo", "level": 2,
              "known_cards": ["dev_provocacao"], "prepared_cards": ["dev_provocacao"],
              "entropy": 0, "max_entropy": 16, "abyss_charge": 0}
    rows = [
        {"turn": 1, "route": "combat_agent", "combat_active": True,
         "used_active_ability": False, "entropy_spent": 0,
         "resolved_action": {"kind": "attack"},
         "entropy": 0, "max_entropy": 16, "abyss_charge": 0, "latency_ms": 1},
    ]
    s = tm.build_summary(_result(player=player), rows)
    # dev_provocacao custa 2; Entropia 0 < 2 → starvation 100%
    assert s["entropy"]["starvation_pct_combat"] == 100.0


def test_summary_nao_chama_cura_fuga_ou_manobra_de_ataque_basico():
    player = {"class_name": "Devoto do Abismo",
              "prepared_cards": ["dev_provocacao"],
              "entropy": 16, "max_entropy": 16, "abyss_charge": 0}
    rows = [
        {"turn": i, "route": "combat_agent", "combat_active": True,
         "used_active_ability": False, "entropy_spent": 0,
         "resolved_action": {"kind": kind},
         "entropy": 16, "max_entropy": 16, "abyss_charge": 0, "latency_ms": 1}
        for i, kind in enumerate(("item", "flee", "maneuver", "pass"), 1)
    ]
    entropy = tm.build_summary(_result(player=player), rows)["entropy"]
    assert entropy["pct_combat_turns_basic_only"] == 0.0
    assert entropy["flooding_pct_combat"] == 0.0


def test_summary_sem_combate_nao_divide_por_zero():
    s = tm.build_summary(_result(player={"class_name": "Corruptor"}),
                         [{"turn": 1, "route": "storyteller", "combat_active": False,
                           "entropy": 1, "max_entropy": 10, "abyss_charge": 0,
                           "latency_ms": 1}])
    assert s["entropy"]["flooding_pct_combat"] is None
    assert s["entropy"]["spent_per_combat_turn"] is None


def test_min_active_entropy_cost():
    devoto = {"prepared_cards": ["dev_provocacao"]}
    assert tm._min_active_entropy_cost(devoto) == 2
    assert tm._min_active_entropy_cost({"prepared_cards": []}) == 0


def test_knobs_de_classe_finalizados_e_gatilhos_passivos_limitados():
    from gamedata import CLASSES

    def notes(value):
        if isinstance(value, dict):
            for key, child in value.items():
                if key == "note" and isinstance(child, str):
                    yield child
                yield from notes(child)
        elif isinstance(value, list):
            for child in value:
                yield from notes(child)

    assert not any("[BALANCEAR]" in note for note in notes(CLASSES))
    assert CLASSES["Devoto do Abismo"]["entropy_trigger"]["charge_cap"] == 6
    assert CLASSES["Médico de Campo"]["entropy_trigger"]["charge_cap"] == 6


# --- spec playtest-agente-curioso-entropia: gasto carimbado no combate --------

def test_use_card_gasta_entropia():
    from services import cards
    player = {"entropy": 16, "prepared_cards": ["dev_provocacao"],
              "virtue_cards": [], "card_usage": {}}
    res = cards.use_card({"player": player}, "dev_provocacao")
    assert res["ok"] and player["entropy"] == 14


def test_ataque_basico_gasta_zero():
    player = {"entropy": 16}
    before = player["entropy"]
    assert player["entropy"] - before == 0


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
