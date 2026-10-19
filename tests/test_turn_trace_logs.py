"""SPEC-247: decisão de rota (fonte/motivo), ciclo de vida do SSE e 409/replay de operação."""
import json
import threading
import time
import uuid

import pytest
from langchain_core.messages import HumanMessage

from observability import logging_setup

SENT_TEXT = "TEXTOSENTINELA247"


@pytest.fixture(autouse=True)
def _logs(monkeypatch):
    monkeypatch.setenv("RPG_RATE_LIMIT", "0")
    logging_setup.configure_logging({"RPG_LOG_LEVEL": "debug"})


def _lines(capsys):
    out = []
    for raw in capsys.readouterr().out.splitlines():
        try:
            out.append(json.loads(raw))
        except ValueError:
            pass
    return out


def _find(lines, event):
    return [x for x in lines if x.get("event") == event]


def test_router_decision_source_gate(capsys):
    from agents.router import dm_router_node, last_decision
    state = {"messages": [HumanMessage(content=f"ataco {SENT_TEXT}")], "world": {},
             "combat": {"active": True, "idle_turns": 0}}
    payload = dm_router_node(state)
    assert payload["next"] == "combat_agent" and last_decision()["route_source"] == "combat_gate"
    assert "route_source" not in payload       # contrato `off` byte-identico (SPEC-217)
    (line,) = _find(_lines(capsys), "router.decision")
    assert line["source"] == "combat_gate" and line["route"] == "combat_agent"
    assert line["jev_mode"] == "off" and line["target_kind"] == "none"
    assert line["level"] == "info"


def test_router_classify_fallback_reason(capsys, monkeypatch):
    import agents.router as router
    from llm_setup import FallbackLLM
    monkeypatch.setattr(router, "get_llm", lambda **k: FallbackLLM("sem chave"))
    state = {"messages": [HumanMessage(content=f"ando pela estrada vazia {SENT_TEXT}")], "world": {}}
    router.dm_router_node(state)
    decision = router.last_decision()
    assert decision["route_source"] == "classify_fallback"
    assert decision["route_fallback_reason"] in {"not_router_decision", "invoke_exception"}
    lines = _lines(capsys)
    (line,) = _find(lines, "router.decision")
    assert line["source"] == "classify_fallback" and line["fallback_reason"] == decision["route_fallback_reason"]
    assert SENT_TEXT not in json.dumps(lines)


def test_router_decision_classify_with_mock(capsys, monkeypatch):
    import agents.router as router
    monkeypatch.delenv("RPG_FORCE_MOCK", raising=False)
    from mock_llm import MockLLM
    monkeypatch.setattr(router, "get_llm", lambda **k: MockLLM(temperature=0))
    state = {"messages": [HumanMessage(content="observo a praça")], "world": {}}
    router.dm_router_node(state)
    assert router.last_decision()["route_source"] in {"classify", "interlocutor", "story_regex", "classify_fallback"}
    assert len(_find(_lines(capsys), "router.decision")) == 1


@pytest.fixture()
def client(monkeypatch):
    import api
    api._rate_hits.clear()
    from fastapi.testclient import TestClient
    return TestClient(api.app)


def _new_game(client):
    r = client.post("/game/new", json={"name": "Trace", "race": "Humano", "class_name": "Sangromante",
                                      "region": "Nova Arcádia", "level": 1})
    assert r.status_code == 200, r.text
    return r.json()["game_id"]


def test_turn_line_has_route_source(client, capsys):
    gid = _new_game(client)
    capsys.readouterr()
    r = client.post("/game/action", json={"input_text": f"olho {SENT_TEXT}", "game_id": gid,
                                         "action_id": str(uuid.uuid4())})
    assert r.status_code == 200, r.text
    turn = _find(_lines(capsys), "turn")
    assert turn and turn[0].get("route_source")


def test_sse_disconnect_logged(client, capsys):
    import api
    gid = _new_game(client)
    capsys.readouterr()
    req = api.ActionRequest(input_text=f"olho {SENT_TEXT}", game_id=gid, action_id=str(uuid.uuid4()))
    gen = api._stream_turn(req, gid, None, None)
    assert next(gen).startswith("event: accepted")
    next(gen)                         # o worker so nasce depois do `accepted` ser entregue
    gen.close()                       # o cliente caiu no meio do turno
    deadline = time.time() + 30
    lines: list = []
    while time.time() < deadline:
        lines += _lines(capsys)
        if _find(lines, "sse.worker_finished_after_disconnect"):
            break
        time.sleep(0.2)
    assert _find(lines, "sse.started")
    (gone,) = _find(lines, "sse.client_disconnected")
    assert gone["phase"] and gone["elapsed_ms"] >= 0
    (done,) = _find(lines, "sse.worker_finished_after_disconnect")
    assert done["outcome"] in {"ok", "error"}
    assert SENT_TEXT not in json.dumps(lines)


def test_sse_error_logged_and_turn_delivery_error_type(client, capsys, monkeypatch):
    import api
    gid = _new_game(client)

    def boom(*a, **k):
        raise RuntimeError(f"segredo {SENT_TEXT}")

    monkeypatch.setattr(api, "_execute_action", boom)
    capsys.readouterr()
    with client.stream("POST", "/game/action/stream", json={
            "input_text": "olho", "game_id": gid, "action_id": str(uuid.uuid4())}) as r:
        "".join(r.iter_text())
    lines = _lines(capsys)
    (err,) = _find(lines, "sse.error")
    assert err["error_type"] == "RuntimeError" and err["code"] == "internal_turn_error"
    delivery = _find(lines, "turn_delivery")
    assert delivery and delivery[0]["error_type"] == "RuntimeError"
    assert SENT_TEXT not in json.dumps(lines)


class _FakeCoordinator:
    def __init__(self, receipt=None, claim_exc=None):
        self._receipt, self._claim_exc = receipt, claim_exc

    def receipt(self, *a, **k):
        if isinstance(self._receipt, Exception):
            raise self._receipt
        return self._receipt

    def claim(self, *a, **k):
        raise self._claim_exc


class _FakeRuntime:
    def __init__(self, coordinator):
        self.turn_coordinator = coordinator


def _patch_db(monkeypatch, coordinator):
    import api
    from infrastructure import request_context, runtime
    from infrastructure.contracts import Principal
    principal = Principal(uuid.uuid4(), "iss", "sub")
    monkeypatch.setattr(api, "_database_profile", lambda: True)
    monkeypatch.setattr(runtime, "get_runtime", lambda: _FakeRuntime(coordinator))
    monkeypatch.setattr(request_context, "current_principal", lambda **k: principal)


@pytest.mark.parametrize("exc_name,reason", [
    ("LeaseHeld", "operation_in_progress"), ("StaleVersion", "stale_version"),
    ("Conflict", "operation_conflict")])
def test_operation_conflict_logged(capsys, monkeypatch, exc_name, reason):
    import api
    from fastapi import HTTPException
    from infrastructure import contracts
    _patch_db(monkeypatch, _FakeCoordinator(claim_exc=getattr(contracts, exc_name)("x")))
    state = {"game_id": str(uuid.uuid4()), "_storage_version": 1}
    req = api.ActionRequest(input_text="olho", game_id=state["game_id"], action_id=str(uuid.uuid4()))
    with pytest.raises(HTTPException) as caught:
        api._begin_turn_operation(state, req)
    assert caught.value.status_code == 409
    (line,) = _find(_lines(capsys), "operation.rejected")
    assert line["reason"] == reason and line["op_kind"] == "turn"
    assert req.action_id not in json.dumps(line)


def test_request_mismatch_logged(capsys, monkeypatch):
    import api
    from fastapi import HTTPException
    from infrastructure.contracts import Conflict
    _patch_db(monkeypatch, _FakeCoordinator(receipt=Conflict("mismatch")))
    state = {"game_id": str(uuid.uuid4())}
    req = api.ActionRequest(input_text="olho", game_id=state["game_id"], action_id=str(uuid.uuid4()))
    with pytest.raises(HTTPException):
        api._begin_turn_operation(state, req)
    (line,) = _find(_lines(capsys), "operation.rejected")
    assert line["reason"] == "request_mismatch"


def test_replay_logged(capsys, monkeypatch):
    import api
    cached = api.GameResponse.model_construct()
    _patch_db(monkeypatch, _FakeCoordinator(receipt={"response": {"x": 1}}))
    monkeypatch.setattr(api.GameResponse, "model_validate", classmethod(lambda cls, v: cached))
    state = {"game_id": str(uuid.uuid4())}
    req = api.ActionRequest(input_text="olho", game_id=state["game_id"], action_id=str(uuid.uuid4()))
    claim, _hash, replay = api._begin_turn_operation(state, req)
    assert claim is None and replay is cached
    (line,) = _find(_lines(capsys), "operation.replayed")
    assert line["op_kind"] == "turn" and line["level"] == "info"
