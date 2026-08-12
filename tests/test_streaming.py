"""Suíte da spec streaming-turno-sse — fases do grafo via SSE + telemetria de
LLM em produção. Offline/MockLLM (conftest força RPG_FORCE_MOCK=1)."""
from __future__ import annotations

import copy
import json
import random
import uuid

import pytest

import persistence


# ---------------------------------------------------------------------------
# Etapa 1 — caracterização do LangGraph (app.stream)
# ---------------------------------------------------------------------------

def _initial_state(seed: int) -> dict:
    from playtest.runner import _build_initial_state
    random.seed(seed)
    return _build_initial_state("explorador", seed)


def test_graph_stream_emite_updates_por_no(tmp_path, monkeypatch):
    monkeypatch.setattr(persistence, "SAVES_DIR", str(tmp_path))
    from main import app as game_graph
    state = _initial_state(1)
    nodes, final = [], None
    for mode, data in game_graph.stream(state, stream_mode=["updates", "values"]):
        if mode == "updates":
            nodes.extend(data.keys())
        else:
            final = data
    assert nodes[0] == "campaign_manager"
    assert "dm_router" in nodes
    assert nodes[-1] == "archivist"
    # entre o router e o archivist roda exatamente a rota escolhida
    assert final is not None and final.get("world")


def test_estado_final_do_stream_igual_ao_invoke(tmp_path, monkeypatch):
    monkeypatch.setattr(persistence, "SAVES_DIR", str(tmp_path))
    from main import app as game_graph
    base = _initial_state(7)
    s_invoke, s_stream = copy.deepcopy(base), copy.deepcopy(base)

    random.seed(123)
    inv = game_graph.invoke(s_invoke)

    random.seed(123)
    final = None
    for mode, data in game_graph.stream(s_stream, stream_mode=["updates", "values"]):
        if mode == "values":
            final = data
    assert final is not None
    assert final["world"]["turn_count"] == inv["world"]["turn_count"]
    assert final["player"] == inv["player"]
    assert final["messages"][-1].content == inv["messages"][-1].content


# ---------------------------------------------------------------------------
# Etapas 2/3 — endpoint SSE (TestClient sobre MockLLM)
# ---------------------------------------------------------------------------

@pytest.fixture()
def client(monkeypatch):
    import api
    monkeypatch.setenv("RPG_RATE_LIMIT", "0")
    api._rate_hits.clear()
    from fastapi.testclient import TestClient
    return TestClient(api.app)


def _new_game(client) -> str:
    r = client.post("/game/new", json={
        "name": "Streamer", "race": "Humano",
        "class_name": "Sangromante", "region": "Nova Arcádia",
        "level": 1, "backstory": ""})
    assert r.status_code == 200, r.text
    return r.json()["game_id"]


def _read_sse(resp) -> list:
    """Parseia o corpo SSE em [(event, data_dict)] na ordem de chegada."""
    events = []
    event_name = None
    for line in resp.iter_lines():
        line = line.decode() if isinstance(line, bytes) else line
        if line.startswith("event: "):
            event_name = line[len("event: "):].strip()
        elif line.startswith("data: ") and event_name:
            events.append((event_name, json.loads(line[len("data: "):])))
            event_name = None
    return events


def test_stream_ordem_de_eventos(client):
    gid = _new_game(client)
    with client.stream("POST", "/game/action/stream",
                       json={"input_text": "olho ao redor", "game_id": gid}) as r:
        assert r.status_code == 200
        assert r.headers["content-type"].startswith("text/event-stream")
        events = _read_sse(r)
    names = [e for e, _ in events]
    assert names[0] == "accepted"
    assert events[0][1]["game_id"] == gid
    assert "phase" in names and "route" in names
    assert names.index("phase") < names.index("route") < names.index("visual")
    assert names.index("visual") < names.index("narrative") < names.index("state")
    visual = next(d for e, d in events if e == "visual")
    state = next(d for e, d in events if e == "state")
    assert visual == state["visual"]
    # narrativa chega em chunks e fecha com done=True antes do state
    narr = [d for e, d in events if e == "narrative"]
    assert narr and narr[-1]["done"] is True
    assert names[-1] == "state"
    # fases na ordem real do grafo
    phases = [d["node"] for e, d in events if e == "phase"]
    assert phases[0] == "campaign_manager" and phases[-1] == "archivist"


def test_stream_state_igual_ao_post(client):
    gid = _new_game(client)
    with client.stream("POST", "/game/action/stream",
                       json={"input_text": "sigo em frente", "game_id": gid}) as r:
        events = _read_sse(r)
    state_evt = next(d for e, d in events if e == "state")
    visual_evt = next(d for e, d in events if e == "visual")
    assert visual_evt == state_evt["visual"]
    # o save persistiu o MESMO estado que o GameResponse do stream reporta
    r2 = client.get("/game/state", params={"game_id": gid})
    assert r2.status_code == 200
    assert r2.json() == state_evt
    # narrativa reconstituída dos chunks == message final
    narr = "".join(d["chunk"] for e, d in events if e == "narrative")
    assert narr == state_evt["message"]
    # o POST clássico continua vivo (fallback)
    r3 = client.post("/game/action", json={"input_text": "descanso", "game_id": gid})
    assert r3.status_code == 200


def test_stream_memorial_devolve_error(client, tmp_path, monkeypatch):
    gid = _new_game(client)
    state = persistence.load_game_state(persistence.save_path(gid))
    state["game_over"] = True
    persistence.save_game_state(state)
    with client.stream("POST", "/game/action/stream",
                       json={"input_text": "ataco", "game_id": gid}) as r:
        events = _read_sse(r)
    assert events[0][0] == "accepted"
    assert events[-1][0] == "error"
    assert events[-1][1]["code"] == 409


def test_stream_respeita_rate_limit(monkeypatch):
    import api
    from fastapi.testclient import TestClient
    monkeypatch.setenv("RPG_RATE_LIMIT", "2")
    api._rate_hits.clear()
    client = TestClient(api.app)
    gid = str(uuid.uuid4())  # save não existe: 404, mas conta na janela
    codes = []
    for _ in range(3):
        r = client.post("/game/action/stream",
                        json={"input_text": "x", "game_id": gid})
        codes.append(r.status_code)
    api._rate_hits.clear()
    assert codes[-1] == 429


def test_stream_erro_no_meio_emite_error_sanitizado(client, monkeypatch):
    import api
    gid = _new_game(client)

    class _Boom:
        def stream(self, *a, **k):
            raise RuntimeError("segredo interno: stacktrace com path C:\\x")

        def invoke(self, *a, **k):
            raise RuntimeError("nunca chega aqui")

    monkeypatch.setattr(api, "game_graph", _Boom())
    with client.stream("POST", "/game/action/stream",
                       json={"input_text": "x", "game_id": gid}) as r:
        events = _read_sse(r)
    assert events[-1][0] == "error"
    detail = events[-1][1]["detail"]
    assert "segredo interno" not in detail and "stacktrace" not in detail


# ---------------------------------------------------------------------------
# Etapa 4 — telemetria de LLM em produção (R5)
# ---------------------------------------------------------------------------

def test_log_de_turno_tem_custo_e_providers(client, monkeypatch):
    import api
    logs = []
    monkeypatch.setattr(api._turn_logger, "info", lambda msg: logs.append(msg))
    gid = _new_game(client)
    r = client.post("/game/action", json={"input_text": "sigo", "game_id": gid})
    assert r.status_code == 200
    rec = json.loads(logs[-1])
    for campo in ("llm_calls", "llm_providers", "fell_back", "cost_usd_est"):
        assert campo in rec, campo
    # MockLLM não dispara o hook do roteamento → custo 0
    assert rec["llm_calls"] == 0 and rec["cost_usd_est"] == 0
    # nada de telemetria no GameResponse (dev-only)
    body = r.json()
    assert "llm_calls" not in body and "cost_usd_est" not in body


def test_hook_nao_vaza_entre_turnos():
    import api
    token = api._llm_turn_events.set([])
    api._telemetry_hook("groq", "llama-3.3-70b-versatile", "fast", 12, False)
    assert len(api._llm_turn_events.get()) == 1
    api._llm_turn_events.reset(token)
    # fora de turno: hook é no-op silencioso (acumulador None)
    assert api._llm_turn_events.get() is None
    api._telemetry_hook("groq", "m", "fast", 1, True)  # não pode crashar
    assert api._llm_turn_events.get() is None
