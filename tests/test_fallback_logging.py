"""SPEC-250: fallbacks de nos do grafo deixam rastro (`<no>.fallback`) sem mudar o comportamento."""

import json
import uuid

import pytest

from observability import logging_setup
from observability.telemetry import begin_fallbacks, end_fallbacks, log_fallback, request_scope

SENT = "TEXTOSENTINELA250"


@pytest.fixture(autouse=True)
def _logs():
    logging_setup.configure_logging({"RPG_LOG_LEVEL": "debug"})


def _lines(capsys):
    out = []
    for raw in capsys.readouterr().out.splitlines():
        try:
            out.append(json.loads(raw))
        except ValueError:
            pass
    return out


def test_log_fallback_has_reason_and_error_type_only(capsys):
    with request_scope("fb-req-0000001"):
        log_fallback("storyteller", "structured_invalid", ValueError(f"segredo {SENT}"))
    (line,) = [x for x in _lines(capsys) if x["event"] == "storyteller.fallback"]
    assert line["reason"] == "structured_invalid" and line["error_type"] == "ValueError"
    assert line["level"] == "warning" and line["request_id"] == "fb-req-0000001"
    assert SENT not in json.dumps(line)


def test_dedupe_per_turn_but_counted_per_turn(capsys):
    token, bucket = begin_fallbacks()
    try:
        for _ in range(3):
            log_fallback("npc", "rag_unavailable")
    finally:
        end_fallbacks(token)
    assert len([x for x in _lines(capsys) if x["event"] == "npc.fallback"]) == 1
    assert bucket == ["npc.rag_unavailable"] * 3
    log_fallback("npc", "rag_unavailable")  # fora de um turno: sem dedupe
    log_fallback("npc", "rag_unavailable")
    assert len([x for x in _lines(capsys) if x["event"] == "npc.fallback"]) == 2


def test_storyteller_with_fallback_llm_logs_structured_invalid(capsys, monkeypatch):
    from fastapi.testclient import TestClient

    import agents.storyteller as st
    import api
    from llm_setup import FallbackLLM

    monkeypatch.setenv("RPG_RATE_LIMIT", "0")
    api._rate_hits.clear()
    client = TestClient(api.app)
    gid = client.post(
        "/game/new",
        json={
            "name": "Fb",
            "race": "Humano",
            "class_name": "Sangromante",
            "region": "Nova Arcádia",
            "level": 1,
        },
    ).json()["game_id"]
    monkeypatch.setattr(st, "get_llm", lambda **k: FallbackLLM("sem chave"))
    capsys.readouterr()
    r = client.post(
        "/game/action",
        json={
            "input_text": f"ando pela estrada {SENT}",
            "game_id": gid,
            "action_id": str(uuid.uuid4()),
        },
    )
    assert r.status_code == 200, r.text
    lines = _lines(capsys)
    fb = [x for x in lines if x["event"] == "storyteller.fallback"]
    assert fb and fb[0]["reason"] == "structured_invalid"
    turn = [x for x in lines if x["event"] == "turn"]
    assert turn and turn[0]["fallbacks"].get("storyteller.structured_invalid") == 1
    assert SENT not in json.dumps(lines)


def test_lease_release_failure_is_logged(capsys):
    import api

    class _Claim:
        operation_id = uuid.uuid4()

    api._release_failed(_Claim(), RuntimeError(f"db {SENT}"), ValueError("x"))
    (line,) = [x for x in _lines(capsys) if x["event"] == "operation.release_failed"]
    assert line["level"] == "error" and line["error_type"] == "RuntimeError"
    assert line["cause_type"] == "ValueError" and line["op_ref"] and SENT not in json.dumps(line)


def test_campaign_planner_error_logs_template_used(capsys, monkeypatch):
    from fastapi.testclient import TestClient

    import agents.campaign_manager as cm
    import api

    monkeypatch.setenv("RPG_RATE_LIMIT", "0")
    api._rate_hits.clear()
    gid = (
        TestClient(api.app)
        .post(
            "/game/new",
            json={
                "name": "Fb",
                "race": "Humano",
                "class_name": "Sangromante",
                "region": "Nova Arcádia",
                "level": 1,
            },
        )
        .json()["game_id"]
    )
    state = api.load_game_state(api._resolve_save_file(gid))
    state["campaign_plan"] = {}  # sem plano anterior => template

    class _Boom:
        def with_structured_output(self, *_a, **_k):
            raise RuntimeError(f"boom {SENT}")

    monkeypatch.setattr(cm, "get_llm", lambda **k: _Boom())
    capsys.readouterr()
    plan = cm._build_plan(state)
    assert plan["beats"]
    # So a linha desta chamada direta (sem request): threads de turno de outros testes carregam request_id.
    (line,) = [
        x for x in _lines(capsys) if x["event"] == "campaign.fallback" and not x.get("request_id")
    ]
    assert line["reason"] == "template_used" and line["error_type"] == "RuntimeError"
    assert SENT not in json.dumps(line)
