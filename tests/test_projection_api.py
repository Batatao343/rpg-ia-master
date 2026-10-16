"""SPEC-213 — modo A (`post_response`) na API: narração antes dos derivados,
serialização, restart, idempotência e exposição de status. Offline/MockLLM."""
from __future__ import annotations

import json
import threading

import pytest

import persistence
from services import projections


@pytest.fixture()
def client(monkeypatch):
    import api
    import agents.archivist as archive
    monkeypatch.setenv("RPG_RATE_LIMIT", "0")
    monkeypatch.setenv(projections.MODE_ENV, "post_response")
    # Força a cadência do arquivista: todo turno tem derivado a projetar.
    monkeypatch.setattr(archive, "_should_archive", lambda state, turn: True)
    api._rate_hits.clear()
    from fastapi.testclient import TestClient
    return TestClient(api.app)


def _new_game(client) -> str:
    r = client.post("/game/new", json={
        "name": "Projetor", "race": "Humano", "class_name": "Sangromante",
        "region": "Nova Arcádia", "level": 1, "backstory": ""})
    assert r.status_code == 200, r.text
    return r.json()["game_id"]


def _read_sse(resp) -> list:
    events, name = [], None
    for line in resp.iter_lines():
        line = line.decode() if isinstance(line, bytes) else line
        if line.startswith("event: "):
            name = line[len("event: "):].strip()
        elif line.startswith("data: ") and name:
            events.append((name, json.loads(line[len("data: "):])))
            name = None
    return events


def _load(gid):
    return persistence.load_game_state(persistence.save_path(gid))


def _wait_lock(gid):
    import api
    with api._game_lock(gid):
        pass


def _gated_executor(monkeypatch, gate: threading.Event, log: list):
    import agents.archivist as archive
    real = archive.run_derived_projection

    def gated(state, plan):
        log.append(("start", state.get("game_id"), plan.get("action_id")))
        released = gate.wait(timeout=10)
        log.append(("released", released))
        return real(state, plan)

    monkeypatch.setattr(archive, "run_derived_projection", gated)
    return real


def test_sse_done_before_summary(client, monkeypatch):
    """A narração (done + state) chega ao cliente ANTES de o derivado terminar."""
    gid = _new_game(client)
    gate, log = threading.Event(), []
    _gated_executor(monkeypatch, gate, log)
    with client.stream("POST", "/game/action/stream",
                       json={"input_text": "olho ao redor", "game_id": gid}) as r:
        events = _read_sse(r)
        names = [e for e, _ in events]
        assert names[-1] == "state"
        assert ("narrative" in names)
        final = events[-1][1]
        assert final["projections"]["summary"]["status"] == "pending"
        gate.set()
    _wait_lock(gid)
    assert ("released", True) in log            # a projeção esperou a entrega
    saved = _load(gid)
    assert saved["projection_state"]["summary"]["status"] == "completed"
    assert saved["pending_derived"] is None


def test_sse_drop_after_done_completes_projection(client, monkeypatch):
    gid = _new_game(client)
    gate, log = threading.Event(), []
    _gated_executor(monkeypatch, gate, log)
    with client.stream("POST", "/game/action/stream",
                       json={"input_text": "sigo", "game_id": gid}) as r:
        for line in r.iter_lines():
            if '"done": true' in (line if isinstance(line, str) else line.decode()):
                break                          # cliente "cai" após o done
    gate.set()
    _wait_lock(gid)
    saved = _load(gid)
    assert saved["projection_state"]["summary"]["status"] == "completed"
    assert saved["projection_state"]["summary"]["projected_version"] == \
        saved["projection_state"]["canonical_version"]


def test_two_rapid_actions_serialize(client):
    """R14: duas ações concorrentes no mesmo jogo serializam; derivados em ordem,
    sem duplicação; a 2ª lê o canônico completo da 1ª."""
    gid = _new_game(client)
    base = _load(gid)["projection_state"]["canonical_version"]
    results = []

    def act(text):
        results.append(client.post("/game/action", json={"input_text": text, "game_id": gid}))

    threads = [threading.Thread(target=act, args=(t,)) for t in ("olho", "escuto")]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert [r.status_code for r in results] == [200, 200]
    saved = _load(gid)
    ps = saved["projection_state"]
    assert ps["canonical_version"] >= base + 2
    assert ps["canonical_version"] == saved["continuity"]["session_action_count"]
    assert all(ps[n]["status"] == "completed"
               and ps[n]["projected_version"] == ps["canonical_version"]
               for n in projections.PROJECTIONS)
    prose = [(e["turn"], e["text"]) for ch in saved.get("chronicle") or []
             for e in ch.get("entries", []) if e.get("kind") == "prose"]
    assert len(prose) == len(set(prose))


def test_restart_pending_rescheduled(client, monkeypatch):
    """R15: processo morto com projeção pendente → executa no início do próximo turno."""
    gid = _new_game(client)
    import agents.archivist as archive
    real = archive.run_derived_projection
    calls = []

    def dies(state, plan):
        calls.append(plan["action_id"])
        raise RuntimeError("worker morreu")

    monkeypatch.setattr(archive, "run_derived_projection", dies)
    assert client.post("/game/action", json={"input_text": "olho", "game_id": gid,
                                             "action_id": "11111111-1111-4111-8111-111111111111"}
                       ).status_code == 200
    saved = _load(gid)
    assert saved["pending_derived"]["action_id"] == "11111111-1111-4111-8111-111111111111"
    assert saved["projection_state"]["summary"]["status"] == "failed"

    def recorded(state, plan):
        calls.append(plan["action_id"])
        return real(state, plan)

    monkeypatch.setattr(archive, "run_derived_projection", recorded)
    assert client.post("/game/action", json={"input_text": "escuto", "game_id": gid}
                       ).status_code == 200
    # 1º a projeção antiga (pre_turn), depois a do turno novo.
    assert calls[1] == "11111111-1111-4111-8111-111111111111"
    assert len(calls) == 3
    final = _load(gid)["projection_state"]
    assert final["summary"]["status"] == "completed"
    assert final["summary"]["projected_version"] == final["canonical_version"]


def test_state_exposes_projection_status(client):
    gid = _new_game(client)
    base = _load(gid)["projection_state"]["canonical_version"]
    r = client.post("/game/action", json={"input_text": "olho", "game_id": gid})
    body = r.json()
    assert set(body["projections"]) == {"canonical_version", "summary", "memory", "chronicle"}
    state = client.get("/game/state", params={"game_id": gid}).json()
    version = state["projections"]["canonical_version"]
    assert version > base
    assert state["projections"]["summary"] == {"status": "completed",
                                               "projected_version": version}
    # só status: nada de texto derivado no bloco
    assert "narrative_summary" not in json.dumps(state["projections"])


def test_no_thread_spawn(client, monkeypatch):
    """R9: a drenagem roda no dono do lock; nunca dispara thread própria."""
    import api
    gid = _new_game(client)
    state = _load(gid)
    state["pending_derived"] = projections.make_plan(
        new_event_ids=[], new_rejections=False, turn=0, epoch=0)
    state = projections.stamp_commit(state, "acao-x")

    def forbidden(self):
        raise AssertionError("thread disparada pela projeção")

    monkeypatch.setattr(threading.Thread, "start", forbidden)
    drained = api._drain_projection(state, where="test")
    assert drained["pending_derived"] is None
    assert drained["projection_state"]["summary"]["status"] == "completed"


def test_switch_game_mid_stream_projection_stays_with_origin(client, monkeypatch):
    """R14: a projeção pertence ao game_id do turno, não ao jogo ativo do cliente."""
    gid_a, gid_b = _new_game(client), _new_game(client)
    base_b = _load(gid_b)["projection_state"]["canonical_version"]
    gate, log = threading.Event(), []
    _gated_executor(monkeypatch, gate, log)
    with client.stream("POST", "/game/action/stream",
                       json={"input_text": "olho", "game_id": gid_a}) as r:
        _read_sse(r)
    # cliente troca para B (sem tocar no lock de A) enquanto A ainda projeta
    state_b = client.get("/game/state", params={"game_id": gid_b}).json()
    assert state_b["projections"]["canonical_version"] == base_b
    gate.set()
    _wait_lock(gid_a)
    started = [entry for entry in log if entry[0] == "start"]
    assert started and started[0][1] == gid_a
    assert _load(gid_a)["projection_state"]["summary"]["status"] == "completed"
    assert _load(gid_b)["projection_state"]["canonical_version"] == base_b


def test_inline_default_keeps_post_equal_to_state(monkeypatch):
    """R11: sem a env, o modo é inline e o GameResponse == /game/state."""
    import api
    monkeypatch.delenv(projections.MODE_ENV, raising=False)
    monkeypatch.setenv("RPG_RATE_LIMIT", "0")
    api._rate_hits.clear()
    from fastapi.testclient import TestClient
    client = TestClient(api.app)
    gid = _new_game(client)
    body = client.post("/game/action", json={"input_text": "olho", "game_id": gid}).json()
    assert body == client.get("/game/state", params={"game_id": gid}).json()
    assert _load(gid)["pending_derived"] is None
