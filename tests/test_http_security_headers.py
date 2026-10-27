"""SPEC-337 R1-R4: headers de segurança em cada superfície HTTP real."""

from __future__ import annotations

from uuid import uuid4

import pytest
from fastapi.routing import APIRoute
from fastapi.testclient import TestClient

import api
from tests.fakes.two_principals import (  # noqa: F401  (fixtures)
    HSTS_VALUE,
    assert_security_headers,
    spa_mount,
    two_principals,
)

PROFILES = ("legacy", "local")


@pytest.fixture
def client_factory(monkeypatch):
    def make(profile: str = "legacy") -> TestClient:
        monkeypatch.setenv("RPG_RUNTIME_PROFILE", profile)
        return TestClient(api.app, raise_server_exceptions=False)

    return make


def _boom(*_a, **_k):
    raise RuntimeError("segredo-interno C:\\x")


def _surface_response(name: str, monkeypatch, client_factory, two_principals_fixture=None):
    """Executa a requisição da superfície ``name``. Retorna ``(response, path)``."""
    ghost = str(uuid4())
    if name == "health":
        return client_factory().get("/health"), "/health"
    if name == "spa_index":
        return client_factory().get("/"), "/"
    if name == "spa_asset":
        return client_factory().get("/assets/x.js"), "/assets/x.js"
    if name == "not_found":
        return client_factory().get("/nao-existe"), "/nao-existe"
    if name == "api_404":
        return client_factory().get("/game/state", params={"game_id": ghost}), "/game/state"
    if name == "validation_422":
        return client_factory().post("/auth/login", json={"x": 1}), "/auth/login"
    if name == "body_413":
        big = b'{"input_text":"' + b"a" * (300 * 1024) + b'"}'
        return (
            client_factory().post(
                "/game/action", content=big, headers={"content-type": "application/json"}
            ),
            "/game/action",
        )
    if name == "rate_429":
        monkeypatch.setenv("RPG_RATE_LIMIT", "1")
        api._rate_hits.clear()
        client = client_factory()
        last = None
        for _ in range(4):
            last = client.post("/game/action", json={})
        return last, "/game/action"
    if name == "server_500":
        monkeypatch.setattr(api, "load_game_state", _boom)
        return client_factory().get("/game/state"), "/game/state"
    if name == "stream":
        return (
            client_factory().post(
                "/game/action/stream", json={"input_text": "oi", "game_id": ghost}
            ),
            "/game/action/stream",
        )
    tp = two_principals_fixture
    if name == "db_401":
        anon = TestClient(api.app, raise_server_exceptions=False)
        return anon.get("/game/state", params={"game_id": str(tp.game_a)}), "/game/state"
    if name == "db_403_origin":
        resp = tp.client_a.post(
            "/game/equip",
            json={"unequip_slot": "weapon", "game_id": str(tp.game_a)},
            headers={"Origin": "https://evil.example"},
        )
        assert resp.status_code == 403
        return resp, "/game/equip"
    raise AssertionError(name)


_LEGACY_SURFACES = [
    "health",
    "spa_index",
    "spa_asset",
    "not_found",
    "api_404",
    "validation_422",
    "body_413",
    "rate_429",
    "server_500",
    "stream",
]
_DB_SURFACES = ["db_401", "db_403_origin"]
_EXPECTED = {
    "api_404": 404,
    "validation_422": 422,
    "body_413": 413,
    "rate_429": 429,
    "server_500": 500,
    "not_found": 404,
}


def _run(name, monkeypatch, client_factory, request):
    needs_spa = name in {"spa_index", "spa_asset"}
    if needs_spa:
        request.getfixturevalue("spa_mount")
    tp = request.getfixturevalue("two_principals") if name in _DB_SURFACES else None
    response, path = _surface_response(name, monkeypatch, client_factory, tp)
    if name in _EXPECTED:
        assert response.status_code == _EXPECTED[name], (name, response.status_code)
    return response, path


@pytest.mark.parametrize("hsts", [False, True], ids=["plain", "hsts"])
@pytest.mark.parametrize("name", _LEGACY_SURFACES + _DB_SURFACES)
def test_security_headers_on_every_surface(name, hsts, monkeypatch, client_factory, request):
    monkeypatch.setenv("RPG_COOKIE_SECURE", "1" if hsts else "0")
    response, path = _run(name, monkeypatch, client_factory, request)
    assert_security_headers(response, path=path, hsts=hsts)  # R1 + R3


_NO_STORE_YES = ["api_404", "validation_422", "body_413", "rate_429", "server_500", "stream"]
_NO_STORE_NO = ["health", "spa_index", "spa_asset", "not_found"]


@pytest.mark.parametrize("name", _NO_STORE_YES + _NO_STORE_NO + _DB_SURFACES)
def test_no_store_on_session_paths_only(name, monkeypatch, client_factory, request):
    response, path = _run(name, monkeypatch, client_factory, request)
    if path.startswith(("/game", "/account", "/auth")):
        assert response.headers.get("cache-control") == "no-store", (name, path)
    else:
        assert response.headers.get("cache-control") != "no-store", (name, path)


def test_no_store_on_data_map_with_game_only(client_factory):
    client = client_factory()
    with_game = client.get("/data/map", params={"game_id": str(uuid4())})
    assert with_game.headers.get("cache-control") == "no-store"
    assert client.get("/data/options").headers.get("cache-control") != "no-store"


def test_docs_paths_have_no_csp(monkeypatch, client_factory):
    monkeypatch.setattr(api, "_DOCS_PATHS", {"/docs"})
    response = client_factory().get("/docs")
    assert "content-security-policy" not in response.headers
    assert response.headers.get("x-frame-options") == "DENY"


def test_hsts_absent_without_secure_cookie(monkeypatch, client_factory):
    monkeypatch.setenv("RPG_COOKIE_SECURE", "0")
    assert "strict-transport-security" not in client_factory().get("/health").headers
    monkeypatch.setenv("RPG_COOKIE_SECURE", "1")
    assert client_factory().get("/health").headers["strict-transport-security"] == HSTS_VALUE


def _sweepable(route: APIRoute) -> bool:
    if "{" in route.path or route.path.startswith(("/internal", "/docs", "/redoc", "/openapi")):
        return False
    return "GET" in route.methods or bool(route.body_field and "POST" in route.methods)


def test_no_route_overrides_frame_or_csp(client_factory):
    """R4: nenhum handler enfraquece XFO/CSP (um ``setdefault`` vencido apareceria aqui)."""
    client = client_factory()
    seen = 0
    for route in api.app.routes:
        if not isinstance(route, APIRoute) or not _sweepable(route):
            continue
        if "GET" in route.methods:
            response = client.get(route.path)
        else:
            response = client.post(route.path, json={"__probe__": 1})
        assert response.headers.get("x-frame-options") == "DENY", route.path
        assert response.headers.get("content-security-policy") == api.CONTENT_SECURITY_POLICY, (
            route.path
        )
        seen += 1
    assert seen > 20
