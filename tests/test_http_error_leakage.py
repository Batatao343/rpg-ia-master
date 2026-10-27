"""SPEC-337: erros HTTP sem vazamento (R11-R13)."""

from __future__ import annotations

from fastapi.testclient import TestClient

import api


def test_422_does_not_echo_input(monkeypatch):
    monkeypatch.setenv("RPG_RUNTIME_PROFILE", "legacy")
    client = TestClient(api.app, raise_server_exceptions=False)
    out = client.post(
        "/auth/signup",
        json={"email": "x@y.z", "password": "curta-XYZ", "age_confirmed": True},
    )
    assert out.status_code == 422
    assert "curta-XYZ" not in out.text
    body = out.json()
    assert body["code"] == "validation_failed" and body["request_id"]
    assert body["detail"]
    for item in body["detail"]:
        assert set(item) == {"type", "loc", "msg"}
