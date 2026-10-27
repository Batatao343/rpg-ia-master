"""SPEC-337 R5-R7: atributos de cookie lidos do ``Set-Cookie`` cru."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
from fastapi.testclient import TestClient

import api
from services.account_security import proof
from services.auth_sessions import CsrfSigner, SessionTokens
from tests.test_account_lifecycle_security import account_client  # noqa: F401  (fixture)

SECRET = "s" * 32

# nome -> (HttpOnly, SameSite, Path, Max-Age)
EXPECTED = {
    "rpg_access": (True, "lax", "/", None),
    "rpg_refresh": (True, "strict", "/auth/refresh", None),
    "rpg_csrf": (False, "strict", "/", None),
    "rpg_recent": (True, "strict", "/", "300"),
    "rpg_deletion": (True, "strict", "/account/delete", "604800"),
}
FLOWS = {
    "login": {"rpg_access", "rpg_refresh", "rpg_csrf", "rpg_recent"},
    "refresh": {"rpg_access", "rpg_refresh", "rpg_csrf"},
    "reauth": {"rpg_recent"},
    "delete": {"rpg_deletion"},
}


def parse_set_cookie(header: str) -> tuple[str, dict[str, str | bool]]:
    first, *attrs = [part.strip() for part in header.split(";")]
    name, _, value = first.partition("=")
    parsed: dict[str, str | bool] = {"value": value}
    for attr in attrs:
        key, sep, val = attr.partition("=")
        parsed[key.strip().lower()] = val.strip() if sep else True
    return name, parsed


def cookies_of(response) -> list[tuple[str, dict]]:
    return [parse_set_cookie(h) for h in response.headers.get_list("set-cookie")]


def _prime(client, a, *, secure_env: bool):
    """Cookies de entrada postos à mão (o jar do httpx não reenvia ``Secure`` por http)."""
    csrf = CsrfSigner(SECRET).issue()
    client.cookies.set("rpg_csrf", csrf)
    client.cookies.set("rpg_access", "a")
    client.cookies.set("rpg_refresh", "r1", path="/auth/refresh")
    client.cookies.set("rpg_recent", proof(a, "recent", "a"))
    return {"X-CSRF-Token": csrf}


def _fire(flow, client, identity, a, monkeypatch):
    headers = _prime(client, a, secure_env=False)
    if flow == "login":
        return client.post("/auth/login", json={"email": "a@test.test", "password": "long-password"})
    if flow == "refresh":
        monkeypatch.setattr(
            identity,
            "refresh",
            lambda _t: SessionTokens("a", "r2", datetime.now(UTC) + timedelta(hours=1), a),
        )
        return client.post("/auth/refresh", headers=headers)
    if flow == "reauth":
        return client.post("/auth/reauth", json={"password": "correct-password"}, headers=headers)
    if flow == "delete":

        class Lifecycle:
            def __init__(self, *_):
                pass

            def begin(self, owner):
                pass

            def finish(self, owner):
                return "deleting"

        monkeypatch.setattr("infrastructure.account_lifecycle.PostgresAccountLifecycle", Lifecycle)
        return client.post("/account/delete", json={"confirmation": "EXCLUIR"}, headers=headers)
    raise AssertionError(flow)


@pytest.mark.parametrize("secure", ["0", "1"], ids=["secure0", "secure1"])
@pytest.mark.parametrize("flow", list(FLOWS))
def test_cookie_attributes(flow, secure, account_client, monkeypatch):  # noqa: F811
    client, identity, a, _ = account_client
    monkeypatch.setenv("RPG_COOKIE_SECURE", secure)
    response = _fire(flow, client, identity, a, monkeypatch)
    assert response.status_code in {200, 202}, (flow, response.status_code, response.text)
    live = {
        name: attrs
        for name, attrs in cookies_of(response)
        if attrs.get("max-age") != "0" and not str(attrs.get("value")) == '""'
    }
    assert FLOWS[flow] <= set(live), (flow, sorted(live))
    for name in FLOWS[flow]:
        httponly, samesite, path, max_age = EXPECTED[name]
        attrs = live[name]
        assert bool(attrs.get("httponly")) is httponly, name
        assert str(attrs.get("samesite")).lower() == samesite, name
        assert attrs.get("path") == path, name
        assert attrs.get("max-age") == max_age, name
    for name, attrs in live.items():
        assert "domain" not in attrs, name
        assert bool(attrs.get("secure")) is (secure == "1"), name


def _cleared(response) -> dict[str, str]:
    """nome -> Path dos cookies emitidos com Max-Age=0."""
    return {
        name: str(attrs.get("path"))
        for name, attrs in cookies_of(response)
        if attrs.get("max-age") == "0"
    }


def test_logout_and_delete_clear_with_same_path(account_client, monkeypatch):  # noqa: F811
    client, identity, a, _ = account_client
    created = {name: EXPECTED[name][2] for name in EXPECTED}

    headers = _prime(client, a, secure_env=False)
    out = client.post("/auth/logout", headers=headers)
    assert out.status_code == 204
    cleared = _cleared(out)
    assert set(cleared) >= {"rpg_access", "rpg_refresh", "rpg_csrf", "rpg_recent", "rpg_deletion"}
    for name, path in cleared.items():
        assert path == created[name], name

    response = _fire("delete", client, identity, a, monkeypatch)
    cleared = _cleared(response)
    assert set(cleared) >= {"rpg_access", "rpg_refresh", "rpg_recent"}
    for name, path in cleared.items():
        assert path == created[name], name


@pytest.mark.parametrize("path", ["/auth/login", "/auth/refresh", "/auth/signup"])
def test_legacy_auth_routes_closed_without_set_cookie(path, monkeypatch):
    monkeypatch.setenv("RPG_RUNTIME_PROFILE", "legacy")
    monkeypatch.setenv("RPG_SESSION_SECRET", SECRET)
    client = TestClient(api.app, raise_server_exceptions=False)
    body = {"email": "a@test.test", "password": "long-password-1", "age_confirmed": True}
    response = client.post(path, json=body)
    # login/signup: 404 (api.py ``auth desativada``); refresh não tem esse guard, mas o CSRF
    # fecha antes de qualquer sessão (403): o que importa é nunca emitir cookie.
    expected = 403 if path == "/auth/refresh" else 404
    assert response.status_code == expected, (path, response.status_code)
    assert response.headers.get_list("set-cookie") == []
