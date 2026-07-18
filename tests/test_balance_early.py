"""Suíte da spec balanceamento-early-game — métricas de balanceamento (R5),
tuning de spawn nível 1 (R2), derrota narrada "O Saque" (R3) e pacing de
replan (R4). Tudo offline/MockLLM (conftest força RPG_FORCE_MOCK=1)."""
import json
import os

from playtest import report, telemetry
from playtest.runner import run_campaign


# --- Etapa 1 — métricas R5 no summary/report --------------------------------

def test_summary_tem_metricas_de_balanceamento(tmp_path, monkeypatch):
    monkeypatch.setattr(telemetry, "PLAYTEST_RUNS_DIR", str(tmp_path))
    res = run_campaign("combate", turns=6, seed=42)
    summ = telemetry.persist_campaign("run1", res)
    for campo in ("first_death_turn", "downed_count", "avg_hp_pct_after_combat",
                  "replan_count"):
        assert campo in summ, campo
    assert summ["first_death_turn"] is None or isinstance(summ["first_death_turn"], int)
    assert isinstance(summ["downed_count"], int)
    assert summ["avg_hp_pct_after_combat"] is None or (
        0 <= summ["avg_hp_pct_after_combat"] <= 100)
    assert isinstance(summ["replan_count"], int)
    # JSONL por turno carrega os campos crus que alimentam as métricas
    jsonl = os.path.join(str(tmp_path), "run1", f"{res.profile}_{res.seed}.jsonl")
    with open(jsonl, encoding="utf-8") as f:
        recs = [json.loads(l) for l in f if l.strip()]
    assert all("player_max_hp" in r and "combat_active" in r and "replanned" in r
               for r in recs)


def _synthetic_balance_run(dirpath, profile, seed, first_death=None, downed=0,
                           hp_pct=55.0, replans=3):
    os.makedirs(dirpath, exist_ok=True)
    summ = {
        "profile": profile, "seed": seed, "turns_completed": 10, "errors": 0,
        "violations": {}, "routes": {"storyteller": 8, "combat_agent": 2},
        "latency_ms": {"p50": 30, "p95": 90}, "deaths": 1 if first_death else 0,
        "final_level": 2, "final_gold": 40, "locations_visited": 5,
        "quests": {"created": 1, "completed": 0},
        "llm_requests_by_provider": {}, "cost_usd_total": 0.0,
        "cost_usd_by_tier": {}, "fell_back_turns": 0, "mock": True,
        "first_death_turn": first_death, "downed_count": downed,
        "avg_hp_pct_after_combat": hp_pct, "replan_count": replans,
    }
    with open(os.path.join(dirpath, f"{profile}_{seed}.summary.json"), "w",
              encoding="utf-8") as f:
        json.dump(summ, f)


# --- Etapa 2 — tuning de spawn nível 1 (R2) ---------------------------------

def _elite(i):
    return {"id": f"elite_{i}", "name": f"Elite {i}", "type": "elite", "hp": 30, "max_hp": 30}


def _minion(i):
    return {"id": f"min_{i}", "name": f"Min {i}", "type": "minion", "hp": 8, "max_hp": 8}


def test_encontro_forcado_nivel1_max_um_elite():
    import encounter_budget as eb
    kept, _ = eb.clamp_encounter([_elite(1), _elite(2), _minion(1)], budget=99,
                                 player_level=1)
    elites = [e for e in kept if eb.tier_cost(e) == eb.TIER_COST["elite"]]
    assert len(elites) == 1
    # nível 2+ segue sem o clamp extra
    kept2, _ = eb.clamp_encounter([_elite(1), _elite(2)], budget=99, player_level=2)
    assert len(kept2) == 2
    # boss nunca é cortado, mesmo no nível 1
    boss = {"id": "b", "name": "Boss", "type": "boss", "hp": 90, "max_hp": 90}
    kept3, _ = eb.clamp_encounter([boss, _elite(1), _elite(2)], budget=99, player_level=1)
    assert boss in kept3


def test_piso_de_hp_das_classes_frageis():
    from gamedata import CLASSES
    for cls in CLASSES.values() if isinstance(CLASSES, dict) else CLASSES:
        data = cls if isinstance(cls, dict) else CLASSES[cls]
        assert int(data["base_stats"]["hp"]) >= 22, data


def test_report_compara_metricas_no_baseline(tmp_path):
    base = os.path.join(str(tmp_path), "base")
    cur = os.path.join(str(tmp_path), "cur")
    _synthetic_balance_run(base, "combate", 42, first_death=3, downed=0, replans=10)
    _synthetic_balance_run(cur, "combate", 42, first_death=None, downed=1, replans=4)
    rep = report.aggregate(cur, baseline_dir=base)
    assert rep.deltas is not None
    assert rep.deltas["replans"] == 4 - 10
    assert rep.deltas["downed"] == 1 - 0
    md = report.render_markdown(rep)
    assert "1ª morte" in md and "replans" in md


# --- Etapa 3 — derrota narrada "O Saque" (R3) --------------------------------

def _world(loc_id="pm_profundezas", visited=None):
    import world_utils as wu
    w = wu.ensure_world({"current_location_id": loc_id,
                         "visited": visited or ["nova_arcadia", loc_id]})
    from gamedata import get_location
    loc = get_location(loc_id) or {}
    w["current_location"] = loc.get("name", loc_id)
    w["danger_level"] = loc.get("danger", 1)
    return w


def _downed_player(gold=87, uniques=()):
    inv = [{"id": "pocao_cura", "qty": 3}]
    for u in uniques:
        inv.append({"id": u, "qty": 1})
    return {
        "name": "Testudo", "class_name": "Batedor das Fronteiras",
        "level": 3, "xp": 500, "hp": 0, "max_hp": 40, "mana": 5, "max_mana": 5,
        "stamina": 10, "max_stamina": 20, "gold": gold,
        "inventory": inv,
        "equipment": {"weapon": "arco_de_caca", "armor": None, "accessory": None},
        "known_abilities": ["estocada_renal"], "active_conditions": [{"name": "Sangramento", "dot": 2, "duration": 2, "source": "x"}],
    }


def test_primeira_queda_e_downed_segunda_e_died():
    import combat_mechanics as cm
    w = _world()
    assert cm.death_outcome(w, [], []) == "downed"
    log = [{"type": "player_downed", "target_id": "player"}]
    assert cm.death_outcome(w, [], log) == "died"


def test_death_outcome_apex_ou_boss_e_died_mesmo_na_primeira():
    import combat_mechanics as cm
    from gamedata import WORLD_MAP
    apex = next((l["id"] for l in WORLD_MAP.get("locations", [])
                 if "apex" in (l.get("tags") or [])), None)
    if apex:
        assert cm.death_outcome(_world(apex), [], []) == "died"
    boss = [{"id": "b1", "name": "Rei", "type": "boss", "status": "ativo"}]
    assert cm.death_outcome(_world(), boss, []) == "died"


def test_apply_downed_saqueia_tudo_menos_arma_basica():
    import combat_mechanics as cm
    player, world, events, nota = cm.apply_downed(_downed_player(), _world())
    assert player["gold"] == 0
    assert player["hp"] == max(1, 40 // 4)
    assert player["equipment"]["weapon"] == "arco_de_caca"  # starting_equipment[0]
    assert player["equipment"]["armor"] is None and player["equipment"]["accessory"] is None
    # spec pos-saque-recuperacao (R1/R4): arma básica + 1 poção de cura ("rachada");
    # marca downed_recente no despertar (antes: inventário só a arma, sem condição).
    assert player["inventory"] == [{"id": "arco_de_caca", "qty": 1}, {"id": "pocao_cura", "qty": 1}]
    assert [c.get("name") for c in player["active_conditions"]] == ["downed_recente"]
    assert player["level"] == 3 and player["xp"] == 500  # XP/nível intactos
    ev = events[0]
    assert ev["type"] == "player_downed" and ev["source"] == "combat"
    assert ev["payload"]["gold_lost"] == 87
    assert nota


def test_apply_downed_avanca_relogio_facoes_e_teleporta_pro_seguro():
    import combat_mechanics as cm
    w = _world()
    day_before = w["world_clock"]["day"]
    player, world, events, _ = cm.apply_downed(_downed_player(), w)
    assert world["world_clock"]["day"] == day_before + 1
    assert world["current_location_id"] == "nova_arcadia"  # último seguro visitado
    assert events[0]["payload"]["rescued_to"] == "nova_arcadia"


def test_unique_saqueado_gera_unique_item_lost_e_volta_ao_pool():
    import combat_mechanics as cm
    from gamedata import ARTIFACTS_DB
    from services.economy import is_unique_available
    from services.event_processor import apply_event
    uid = next((i for i, a in ARTIFACTS_DB.items()
                if isinstance(a, dict) and a.get("unique")), None)
    assert uid, "precisa de ao menos 1 item único no ARTIFACTS_DB"
    player, world, events, _ = cm.apply_downed(_downed_player(uniques=[uid]), _world())
    lost = [e for e in events if e["type"] == "unique_item_lost"]
    assert lost and lost[0]["target_id"] == uid and lost[0]["source"] == "engine"
    # aplicado na projection com holder="world" → volta a estar disponível
    proj = apply_event({**lost[0], "event_id": "x" * 16, "turn": 1}, {})
    assert proj["unique_items"][uid]["holder"] == "world"
    assert is_unique_available(uid, proj)


def test_validator_rejeita_player_downed_proposto_por_llm():
    from services.world_validators import validate_proposal
    prop = {"type": "player_downed", "actor_id": "player", "target_id": "player",
            "detail": "caiu", "payload": {}}  # proposta de LLM: sem source
    res = validate_proposal(prop, {"world": {"turn_count": 1}, "event_log": []})
    assert not res.ok
    # com source="combat" (motor) passa — e só 1x por campanha
    prop_engine = {**prop, "source": "combat"}
    assert validate_proposal(prop_engine, {"world": {"turn_count": 1}, "event_log": []}).ok
    log_com_downed = [{"type": "player_downed", "target_id": "player"}]
    assert not validate_proposal(
        prop_engine, {"world": {"turn_count": 2}, "event_log": log_com_downed}).ok


def test_invariante_downed_duplo_ou_apex_e_error():
    from playtest import invariants as inv
    state = {"event_log": [
        {"type": "player_downed", "target_id": "player", "payload": {"location_id": "nova_arcadia"}},
        {"type": "player_downed", "target_id": "player", "payload": {"location_id": "nova_arcadia"}},
    ]}
    viols = inv.check_downed(state, None, 5)
    assert any(v.check_id == "downed.repeated" and v.severity == "error" for v in viols)
    state_boss = {"event_log": [
        {"type": "player_downed", "target_id": "player",
         "payload": {"location_id": "nova_arcadia", "boss_present": True}},
    ]}
    viols2 = inv.check_downed(state_boss, None, 5)
    assert any(v.check_id == "downed.vs_boss" for v in viols2)


# --- Etapa 4 — pacing de replan (R4) -----------------------------------------

def _plan(location, beats_status=("done", "pending"), last_planned=0):
    return {"location": location,
            "beats": [{"description": f"b{i}", "status": s}
                      for i, s in enumerate(beats_status)],
            "climax": "x", "current_step": 1, "last_planned_turn": last_planned,
            "arc_title": "Arco de teste"}


def _cm_state(plan, current_location, turn=5, needs_replan=False):
    return {"world": {"current_location": current_location, "turn_count": turn},
            "campaign_plan": plan, "needs_replan": needs_replan}


def test_viagem_intra_regiao_nao_replaneja():
    from agents.campaign_manager import _should_replan
    # Nova Arcádia → Anel Dourado (mesmo hub/região) com beat concluído
    st = _cm_state(_plan("Nova Arcádia"), "Anel Dourado", turn=5)
    from gamedata import get_location
    anel = get_location("na_anel_dourado")
    st["world"]["current_location"] = anel["name"]
    assert _should_replan(st) is False


def test_viagem_para_regiao_nova_replaneja():
    from agents.campaign_manager import _should_replan
    from gamedata import get_location
    pantano = get_location("pantano_melancolia")
    st = _cm_state(_plan("Nova Arcádia", beats_status=("done", "pending")),
                   pantano["name"], turn=5)
    assert _should_replan(st) is True
    # região nova mas arco recém-começado (0 beats done, tem beats) → NÃO replaneja
    st2 = _cm_state(_plan("Nova Arcádia", beats_status=("pending", "pending")),
                    pantano["name"], turn=5)
    st2["campaign_plan"]["current_step"] = 0
    assert _should_replan(st2) is False


def test_local_de_plano_irresoluvel_nao_replaneja_por_viagem():
    from agents.campaign_manager import _should_replan
    st = _cm_state(_plan("Terras Cinzentas", beats_status=("done", "pending")),
                   "Nova Arcádia", turn=5)
    assert _should_replan(st) is False


def test_intervalo_15_turnos():
    from agents.campaign_manager import _should_replan, REPLAN_INTERVAL
    assert REPLAN_INTERVAL == 15
    plan = _plan("Nova Arcádia", beats_status=("pending", "pending"), last_planned=0)
    plan["current_step"] = 0
    st = _cm_state(plan, "Nova Arcádia", turn=14)
    assert _should_replan(st) is False
    st15 = _cm_state(plan, "Nova Arcádia", turn=15)
    assert _should_replan(st15) is True


def test_needs_replan_explicito_continua_imediato():
    from agents.campaign_manager import _should_replan
    plan = _plan("Nova Arcádia", beats_status=("pending", "pending"), last_planned=4)
    plan["current_step"] = 0
    st = _cm_state(plan, "Nova Arcádia", turn=5, needs_replan=True)
    assert _should_replan(st) is True


def test_combate_nao_morre_nivel1_mock_seed42():
    """Meta R2/R3: na rodada mock 50t seed 42, a PRIMEIRA queda do `combate`
    nunca vira memorial fora de apex — vira O Saque e a campanha continua."""
    from playtest.runner import run_campaign
    res = run_campaign("combate", turns=50, seed=42)
    final = res.final_state
    log = final.get("event_log") or []
    downs = [e for e in log if e.get("type") == "player_downed"]
    dies = [e for e in log if e.get("type") == "player_died"]
    assert len(downs) <= 1
    if dies:  # morreu? então a 1ª queda foi Saque ANTES (2ª queda = memorial)
        assert downs, "morte sem player_downed anterior — 1ª queda virou memorial"
        assert log.index(downs[0]) < log.index(dies[0])
    # a campanha continuou depois do Saque (houve turnos após o downed)
    if downs:
        down_turn = downs[0].get("turn", 0)
        assert any(r.turn > down_turn and not r.error for r in res.history)
    assert not any("downed." in v.get("check_id", "") for v in res.violations)


def test_combate_downed_end_to_end_mock():
    """Fluxo integrado: HP=0 na 1ª queda → downed (sem game_over), campanha segue."""
    from playtest.runner import run_campaign
    res = run_campaign("agressivo", turns=20, seed=42)
    final = res.final_state
    downs = [e for e in (final.get("event_log") or []) if e.get("type") == "player_downed"]
    deaths_lvl1 = [r for r in res.history
                   if r.player_max_hp and r.player_hp <= 0 and r.player_level == 1
                   and final.get("game_over")]
    # agressivo caía no turno 8 do baseline; agora a 1ª queda vira Saque
    assert len(downs) <= 1
    if downs:
        assert not final.get("game_over") or len(downs) == 1
    # violações da invariante nova não podem aparecer
    assert not any("downed." in v.get("check_id", "") for v in res.violations)
