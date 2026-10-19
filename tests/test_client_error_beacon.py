"""SPEC-244: POST /telemetry/client-error — corpo fechado, <= 4 KiB, rate limit, sem PII no log."""
import json

import pytest

from observability import logging_setup

GOOD = {
    "kind": "render", "error_name": "TypeError", "code": "render_failed",
    "route": "/game/{id}/codex", "request_id": "abc123def456", "build": "abcdef1+202610191345",
    "client": "web", "stack": ["assets/index-Bx1.js:1:2345", "assets/vendor-9a.js:12:7"], "ts": 1760000000000,
}


@pytest.fixture()
def client(monkeypatch):
    import api
    monkeypatch.setenv("RPG_RATE_LIMIT", "0")
    monkeypatch.delenv("RPG_CLIENT_ERROR_REPORT", raising=False)
    api._rate_hits.clear()
    logging_setup.configure_logging({"RPG_LOG_LEVEL": "debug"})
    from fastapi.testclient import TestClient
    return TestClient(api.app, raise_server_exceptions=False)


def _events(capsys, name):
    out = []
    for raw in capsys.readouterr().out.splitlines():
        try:
            row = json.loads(raw)
        except ValueError:
            continue
        if row.get("event") == name:
            out.append(row)
    return out


def test_valid_report_logged_and_counted(client, capsys):
    from observability.metrics import metrics
    key = ("rpg_client_errors_total", (("kind", "render"),))
    before = metrics._values.get(key, 0)
    capsys.readouterr()
    r = client.post("/telemetry/client-error", json=GOOD, headers={"X-Request-ID": "beacon-req-01"})
    assert r.status_code == 204
    row = _events(capsys, "client.error")[0]
    assert row["level"] == "warning" and row["kind"] == "render" and row["error_name"] == "TypeError"
    assert row["request_id"] == "abc123def456" and row["beacon_request_id"] == "beacon-req-01"
    assert row["build"] == "abcdef1+202610191345" and row["client"] == "web"
    assert row["stack"] == GOOD["stack"] and row["route"] == "/game/{id}/codex"
    assert metrics._values.get(key, 0) - before == 1


def test_kind_enum_enforced(client):
    assert client.post("/telemetry/client-error", json={**GOOD, "kind": "pwned"}).status_code == 422


def test_free_text_and_extra_fields_rejected(client, capsys):
    capsys.readouterr()
    for bad in ({**GOOD, "message": "Cannot read jogador@mail.com"},           # campo extra (texto livre)
                {**GOOD, "error_name": "Erro de jogador@mail.com"},           # nome com espaco/email
                {**GOOD, "route": "/game/x?email=jogador@mail.com"},          # query/email na rota
                {**GOOD, "stack": ["https://h/assets/a.js?token=SEGREDO:1:2"]},  # URL/query no stack
                {**GOOD, "code": "Texto Livre do jogador"}):
        assert client.post("/telemetry/client-error", json=bad).status_code == 422
    out = capsys.readouterr().out
    assert "jogador@mail.com" not in out and "SEGREDO" not in out


def test_size_limit(client):
    big = {**GOOD, "stack": ["assets/index.js:1:1"] * 10}
    raw = json.dumps(big) + " " * 5000
    r = client.post("/telemetry/client-error", content=raw, headers={"Content-Type": "application/json"})
    assert r.status_code == 413


def test_stack_capped(client):
    assert client.post("/telemetry/client-error",
                       json={**GOOD, "stack": ["assets/a.js:1:1"] * 21}).status_code == 422


def test_kill_switch(client, monkeypatch):
    monkeypatch.setenv("RPG_CLIENT_ERROR_REPORT", "0")
    assert client.post("/telemetry/client-error", json=GOOD).status_code == 404


def test_rate_limited_per_ip(client, monkeypatch):
    import api
    monkeypatch.setenv("RPG_RATE_LIMIT", "")
    monkeypatch.setenv("RPG_LIMIT_TELEMETRY_IP", "3")
    api._rate_hits.clear()
    codes = [client.post("/telemetry/client-error", json=GOOD).status_code for _ in range(4)]
    api._rate_hits.clear()
    assert codes[:3] == [204, 204, 204] and codes[3] == 429


def test_public_in_db_profile_without_session(client, monkeypatch):
    """Erro na tela de login (sem sessao) tambem precisa chegar: rota fora da fronteira de sessao."""
    import api
    monkeypatch.setattr(api, "_database_profile", lambda: True)
    r = client.post("/telemetry/client-error", json=GOOD)
    assert r.status_code == 204


def test_cross_origin_rejected(client, monkeypatch):
    import api
    monkeypatch.setattr(api, "_database_profile", lambda: True)
    r = client.post("/telemetry/client-error", json=GOOD, headers={"Origin": "https://evil.example"})
    assert r.status_code == 403
