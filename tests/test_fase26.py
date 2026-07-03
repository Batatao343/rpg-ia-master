"""
Suíte da Fase 2.6 — Structured world changes (LLM propõe, motor valida/aplica).
Spec: specs/fase-2.6-structured-events.md. 100% offline.

Usa ids canônicos reais de data/graph/entities.json:
  npc vivo canônico: npc_valerius (controla nova_arcadia)
  npc com segredo:   npc_velha_magda (edge secret 'leads' mao_sombria)
  location:          nova_arcadia
  facções:           legiao_ferro, mao_sombria
"""

import pytest

from services import graph_resolver as gr
from services.event_processor import apply_event, process_pending_events
from services.world_validators import validate_proposal


@pytest.fixture(autouse=True)
def _fresh_graph_cache():
    gr.clear_cache()
    yield
    gr.clear_cache()


def _state(**over) -> dict:
    base = {
        "world": {"turn_count": 5, "current_location": "nova_arcadia"},
        "world_projection": {},
        "event_log": [],
        "pending_world_events": [],
        "campaign_plan": {"beats": [{"description": "b0", "status": "active"}]},
    }
    base.update(over)
    return base


# ---------------------------------------------------------------------------
# Etapa 1 — validadores
# ---------------------------------------------------------------------------

def test_valida_npc_killed_ok():
    prop = {"type": "npc_killed", "actor_id": "player", "target_id": "npc_valerius"}
    res = validate_proposal(prop, _state())
    assert res.ok, res.reason


def test_rejeita_id_inexistente():
    prop = {"type": "npc_killed", "target_id": "npc_fantasma"}
    res = validate_proposal(prop, _state())
    assert not res.ok
    assert "npc_fantasma" in res.reason


def test_rejeita_npc_ja_morto():
    proj = {"entities": {"npc_valerius": {"alive": False}}}
    prop = {"type": "npc_killed", "target_id": "npc_valerius"}
    res = validate_proposal(prop, _state(world_projection=proj))
    assert not res.ok
    assert "morto" in res.reason.lower()


def test_rejeita_duplicata_no_turno():
    log = [{"type": "npc_killed", "target_id": "npc_valerius", "turn": 5}]
    prop = {"type": "npc_killed", "target_id": "npc_valerius"}
    res = validate_proposal(prop, _state(event_log=log))
    assert not res.ok
    assert "duplicata" in res.reason.lower()


def test_duplicata_so_conta_mesmo_turno():
    """Mesmo type+target em turno ANTERIOR não bloqueia (só o turno atual)."""
    log = [{"type": "npc_killed", "target_id": "npc_grum", "turn": 1}]
    prop = {"type": "npc_killed", "target_id": "npc_grum"}
    res = validate_proposal(prop, _state(event_log=log))
    assert res.ok, res.reason


def test_rejeita_payload_malformado():
    """Falta o target_id obrigatório → Pydantic falha → rejeitado sem exceção."""
    res = validate_proposal({"type": "npc_killed"}, _state())
    assert not res.ok
    assert "malformada" in res.reason.lower()


def test_rejeita_type_desconhecido():
    res = validate_proposal({"type": "meteoro", "target_id": "npc_valerius"}, _state())
    assert not res.ok


def test_secret_revealed_ok():
    prop = {"type": "secret_revealed", "target_id": "npc_velha_magda",
            "detail": "Magda lidera a Mão Sombria"}
    res = validate_proposal(prop, _state())
    assert res.ok, res.reason


def test_secret_revealed_rejeita_sem_segredo():
    """Alvo sem edge hidden/secret → nada a revelar."""
    prop = {"type": "secret_revealed", "target_id": "npc_grum"}
    res = validate_proposal(prop, _state())
    assert not res.ok


def test_secret_revealed_rejeita_ja_revelado():
    proj = {"revealed_facts": {"ev1": {"entity_id": "npc_velha_magda", "fact": "x"}}}
    prop = {"type": "secret_revealed", "target_id": "npc_velha_magda"}
    res = validate_proposal(prop, _state(world_projection=proj))
    assert not res.ok
    assert "revelado" in res.reason.lower()


def test_location_control_changed_ok():
    prop = {"type": "location_control_changed", "target_id": "nova_arcadia",
            "payload": {"new_controller_id": "legiao_ferro"}}
    res = validate_proposal(prop, _state())
    assert res.ok, res.reason


def test_location_control_rejeita_controlador_nao_faccao():
    prop = {"type": "location_control_changed", "target_id": "nova_arcadia",
            "payload": {"new_controller_id": "npc_valerius"}}
    res = validate_proposal(prop, _state())
    assert not res.ok


def test_faction_relation_changed_ok():
    prop = {"type": "faction_relation_changed", "target_id": "legiao_ferro",
            "payload": {"other_faction_id": "mao_sombria", "relation": "enemy_of"}}
    res = validate_proposal(prop, _state())
    assert res.ok, res.reason


def test_quest_completed_ok():
    prop = {"type": "quest_completed", "target_id": "b0", "payload": {"beat_index": 0}}
    res = validate_proposal(prop, _state())
    assert res.ok, res.reason


def test_quest_completed_rejeita_beat_fora():
    prop = {"type": "quest_completed", "target_id": "b9", "payload": {"beat_index": 9}}
    res = validate_proposal(prop, _state())
    assert not res.ok


# ---------------------------------------------------------------------------
# Etapa 2 — event processor
# ---------------------------------------------------------------------------

def test_fila_vazia_e_noop():
    assert process_pending_events(_state()) == {}


def test_npc_killed_aplica_na_projection():
    st = _state(pending_world_events=[
        {"type": "npc_killed", "actor_id": "player", "target_id": "npc_valerius",
         "source": "combat"},
    ])
    up = process_pending_events(st)
    assert gr.is_alive("npc_valerius", up["world_projection"]) is False
    assert len(up["event_log"]) == 1
    assert up["event_log"][0]["type"] == "npc_killed"
    assert up["event_log"][0]["source"] == "combat"
    assert up["event_log"][0]["event_id"]  # uuid preenchido
    assert up["pending_world_events"] == []


def test_rejeitado_nao_entra_no_log():
    st = _state(pending_world_events=[
        {"type": "npc_killed", "target_id": "npc_fantasma"},  # id inexistente
    ])
    up = process_pending_events(st)
    assert up["event_log"] == []
    assert up["pending_world_events"] == []


def test_secret_revealed_registra_fato():
    st = _state(pending_world_events=[
        {"type": "secret_revealed", "target_id": "npc_velha_magda",
         "detail": "Magda lidera a Mão Sombria"},
    ])
    up = process_pending_events(st)
    facts = up["world_projection"]["revealed_facts"]
    assert len(facts) == 1
    fato = next(iter(facts.values()))
    assert fato["entity_id"] == "npc_velha_magda"
    assert fato["revealed_at_turn"] == 5
    assert "Magda" in fato["fact"]


def test_location_control_changed_troca_edge():
    st = _state(pending_world_events=[
        {"type": "location_control_changed", "target_id": "nova_arcadia",
         "payload": {"new_controller_id": "legiao_ferro"}},
    ])
    up = process_pending_events(st)
    proj = up["world_projection"]
    assert gr.get_current_controller("nova_arcadia", proj) == "legiao_ferro"
    # edge base vigente foi para disabled_edges com auditoria
    disabled = {d["edge_id"] for d in proj.get("disabled_edges", [])}
    assert "e_valerius_controla_arcadia" in disabled
    assert all(d.get("disabled_by_event") for d in proj["disabled_edges"])


def test_duplicata_no_mesmo_lote_so_aplica_uma():
    st = _state(pending_world_events=[
        {"type": "npc_killed", "target_id": "npc_valerius"},
        {"type": "npc_killed", "target_id": "npc_valerius"},  # duplicata no lote
    ])
    up = process_pending_events(st)
    assert len(up["event_log"]) == 1


def test_apply_event_e_puro():
    """apply_event não muta a projection recebida."""
    proj = {"entities": {}}
    ev = {"event_id": "abc", "turn": 1, "type": "npc_killed", "target_id": "npc_valerius",
          "payload": {}}
    out = apply_event(ev, proj)
    assert proj == {"entities": {}}  # original intacto
    assert out["entities"]["npc_valerius"]["alive"] is False


# ---------------------------------------------------------------------------
# Etapa 3 — integração archivist (turno trivial: processa eventos sem tocar no LLM)
# ---------------------------------------------------------------------------

def test_archivist_processa_pendings():
    from agents.archivist import archive_node
    st = _state(game_id="t26", archivist_last_run=5, messages=[],
                pending_world_events=[{"type": "npc_killed", "target_id": "npc_valerius"}])
    up = archive_node(st)
    assert up["archive_due"] is False           # turno trivial (não rodou o LLM)
    assert len(up["event_log"]) == 1
    assert gr.is_alive("npc_valerius", up["world_projection"]) is False
    assert up["pending_world_events"] == []


def test_archivist_fila_vazia_nao_mexe_no_mundo():
    from agents.archivist import archive_node
    st = _state(game_id="t26", archivist_last_run=5, messages=[])
    up = archive_node(st)
    assert up == {"archive_due": False}          # sem event_updates quando fila vazia


# ---------------------------------------------------------------------------
# Etapa 4 — storyteller propõe
# ---------------------------------------------------------------------------

def test_storyupdate_schema_tem_proposed_events():
    from agents.storyteller import StoryUpdate
    su = StoryUpdate(narrative="x")
    assert su.proposed_events == []


class _FakeStoryLLM:
    """Devolve um StoryUpdate com uma proposta de evento (offline)."""

    def __init__(self, events):
        self._events = events

    def with_structured_output(self, model, *_a, **_k):
        self._model = model
        return self

    def with_retry(self, *_a, **_k):
        return self

    def invoke(self, _msgs):
        return self._model(
            narrative="O guarda arregala os olhos ao ouvir a verdade.",
            introduced_npcs=[],
            proposed_events=self._events,
        )


def _story_state():
    from langchain_core.messages import HumanMessage
    st = _state(game_id="pytest26", narrative_summary="", archivist_last_run=0,
                messages=[HumanMessage(content="revelo o segredo ao guarda")],
                npcs={}, factions=[], faction_intel={},
                player={"name": "T", "class_name": "Guerreiro"},
                campaign_plan={})
    st["world"] = {"current_location": "nova_arcadia", "turn_count": 5, "time_of_day": "Dia",
                   "weather": "Neutro", "danger_level": 1, "quest_plan": []}
    return st


def test_storyteller_enfileira_proposta(monkeypatch):
    import agents.storyteller as stt
    ev = {"type": "secret_revealed", "target_id": "npc_velha_magda",
          "detail": "Magda lidera a Mão Sombria"}
    monkeypatch.setattr(stt, "get_llm", lambda *a, **k: _FakeStoryLLM([ev]))
    out = stt.storyteller_node(_story_state())
    assert "pending_world_events" in out
    assert out["pending_world_events"][0]["type"] == "secret_revealed"
    assert out["pending_world_events"][0]["target_id"] == "npc_velha_magda"


def test_storyteller_fallback_nao_quebra(monkeypatch):
    """FallbackLLM devolve AIMessage (não StoryUpdate) → guard try/except segura o turno."""
    import agents.storyteller as stt
    from llm_setup import FallbackLLM
    monkeypatch.setattr(stt, "get_llm", lambda *a, **k: FallbackLLM("quota"))
    out = stt.storyteller_node(_story_state())
    assert "messages" in out            # não estourou; devolveu narração de fallback


# ---------------------------------------------------------------------------
# Etapa 5 — combat determinístico (npc_killed sem LLM)
# ---------------------------------------------------------------------------

def test_combate_gera_npc_killed_para_canonico():
    from agents.combat import _kill_events
    dead = [{"id": "npc_valerius_1", "name": "Lorde Valerius", "status": "morto"}]
    kills = _kill_events(dead)
    assert len(kills) == 1
    assert kills[0]["type"] == "npc_killed"
    assert kills[0]["target_id"] == "npc_valerius"   # sufixo de instância removido
    assert kills[0]["source"] == "combat"


def test_inimigo_generico_nao_gera_evento():
    from agents.combat import _kill_events
    dead = [{"id": "goblin_1", "name": "Goblin 1", "status": "morto"}]
    assert _kill_events(dead) == []


def test_canonical_enemy_id_sem_id():
    from agents.combat import _canonical_enemy_id
    assert _canonical_enemy_id({"name": "sem id"}) is None


def test_combate_e_processor_ponta_a_ponta():
    """Kill canônico do combate, validado/aplicado pelo processor, mata na projection."""
    from agents.combat import _kill_events
    kills = _kill_events([{"id": "npc_grum_1", "name": "Grum", "status": "morto"}])
    st = _state(pending_world_events=kills)
    up = process_pending_events(st)
    assert gr.is_alive("npc_grum", up["world_projection"]) is False
