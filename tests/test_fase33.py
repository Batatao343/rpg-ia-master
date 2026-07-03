"""
Suíte da Fase 3.3 — Quest log (side quests persistentes).
Spec: specs/fase-3.3-quest-log.md. 100% offline.

Usa ids reais de data/graph/entities.json e data/world_map.json (mesmos da Fase 3.1/3.2):
  npc vivo canônico: npc_valerius (controla nova_arcadia)
  location:          nova_arcadia
"""

import copy

import pytest

from services import graph_resolver as gr
from services import quest_log as ql
from services.event_processor import process_pending_events
from services.world_validators import validate_proposal

NOVA_ARCADIA = "nova_arcadia"
NPC_VALERIUS = "npc_valerius"


def _state(**over) -> dict:
    base = {
        "world": {"turn_count": 5, "current_location": "nova_arcadia"},
        "world_projection": {}, "event_log": [], "pending_world_events": [],
        "chronicle": [], "quests": [],
        "campaign_plan": {"beats": [{"description": "b0", "status": "active"}]},
    }
    base.update(over)
    return base


@pytest.fixture(autouse=True)
def _fresh_graph_cache():
    gr.clear_cache()
    yield
    gr.clear_cache()


# ---------------------------------------------------------------------------
# Etapa 1 — services/quest_log.py (puro)
# ---------------------------------------------------------------------------

def test_registra_quest_valida():
    proposals = [{"title": "Recuperar o medalhão", "description": "Um pedido urgente.",
                  "origin_name": "Valerius", "origin_entity_id": NPC_VALERIUS,
                  "location_id": NOVA_ARCADIA, "reward_hint": "50 moedas"}]
    quests, created = ql.register_proposed_quests([], proposals, turn=5)
    assert len(quests) == 1 and len(created) == 1
    q = quests[0]
    assert q["title"] == "Recuperar o medalhão"
    assert q["status"] == "active"
    assert q["origin_entity_id"] == NPC_VALERIUS
    assert q["location_id"] == NOVA_ARCADIA
    assert q["created_turn"] == 5
    assert q["id"]


def test_titulo_vazio_ignorado():
    quests, created = ql.register_proposed_quests([], [{"title": "  "}], turn=1)
    assert quests == [] and created == []


def test_dedupe_titulo_similar():
    existing = [{"id": "q1", "title": "Caçar o lobo branco", "status": "active"}]
    proposals = [{"title": "Cace o Lobo Branco"}]
    quests, created = ql.register_proposed_quests(existing, proposals, turn=2)
    assert len(quests) == 1  # não duplicou
    assert created == []


def test_dedupe_ignora_resolvidas():
    existing = [{"id": "q1", "title": "Caçar o lobo branco", "status": "completed"}]
    proposals = [{"title": "Cace o Lobo Branco"}]
    quests, created = ql.register_proposed_quests(existing, proposals, turn=2)
    assert len(quests) == 2  # completed não conta pro dedupe
    assert len(created) == 1


def test_location_invalida_zerada():
    proposals = [{"title": "Explorar as ruínas", "location_id": "local_que_nao_existe"}]
    quests, created = ql.register_proposed_quests([], proposals, turn=1)
    assert quests[0]["location_id"] == ""
    assert created[0]["location_id"] == ""


def test_origin_entity_invalida_zerada():
    proposals = [{"title": "Ajudar o forasteiro", "origin_entity_id": "id_inventado_123"}]
    quests, created = ql.register_proposed_quests([], proposals, turn=1)
    assert quests[0]["origin_entity_id"] == ""


def test_teto_de_ativas():
    existing = [{"id": f"q{i}", "title": f"Missão {i}", "status": "active"} for i in range(8)]
    quests, created = ql.register_proposed_quests(existing, [{"title": "Nona missão"}], turn=1)
    assert len(quests) == 8  # 9ª ignorada
    assert created == []


def test_proposta_dict_malformado_nao_quebra():
    quests, created = ql.register_proposed_quests([], [{}, {"title": None}], turn=1)
    assert quests == [] and created == []


def test_aceita_pydantic_e_dict():
    from services.structured_outputs import ProposedQuest
    p = ProposedQuest(title="Missão via Pydantic")
    quests, created = ql.register_proposed_quests([], [p], turn=1)
    assert len(created) == 1
    assert created[0]["title"] == "Missão via Pydantic"


def test_register_nao_muta_lista_original():
    original = [{"id": "q1", "title": "Existente", "status": "active"}]
    frozen = copy.deepcopy(original)
    ql.register_proposed_quests(original, [{"title": "Nova missão totalmente distinta"}], turn=1)
    assert original == frozen


def test_complete_quest_marca_completed():
    quests = [{"id": "q1", "title": "X", "status": "active"}]
    out = ql.complete_quest(quests, "q1", turn=9)
    assert out[0]["status"] == "completed"
    assert out[0]["resolved_turn"] == 9
    assert quests[0]["status"] == "active"  # original intocado


def test_complete_quest_id_invalido_sem_mudanca():
    quests = [{"id": "q1", "title": "X", "status": "active"}]
    out = ql.complete_quest(quests, "id_que_nao_existe", turn=9)
    assert out == quests


def test_complete_quest_ja_resolvida_sem_mudanca():
    quests = [{"id": "q1", "title": "X", "status": "completed", "resolved_turn": 3}]
    out = ql.complete_quest(quests, "q1", turn=9)
    assert out[0]["resolved_turn"] == 3  # não reabre/re-resolve


def test_fail_orphan():
    quests = [{"id": "q1", "title": "Vingar o irmão", "status": "active",
              "origin_entity_id": NPC_VALERIUS}]
    new_quests, events = ql.fail_orphan_quests(quests, NPC_VALERIUS, turn=7)
    assert new_quests[0]["status"] == "failed"
    assert new_quests[0]["resolved_turn"] == 7
    assert len(events) == 1
    ev = events[0]
    assert ev["type"] == "quest_failed"
    assert ev["source"] == "system"
    assert ev["payload"]["quest_id"] == "q1"
    assert ev["payload"]["quest_title"] == "Vingar o irmão"


def test_fail_orphan_ignora_quest_sem_origin():
    quests = [{"id": "q1", "title": "X", "status": "active", "origin_entity_id": ""}]
    new_quests, events = ql.fail_orphan_quests(quests, "", turn=7)
    assert new_quests == quests
    assert events == []


def test_fail_orphan_ignora_ja_resolvida():
    quests = [{"id": "q1", "title": "X", "status": "completed", "origin_entity_id": NPC_VALERIUS}]
    new_quests, events = ql.fail_orphan_quests(quests, NPC_VALERIUS, turn=7)
    assert new_quests[0]["status"] == "completed"  # não regride
    assert events == []


def test_quest_markers():
    quests = [
        {"id": "q1", "status": "active", "location_id": NOVA_ARCADIA},
        {"id": "q2", "status": "active", "location_id": ""},
        {"id": "q3", "status": "completed", "location_id": NOVA_ARCADIA},
    ]
    markers = ql.quest_markers(quests)
    assert markers == [{"quest_id": "q1", "location_id": NOVA_ARCADIA}]


# ---------------------------------------------------------------------------
# Etapa 2 — validador + event_processor (pipeline completo)
# ---------------------------------------------------------------------------

def test_quest_completed_por_id_valida():
    quests = [{"id": "q1", "title": "Recuperar o medalhão", "status": "active"}]
    prop = {"type": "quest_completed", "target_id": "q1", "payload": {"quest_id": "q1"}}
    res = validate_proposal(prop, _state(quests=quests))
    assert res.ok, res.reason


def test_quest_completed_id_invalido_rejeitado():
    prop = {"type": "quest_completed", "target_id": "q_fantasma",
            "payload": {"quest_id": "q_fantasma"}}
    res = validate_proposal(prop, _state(quests=[]))
    assert not res.ok
    assert "q_fantasma" in res.reason


def test_quest_completed_beat_index_continua_regressao():
    prop = {"type": "quest_completed", "target_id": "b0", "payload": {"beat_index": 0}}
    res = validate_proposal(prop, _state())  # sem quest_id no payload
    assert res.ok, res.reason


def test_pipeline_quest_completed_aplica_e_gera_milestone():
    quests = [{"id": "q1", "title": "Recuperar o medalhão", "status": "active",
              "created_turn": 1, "resolved_turn": 0}]
    state = _state(quests=quests, pending_world_events=[
        {"type": "quest_completed", "target_id": "q1", "payload": {"quest_id": "q1"}},
    ])
    out = process_pending_events(state)
    assert out["quests"][0]["status"] == "completed"
    assert out["quests"][0]["resolved_turn"] == 5
    assert out["chronicle"]
    milestone = out["chronicle"][-1]["entries"][-1]["text"]
    assert "Recuperar o medalhão" in milestone
    assert "q1" not in milestone  # não vaza o id cru


def test_pipeline_npc_killed_falha_quest_orfa():
    quests = [{"id": "q1", "title": "Proteger Valerius", "status": "active",
              "origin_entity_id": NPC_VALERIUS, "created_turn": 1, "resolved_turn": 0}]
    state = _state(quests=quests, pending_world_events=[
        {"type": "npc_killed", "target_id": NPC_VALERIUS},
    ])
    out = process_pending_events(state)
    failed = [q for q in out["quests"] if q["id"] == "q1"][0]
    assert failed["status"] == "failed"
    assert failed["resolved_turn"] == 5
    qfailed_events = [e for e in out["event_log"] if e["type"] == "quest_failed"]
    assert len(qfailed_events) == 1
    assert qfailed_events[0]["source"] == "system"
    assert qfailed_events[0]["payload"]["quest_id"] == "q1"
    # milestone da falha entrou na crônica com o título, não o id
    texts = [e["text"] for e in out["chronicle"][-1]["entries"]]
    assert any("Proteger Valerius" in t and "fracassou" in t for t in texts)


# ---------------------------------------------------------------------------
# Etapa 3 — agentes (storyteller + npc_actor)
# ---------------------------------------------------------------------------

class _FakeStoryLLM:
    """Devolve um StoryUpdate com proposed_quests controlado (offline, determinístico)."""

    def __init__(self, quests=None, events=None):
        self._quests = quests or []
        self._events = events or []
        self.received = None

    def with_structured_output(self, model, *_a, **_k):
        self._model = model
        return self

    def with_retry(self, *_a, **_k):
        return self

    def invoke(self, msgs):
        self.received = msgs
        return self._model(narrative="O andarilho pede um favor.", introduced_npcs=[],
                           proposed_events=self._events, proposed_quests=self._quests)


def _story_state(quests=None):
    from langchain_core.messages import HumanMessage
    return {
        "game_id": "pytest33", "narrative_summary": "", "archivist_last_run": 0,
        "messages": [HumanMessage(content="converso com o andarilho")],
        "npcs": {}, "factions": [], "faction_intel": {}, "quests": quests or [],
        "player": {"name": "T", "class_name": "Guerreiro"},
        "campaign_plan": {},
        "world": {"current_location": "nova_arcadia", "turn_count": 5,
                  "time_of_day": "Dia", "weather": "Neutro", "danger_level": 1, "quest_plan": []},
    }


def test_storyteller_registra_proposed_quests(monkeypatch):
    import agents.storyteller as stt
    quest = {"title": "Recuperar o medalhão", "origin_name": "Andarilho",
             "location_id": "local_inventado"}
    fake = _FakeStoryLLM(quests=[quest])
    monkeypatch.setattr(stt, "get_llm", lambda *a, **k: fake)
    out = stt.storyteller_node(_story_state())
    assert "quests" in out
    assert out["quests"][0]["title"] == "Recuperar o medalhão"
    assert out["quests"][0]["location_id"] == ""  # id inválido zerado
    assert out["archive_due"] is True


def test_storyteller_sem_proposta_nao_toca_quests(monkeypatch):
    import agents.storyteller as stt
    fake = _FakeStoryLLM(quests=[])
    monkeypatch.setattr(stt, "get_llm", lambda *a, **k: fake)
    out = stt.storyteller_node(_story_state())
    assert "quests" not in out


def test_prompt_lista_quests_ativas(monkeypatch):
    import agents.storyteller as stt
    existing = [{"id": "q1", "title": "Vingar o irmão", "origin_name": "Grum", "status": "active"}]
    fake = _FakeStoryLLM()
    monkeypatch.setattr(stt, "get_llm", lambda *a, **k: fake)
    stt.storyteller_node(_story_state(quests=existing))
    sys_content = str(fake.received[0].content)
    assert "Vingar o irmão" in sys_content
    assert "q1" in sys_content


def test_storyteller_fallback_nao_quebra_quests(monkeypatch):
    import agents.storyteller as stt
    from llm_setup import FallbackLLM
    monkeypatch.setattr(stt, "get_llm", lambda *a, **k: FallbackLLM("quota"))
    out = stt.storyteller_node(_story_state())
    assert "messages" in out
    assert "quests" not in out


class _FakeNpcLLM:
    def __init__(self, quests=None):
        self._quests = quests or []

    def with_structured_output(self, model, *_a, **_k):
        self._model = model
        return self

    def invoke(self, _msgs):
        return self._model(dialogue="Preciso da sua ajuda.", action_description="encara você",
                           memory_update="Pediu ajuda ao herói.", relationship_change=1,
                           proposed_quests=self._quests)


def _npc_state(quests=None):
    from langchain_core.messages import HumanMessage
    return {
        "game_id": "pytest33", "active_npc_name": "Grum",
        "npcs": {"Grum": {"name": "Grum", "role": "guarda", "location": "nova_arcadia",
                          "relationship": 5, "memory": []}},
        "factions": [], "faction_intel": {}, "quests": quests or [],
        "messages": [HumanMessage(content="preciso da sua ajuda?")],
        "world": {"turn_count": 5, "current_location": "nova_arcadia"},
    }


def test_npc_propoe_quest_origem_resolvida_em_python(monkeypatch):
    import agents.npc as npc_mod
    quest = {"title": "Entregar o recado", "origin_name": "outra pessoa qualquer",
             "origin_entity_id": "id_que_o_llm_inventou"}
    fake = _FakeNpcLLM(quests=[quest])
    monkeypatch.setattr(npc_mod, "get_llm", lambda *a, **k: fake)
    out = npc_mod.npc_actor_node(_npc_state())
    assert "quests" in out
    created = out["quests"][0]
    assert created["title"] == "Entregar o recado"
    assert created["origin_name"] == "Grum"  # sobrescrito pelo código, não pelo LLM
    assert created["origin_entity_id"] == "npc_grum"  # id do LLM ignorado; match real usado


def test_npc_sem_proposta_nao_toca_quests(monkeypatch):
    import agents.npc as npc_mod
    fake = _FakeNpcLLM(quests=[])
    monkeypatch.setattr(npc_mod, "get_llm", lambda *a, **k: fake)
    out = npc_mod.npc_actor_node(_npc_state())
    assert "quests" not in out


def test_npc_origem_canonica_valerius():
    import agents.npc as npc_mod
    assert npc_mod._canonical_npc_id("Lorde Protetor Valerius") == "npc_valerius"
    assert npc_mod._canonical_npc_id("Ninguém Existe Com Esse Nome") == ""


# ---------------------------------------------------------------------------
# Etapa 4 — API + persistência
# ---------------------------------------------------------------------------

def test_quest_block_main_side_markers():
    import api
    plan = {"beats": [{"description": "Encontre o mapa", "status": "active"}],
            "current_step": 0, "climax": "O confronto final", "arc_title": "Arco Teste"}
    quests = [
        {"id": "q1", "title": "Ativa", "status": "active", "location_id": NOVA_ARCADIA,
         "resolved_turn": 0},
        {"id": "q2", "title": "Concluída", "status": "completed", "resolved_turn": 3},
    ]
    block = api._quest_block(plan, quests)
    assert block["main"]["objective"] == "Encontre o mapa"
    assert block["main"]["arc_title"] == "Arco Teste"
    assert [q["id"] for q in block["side"]] == ["q1", "q2"]
    assert block["markers"] == [{"quest_id": "q1", "location_id": NOVA_ARCADIA}]


def test_quest_block_side_resolvidas_limitadas_a_5():
    import api
    quests = [{"id": f"q{i}", "title": f"T{i}", "status": "completed", "resolved_turn": i}
              for i in range(7)]
    block = api._quest_block({}, quests)
    assert len(block["side"]) == 5
    assert block["side"][0]["id"] == "q6"  # mais recente primeiro


def test_save_antigo_sem_quests_carrega_vazio(tmp_path, monkeypatch):
    import json
    import persistence
    monkeypatch.setattr(persistence, "SAVES_DIR", str(tmp_path))
    old_save = {
        "game_id": "velho", "player": {"inventory": []}, "world": {},
        "messages": _serialize_msgs_stub(),
    }
    with open(tmp_path / "velho.json", "w", encoding="utf-8") as f:
        json.dump(old_save, f)
    state = persistence.load_game_state(str(tmp_path / "velho.json"))
    assert state["quests"] == []


def _serialize_msgs_stub():
    return [{"type": "ai", "content": "Bem-vindo."}]
