"""SPEC-220: logout revoga refresh, erros 401/403 fechados, lockout só por falha, Origin no login."""
from __future__ import annotations

import ast
from datetime import UTC, datetime, timedelta
from pathlib import Path
from types import SimpleNamespace
from uuid import uuid4

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

import api
from infrastructure.contracts import Principal, Unauthorized
from infrastructure.local_adapters import MemoryRateLimiter
from services.auth_sessions import CsrfSigner, SessionTokens

ORIGIN = "http://localhost:5173"
SECRET = "s" * 32


class FakeIdentity:
    """Verificador falso: 'good'/'fresh' são acessos válidos; 'expired' não."""

    def __init__(self):
        self.owner = uuid4()
        self.logged_out: list[str] = []
        self.refreshed: list[str] = []
        self.revoked_all: list = []
        self.logins: list[str] = []
        self.valid_refresh = {"r1"}

    def verify(self, token):
        if token in {"good", "fresh"}:
            return Principal(self.owner, "auth", str(self.owner))
        raise Unauthorized("token inválido: detalhe interno xyz")

    def login(self, email, password):
        self.logins.append(email)
        if password != "correct-password":
            raise Unauthorized("credenciais inválidas")
        return SessionTokens("good", "r1", datetime.now(UTC) + timedelta(hours=1), self.owner)

    def refresh(self, token):
        self.refreshed.append(token)
        if token not in self.valid_refresh:
            raise Unauthorized("sessão inválida")
        self.valid_refresh.discard(token)
        return SessionTokens("fresh", "r2", datetime.now(UTC) + timedelta(hours=1), self.owner)

    def logout(self, access):
        if access not in {"good", "fresh"}:
            raise Unauthorized("sessão inválida")
        self.logged_out.append(access)

    def revoke_all(self, user_id):
        self.revoked_all.append(user_id)
        return True


@pytest.fixture
def hardened(monkeypatch):
    identity = FakeIdentity()
    runtime = SimpleNamespace(identity_verifier=identity, rate_limiter=MemoryRateLimiter())
    monkeypatch.setenv("RPG_SESSION_SECRET", SECRET)
    monkeypatch.setenv("RPG_AUTH_CAPTCHA_REQUIRED", "0")
    monkeypatch.setenv("RPG_AUTH_CAPTCHA_MODE", "app")
    monkeypatch.setattr(api, "_database_profile", lambda: True)
    monkeypatch.setattr("infrastructure.runtime.get_runtime", lambda: runtime)
    client = TestClient(api.app, raise_server_exceptions=False)
    client.headers["Origin"] = ORIGIN
    return client, identity, runtime


def _csrf(client) -> dict:
    token = CsrfSigner(SECRET).issue()
    client.cookies.set("rpg_csrf", token)
    return {"X-CSRF-Token": token}


# --- R1/R2: logout ----------------------------------------------------------

def test_logout_with_expired_access_leaves_no_500(hardened):
    client, identity, _ = hardened
    headers = _csrf(client)
    client.cookies.set("rpg_access", "expired")
    out = client.post("/auth/logout", headers=headers)
    assert out.status_code == 204


def test_logout_expired_access_uses_refresh_then_global_logout(hardened):
    client, identity, _ = hardened
    headers = _csrf(client)
    client.cookies.set("rpg_access", "expired")
    client.cookies.set("rpg_refresh", "r1", path="/auth/refresh")
    out = client.post("/auth/refresh/logout", headers=headers)
    assert out.status_code == 204
    assert identity.refreshed == ["r1"]
    assert identity.logged_out == ["fresh"]          # access derivado do refresh
    assert identity.revoked_all == [identity.owner]  # D-A: defesa extra
    set_cookies = out.headers.get_list("set-cookie")
    assert any(h.startswith("rpg_refresh=") and "Max-Age=0" in h for h in set_cookies)


def test_logout_with_invalid_refresh_is_still_204(hardened):
    client, identity, _ = hardened
    headers = _csrf(client)
    client.cookies.set("rpg_refresh", "stolen-and-rotated", path="/auth/refresh")
    out = client.post("/auth/refresh/logout", headers=headers)
    assert out.status_code == 204 and identity.logged_out == []


def test_logout_without_any_cookie_is_204(hardened):
    client, identity, _ = hardened
    out = client.post("/auth/logout", headers=_csrf(client))
    assert out.status_code == 204
    assert identity.logged_out == [] and identity.refreshed == []


def test_logout_revoke_all_when_available(hardened):
    client, identity, _ = hardened
    headers = _csrf(client)
    client.cookies.set("rpg_access", "good")
    assert client.post("/auth/logout", headers=headers).status_code == 204
    assert identity.logged_out == ["good"] and identity.revoked_all == [identity.owner]


def test_logout_upstream_failure_never_500(hardened, monkeypatch):
    import httpx
    client, identity, _ = hardened
    headers = _csrf(client)
    client.cookies.set("rpg_access", "good")

    def down(_access):
        raise httpx.ConnectError("auth upstream down")
    monkeypatch.setattr(identity, "logout", down)
    assert client.post("/auth/logout", headers=headers).status_code == 204


def test_logout_bad_csrf_403(hardened):
    client, _, _ = hardened
    client.cookies.set("rpg_access", "good")
    out = client.post("/auth/logout", headers={"X-CSRF-Token": "forged"})
    assert out.status_code == 403 and out.json()["detail"] == "csrf_invalid"
    no_origin = client.post("/auth/logout", headers={"Origin": ""})
    assert no_origin.status_code == 403 and no_origin.json()["detail"] in {"origin_denied", "csrf_invalid"}


# --- R3/R8/R10: códigos fechados ----------------------------------------------

def test_session_boundary_401_code_only(hardened):
    client, _, _ = hardened
    client.cookies.set("rpg_access", "expired")
    out = client.get("/account/balance")
    assert out.status_code == 401
    assert out.json()["detail"] == "session_invalid"
    assert "xyz" not in out.text


def test_game_mutation_bad_csrf_is_403_not_401(hardened):
    client, _, _ = hardened
    client.cookies.set("rpg_access", "good")
    out = client.post("/game/new", json={}, headers={"X-CSRF-Token": "forged"})
    assert out.status_code == 403 and out.json()["detail"] == "csrf_invalid"


def test_short_session_secret_is_503_without_internal_message(hardened, monkeypatch):
    client, _, _ = hardened
    client.cookies.set("rpg_access", "good")
    monkeypatch.setenv("RPG_SESSION_SECRET", "short")
    out = client.post("/game/new", json={}, headers={"X-CSRF-Token": "x"})
    assert out.status_code == 503 and out.json()["detail"] == "server_misconfigured"
    out = client.post("/auth/logout", headers={"X-CSRF-Token": "x"})
    assert out.status_code == 503 and out.json()["detail"] == "server_misconfigured"


def test_session_boundary_handler_value_error_is_500_not_401(monkeypatch, hardened):
    _, identity, _ = hardened
    app = FastAPI()
    app.middleware("http")(api._session_boundary)

    @app.get("/game/_raise_value_error")
    def boom():
        raise ValueError("segredo interno do handler")

    client = TestClient(app, raise_server_exceptions=False)
    client.cookies.set("rpg_access", "good")
    out = client.get("/game/_raise_value_error")
    assert out.status_code == 500
    assert "segredo interno" not in out.text


def test_auth_error_codes_closed_set():
    """Toda string passada a Unauthorized(...) no código vira um código público fechado."""
    from infrastructure.contracts import AUTH_ERROR_CODES, public_auth_code

    root = Path(__file__).resolve().parents[1]
    literals = set()
    for path in root.rglob("*.py"):
        if any(part in {".venv", "node_modules", "tests", ".git"} for part in path.parts):
            continue
        try:
            tree = ast.parse(path.read_text(encoding="utf-8"))
        except (SyntaxError, UnicodeDecodeError):
            continue
        for node in ast.walk(tree):
            if (isinstance(node, ast.Call) and getattr(node.func, "id", None) in {"Unauthorized", "CsrfError"}
                    and node.args and isinstance(node.args[0], ast.Constant)):
                literals.add(node.args[0].value)
    assert literals, "AST scan must find Unauthorized(...) call sites"
    for literal in literals:
        assert public_auth_code(Unauthorized(literal)) in AUTH_ERROR_CODES, literal
    assert public_auth_code(Unauthorized("sessão ausente")) == "session_missing"
    assert public_auth_code(Unauthorized("qualquer coisa interna")) == "session_invalid"


def test_auth_routes_never_5xx_on_client_garbage(hardened):
    client, _, _ = hardened
    cases = [
        ("/auth/logout", {}), ("/auth/refresh/logout", {}), ("/auth/refresh", {}),
        ("/auth/reauth", {"password": "whatever-123"}),
    ]
    for cookies in ({}, {"rpg_access": ""}, {"rpg_access": "garbage", "rpg_csrf": "a.b"},
                    {"rpg_refresh": "x", "rpg_csrf": ""}):
        client.cookies.clear()
        for key, value in cookies.items():
            client.cookies.set(key, value)
        for headers in ({}, {"X-CSRF-Token": ""}, {"X-CSRF-Token": "a.b"}, {"Origin": "https://evil.test"}):
            for path, body in cases:
                out = client.post(path, json=body, headers=headers)
                assert out.status_code < 500 or out.status_code == 404, (path, cookies, headers, out.text)


# --- R4: lockout só por falha ---------------------------------------------------

def _login(client, password="correct-password", email="victim@test.test"):
    return client.post("/auth/login", json={"email": email, "password": password})


def test_login_success_does_not_consume_email_bucket(hardened):
    client, _, _ = hardened
    for _ in range(12):
        assert _login(client).status_code == 200


def test_login_failures_lock_after_10(hardened):
    client, identity, _ = hardened
    for _ in range(10):
        assert _login(client, "wrong-password").status_code == 401
    locked = _login(client, "wrong-password")
    assert locked.status_code == 429 and locked.json()["detail"] == "auth_rate_limit"
    calls = len(identity.logins)
    assert _login(client).status_code == 429      # bloqueado antes de tocar o IdP
    assert len(identity.logins) == calls


def test_login_success_resets_email_bucket(hardened):
    client, _, _ = hardened
    for _ in range(3):
        assert _login(client, "wrong-password").status_code == 401
    assert _login(client).status_code == 200
    for _ in range(10):
        assert _login(client, "wrong-password").status_code == 401
    assert _login(client, "wrong-password").status_code == 429


def test_login_failure_response_is_closed_code(hardened):
    client, _, _ = hardened
    out = _login(client, "wrong-password")
    assert out.json()["detail"] == "credentials_invalid"


def test_signup_bucket_is_email_ip_composite():
    from fastapi import HTTPException

    from services.account_security import auth_limit

    runtime = SimpleNamespace(rate_limiter=MemoryRateLimiter())

    def req(ip):
        return SimpleNamespace(client=SimpleNamespace(host=ip))
    for _ in range(5):
        auth_limit(runtime, req("10.0.0.1"), action="signup", email="v@test.test")
    with pytest.raises(HTTPException) as exc:
        auth_limit(runtime, req("10.0.0.1"), action="signup", email="v@test.test")
    assert exc.value.status_code == 429
    auth_limit(runtime, req("10.0.0.2"), action="signup", email="V@Test.Test")  # outro IP passa


def test_reset_email_only_bucket_blocks_bombing_from_many_ips():
    from fastapi import HTTPException

    from services.account_security import auth_limit

    runtime = SimpleNamespace(rate_limiter=MemoryRateLimiter())
    for index in range(20):
        auth_limit(runtime, SimpleNamespace(client=SimpleNamespace(host=f"10.1.0.{index}")),
                   action="reset", email="v@test.test")
    with pytest.raises(HTTPException):
        auth_limit(runtime, SimpleNamespace(client=SimpleNamespace(host="10.1.1.1")),
                   action="reset", email="v@test.test")
    # O bucket de reset nunca bloqueia o login da vítima.
    auth_limit(runtime, SimpleNamespace(client=SimpleNamespace(host="10.1.1.1")),
               action="login", email="v@test.test")


def test_bucket_keys_cover_new_address_derived_buckets():
    from services.account_security import auth_email_bucket_keys, auth_email_bucket_prefixes

    keys = auth_email_bucket_keys("V@Test.Test")
    assert any(key.startswith("auth:login:email:") for key in keys)
    assert all(prefix.endswith(":") for prefix in auth_email_bucket_prefixes("v@test.test"))
    assert auth_email_bucket_prefixes("V@Test.Test") == auth_email_bucket_prefixes("v@test.test")


# --- R5: Origin no login modo app ----------------------------------------------

def test_login_app_mode_requires_origin(hardened):
    client, identity, _ = hardened
    for origin in ("", "https://evil.test"):
        out = client.post("/auth/login", json={"email": "a@test.test", "password": "correct-password"},
                          headers={"Origin": origin})
        assert out.status_code == 403 and out.json()["detail"] == "origin_denied"
    assert identity.logins == []


# --- R9: senha mínima ---------------------------------------------------------

def test_signup_requires_10_chars_but_login_keeps_legacy_passwords(hardened, monkeypatch):
    client, identity, _ = hardened
    assert client.post("/auth/signup", json={"email": "n@test.test", "password": "123456789"}).status_code == 422
    monkeypatch.setattr(identity, "login", lambda email, password: SessionTokens(
        "good", "r1", datetime.now(UTC) + timedelta(hours=1), identity.owner))
    assert client.post("/auth/login", json={"email": "o@test.test", "password": "8chars!!"}).status_code == 200
    assert client.post("/auth/reset/confirm", json={"token_hash": "x" * 12,
                                                    "new_password": "123456789"}).status_code == 422


# --- R9: política declarada do Auth remoto (passo do dono aplicar) -------------

def test_staging_auth_config_declares_session_policy_and_rejects_loose_redirects():
    from scripts.staging import auth_config, common

    env = {"RPG_STAGING_TURNSTILE_SECRET": "x", "RPG_STAGING_SITE_URL": "https://stg.example.app"}
    cfg = auth_config.desired_config(env)
    assert cfg["password_min_length"] >= 10 and cfg["refresh_token_rotation_enabled"] is True
    assert cfg["security_refresh_token_reuse_interval"] == 10 and cfg["jwt_exp"] == 3600
    assert cfg["security_update_password_require_reauthentication"] is True
    assert cfg["disable_signup"] is False
    assert "password_min_length" in auth_config.diff_config({}, cfg)
    for bad in ("https://*.example.app", "http://stg.example.app/cb"):
        with pytest.raises((common.GuardError, SystemExit)):
            auth_config.desired_config({**env, "RPG_STAGING_REDIRECT_URLS": bad})
    auth_config.desired_config({**env, "RPG_STAGING_REDIRECT_URLS": "http://localhost:5173,https://stg.example.app"})
    toml = (Path(__file__).resolve().parents[1] / "supabase" / "config.toml").read_text(encoding="utf-8")
    assert "minimum_password_length = 10" in toml


def test_login_failure_lockout_is_per_email_and_ip_so_victim_is_not_dosed():
    """Revisão Sol: 10 falhas de um IP atacante não trancam a vítima em outro IP."""
    from fastapi import HTTPException

    from services.account_security import auth_limit, auth_success

    runtime = SimpleNamespace(rate_limiter=MemoryRateLimiter())
    attacker = SimpleNamespace(client=SimpleNamespace(host="203.0.113.9"))
    victim = SimpleNamespace(client=SimpleNamespace(host="198.51.100.7"))
    for _ in range(10):
        auth_limit(runtime, attacker, action="login", email="v@test.test")
        try:
            auth_limit(runtime, attacker, action="login", email="v@test.test", stage="failure")
        except HTTPException:
            pass
    with pytest.raises(HTTPException) as exc:
        auth_limit(runtime, attacker, action="login", email="v@test.test")
    assert exc.value.status_code == 429
    auth_limit(runtime, victim, action="login", email="V@Test.Test")  # vítima entra
    auth_success(runtime, action="login", email="v@test.test", request=victim)
    with pytest.raises(HTTPException):  # sucesso da vítima não destrava o atacante
        auth_limit(runtime, attacker, action="login", email="v@test.test")
