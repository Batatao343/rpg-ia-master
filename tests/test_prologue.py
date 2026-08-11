# -*- coding: utf-8 -*-
"""Testes da spec inicio-personalizado — prólogo + seed de arco pessoal.

Suíte offline (RPG_FORCE_MOCK=1 via conftest): MockLLM devolve a fixture
StartScenario; FallbackLLM cai no template determinístico (guard R3).
"""

import pytest

from llm_setup import FallbackLLM
from services.prologue import (
    ATTITUDES,
    REL_MAP,
    SeedNPC,
    StartScenario,
    StartScenarioIn,
    _normalize,
    build_start_scenario,
    fallback_scenario,
    scenario_to_state_seed,
)

CHAR_INPUT = {
    "name": "Kaelen",
    "race": "Humano",
    "class_name": "Sangromante",
    "region": "Nova Arcádia",
    "level": 1,
    "backstory": "renegado de uma família nobre que busca recuperar seu nome",
}


def test_build_scenario_mock():
    scenario, mock = build_start_scenario(CHAR_INPUT)
    assert isinstance(scenario, StartScenario)
    assert mock is True
    assert 3 <= len(scenario.beats) <= 5
    assert scenario.prologue
    assert scenario.opening_scene_brief
    assert scenario.arc_title
    # fixture em pt-BR com 1 NPC aliado (exercita R8 nos testes de seed)
    assert scenario.seed_npcs and scenario.seed_npcs[0].attitude in ATTITUDES


def test_fallback_scenario_deterministic(monkeypatch):
    import services.prologue as prologue

    monkeypatch.setattr(prologue, "get_llm",
                        lambda *a, **k: FallbackLLM("sem provider"))
    scenario, mock = prologue.build_start_scenario(CHAR_INPUT)
    assert isinstance(scenario, StartScenario)
    assert "Kaelen" in scenario.prologue
    assert "Nova Arcádia" in scenario.prologue
    assert scenario.seed_npcs == []
    assert len(scenario.beats) >= 3
    assert mock is False


def test_fallback_scenario_direct():
    s = fallback_scenario(CHAR_INPUT)
    assert "Kaelen" in s.prologue and "Nova Arcádia" in s.opening_scene_brief
    assert s.arc_title  # default_chapter_title da região
    assert s.seed_npcs == []


def test_scenario_to_state_seed():
    scenario, _ = build_start_scenario(CHAR_INPUT)
    char = dict(CHAR_INPUT, game_id="game-teste")
    seed = scenario_to_state_seed(scenario, char, start_loc_id="nova_arcadia")

    plan = seed["campaign_plan"]
    assert plan["arc_title"] == scenario.arc_title
    assert plan["current_step"] == 0
    assert plan["last_planned_turn"] == 0
    assert plan["location"] == "Nova Arcádia"
    assert plan["beats"] and all(b["status"] == "pending" for b in plan["beats"])
    assert all(len(b["description"]) <= 300 for b in plan["beats"])

    assert seed["npcs"], "fixture do mock tem 1 seed NPC"
    npc = next(iter(seed["npcs"].values()))
    assert npc["in_scene"] is True
    assert npc["known_by_player"] is True
    assert npc["home_location_id"] == "nova_arcadia"
    att = scenario.seed_npcs[0].attitude
    assert npc["initial_relationship"] == REL_MAP[att]
    assert npc["combat_stats"]["hp"] > 0

    assert scenario.opening_scene_brief in seed["opening_message"]
    assert seed["chronicle_title"] == scenario.arc_title
    assert scenario.prologue[:100] in seed["summary_extra"]


def test_seed_beat_truncated_not_rejected():
    """Beat individual > 300 chars é truncado no seed (não rejeitado)."""
    s = fallback_scenario(CHAR_INPUT)
    data = s.model_dump()
    data["beats"] = ["x" * 500, "beat dois", "beat três"]
    s2 = StartScenario(**data)
    seed = scenario_to_state_seed(s2, CHAR_INPUT, start_loc_id="loc")
    assert len(seed["campaign_plan"]["beats"][0]["description"]) == 300


def test_normalize_truncates_llm_overflow():
    """Achado do smoke real: LLMs escrevem além dos tetos (climax > 300,
    attitude livre) — `_normalize` trunca para o cenário passar na borda
    estrita do /game/new (StartScenarioIn)."""
    bruto = StartScenario(
        prologue="p" * 2500, opening_scene_brief="b" * 1500,
        arc_title="a" * 120, beats=["x" * 400] * 6, climax="c" * 700,
        seed_npcs=[SeedNPC(name="N" * 80, role="r" * 100,
                           attitude="cauteloso e ambicioso", persona="q" * 500)],
    )
    out = _normalize(bruto, CHAR_INPUT)
    StartScenarioIn(**out.model_dump())  # não levanta: dentro dos tetos
    assert len(out.climax) == 300
    assert len(out.beats) == 5
    assert out.seed_npcs[0].attitude == "neutro"


# ---------------------------------------------------------------------------
# Etapa 2 — endpoint POST /game/prologue
# ---------------------------------------------------------------------------

_NEW_PAYLOAD = {
    "name": "Kaelen", "class_name": "Sangromante", "race": "Humano",
    "region": "Nova Arcádia", "backstory": "renegado de família nobre", "level": 1,
}


def _client():
    from fastapi.testclient import TestClient

    import api
    return TestClient(api.app), api


def test_api_prologue_returns_scenario():
    client, _ = _client()
    resp = client.post("/game/prologue", json=_NEW_PAYLOAD)
    assert resp.status_code == 200
    body = resp.json()
    assert body["mock"] is True
    sc = body["scenario"]
    assert set(sc.keys()) >= {"prologue", "opening_scene_brief", "arc_title",
                              "beats", "climax", "seed_npcs"}
    assert 3 <= len(sc["beats"]) <= 5


def test_api_prologue_rate_limited(monkeypatch):
    client, api = _client()
    monkeypatch.setenv("RPG_RATE_LIMIT", "2")
    api._rate_hits.clear()
    codes = [client.post("/game/prologue", json=_NEW_PAYLOAD).status_code
             for _ in range(4)]
    assert 429 in codes
    api._rate_hits.clear()


# ---------------------------------------------------------------------------
# Etapa 3 — seed no /game/new
# ---------------------------------------------------------------------------

def _scenario_dict() -> dict:
    scenario, _ = build_start_scenario(CHAR_INPUT)
    return scenario.model_dump()


def _new_with_scenario(tmp_path, monkeypatch, scenario: dict | None):
    import persistence
    monkeypatch.setattr(persistence, "SAVES_DIR", str(tmp_path))
    client, _ = _client()
    payload = dict(_NEW_PAYLOAD)
    if scenario is not None:
        payload["scenario"] = scenario
    return client.post("/game/new", json=payload)


def test_new_game_with_scenario_seeds_plan(tmp_path, monkeypatch):
    sc = _scenario_dict()
    resp = _new_with_scenario(tmp_path, monkeypatch, sc)
    assert resp.status_code == 200
    body = resp.json()
    assert body["quest"]["main"]["arc_title"] == sc["arc_title"]
    assert body["chronicle"][0]["title"] == sc["arc_title"]
    beats = body["quest"]["main"]["beats"]
    assert [b["description"] for b in beats] == sc["beats"]


def test_seeded_plan_survives_first_invoke(tmp_path, monkeypatch):
    """R7 — campaign_manager não replaneja no turno da criação."""
    import persistence

    sc = _scenario_dict()
    resp = _new_with_scenario(tmp_path, monkeypatch, sc)
    assert resp.status_code == 200
    state = persistence.load_game_state(
        persistence.save_path(resp.json()["game_id"]))
    plan = state["campaign_plan"]
    assert plan["arc_title"] == sc["arc_title"]
    assert plan["last_planned_turn"] == 0  # não foi refeito pelo manager
    # e o capítulo 1 continua sendo o arco pessoal (nenhum capítulo novo)
    assert state["chronicle"][0]["title"] == sc["arc_title"]


def test_new_game_with_scenario_seeds_npcs(tmp_path, monkeypatch):
    """R8 — NPC semeado é alvo válido da rota NPC no turno 1."""
    import persistence
    from agents.npc import npc_actor_node

    sc = _scenario_dict()
    npc_name = sc["seed_npcs"][0]["name"]
    resp = _new_with_scenario(tmp_path, monkeypatch, sc)
    assert resp.status_code == 200
    state = persistence.load_game_state(
        persistence.save_path(resp.json()["game_id"]))

    npc = state["npcs"][npc_name]
    assert npc["in_scene"] is True
    assert npc["known_by_player"] is True

    state["active_npc_name"] = npc_name
    from langchain_core.messages import HumanMessage
    state["messages"].append(HumanMessage(content=f"Falo com {npc_name}."))
    out = npc_actor_node(state)
    msg = out["messages"][-1].content
    assert "Ninguém responde" not in msg
    assert "não está aqui" not in msg


def test_new_game_without_scenario_unchanged(tmp_path, monkeypatch):
    """R6 — payload sem scenario mantém o fluxo clássico."""
    import persistence

    resp = _new_with_scenario(tmp_path, monkeypatch, None)
    assert resp.status_code == 200
    body = resp.json()
    assert body["chronicle"][0]["title"].startswith("O início da jornada")
    state = persistence.load_game_state(
        persistence.save_path(body["game_id"]))
    # mensagem inicial clássica (não o brief de cena do prólogo)
    texts = [m.get("content", "") for m in _raw_messages(state)]
    assert any("Descreva o cenário ao meu redor" in t for t in texts)
    assert not any("Cena de abertura:" in t for t in texts)


def _raw_messages(state) -> list:
    out = []
    for m in state.get("messages", []):
        content = getattr(m, "content", None)
        out.append({"content": content if content is not None else str(m)})
    return out


def test_scenario_validation_rejects_oversize(tmp_path, monkeypatch):
    """R4 — 6 beats ou 3 npcs → 422 na borda."""
    sc = _scenario_dict()
    seis_beats = dict(sc, beats=["b"] * 6)
    assert _new_with_scenario(tmp_path, monkeypatch, seis_beats).status_code == 422

    npc = {"name": "X", "role": "r", "attitude": "neutro", "persona": "p"}
    tres_npcs = dict(sc, seed_npcs=[npc, npc, npc])
    assert _new_with_scenario(tmp_path, monkeypatch, tres_npcs).status_code == 422

    prologo_gigante = dict(sc, prologue="x" * 3000)
    assert _new_with_scenario(tmp_path, monkeypatch, prologo_gigante).status_code == 422
