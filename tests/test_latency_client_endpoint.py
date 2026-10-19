"""SPEC-200 Etapa 4 — beacon cliente->servidor (desligado por default, corpo fechado)."""

from __future__ import annotations

import json
import logging
from types import SimpleNamespace
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

import api
from infrastructure.contracts import Principal, Unauthorized
from observability.metrics import metrics
from services.auth_sessions import CsrfSigner

PATH = "/telemetry/client-latency"


def _body(**extra):
    base = {
        "action_id": str(uuid4()),
        "transport": "stream",
        "ack_ms": 40,
        "first_phase_ms": 900,
        "ttfmc_ms": 5000,
        "ttlt_ms": 5100,
        "state_ms": 5200,
        "outcome": "ok",
    }
    base.update(extra)
    return base


@pytest.fixture()
def enabled(monkeypatch):
    monkeypatch.setenv("RPG_CLIENT_LATENCY_REPORT", "1")
    monkeypatch.setenv("RPG_RATE_LIMIT", "0")
    return TestClient(api.app)


def test_disabled_by_default(monkeypatch):
    monkeypatch.delenv("RPG_CLIENT_LATENCY_REPORT", raising=False)
    client = TestClient(api.app)
    assert client.post(PATH, json=_body()).status_code == 404
    assert "client_latency_report" not in client.get("/auth/config").json()


def test_enabled_flag_in_auth_config(enabled):
    assert enabled.get("/auth/config").json()["client_latency_report"] is True


def test_accepts_valid_report_and_logs(enabled, caplog):
    caplog.set_level(logging.INFO, logger="rpg.turn")
    key = "rpg_turn_first_content_seconds{'route': '/game/action/stream', 'source': 'client'}.count"
    before = metrics.snapshot().get(key, 0)
    body = _body()
    response = enabled.post(PATH, json=body)
    assert response.status_code == 204 and response.content == b""
    assert metrics.snapshot()[key] == before + 1
    lines = [
        json.loads(r.getMessage())
        for r in caplog.records
        if r.name == "rpg.turn" and "client_latency" in r.getMessage()
    ]
    assert lines and lines[-1]["evt"] == "client_latency"
    assert body["action_id"] not in json.dumps(lines[-1])  # so pseudonimo


def test_rejects_extra_fields_and_text(enabled):
    for extra in ({"game_id": str(uuid4())}, {"input_text": "meu segredo"}, {"note": "x"}):
        assert enabled.post(PATH, json=_body(**extra)).status_code == 422
    assert enabled.post(PATH, json=_body(action_id="nao-uuid")).status_code == 422
    assert enabled.post(PATH, json=_body(transport="ws")).status_code == 422
    assert enabled.post(PATH, json=_body(ttfmc_ms="1000ms")).status_code == 422


def test_clamps_values(enabled):
    key = "rpg_turn_last_content_seconds{'route': '/game/action/stream', 'source': 'client'}.max"
    assert enabled.post(PATH, json=_body(ttlt_ms=10**12, ttfmc_ms=-5)).status_code == 204
    assert metrics.snapshot()[key] <= 600.0
    # o modelo clampa para [0, 600000] antes de qualquer uso
    model = api.ClientLatencyReport(**_body(ttlt_ms=10**12, ttfmc_ms=-5))
    assert model.ttlt_ms == 600_000 and model.ttfmc_ms == 0


def test_requires_csrf_and_session(monkeypatch):
    """Perfil com banco: o beacon passa pelo mesmo boundary de sessao/CSRF das mutacoes."""
    owner = uuid4()
    principal = Principal(owner, "test", str(owner))
    secret = "a" * 64
    csrf = CsrfSigner(secret).issue()
    monkeypatch.setenv("RPG_SESSION_SECRET", secret)
    monkeypatch.setenv("RPG_CLIENT_LATENCY_REPORT", "1")
    monkeypatch.setenv("RPG_RATE_LIMIT", "0")
    monkeypatch.setattr(api, "_database_profile", lambda: True)

    def verify(cookie):
        if cookie != "valid":
            raise Unauthorized("session absent")
        return principal

    runtime = SimpleNamespace(
        identity_verifier=SimpleNamespace(verify=verify),
        rate_limiter=SimpleNamespace(
            consume=lambda *a, **k: SimpleNamespace(allowed=True, retry_after_seconds=1)
        ),
    )
    monkeypatch.setattr("infrastructure.runtime.get_runtime", lambda: runtime)
    client = TestClient(api.app)
    headers = {"origin": "http://localhost:5173", "x-csrf-token": csrf}
    assert client.post(PATH, json=_body(), headers=headers).status_code == 401  # sem sessao
    client.cookies.set("rpg_access", "valid")
    assert (
        client.post(PATH, json=_body(), headers=headers).status_code == 403
    )  # sem cookie CSRF (SPEC-220 R10)
    client.cookies.set("rpg_csrf", csrf)
    assert client.post(PATH, json=_body(), headers=headers).status_code == 204


def test_rate_limited_in_own_bucket(monkeypatch):
    monkeypatch.setenv("RPG_CLIENT_LATENCY_REPORT", "1")
    monkeypatch.setenv("RPG_RATE_LIMIT", "2")
    api._rate_hits.clear()
    client = TestClient(api.app)
    codes = [client.post(PATH, json=_body()).status_code for _ in range(3)]
    assert codes == [204, 204, 429]
    # o balde das acoes nao foi consumido pelo beacon
    assert not any(k for k in api._rate_hits if not k.endswith("#latency") and api._rate_hits[k])
    api._rate_hits.clear()
