"""
Suíte da Fase 2.7 — Rules engine sistêmica (líder morre → cascata de mundo).
Spec: specs/SPEC-004-fase-2.7-rules-engine.md. 100% offline e determinística (sem LLM).

Ids canônicos reais de data/graph/entities.json usados aqui:
  npc que controla local direto: npc_valerius → nova_arcadia (não lidera fação)
  líderes que controlam território: npc_kahen → poder_kahen → brekmar;
                                    npc_o_que_ouve_mais_longe → colmeia_hospedeiros → selva_xylos
  líder sem território: npc_velha_magda → mao_sombria
"""

import pytest

from services import graph_resolver as gr
from services import rule_engine as re_
from services.rule_engine import RuleActionError


@pytest.fixture(autouse=True)
def _fresh_graph_cache():
    gr.clear_cache()
    re_._rules_cache = None
    yield
    gr.clear_cache()
    re_._rules_cache = None


# ---------------------------------------------------------------------------
# Etapa 1 — resolvedor seguro + conditions
# ---------------------------------------------------------------------------

def _ctx(**over):
    base = {
        "event": {"type": "npc_killed", "target_id": "npc_valerius",
                  "payload": {"new_controller_id": "legiao_ferro"}},
        "target": {"id": "npc_valerius", "type": "npc", "tags": ["governante"]},
        "component": {
            "faction_member": {"faction_id": "selo_palido"},
            "power_vacuum_trigger": {"base_instability_delta": -45,
                                     "rival_factions": ["culto_clareira", "outra"]},
        },
    }
    base.update(over)
    return base


def test_resolve_component_path():
    assert re_.resolve_path("component:faction_member.faction_id", _ctx()) == "selo_palido"


def test_resolve_index():
    assert re_.resolve_path(
        "component:power_vacuum_trigger.rival_factions[0]", _ctx()) == "culto_clareira"


def test_resolve_literais():
    assert re_.resolve_path(False, _ctx()) is False
    assert re_.resolve_path(-45, _ctx()) == -45
    assert re_.resolve_path(["a", "b"], _ctx()) == ["a", "b"]


def test_resolve_event_e_target():
    assert re_.resolve_path("event.type", _ctx()) == "npc_killed"
    assert re_.resolve_path("event.payload.new_controller_id", _ctx()) == "legiao_ferro"
    assert re_.resolve_path("target.type", _ctx()) == "npc"


def test_resolve_rejeita_expressao_arbitraria():
    for bad in ("__import__('os')", "event.__class__", "os.system('x')", "target.__dict__"):
        with pytest.raises(RuleActionError):
            re_.resolve_path(bad, _ctx())


def test_resolve_rejeita_chave_inexistente():
    with pytest.raises(RuleActionError):
        re_.resolve_path("component:faction_member.inexistente", _ctx())


def test_conditions_has_component():
    rule = {"conditions": [{"target_has_component": "power_vacuum_trigger"}]}
    # valerius tem o componente (overlay components.json); npc_grum não.
    assert re_.check_conditions(rule, {"target_id": "npc_valerius"}, {}) is True
    assert re_.check_conditions(rule, {"target_id": "npc_grum"}, {}) is False


def test_conditions_missing_component():
    rule = {"conditions": [{"target_missing_component": "power_vacuum_trigger"}]}
    assert re_.check_conditions(rule, {"target_id": "npc_grum"}, {}) is True
    assert re_.check_conditions(rule, {"target_id": "npc_valerius"}, {}) is False


def test_conditions_has_tag():
    rule = {"conditions": [{"target_has_tag": "governante"}]}
    ev = {"target_id": "npc_valerius"}
    assert re_.check_conditions(rule, ev, {}) is True
    rule2 = {"conditions": [{"target_has_tag": "inexistente"}]}
    assert re_.check_conditions(rule2, ev, {}) is False


def test_conditions_vazias_casam():
    assert re_.check_conditions({}, {"target_id": "npc_valerius"}, {}) is True


# ---------------------------------------------------------------------------
# Etapa 2 — ações + run_rules
# ---------------------------------------------------------------------------

def _st(**over):
    base = {"world_projection": {}, "factions": []}
    base.update(over)
    return base


def test_adjust_stability_clampa():
    st = _st()
    ev = {"target_id": "npc_valerius"}
    action = {"op": "adjust_faction_stability", "faction": "mao_sombria", "delta": -200}
    re_.execute_action(action, ev, st)
    assert st["world_projection"]["entities"]["mao_sombria"]["stability"] == -100


def test_adjust_stability_espelha_em_state_factions():
    st = _st(factions=[{"id": "mao_sombria", "stability": 10}])
    action = {"op": "adjust_faction_stability", "faction": "mao_sombria", "delta": -5}
    re_.execute_action(action, {"target_id": "npc_valerius"}, st)
    assert st["factions"][0]["stability"] == 5


def test_emit_event_gera_derivado():
    st = _st()
    action = {"op": "emit_event", "type": "location_control_changed",
              "targets": ["nova_arcadia"], "payload": {"new_controller_id": "mao_sombria"}}
    ev = {"target_id": "npc_valerius", "actor_id": "player"}
    out = re_.execute_action(action, ev, st)
    assert len(out) == 1
    assert out[0]["source"] == "rule_engine"
    assert out[0]["type"] == "location_control_changed"
    assert out[0]["target_id"] == "nova_arcadia"
    assert out[0]["payload"]["new_controller_id"] == "mao_sombria"


def test_op_desconhecido_nao_quebra():
    re_._rules_cache = [{
        "id": "rule_bugada", "trigger": "npc_killed",
        "actions": [{"op": "op_inventado", "foo": "bar"}],
    }]
    ev = {"type": "npc_killed", "target_id": "npc_grum", "payload": {}}
    # não levanta; regra é descartada
    assert re_.run_rules(ev, _st()) == []


def test_profundidade_maxima():
    """Regra que emite um evento do MESMO tipo que a dispara → recursão limitada a depth 2."""
    re_._rules_cache = [{
        "id": "rule_loop", "trigger": "npc_killed",
        "actions": [{"op": "emit_event", "type": "npc_killed", "targets": ["npc_grum"]}],
    }]
    ev = {"type": "npc_killed", "target_id": "npc_grum", "payload": {}}
    derived = re_.run_rules(ev, _st())
    # depth0 emite d1(depth1); d1 emite d2(depth2); d2 para → 2 derivados, sem loop infinito.
    assert len(derived) == 2
    assert all(d["source"] == "rule_engine" for d in derived)


# ---------------------------------------------------------------------------
# Etapa 3 — dados: world_rules.json + components.json (overlay)
# ---------------------------------------------------------------------------

_WHITELIST_OPS = {"set_entity_state", "adjust_faction_stability",
                  "disable_controls_edges", "create_dynamic_edge", "emit_event"}
_KNOWN_TRIGGERS = {"npc_killed", "secret_revealed", "location_control_changed",
                   "quest_completed", "faction_relation_changed"}


def test_rules_json_valido():
    rules = re_.load_rules()
    assert rules, "world_rules.json vazio"
    ids = [r["id"] for r in rules]
    assert len(ids) == len(set(ids)), "id de regra duplicado"
    for r in rules:
        assert r["trigger"] in _KNOWN_TRIGGERS, f"trigger desconhecido: {r['trigger']}"
        for a in r.get("actions", []):
            assert a.get("op") in _WHITELIST_OPS, f"op fora da whitelist: {a.get('op')}"


def test_componente_carrega_via_overlay():
    ent = gr.get_entity("npc_valerius")
    assert "power_vacuum_trigger" in ent.get("components", {})
    # overlay não apaga campos existentes da entidade
    assert ent.get("type") == "npc" and ent.get("tags")


def test_lideres_tem_componentes_completos():
    """Toda entidade em components.json com power_vacuum_trigger deve liderar uma fação
    (edge leads) OU controlar um local (edge controls); successor_id, se presente, existe."""
    import json
    with open("data/graph/components.json", encoding="utf-8") as f:
        comps = json.load(f)
    for eid, cmp in comps.items():
        if eid.startswith("_") or "power_vacuum_trigger" not in cmp:
            continue
        leads = gr.resolve_edges({}, entity_id=eid, edge_type="leads", include_hidden=True)
        controls = gr.resolve_edges({}, entity_id=eid, edge_type="controls", include_hidden=True)
        has_leads = any(e["source"] == eid for e in leads)
        has_controls = any(e["source"] == eid for e in controls)
        assert has_leads or has_controls, f"{eid} não lidera nem controla nada"
        succ = cmp["power_vacuum_trigger"].get("successor_id")
        if succ:
            assert gr.get_entity(succ), f"successor_id inexistente: {succ}"


# ---------------------------------------------------------------------------
# Etapa 4 — integração no event_processor + prova de generalidade
# ---------------------------------------------------------------------------

from services.event_processor import process_pending_events


def _kill(npc_id: str, **over) -> dict:
    st = {
        "world": {"turn_count": 7},
        "world_projection": {},
        "event_log": [],
        "factions": [],
        "pending_world_events": [{"type": "npc_killed", "actor_id": "player",
                                  "target_id": npc_id, "payload": {}, "source": "combat"}],
    }
    st.update(over)
    return process_pending_events(st)


def test_morte_de_lider_dispara_cascata():
    out = _kill("npc_valerius")
    log = out["event_log"]
    proj = out["world_projection"]
    # evento base + derivado auditável
    assert any(e["type"] == "npc_killed" and e["target_id"] == "npc_valerius" for e in log)
    derived = [e for e in log if e.get("source") == "rule_engine"]
    assert any(e["type"] == "location_control_changed" and e["target_id"] == "nova_arcadia"
               for e in derived), "cascata não gerou location_control_changed"
    # controle do local mudou para o rival (override = mao_sombria)
    assert gr.get_current_controller("nova_arcadia", proj) == "mao_sombria"
    # cascata depth-2: rule_control_change_ripple bumpou a stability do novo dono
    assert proj["entities"]["mao_sombria"]["stability"] == 5


def test_mesma_regra_dois_lideres():
    """npc_kahen e npc_o_que_ouve_mais_longe (líderes que controlam território) disparam
    a MESMA rule_faction_leader_death — cada um destabiliza a fação e troca o controle."""
    for npc, faction, loc in [
        ("npc_kahen", "poder_kahen", "brekmar"),
        ("npc_o_que_ouve_mais_longe", "colmeia_hospedeiros", "selva_xylos"),
    ]:
        out = _kill(npc)
        proj = out["world_projection"]
        derived = [e for e in out["event_log"] if e.get("source") == "rule_engine"]
        assert any(e["type"] == "location_control_changed" and e["target_id"] == loc
                   for e in derived), f"{npc} não trocou controle de {loc}"
        # fação liderada perdeu stability (delta -50, clamp)
        assert proj["entities"][faction]["stability"] < 0
        # o local mudou de dono
        assert gr.get_current_controller(loc, proj) not in (None, npc)


def test_npc_comum_so_marca_morto():
    """NPC sem power_vacuum_trigger → regra genérica, sem cascata de controle."""
    out = _kill("npc_grum")
    assert out["world_projection"]["entities"]["npc_grum"]["alive"] is False
    assert not [e for e in out["event_log"] if e.get("source") == "rule_engine"]


def test_codigo_nao_menciona_valerius():
    """R7/aceite: nenhum id de NPC específico hardcoded em services/ ou agents/."""
    import pathlib
    root = pathlib.Path(".")
    for folder in ("services", "agents"):
        for py in (root / folder).rglob("*.py"):
            text = py.read_text(encoding="utf-8")
            assert "npc_valerius" not in text, f"{py} menciona npc_valerius"


def test_save_antigo_sem_projection_nao_quebra():
    """State legado sem world_projection/factions → cascata tolera e não levanta."""
    st = {
        "world": {"turn_count": 1},
        "event_log": [],
        "pending_world_events": [{"type": "npc_killed", "target_id": "npc_grum", "payload": {}}],
    }
    out = process_pending_events(st)  # não levanta
    assert out["world_projection"]["entities"]["npc_grum"]["alive"] is False


def test_fila_vazia_noop():
    assert process_pending_events({"pending_world_events": []}) == {}
