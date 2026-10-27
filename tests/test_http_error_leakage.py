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


# --- R11: corpo malformado não vaza ------------------------------------------

import json  # noqa: E402
import re  # noqa: E402
from uuid import uuid4  # noqa: E402

import pytest  # noqa: E402
from fastapi.routing import APIRoute  # noqa: E402

from tests.fakes.two_principals import forbidden_leak, two_principals  # noqa: E402,F401

PAYLOADS = {
    "truncated": b"{",
    "wrong_type": b"[]",
    "huge_string": json.dumps("x" * (300 * 1024)).encode(),
}
RAW_BODY_ROUTES = [
    ("POST", "/payments/stripe/webhook"),
    ("POST", "/account/transcriptions"),
    ("POST", "/auth/refresh"),
    ("POST", "/auth/logout"),
]


def _body_routes() -> list[tuple[str, str]]:
    out = []
    for route in api.app.routes:
        if not isinstance(route, APIRoute) or not route.include_in_schema or not route.body_field:
            continue
        for method in sorted(route.methods - {"HEAD", "OPTIONS"}):
            out.append((method, route.path))
    return out


def _fill(path: str, game: str) -> str:
    def repl(match):
        name = match.group(1)
        return game if name in {"game_id", "id"} else str(uuid4())

    return re.sub(r"\{([^}:]+)(?::[^}]*)?\}", repl, path)


def _hammer(client, routes, payload: bytes, game: str) -> list[str]:
    problems: list[str] = []
    for method, path in routes:
        url = _fill(path, game)
        response = client.request(
            method,
            url,
            content=payload,
            headers={"content-type": "application/json", "Idempotency-Key": str(uuid4())},
        )
        text = response.text
        if response.status_code >= 500 and response.status_code != 503:  # 503 = recurso desligado
            problems.append(f"{method} {path}: {response.status_code}")
        found = forbidden_leak(text)
        if found:
            problems.append(f"{method} {path}: vaza {found}")
        if "traceback" in response.headers.get("content-type", "").lower():
            problems.append(f"{method} {path}: content-type")
    return problems


def test_there_are_body_routes():
    assert len(_body_routes()) >= 20


@pytest.mark.parametrize("payload", list(PAYLOADS))
def test_malformed_body_no_leak_legacy(payload, monkeypatch):
    monkeypatch.setenv("RPG_RUNTIME_PROFILE", "legacy")
    client = TestClient(api.app, raise_server_exceptions=False)
    problems = _hammer(client, _body_routes() + RAW_BODY_ROUTES, PAYLOADS[payload], str(uuid4()))
    assert not problems, problems


@pytest.mark.parametrize("payload", list(PAYLOADS))
def test_malformed_body_no_leak_db_offline(payload, two_principals):
    tp = two_principals
    routes = [r for r in _body_routes() + RAW_BODY_ROUTES if not r[1].startswith("/internal")]
    problems = _hammer(tp.client_a, routes, PAYLOADS[payload], str(tp.game_a))
    assert not problems, problems


# --- R12: 500 genérico --------------------------------------------------------


def test_unhandled_500_is_generic(monkeypatch):
    monkeypatch.setenv("RPG_RUNTIME_PROFILE", "legacy")

    def boom(*_a, **_k):
        raise RuntimeError("segredo-interno C:\\x")

    monkeypatch.setattr(api, "load_game_state", boom)
    client = TestClient(api.app, raise_server_exceptions=False)
    out = client.get("/game/state")
    assert out.status_code == 500
    assert out.json() == {
        "detail": "internal_error",
        "code": "internal_error",
        "request_id": out.headers["x-request-id"],
    }
    assert "segredo-interno" not in out.text and "C:\\" not in out.text
