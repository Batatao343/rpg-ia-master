"""SPEC-337 R8-R10: CORS e Origin (usa as origens default; ``api._CORS_ORIGINS`` é do import)."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

import api
from tests.fakes.two_principals import two_principals  # noqa: F401  (fixture)

GOOD = "http://localhost:5173"
EVIL = "https://evil.example"


@pytest.fixture
def legacy_client(monkeypatch):
    monkeypatch.setenv("RPG_RUNTIME_PROFILE", "legacy")
    return TestClient(api.app, raise_server_exceptions=False)


def test_default_origins_assumption():
    assert (
        GOOD in api._CORS_ORIGINS and EVIL not in api._CORS_ORIGINS and "*" not in api._CORS_ORIGINS
    )


def test_allowed_origin_gets_acao_with_credentials(legacy_client):
    out = legacy_client.get("/health", headers={"Origin": GOOD})
    assert out.headers["access-control-allow-origin"] == GOOD
    assert out.headers["access-control-allow-credentials"] == "true"
    assert "origin" in out.headers.get("vary", "").lower()


def test_unknown_origin_gets_no_acao(legacy_client):
    out = legacy_client.get("/health", headers={"Origin": EVIL})
    assert "access-control-allow-origin" not in out.headers
    assert legacy_client.get("/health").headers.get("access-control-allow-origin") != "*"


def _preflight(client, *, origin=GOOD, method="POST", headers="content-type"):
    req = {"Origin": origin, "Access-Control-Request-Method": method}
    if headers:
        req["Access-Control-Request-Headers"] = headers
    return client.options("/health", headers=req)


def test_preflight_allowed(legacy_client):
    out = _preflight(legacy_client)
    assert out.status_code == 200
    assert "POST" in out.headers["access-control-allow-methods"]
    assert out.headers["access-control-allow-origin"] == GOOD


@pytest.mark.parametrize(
    "kind,kwargs",
    [
        ("origin", {"origin": EVIL}),
        ("method", {"method": "PUT"}),
        ("header", {"headers": "x-evil"}),
    ],
)
def test_preflight_denied(kind, kwargs, legacy_client):
    out = _preflight(legacy_client, **kwargs)
    assert out.status_code == 400, kind
    if kind == "origin":
        assert "access-control-allow-origin" not in out.headers
    else:
        # Starlette ecoa o ACAO da origem permitida no 400 (o navegador reprova pelo status);
        # o que fecha o preflight é o 400 + motivo no corpo.
        assert "Disallowed CORS" in out.text
        assert "PUT" not in out.headers.get("access-control-allow-methods", "")
        assert "x-evil" not in out.headers.get("access-control-allow-headers", "").lower()


def _mutate(tp, origin):
    headers = {} if origin is None else {"Origin": origin}
    client = tp.client_a
    if origin is None:
        client.headers.pop("Origin", None)
    return client.post(
        "/game/equip",
        json={"unequip_slot": "weapon", "game_id": str(tp.game_a)},
        headers=headers,
    )


@pytest.mark.parametrize("origin", [EVIL, None, "null"], ids=["evil", "missing", "null"])
def test_mutation_origin_denied(origin, two_principals):
    out = _mutate(two_principals, origin)
    assert out.status_code == 403
    assert out.json()["detail"] == "origin_denied"


def test_mutation_allowed_origin_passes_boundary(two_principals):
    out = _mutate(two_principals, GOOD)
    assert out.status_code != 403, out.text
