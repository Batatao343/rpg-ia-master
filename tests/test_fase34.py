"""
Suíte da Fase 3.4 — Visualização de estado (mapa dinâmico + histórico de reputação).
Spec: specs/SPEC-009-fase-3.4-visualizacao-estado.md. 100% offline, zero LLM.

Usa ids reais de data/graph/entities.json e data/world_map.json (mesmos das fases
2.6/2.7/3.1/3.2/3.3):
  location: nova_arcadia (controlada por legiao_ferro nos fixtures de 2.6/2.7)
  facções:  legiao_ferro, mao_sombria
"""

import pytest

from services import graph_resolver as gr
from services import state_views as sv

NOVA_ARCADIA = "nova_arcadia"
LEGIAO = "legiao_ferro"
MAO_SOMBRIA = "mao_sombria"


@pytest.fixture(autouse=True)
def _fresh_graph_cache():
    gr.clear_cache()
    yield
    gr.clear_cache()


# ---------------------------------------------------------------------------
# Etapa 1 — services/state_views.py (puro)
# ---------------------------------------------------------------------------

def _rep_event(turn, delta, value, fid=LEGIAO):
    return {"type": "reputation_changed", "target_id": fid, "turn": turn,
            "payload": {"delta": delta, "new_value": value, "reason": "ajudou"}}


def test_history_ordena_e_limita():
    events = [_rep_event(t, 5, t) for t in range(25)]
    hist = sv.reputation_history(events, LEGIAO, limit=20)
    assert len(hist) == 20
    assert [h["turn"] for h in hist] == list(range(5, 25))  # cronológico, últimos 20
    assert hist[-1]["value"] == 24


def test_history_ignora_outras_faccoes():
    events = [_rep_event(1, 5, 5, fid=LEGIAO), _rep_event(2, 5, 5, fid=MAO_SOMBRIA)]
    hist = sv.reputation_history(events, LEGIAO)
    assert len(hist) == 1
    assert hist[0]["turn"] == 1


def test_stability_label_limiares():
    assert sv.stability_label({"entities": {LEGIAO: {"stability": -150}}}, LEGIAO) == "em colapso"
    assert sv.stability_label({"entities": {LEGIAO: {"stability": -100}}}, LEGIAO) == "em colapso"
    assert sv.stability_label({"entities": {LEGIAO: {"stability": -50}}}, LEGIAO) == "instável"
    assert sv.stability_label({"entities": {LEGIAO: {"stability": 0}}}, LEGIAO) == "estável"
    assert sv.stability_label({"entities": {LEGIAO: {"stability": 50}}}, LEGIAO) == "estável"


def test_stability_label_ausente():
    assert sv.stability_label({}, LEGIAO) == "estável"
    assert sv.stability_label(None, LEGIAO) == "estável"


def _ctrl_event(loc_id, new_controller, turn):
    return {"type": "location_control_changed", "target_id": loc_id, "turn": turn,
            "payload": {"new_controller_id": new_controller}}


def test_control_changes_respeita_fog():
    events = [_ctrl_event(NOVA_ARCADIA, LEGIAO, 10)]
    out = sv.recent_control_changes(events, visited=[], current_turn=15)
    assert out == []
    out2 = sv.recent_control_changes(events, visited=[NOVA_ARCADIA], current_turn=15)
    assert len(out2) == 1
    assert out2[0]["location_id"] == NOVA_ARCADIA
    assert out2[0]["controller_name"]  # resolvido via grafo, não o id cru


def test_control_changes_janela():
    events = [_ctrl_event(NOVA_ARCADIA, LEGIAO, 1)]
    out = sv.recent_control_changes(events, visited=[NOVA_ARCADIA], current_turn=40)  # >30
    assert out == []
    out2 = sv.recent_control_changes(events, visited=[NOVA_ARCADIA], current_turn=25)  # <=30
    assert len(out2) == 1


def test_active_threats_ttl():
    world = {"threat_alerts": [
        {"region_id": "nova_arcadia", "hint": "Rato da Peste", "turn": 5},
        {"region_id": "skallgard", "hint": "Bandido", "turn": 0},
    ]}
    out = sv.active_threats(world, current_turn=7)  # TTL=6: turn=5 (diff 2) vale, turn=0 (diff 7) expirou
    assert len(out) == 1
    assert out[0]["region_id"] == "nova_arcadia"


def test_active_threats_nao_consome():
    world = {"threat_alerts": [{"region_id": "x", "hint": "y", "turn": 5}]}
    sv.active_threats(world, current_turn=6)
    assert len(world["threat_alerts"]) == 1  # leitura, não mutou


def test_visible_controllers_projection_vence_legado():
    world = {"visited": [NOVA_ARCADIA], "controlled": {NOVA_ARCADIA: MAO_SOMBRIA}}
    proj = {"dynamic_edges": [{"id": "dyn1", "source": LEGIAO, "type": "controls",
                               "target": NOVA_ARCADIA, "visibility": "public"}]}
    out = sv.visible_controllers(world, proj)
    # dynamic (LEGIAO, pública) vence tanto o base do grafo (Valerius) quanto o legado (Mão Sombria)
    assert out[NOVA_ARCADIA] == gr.get_entity(LEGIAO)["name"]


def test_visible_controllers_edge_hidden_nao_aparece():
    # nova_arcadia já tem controlador PÚBLICO no grafo base (npc_valerius) — a edge
    # dynamic hidden (Legião) deve ser ignorada e o público deve prevalecer, não vazar.
    world = {"visited": [NOVA_ARCADIA], "controlled": {}}
    proj = {"dynamic_edges": [{"id": "dyn1", "source": LEGIAO, "type": "controls",
                               "target": NOVA_ARCADIA, "visibility": "hidden"}]}
    out = sv.visible_controllers(world, proj)
    assert out[NOVA_ARCADIA] != gr.get_entity(LEGIAO)["name"]  # a edge hidden não vazou


def test_visible_controllers_fallback_legado():
    world = {"visited": [NOVA_ARCADIA], "controlled": {NOVA_ARCADIA: LEGIAO}}
    out = sv.visible_controllers(world, {})
    assert out[NOVA_ARCADIA]  # sem projection, cai no legado e resolve nome


def test_visible_controllers_so_visitados():
    world = {"visited": [], "controlled": {NOVA_ARCADIA: LEGIAO}}
    out = sv.visible_controllers(world, {})
    assert out == {}


# ---------------------------------------------------------------------------
# Etapa 2 — evento reputation_changed no pipeline (2.6)
# ---------------------------------------------------------------------------

def test_validador_reputation_valida():
    from services.world_validators import validate_proposal
    prop = {"type": "reputation_changed", "target_id": LEGIAO,
            "payload": {"delta": 10, "new_value": 10, "reason": "ajudou"}}
    state = {"world": {"turn_count": 5}, "world_projection": {}, "event_log": []}
    res = validate_proposal(prop, state)
    assert res.ok, res.reason


def test_validador_reputation_rejeita_id_inexistente():
    from services.world_validators import validate_proposal
    prop = {"type": "reputation_changed", "target_id": "faccao_fantasma",
            "payload": {"delta": 10, "new_value": 10, "reason": "ajudou"}}
    state = {"world": {"turn_count": 5}, "world_projection": {}, "event_log": []}
    res = validate_proposal(prop, state)
    assert not res.ok


def test_validador_reputation_rejeita_derrotada():
    from services.world_validators import validate_proposal
    prop = {"type": "reputation_changed", "target_id": LEGIAO,
            "payload": {"delta": 10, "new_value": 10, "reason": "ajudou"}}
    proj = {"entities": {LEGIAO: {"alive": False}}}
    state = {"world": {"turn_count": 5}, "world_projection": proj, "event_log": []}
    res = validate_proposal(prop, state)
    assert not res.ok


def test_apply_reputation_changed_noop_na_projection():
    from services.event_processor import apply_event
    event = {"event_id": "e1", "turn": 5, "type": "reputation_changed",
             "target_id": LEGIAO, "payload": {"delta": 10, "new_value": 10}}
    before = {"entities": {}, "dynamic_edges": []}
    after = apply_event(event, before)
    assert after == before  # fallthrough — nada muda na projection


def test_reputation_changed_nao_vira_milestone():
    from services.chronicle import render_milestone
    event = {"event_id": "e1", "turn": 5, "type": "reputation_changed",
             "target_id": LEGIAO, "payload": {"delta": 10, "new_value": 10}}
    assert render_milestone(event, {}) == ""


def test_pipeline_reputation_changed_completo():
    from services.event_processor import process_pending_events
    state = {
        "world": {"turn_count": 8}, "world_projection": {}, "event_log": [],
        "chronicle": [], "quests": [],
        "pending_world_events": [{"type": "reputation_changed", "target_id": LEGIAO,
                                  "actor_id": "player",
                                  "payload": {"delta": 10, "new_value": 10, "reason": "ajudou"},
                                  "source": "storyteller"}],
    }
    out = process_pending_events(state)
    assert len(out["event_log"]) == 1
    assert out["event_log"][0]["type"] == "reputation_changed"
    assert "chronicle" not in out  # não virou milestone


class _FakeStoryLLM34:
    def __init__(self, impacts=None):
        self._impacts = impacts or []

    def with_structured_output(self, model, *_a, **_k):
        self._model = model
        return self

    def with_retry(self, *_a, **_k):
        return self

    def invoke(self, _msgs):
        return self._model(narrative="A Legião nota sua ajuda.", introduced_npcs=[],
                           faction_impacts=self._impacts)


def test_storyteller_enfileira_reputation_changed(monkeypatch):
    import agents.storyteller as stt
    from langchain_core.messages import HumanMessage
    fake = _FakeStoryLLM34(impacts=[{"faction_id": LEGIAO, "direction": "ajudou"}])
    monkeypatch.setattr(stt, "get_llm", lambda *a, **k: fake)
    state = {
        "game_id": "pytest34", "narrative_summary": "", "archivist_last_run": 0,
        "messages": [HumanMessage(content="ajudo os soldados da legião")],
        "npcs": {}, "quests": [],
        "factions": [{"id": LEGIAO, "name": "Legião de Ferro", "reputation": 0,
                      "disposition": "neutro", "defeated": False}],
        "faction_intel": {}, "player": {"name": "T", "class_name": "Guerreiro"},
        "campaign_plan": {},
        "world": {"current_location": "nova_arcadia", "turn_count": 8,
                  "time_of_day": "Dia", "weather": "Neutro", "danger_level": 1, "quest_plan": []},
    }
    out = stt.storyteller_node(state)
    assert "pending_world_events" in out
    rep = [e for e in out["pending_world_events"] if e["type"] == "reputation_changed"]
    assert len(rep) == 1
    assert rep[0]["target_id"] == LEGIAO
    assert rep[0]["payload"]["delta"] > 0
    assert rep[0]["payload"]["reason"] == "ajudou"


# ---------------------------------------------------------------------------
# Etapa 3 — API (_world_block / _factions_block)
# ---------------------------------------------------------------------------

def test_factions_block_history_so_known():
    import api
    event_log = [_rep_event(1, 10, 10, fid=LEGIAO), _rep_event(2, 10, 10, fid=MAO_SOMBRIA)]
    factions = [
        {"id": LEGIAO, "name": "Legião de Ferro", "reputation": 10, "disposition": "neutro"},
        {"id": MAO_SOMBRIA, "name": "Mão Sombria", "reputation": 10, "disposition": "neutro"},
    ]
    intel = {LEGIAO: {"known": True}}  # só a Legião é conhecida
    out = api._factions_block(factions, intel, turn=5, event_log=event_log, projection={})
    assert len(out) == 1
    assert out[0]["id"] == LEGIAO
    assert len(out[0]["history"]) == 1
    assert out[0]["stability_label"] == "estável"


def test_world_block_overlays_shape():
    import api
    world = {
        "current_location": "Nova Arcádia", "current_location_id": NOVA_ARCADIA,
        "visited": [NOVA_ARCADIA], "turn_count": 10, "danger_level": 1,
        "looming_threat": "algo se aproxima",
        "threat_alerts": [{"region_id": "nova_arcadia", "hint": "Rato da Peste", "turn": 8}],
    }
    event_log = [_ctrl_event(NOVA_ARCADIA, LEGIAO, 9)]
    block = api._world_block(world, projection={}, event_log=event_log)
    assert block["map_overlays"]["looming_threat"] == "algo se aproxima"
    assert len(block["map_overlays"]["threats"]) == 1
    assert len(block["map_overlays"]["control_changes"]) == 1
    assert block["map_overlays"]["control_changes"][0]["location_id"] == NOVA_ARCADIA
    assert isinstance(block["controlled"], dict)


def test_save_antigo_overlays_vazios():
    import api
    world = {"current_location": "X", "visited": []}  # sem threat_alerts/looming_threat
    block = api._world_block(world, projection=None, event_log=None)
    assert block["map_overlays"] == {"control_changes": [], "threats": [], "looming_threat": ""}
    assert block["controlled"] == {}


def test_save_antigo_faction_sem_history():
    import api
    out = api._factions_block(
        [{"id": LEGIAO, "name": "Legião de Ferro", "reputation": 0, "disposition": "neutro"}],
        {LEGIAO: {"known": True}}, turn=1, event_log=None, projection=None,
    )
    assert out[0]["history"] == []
    assert out[0]["stability_label"] == "estável"
