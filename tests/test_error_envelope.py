"""SPEC-242: toda resposta de erro traz {detail, code, request_id}; catálogo fechado."""
import ast
import json
import uuid
from pathlib import Path

import pytest

from services import error_codes as ec

ROOT = Path(__file__).resolve().parents[1]
FILES = ["api.py", "services/cron_internal.py", "services/account_security.py"]
# Expressões dinâmicas aceitas como ``detail`` (já são códigos fechados por construção).
DYNAMIC_OK = {
    "code", "public_auth_code(exc)", "exc.code", "exc.status", "status", "detail",
}


def _http_exception_calls():
    for rel in FILES:
        tree = ast.parse((ROOT / rel).read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.Call) and getattr(node.func, "id", None) == "HTTPException":
                status = node.args[0] if node.args else None
                detail = node.args[1] if len(node.args) > 1 else None
                for kw in node.keywords:
                    if kw.arg == "detail":
                        detail = kw.value
                    if kw.arg == "status_code":
                        status = kw.value
                yield rel, node.lineno, status, detail


def test_every_http_exception_has_catalog_code():
    bad = []
    for rel, line, _status, detail in _http_exception_calls():
        where = f"{rel}:{line}"
        if isinstance(detail, ast.Constant) and isinstance(detail.value, str):
            code = detail.value if detail.value in ec.CODES else ec.prose_code(detail.value)
            if code not in ec.CODES:
                bad.append((where, detail.value))
        elif isinstance(detail, ast.Dict):
            keys = [k.value for k in detail.keys if isinstance(k, ast.Constant)]
            code_node = detail.values[keys.index("code")] if "code" in keys else None
            if not (isinstance(code_node, ast.Constant) and code_node.value in ec.CODES):
                bad.append((where, "dict sem code do catálogo"))
        else:
            src = ast.unparse(detail) if detail is not None else "None"
            if src not in DYNAMIC_OK:
                bad.append((where, src))
    assert not bad, bad


def test_no_str_exc_in_detail():
    for rel in FILES:
        text = (ROOT / rel).read_text(encoding="utf-8")
        assert "detail=str(exc)" not in text and "HTTPException(400, str(exc))" not in text
        assert "HTTPException(status_code=400, detail=err)" not in text


def test_envelope_helpers():
    assert ec.code_for(404, "Jogo não encontrado.") == "game_not_found"
    assert ec.code_for(409, "operation_in_progress") == "operation_in_progress"
    assert ec.code_for(409, {"code": "pending_operation", "message": "x"}) == "pending_operation"
    assert ec.code_for(418, "texto livre qualquer") == "http_418"
    err = ec.api_error(400, "equip_rejected", detail="Não cabe.", foo="bar")
    assert err.code == "equip_rejected" and err.detail == "Não cabe."


def test_docs_are_fresh():
    doc = (ROOT / "docs/operacao/CODIGOS_DE_ERRO.md").read_text(encoding="utf-8")
    assert doc.replace("\r\n", "\n") == ec.render_markdown().replace("\r\n", "\n"), \
        "rode: uv run python scripts/gen_error_codes_doc.py"


@pytest.fixture()
def client(monkeypatch):
    import api
    monkeypatch.setenv("RPG_RATE_LIMIT", "0")
    api._rate_hits.clear()
    from fastapi.testclient import TestClient
    return TestClient(api.app)


def test_404_game_has_code_and_request_id(client):
    r = client.get("/game/state", params={"game_id": str(uuid.uuid4())},
                   headers={"X-Request-ID": "envelope-req-0001"})
    assert r.status_code == 404
    body = r.json()
    assert body["code"] == "no_saved_game" or body["code"] == "game_not_found"
    assert body["detail"] and body["request_id"] == "envelope-req-0001"
    assert r.headers["X-Request-ID"] == "envelope-req-0001"


def test_unknown_route_and_validation_have_code(client):
    r = client.get("/data/nao-existe-xyz")
    assert r.json()["code"] == "not_found" and r.json()["request_id"]
    r = client.post("/game/action", json={})
    assert r.status_code == 422
    body = r.json()
    assert body["code"] == "validation_failed" and isinstance(body["detail"], list)
    assert body["request_id"]


def test_blocked_response_has_code_and_request_id():
    import api
    from observability.telemetry import request_scope
    with request_scope("blocked-req-0001"):
        resp = api._blocked_response("rate_limited", "authfail", 7)
    body = json.loads(resp.body)
    assert body["code"] == "rate_limited" and body["request_id"] == "blocked-req-0001"
    assert body["detail"] == "rate_limited" and body["retry_after_seconds"] == 7


def test_sse_error_event_envelope(client, monkeypatch):
    import api
    from fastapi import HTTPException
    gid = client.post("/game/new", json={
        "name": "Envelope", "race": "Humano", "class_name": "Sangromante",
        "region": "Nova Arcádia", "level": 1}).json()["game_id"]

    def boom(*a, **k):
        raise HTTPException(409, "operation_in_progress")

    monkeypatch.setattr(api, "_execute_action", boom)
    with client.stream("POST", "/game/action/stream", json={
            "input_text": "olho", "game_id": gid,
            "action_id": str(uuid.uuid4())}, headers={"X-Request-ID": "sse-req-000001"}) as r:
        text = "".join(r.iter_text())
    blocks = [b for b in text.split("\n\n") if b.startswith("event: error")]
    assert blocks, text
    payload = json.loads(blocks[0].split("data: ", 1)[1])
    assert payload["error_code"] == "operation_in_progress" and payload["code"] == 409 and payload["request_id"] == "sse-req-000001"
    assert True    # ``code`` numerico = compat do cliente


def test_error_responses_never_echo_exception_text(client, monkeypatch):
    import api
    monkeypatch.setattr(api, "load_game_state", lambda *a, **k: (_ for _ in ()).throw(
        RuntimeError("SEGREDO-NA-EXCECAO")))
    r = client.get("/game/state", params={"game_id": str(uuid.uuid4())})
    assert "SEGREDO-NA-EXCECAO" not in r.text


def test_web_code_list_is_fresh():
    raw = (ROOT / "web/src/lib/errorCodes.json").read_text(encoding="utf-8")
    assert json.loads(raw) == sorted(ec.CODES), "rode: uv run python scripts/gen_error_codes_doc.py"
