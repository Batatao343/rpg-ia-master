"""
Suíte da Fase 3.1 — Diário + Crônica melhorada (capítulos por arco).
Spec: specs/fase-3.1-diario-cronica.md. 100% offline.

Usa ids canônicos reais de data/graph/entities.json:
  npc vivo canônico: npc_valerius (nome "Lorde Protetor Valerius", controla nova_arcadia)
  location:          nova_arcadia
  facções:           legiao_ferro, mao_sombria
"""

import copy
import json
import os
import uuid

import pytest

import persistence
from persistence import load_game_state, save_game_state
from services import chronicle as chron
from services import graph_resolver as gr


@pytest.fixture(autouse=True)
def _fresh_graph_cache():
    gr.clear_cache()
    yield
    gr.clear_cache()


# ---------------------------------------------------------------------------
# Etapa 1 — services/chronicle.py (puro)
# ---------------------------------------------------------------------------

def test_render_milestone_npc_killed():
    ev = {"event_id": "e1", "turn": 5, "type": "npc_killed",
          "actor_id": "player", "target_id": "npc_valerius"}
    txt = chron.render_milestone(ev, {})
    assert "Lorde Protetor Valerius" in txt
    assert "npc_valerius" not in txt


def test_render_milestone_tipo_ignorado():
    ev = {"event_id": "e2", "turn": 5, "type": "faction_relation_changed",
          "target_id": "legiao_ferro", "payload": {"relation": "hostile_to"}}
    assert chron.render_milestone(ev, {}) == ""


def test_render_milestone_secret():
    proj = {"revealed_facts": {"e9": {"entity_id": "npc_velha_magda",
                                      "fact": "Magda lidera a Mão Sombria"}}}
    ev = {"event_id": "e9", "turn": 7, "type": "secret_revealed",
          "target_id": "npc_velha_magda"}
    txt = chron.render_milestone(ev, proj)
    assert "Magda lidera a Mão Sombria" in txt


def test_append_cria_capitulo_default():
    out = chron.append_entry([], text="algo aconteceu", turn=3, kind="prose")
    assert len(out) == 1
    assert out[0]["title"] == "Crônica da jornada"
    assert out[0]["started_turn"] == 0
    assert out[0]["entries"] == [{"text": "algo aconteceu", "turn": 3, "kind": "prose"}]


def test_open_chapter_mesmo_titulo_noop():
    c1 = chron.open_chapter([], title="A Sombra do Norte", turn=2, location="nova_arcadia")
    c2 = chron.open_chapter(c1, title="A Sombra do Norte", turn=9, location="outro_lugar")
    assert c2 is c1  # mesmo título → devolve a lista original, sem capítulo novo
    assert len(c2) == 1


def test_append_e_puro():
    original = [{"title": "T", "started_turn": 0, "location": "", "entries": []}]
    snapshot = copy.deepcopy(original)
    out = chron.append_entry(original, text="x", turn=1, kind="milestone", event_id="e1")
    assert original == snapshot          # entrada não vazou para a lista original
    assert out[0]["entries"][0]["event_id"] == "e1"


# ---------------------------------------------------------------------------
# Etapa 2 — schema + backfill de saves antigos
# ---------------------------------------------------------------------------

def test_save_antigo_chronicle_flat_fica_arquivado(tmp_path, monkeypatch):
    monkeypatch.setattr(persistence, "SAVES_DIR", str(tmp_path))
    save_antigo = {
        "game_id": "legacy",
        "chronicle": ["O herói chegou à cidade.", "Um dragão foi avistado."],
        "player": {"name": "Velho"},
        "world": {},
        "message_history": [],
    }
    file_path = tmp_path / "legacy.json"
    file_path.write_text(json.dumps(save_antigo), encoding="utf-8")

    state = load_game_state(str(file_path))

    assert state is not None
    assert state["archived"] is True
    assert state["chronicle"] == save_antigo["chronicle"]


def test_save_novo_roundtrip(tmp_path, monkeypatch):
    """Capítulos sobrevivem a save → load intactos."""
    monkeypatch.setattr(persistence, "SAVES_DIR", str(tmp_path))
    game_id = f"t31-{uuid.uuid4().hex[:8]}"
    capitulos = [
        {"title": "O início da jornada — Nova Arcádia", "started_turn": 0,
         "location": "nova_arcadia",
         "entries": [{"text": "milestone!", "turn": 2, "kind": "milestone", "event_id": "e1"}]},
        {"title": "A Sombra do Norte", "started_turn": 5, "location": "picos_gelados",
         "entries": [{"text": "prosa do menestrel", "turn": 6, "kind": "prose"}]},
    ]
    state = {
        "game_id": game_id,
        "narrative_summary": "resumo",
        "player": {"name": "Testa", "hp": 10},
        "world": {"current_location": "Nova Arcádia", "turn_count": 6},
        "messages": [],
        "chronicle": capitulos,
    }

    assert save_game_state(state) is True
    loaded = load_game_state(os.path.join(str(tmp_path), f"{game_id}.json"))

    assert loaded["chronicle"] == capitulos


# ---------------------------------------------------------------------------
# Etapa 3 — milestones determinísticos no event_processor
# ---------------------------------------------------------------------------

from services.event_processor import process_pending_events  # noqa: E402


def _state_events(**over) -> dict:
    base = {
        "world": {"turn_count": 7, "current_location": "nova_arcadia"},
        "world_projection": {},
        "event_log": [],
        "factions": [],
        "chronicle": [],
        "pending_world_events": [],
    }
    base.update(over)
    return base


def test_evento_aplicado_gera_milestone():
    st = _state_events(pending_world_events=[
        {"type": "npc_killed", "actor_id": "player", "target_id": "npc_grum",
         "payload": {}, "source": "combat"},
    ])
    out = process_pending_events(st)
    assert "chronicle" in out
    entries = out["chronicle"][-1]["entries"]
    milestones = [e for e in entries if e["kind"] == "milestone"]
    assert len(milestones) == 1
    assert milestones[0]["event_id"] == out["event_log"][0]["event_id"]
    assert "Grum" in milestones[0]["text"]
    assert milestones[0]["turn"] == 7


def test_evento_rejeitado_sem_milestone():
    st = _state_events(pending_world_events=[
        {"type": "npc_killed", "target_id": "npc_fantasma", "payload": {}},
    ])
    out = process_pending_events(st)
    assert "chronicle" not in out  # nada aplicado → crônica intocada


def test_cascata_gera_milestone():
    """Morte de líder (2.7): milestone da morte E do location_control_changed derivado."""
    st = _state_events(pending_world_events=[
        {"type": "npc_killed", "actor_id": "player", "target_id": "npc_valerius",
         "payload": {}, "source": "combat"},
    ])
    out = process_pending_events(st)
    entries = out["chronicle"][-1]["entries"]
    texts = [e["text"] for e in entries]
    assert any("Lorde Protetor Valerius" in t for t in texts)
    assert any("controle" in t for t in texts), "cascata não virou milestone"
    # todo milestone é auditável (aponta para um evento real do log)
    log_ids = {e["event_id"] for e in out["event_log"]}
    assert all(e["event_id"] in log_ids for e in entries)


# ---------------------------------------------------------------------------
# Etapa 4 — archivist (prosa) + campaign_manager (arc_title)
# ---------------------------------------------------------------------------

from agents.archivist import archive_node  # noqa: E402
from agents.campaign_manager import campaign_manager_node  # noqa: E402


def _arch_state(**over) -> dict:
    base = {
        "game_id": "t31",
        "narrative_summary": "",
        "archivist_last_run": 0,
        "archive_due": True,          # força o LLM do arquivista a rodar
        "world": {"turn_count": 4, "current_location": "nova_arcadia"},
        "messages": [],
        "chronicle": [],
        "world_projection": {},
        "event_log": [],
        "pending_world_events": [],
        "factions": [],
    }
    base.update(over)
    return base


def test_archivist_prose_no_capitulo(monkeypatch):
    monkeypatch.setattr("mock_llm.random.random", lambda: 0.0)  # força chronicle_entry
    out = archive_node(_arch_state())
    assert "chronicle" in out
    prose = [e for e in out["chronicle"][-1]["entries"] if e["kind"] == "prose"]
    assert len(prose) == 1
    assert prose[0]["turn"] == 4


def test_archivist_merge_prose_e_milestone(monkeypatch):
    """Turno com evento aplicado + prosa do menestrel → crônica final contém AMBOS."""
    monkeypatch.setattr("mock_llm.random.random", lambda: 0.0)
    st = _arch_state(pending_world_events=[
        {"type": "npc_killed", "actor_id": "player", "target_id": "npc_grum",
         "payload": {}, "source": "combat"},
    ])
    out = archive_node(st)
    kinds = [e["kind"] for e in out["chronicle"][-1]["entries"]]
    assert kinds == ["milestone", "prose"]  # evento consolidado primeiro, prosa por cima


def _camp_state(**over) -> dict:
    base = {
        "world": {"turn_count": 3, "current_location": "nova_arcadia"},
        "messages": [],
        "needs_replan": True,
        "campaign_plan": {"location": "nova_arcadia", "beats": [], "climax": "",
                          "current_step": 0, "last_planned_turn": 0,
                          "arc_title": "Arco Antigo"},
        "chronicle": [{"title": "Arco Antigo", "started_turn": 0,
                       "location": "nova_arcadia", "entries": []}],
        "world_projection": {},
        "event_log": [],
        "pending_world_events": [],
        "narrative_summary": "",
        "npcs": {},
    }
    base.update(over)
    return base


def test_replan_muda_arco_abre_capitulo():
    # MockLLM devolve arc_title "A Verdade Enterrada" ≠ "Arco Antigo" → capítulo novo
    out = campaign_manager_node(_camp_state())
    assert out["campaign_plan"]["arc_title"] == "A Verdade Enterrada"
    assert len(out["chronicle"]) == 2
    novo = out["chronicle"][-1]
    assert novo["title"] == "A Verdade Enterrada"
    assert novo["started_turn"] == 4  # turn_count incrementado pelo nó
    assert novo["entries"] == []


def test_replan_mesmo_arco_nao_abre():
    st = _camp_state()
    st["campaign_plan"]["arc_title"] = "A Verdade Enterrada"  # igual ao do MockLLM
    st["chronicle"][0]["title"] = "A Verdade Enterrada"
    out = campaign_manager_node(st)
    assert "chronicle" not in out  # mesmo arco → crônica intocada


# ---------------------------------------------------------------------------
# Etapa 5 — API (capítulo inicial + serialização)
# ---------------------------------------------------------------------------

def test_format_response_capitulos():
    from langchain_core.messages import AIMessage

    import api
    state = {
        "game_id": "t31-api",
        "messages": [AIMessage(content="O vento uiva.")],
        "player": {"name": "Testa", "inventory": []},
        "world": {"current_location": "Nova Arcádia", "turn_count": 2},
        "chronicle": [
            {"title": "O início da jornada — Nova Arcádia", "started_turn": 0,
             "location": "Nova Arcádia",
             "entries": [{"text": "Grum tombou.", "turn": 2, "kind": "milestone",
                          "event_id": "e1"},
                         {"text": "   ", "turn": 2, "kind": "prose"}]},  # vazia → filtrada
        ],
    }
    resp = api.format_response(state)
    assert len(resp.chronicle) == 1
    cap = resp.chronicle[0]
    assert cap["title"].startswith("O início da jornada")
    assert len(cap["entries"]) == 1  # entrada em branco foi filtrada
    assert cap["entries"][0]["kind"] == "milestone"


def test_game_new_capitulo_inicial(tmp_path, monkeypatch):
    from fastapi.testclient import TestClient

    import api
    import persistence
    monkeypatch.setattr(persistence, "SAVES_DIR", str(tmp_path))

    client = TestClient(api.app)
    resp = client.post("/game/new", json={
        "name": "Testa", "class_name": "Sangromante", "race": "Humano",
        "region": "Nova Arcádia", "backstory": "Um teste.", "level": 1,
    })
    assert resp.status_code == 200
    chron = resp.json()["chronicle"]
    assert len(chron) >= 1
    assert "Nova Arcádia" in chron[0]["title"]
    assert chron[0]["started_turn"] == 0
