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
    assert nodes[0] == "action_guard"
    assert nodes[-1] == "turn_finalizer"
    assert "dm_router" in nodes
    assert "archivist" in nodes
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
    r = client.post(
        "/game/new",
        json={
            "name": "Streamer",
            "race": "Humano",
            "class_name": "Sangromante",
            "region": "Nova Arcádia",
            "level": 1,
            "backstory": "",
        },
    )
    assert r.status_code == 200, r.text
    return r.json()["game_id"]


def _read_sse(resp) -> list:
    """Parseia o corpo SSE em [(event, data_dict)] na ordem de chegada."""
    events = []
    event_name = None
    for line in resp.iter_lines():
        line = line.decode() if isinstance(line, bytes) else line
        if line.startswith("event: "):
            event_name = line[len("event: ") :].strip()
        elif line.startswith("data: ") and event_name:
            events.append((event_name, json.loads(line[len("data: ") :])))
            event_name = None
    return events


def test_stream_ordem_de_eventos(client):
    gid = _new_game(client)
    with client.stream(
        "POST", "/game/action/stream", json={"input_text": "olho ao redor", "game_id": gid}
    ) as r:
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
    # SPEC-318: o plano ja existe (jogo novo) -> o replan sai da frente do router; o no
    # `enrich` roda entre o narrador e o arquivista, DEPOIS da entrega.
    assert phases[0] == "dm_router" and phases[-1] == "archivist"
    assert phases.index("storyteller") < phases.index("enrich") < phases.index("archivist")
    assert names.index("narrative") < len(names) - 1  # entrega antes do fim do turno


def test_stream_state_igual_ao_post(client):
    gid = _new_game(client)
    with client.stream(
        "POST", "/game/action/stream", json={"input_text": "sigo em frente", "game_id": gid}
    ) as r:
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
    with client.stream(
        "POST", "/game/action/stream", json={"input_text": "ataco", "game_id": gid}
    ) as r:
        events = _read_sse(r)
    assert events[0][0] == "accepted"
    assert events[-1][0] == "error"
    assert events[-1][1]["code"] == 409


def test_stream_respeita_rate_limit(monkeypatch):
    from fastapi.testclient import TestClient

    import api

    monkeypatch.setenv("RPG_RATE_LIMIT", "2")
    api._rate_hits.clear()
    client = TestClient(api.app)
    gid = str(uuid.uuid4())  # save não existe: 404, mas conta na janela
    codes = []
    for _ in range(3):
        r = client.post("/game/action/stream", json={"input_text": "x", "game_id": gid})
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
    with client.stream(
        "POST", "/game/action/stream", json={"input_text": "x", "game_id": gid}
    ) as r:
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


# ---------------------------------------------------------------------------
# SPEC-316 — narracao entregue antes do arquivista (RPG_EARLY_NARRATIVE)
# ---------------------------------------------------------------------------


def _stream(client, gid: str, text: str = "olho ao redor", action_id: str | None = None) -> list:
    body = {"input_text": text, "game_id": gid}
    if action_id:
        body["action_id"] = action_id
    with client.stream("POST", "/game/action/stream", json=body) as r:
        assert r.status_code == 200
        return _read_sse(r)


def _names(events: list) -> list[str]:
    return [e for e, _ in events]


def _phase_index(events: list, node: str) -> int:
    return next(i for i, (e, d) in enumerate(events) if e == "phase" and d["node"] == node)


def test_early_narrative_before_archivist_phase(client, monkeypatch):
    monkeypatch.setenv("RPG_EARLY_NARRATIVE", "on")
    gid = _new_game(client)
    events = _stream(client, gid)
    names = _names(events)
    first_narr = names.index("narrative")
    assert first_narr < _phase_index(events, "archivist")
    assert _phase_index(events, "storyteller") < first_narr
    # contrato para o cliente: narrativa -> (fase arquivista) -> visual -> state
    assert names.index("visual") > max(i for i, n in enumerate(names) if n == "narrative")
    assert names[-1] == "state" and names.index("visual") == len(names) - 2
    narr = "".join(d["chunk"] for e, d in events if e == "narrative" and not d.get("replace"))
    final = events[-1][1]["message"]
    replaced = [d for e, d in events if e == "narrative" and d.get("replace")]
    assert (replaced[-1]["chunk"] if replaced else narr) == final
    assert [d["done"] for e, d in events if e == "narrative"][-1] is True


def test_shadow_mode_keeps_order_and_logs(client, monkeypatch):
    import api

    monkeypatch.setenv("RPG_EARLY_NARRATIVE", "shadow")
    logs = []
    real = api._sse_log

    def _spy(event, **kw):
        logs.append((event, kw))
        real(event, **kw)

    monkeypatch.setattr(api, "_sse_log", _spy)
    gid = _new_game(client)
    events = _stream(client, gid)
    names = _names(events)
    assert names.index("visual") < names.index("narrative") < names.index("state")
    assert _phase_index(events, "archivist") < names.index("narrative")
    shadow = [kw for ev, kw in logs if ev == "early_narrative_shadow"]
    assert len(shadow) == 1 and shadow[0]["gain_ms"] >= 0
    assert isinstance(shadow[0]["identical"], bool)
    assert not any(d.get("replace") for e, d in events if e == "narrative")


def test_off_mode_byte_identical_to_head(client, monkeypatch):
    import api

    monkeypatch.setenv("RPG_EARLY_NARRATIVE", "off")
    logs = []
    monkeypatch.setattr(api, "_sse_log", lambda event, **kw: logs.append(event))
    gid = _new_game(client)
    events = _stream(client, gid)
    names = _names(events)
    # ordem legada da SPEC-036: visual -> narrative... -> state, tudo depois do arquivista
    assert names[-1] == "state" and names[-2] == "narrative"
    assert names.index("visual") < names.index("narrative")
    assert _phase_index(events, "archivist") < names.index("visual")
    assert "early_narrative_shadow" not in logs
    assert not any(d.get("replace") for e, d in events if e == "narrative")


def _run_with_mode(client, gid, mode, snapshot, monkeypatch):
    """Restaura o save inicial e roda 1 turno com seed fixo no `mode`."""
    monkeypatch.setenv("RPG_EARLY_NARRATIVE", mode)
    path = persistence.save_path(gid)
    with open(path, "w", encoding="utf-8", newline="") as fh:
        fh.write(snapshot)
    random.seed(99)
    events = _stream(client, gid, action_id="11111111-1111-4111-8111-111111111111")
    with open(path, encoding="utf-8", newline="") as fh:
        return events, fh.read()


def _scrub_timings(save: dict) -> dict:
    """Remove SO `audit_trace[*].timing` (relogios medidos); o resto tem de ser identico."""
    out = dict(save)
    out["audit_trace"] = [
        {k: v for k, v in entry.items() if k != "timing"} if isinstance(entry, dict) else entry
        for entry in save.get("audit_trace") or []
    ]
    return out


def test_final_state_identical_on_vs_off(client, monkeypatch):
    gid = _new_game(client)
    path = persistence.save_path(gid)
    with open(path, encoding="utf-8", newline="") as fh:
        snapshot = fh.read()
    ev_off, save_off = _run_with_mode(client, gid, "off", snapshot, monkeypatch)
    ev_shadow, save_shadow = _run_with_mode(client, gid, "shadow", snapshot, monkeypatch)
    ev_on, save_on = _run_with_mode(client, gid, "on", snapshot, monkeypatch)
    state_off = next(d for e, d in ev_off if e == "state")
    for events in (ev_shadow, ev_on):
        assert next(d for e, d in events if e == "state") == state_off  # GameResponse
    # save identico; so `audit_trace[*].timing` (relogios) muda. Em `on` o timing ganha
    # `ttfmc/ttlt_server_ms` (as marcas agora existem antes de gravar a trilha).
    base = _scrub_timings(json.loads(save_off))
    assert _scrub_timings(json.loads(save_shadow)) == base
    assert _scrub_timings(json.loads(save_on)) == base
    assert _names(ev_on) != _names(ev_off)  # so a ordem dos eventos muda
    assert _names(ev_shadow) == _names(ev_off)


def test_replace_event_when_guard_changes_text(client, monkeypatch):
    import services.turn_delivery as td

    monkeypatch.setenv("RPG_EARLY_NARRATIVE", "on")
    monkeypatch.setattr(td, "early_narrative", lambda *a, **k: "Texto antecipado provisório.")
    gid = _new_game(client)
    events = _stream(client, gid)
    narr = [d for e, d in events if e == "narrative"]
    assert "".join(d["chunk"] for d in narr if not d.get("replace")) == (
        "Texto antecipado provisório."
    )
    replace = [d for d in narr if d.get("replace")]
    assert len(replace) == 1 and replace[0]["done"] is True
    assert replace[0]["chunk"] == events[-1][1]["message"]
    assert _names(events).index("state") > _names(events).index("narrative")


class _EncounterGraph:
    """Proxy do grafo real: o `storyteller` aponta para `combat_agent` e um no de combate
    sintetico narra depois. A execucao real (estado final) segue intacta."""

    def __init__(self, real):
        self._real = real

    def __getattr__(self, name):
        return getattr(self._real, name)

    def stream(self, state, **kw):
        from langchain_core.messages import AIMessage, SystemMessage

        for mode, data in self._real.stream(state, **kw):
            if mode == "updates" and "storyteller" in data:
                story = dict(data["storyteller"])
                story["next"] = "combat_agent"
                story["messages"] = [SystemMessage(content="COMBAT START")]
                yield mode, {"storyteller": story}
                yield (
                    mode,
                    {"combat_agent": {"messages": [AIMessage(content="O combate rebenta.")]}},
                )
                continue
            yield mode, data


def test_encounter_turn_emits_narrative_once(client, monkeypatch):
    import api

    monkeypatch.setenv("RPG_EARLY_NARRATIVE", "on")
    monkeypatch.setattr(api, "game_graph", _EncounterGraph(api.game_graph))
    gid = _new_game(client)
    events = _stream(client, gid)
    dones = [d for e, d in events if e == "narrative" and d["done"] and not d.get("replace")]
    assert len(dones) == 1
    first = "".join(
        d["chunk"] for e, d in events if e == "narrative" and not d["done"] and not d.get("replace")
    )
    assert first == "O combate rebenta."  # a update do storyteller (SystemMessage) nao emitiu


def test_error_after_narrative_marks_shown(client, monkeypatch):
    import api

    monkeypatch.setenv("RPG_EARLY_NARRATIVE", "on")
    gid = _new_game(client)

    def _boom(*a, **k):
        raise RuntimeError("commit falhou")

    monkeypatch.setattr(api, "_commit_turn", _boom)
    events = _stream(client, gid)
    names = _names(events)
    assert "narrative" in names and names[-1] == "error"
    assert events[-1][1]["narrative_shown"] is True
    assert "commit falhou" not in json.dumps(events[-1][1])


def test_error_before_narrative_has_no_shown_flag(client, monkeypatch):
    import api

    monkeypatch.setenv("RPG_EARLY_NARRATIVE", "on")
    gid = _new_game(client)

    class _Boom:
        def stream(self, *a, **k):
            raise RuntimeError("x")

    monkeypatch.setattr(api, "game_graph", _Boom())
    events = _stream(client, gid)
    assert events[-1][0] == "error" and "narrative_shown" not in events[-1][1]


class _DelegationGraph:
    """Antes da update real do `storyteller`, injeta a delegacao `npc_actor -> storyteller`
    (sem interlocutor): so a ultima update narradora pode emitir."""

    def __init__(self, real):
        self._real = real

    def __getattr__(self, name):
        return getattr(self._real, name)

    def stream(self, state, **kw):
        from langchain_core.messages import AIMessage

        for mode, data in self._real.stream(state, **kw):
            if mode == "updates" and "storyteller" in data:
                yield (
                    mode,
                    {
                        "npc_actor": {
                            "messages": [AIMessage(content="Ninguém responde.")],
                            "next": "storyteller",
                        }
                    },
                )
            yield mode, data


def test_npc_delegation_to_storyteller_emits_once(client, monkeypatch):
    import api

    monkeypatch.setenv("RPG_EARLY_NARRATIVE", "on")
    monkeypatch.setattr(api, "game_graph", _DelegationGraph(api.game_graph))
    gid = _new_game(client)
    events = _stream(client, gid)
    dones = [d for e, d in events if e == "narrative" and d["done"] and not d.get("replace")]
    assert len(dones) == 1
    text = "".join(d["chunk"] for e, d in events if e == "narrative" and not d["done"])
    assert "Ninguém responde." not in text
    assert text == events[-1][1]["message"]


def test_http_error_after_narrative_marks_shown(client, monkeypatch):
    from fastapi import HTTPException

    import api

    monkeypatch.setenv("RPG_EARLY_NARRATIVE", "on")
    gid = _new_game(client)

    def _boom(*a, **k):
        raise HTTPException(status_code=503, detail="indisponivel")

    monkeypatch.setattr(api, "_commit_turn", _boom)
    events = _stream(client, gid)
    assert "narrative" in _names(events) and events[-1][0] == "error"
    assert events[-1][1]["narrative_shown"] is True


def test_retry_same_action_id_recovers_turn(client, monkeypatch):
    import api

    monkeypatch.setenv("RPG_EARLY_NARRATIVE", "on")
    gid = _new_game(client)
    action_id = "22222222-2222-4222-8222-222222222222"
    real_commit = api._commit_turn

    def _boom(*a, **k):
        raise RuntimeError("commit falhou")

    monkeypatch.setattr(api, "_commit_turn", _boom)
    failed = _stream(client, gid, action_id=action_id)
    assert failed[-1][0] == "error" and failed[-1][1]["narrative_shown"] is True
    monkeypatch.setattr(api, "_commit_turn", real_commit)
    retried = _stream(client, gid, action_id=action_id)
    assert retried[-1][0] == "state"
    saved = client.get("/game/state", params={"game_id": gid}).json()
    assert saved["message"] == retried[-1][1]["message"]


def test_client_disconnect_after_narrative_done_still_saves(client, monkeypatch):
    import time

    import api
    from observability import latency

    monkeypatch.setenv("RPG_EARLY_NARRATIVE", "on")
    gid = _new_game(client)
    before = client.get("/game/state", params={"game_id": gid}).json()
    req = api.ActionRequest(input_text="olho ao redor", game_id=gid)
    gen = api._stream_turn(req, gid, None, latency.TurnTimeline(transport="stream"))
    for raw in gen:
        if raw.startswith("event: narrative") and '"done": true' in raw:
            break
    gen.close()  # o cliente cai logo apos a narracao (SPEC-247: o worker conclui)
    deadline = time.monotonic() + 20
    after = before
    while time.monotonic() < deadline:
        after = client.get("/game/state", params={"game_id": gid}).json()
        if after != before:
            break
        time.sleep(0.1)
    assert after != before


# ---------------------------------------------------------------------------
# SPEC-319 — tokens reais do narrador (RPG_TOKEN_STREAM)
# ---------------------------------------------------------------------------


def _token_run(client, gid, mode, snapshot, monkeypatch, early="off"):
    monkeypatch.setenv("RPG_TOKEN_STREAM", mode)
    monkeypatch.setenv("RPG_EARLY_NARRATIVE", early)
    path = persistence.save_path(gid)
    with open(path, "w", encoding="utf-8", newline="") as fh:
        fh.write(snapshot)
    random.seed(99)
    events = _stream(client, gid, action_id="22222222-2222-4222-8222-222222222222")
    with open(path, encoding="utf-8", newline="") as fh:
        return events, fh.read()


def test_token_deltas_arrive_before_node_phase(client, monkeypatch):
    monkeypatch.setenv("RPG_TOKEN_STREAM", "on")
    monkeypatch.setenv("RPG_EARLY_NARRATIVE", "off")
    gid = _new_game(client)
    events = _stream(client, gid)
    names = _names(events)
    live = [i for i, (e, d) in enumerate(events) if e == "narrative" and d.get("live")]
    assert len(live) > 1
    # os deltas saem durante o no narrador: antes da fase `storyteller` ser anunciada
    assert live[0] < _phase_index(events, "storyteller")
    narr = [d for e, d in events if e == "narrative"]
    assert narr[-1]["done"] is True and names[-1] == "state"
    text = "".join(d["chunk"] for d in narr if not d.get("replace") and not d.get("reset"))
    replaced = [d for d in narr if d.get("replace")]
    final = events[-1][1]["message"]
    assert (replaced[-1]["chunk"] if replaced else text) == final


def test_replace_when_guard_changes_streamed_text(client, monkeypatch):
    from services import prose_guard

    real = prose_guard.sanitize_player_facing
    monkeypatch.setattr(
        prose_guard, "sanitize_player_facing", lambda t, *a, **k: "Guardado: " + real(t, *a, **k)
    )
    monkeypatch.setenv("RPG_TOKEN_STREAM", "on")
    monkeypatch.setenv("RPG_EARLY_NARRATIVE", "off")
    gid = _new_game(client)
    events = _stream(client, gid)
    narr = [d for e, d in events if e == "narrative"]
    assert any(d.get("live") for d in narr)
    replace = [d for d in narr if d.get("replace")]
    assert len(replace) == 1 and replace[0]["done"] is True
    assert replace[0]["chunk"] == events[-1][1]["message"]
    assert "Guardado: " in replace[0]["chunk"]


def test_reset_event_clears_partial(client, monkeypatch):
    from services import narrative_sink as ns

    real = ns.narrate_structured

    def _with_garbage(llm, schema, messages, **kw):
        ns.emit("parcial que sera descartado. ")
        ns.reset()
        return real(llm, schema, messages, **kw)

    monkeypatch.setattr(ns, "narrate_structured", _with_garbage)
    monkeypatch.setenv("RPG_TOKEN_STREAM", "on")
    monkeypatch.setenv("RPG_EARLY_NARRATIVE", "off")
    gid = _new_game(client)
    events = _stream(client, gid)
    narr = [d for e, d in events if e == "narrative"]
    idx = next(i for i, d in enumerate(narr) if d.get("reset"))
    assert idx > 0 and narr[idx]["chunk"] == ""
    after = "".join(d["chunk"] for d in narr[idx + 1 :] if not d.get("replace"))
    final = events[-1][1]["message"]
    replaced = [d for d in narr[idx + 1 :] if d.get("replace")]
    assert "descartado" not in (replaced[-1]["chunk"] if replaced else after)
    assert (replaced[-1]["chunk"] if replaced else after) == final


def test_shadow_logs_ttft_without_deltas(client, monkeypatch):
    import api

    monkeypatch.setenv("RPG_TOKEN_STREAM", "shadow")
    monkeypatch.setenv("RPG_EARLY_NARRATIVE", "off")
    logs = []
    real = api._sse_log
    monkeypatch.setattr(
        api, "_sse_log", lambda event, **kw: (logs.append((event, kw)), real(event, **kw))
    )
    gid = _new_game(client)
    events = _stream(client, gid)
    assert not any(d.get("live") or d.get("reset") for e, d in events if e == "narrative")
    shadow = [kw for ev, kw in logs if ev == "token_stream_shadow"]
    assert len(shadow) == 1
    assert shadow[0]["ttft_shadow_ms"] is not None and shadow[0]["ttft_shadow_ms"] >= 0
    assert isinstance(shadow[0]["identical_to_final"], bool)  # anti-repeticao pode prefixar


def test_off_byte_identical(client, monkeypatch):
    import api

    monkeypatch.setenv("RPG_TOKEN_STREAM", "off")
    monkeypatch.setenv("RPG_EARLY_NARRATIVE", "off")
    logs = []
    monkeypatch.setattr(api, "_sse_log", lambda event, **kw: logs.append(event))
    gid = _new_game(client)
    events = _stream(client, gid)
    names = _names(events)
    assert names[-1] == "state" and names[-2] == "narrative"
    assert names.index("visual") < names.index("narrative")
    assert "token_stream_shadow" not in logs
    assert not any(d.get("live") for e, d in events if e == "narrative")


def test_final_state_identical_across_token_modes(client, monkeypatch):
    gid = _new_game(client)
    with open(persistence.save_path(gid), encoding="utf-8", newline="") as fh:
        snapshot = fh.read()
    runs = {m: _token_run(client, gid, m, snapshot, monkeypatch) for m in ("off", "shadow", "on")}
    base_state = next(d for e, d in runs["off"][0] if e == "state")
    base_save = _scrub_timings(json.loads(runs["off"][1]))
    for mode in ("shadow", "on"):
        events, save = runs[mode]
        assert next(d for e, d in events if e == "state") == base_state
        assert _scrub_timings(json.loads(save)) == base_save
    assert _names(runs["shadow"][0]) == _names(runs["off"][0])


def test_tokens_plus_early_narrative_closes_once(client, monkeypatch):
    monkeypatch.setenv("RPG_TOKEN_STREAM", "on")
    monkeypatch.setenv("RPG_EARLY_NARRATIVE", "on")
    gid = _new_game(client)
    events = _stream(client, gid)
    narr = [d for e, d in events if e == "narrative"]
    assert narr[-1]["done"] is True
    first_done = next(i for i, d in enumerate(narr) if d.get("done"))
    assert first_done >= len(narr) - 2  # no maximo um replace depois do done
    names = _names(events)
    assert names.index("visual") > max(i for i, n in enumerate(names) if n == "narrative")
    final = events[-1][1]["message"]
    text = "".join(d["chunk"] for d in narr if not d.get("replace") and not d.get("reset"))
    replaced = [d for d in narr if d.get("replace")]
    assert (replaced[-1]["chunk"] if replaced else text) == final
