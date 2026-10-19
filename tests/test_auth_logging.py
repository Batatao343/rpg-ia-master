"""SPEC-245: toda rejeição de auth deixa uma linha com motivo interno fechado, sem PII."""

import base64
import json
import time
from datetime import UTC, datetime, timedelta

import httpx
import pytest

from infrastructure.contracts import AuthUnavailable, Unauthorized, public_auth_code
from infrastructure.supabase_identity import SupabaseIdentityProvider
from observability import logging_setup
from observability.auth_log import session_reason
from tests.test_account_lifecycle_security import account_client  # noqa: F401  (fixture)

EMAIL = "sentinel.user@example.test"


@pytest.fixture(autouse=True)
def _logs():
    logging_setup.configure_logging({"RPG_LOG_LEVEL": "debug", "RPG_LOG_PROPAGATE": "1"})


def _lines(capsys, prefix="auth."):
    out = capsys.readouterr().out
    assert EMAIL not in out and "sentinel.user" not in out  # R7: nenhum e-mail
    return [
        json.loads(x)
        for x in out.splitlines()
        if x.startswith("{") and json.loads(x).get("event", "").startswith(prefix)
    ]


def _gotrue(status, error_code):
    return lambda url, **_kw: httpx.Response(
        status, json={"code": status, "error_code": error_code, "msg": f"{EMAIL} private message"}
    )


def test_login_400_logs_upstream_code_not_email(monkeypatch, capsys):
    monkeypatch.setattr(httpx, "post", _gotrue(400, "email_not_confirmed"))
    provider = SupabaseIdentityProvider("https://auth.test", "publishable")
    with pytest.raises(Unauthorized) as exc:
        provider.login(EMAIL, "password-123", captcha_token="t")
    assert public_auth_code(exc.value) == "email_not_confirmed"
    (line,) = _lines(capsys)
    assert line["event"] == "auth.upstream" and line["op"] == "login"
    assert line["upstream_status"] == 400 and line["upstream_code"] == "email_not_confirmed"
    assert line["public_code"] == "email_not_confirmed" and line["level"] == "warning"
    assert isinstance(line["duration_ms"], int)


def test_unknown_gotrue_code_is_bucketed_as_other(monkeypatch, capsys):
    monkeypatch.setattr(httpx, "post", _gotrue(400, EMAIL))
    with pytest.raises(Unauthorized):
        SupabaseIdentityProvider("https://auth.test", "publishable").login(EMAIL, "password-123")
    (line,) = _lines(capsys)
    assert line["upstream_code"] == "other"


def test_timeout_returns_503_and_logs(monkeypatch, capsys, account_client):  # noqa: F811
    def boom(url, **_kw):
        raise httpx.ReadTimeout("slow " + EMAIL)

    monkeypatch.setattr(httpx, "post", boom)
    with pytest.raises(AuthUnavailable):
        SupabaseIdentityProvider("https://auth.test", "publishable").login(EMAIL, "password-123")
    (line,) = _lines(capsys)
    assert line["upstream_status"] == 0 and line["error_type"] == "ReadTimeout"
    assert line["level"] == "error" and line["public_code"] == "auth_unavailable"
    # rota: AuthUnavailable => 503 fechado (nunca 500)
    client, identity, _, _ = account_client

    def login(email, password):
        raise AuthUnavailable("auth_unavailable")

    monkeypatch.setattr(identity, "login", login)
    r = client.post("/auth/login", json={"email": EMAIL, "password": "password-123"})
    assert r.status_code == 503 and r.json()["detail"] == "auth_unavailable"
    assert r.headers["X-Request-ID"]


def _jwt(exp, aud="authenticated", iss="https://auth.test/auth/v1"):
    def enc(obj):
        return base64.urlsafe_b64encode(json.dumps(obj).encode()).decode().rstrip("=")

    return f"{enc({'alg': 'ES256'})}.{enc({'exp': exp, 'aud': aud, 'iss': iss})}.sig"


def test_prevalidate_reasons():
    provider = SupabaseIdentityProvider("https://auth.test", "publishable")
    with pytest.raises(Unauthorized) as expired:
        provider._prevalidate(_jwt(time.time() - 3600))
    assert session_reason(expired.value) == "expired"
    with pytest.raises(Unauthorized) as aud:
        provider._prevalidate(_jwt(time.time() + 3600, aud="other"))
    assert session_reason(aud.value) == "bad_aud_iss"
    with pytest.raises(Unauthorized) as junk:
        provider._prevalidate("not-a-jwt")
    assert session_reason(junk.value) == "bad_signature"


def test_session_expired_reason(account_client, capsys, monkeypatch):  # noqa: F811
    client, identity, _, _ = account_client

    def verify(token):
        raise Unauthorized("sessão revogada")

    monkeypatch.setattr(identity, "verify", verify)
    client.cookies.set("rpg_access", "zzz")
    r = client.get("/game/saves", headers={"X-Request-ID": "sess-rej-0001"})
    assert r.status_code == 401
    lines = _lines(capsys, "auth.session_rejected")
    assert len(lines) == 1
    assert lines[0]["reason"] == "revoked" and lines[0]["route"] == "/game/saves"
    assert (
        lines[0]["request_id"] == "sess-rej-0001" and lines[0]["public_code"] == "session_invalid"
    )


def test_missing_session_without_cookie_is_debug_only(account_client, capsys, monkeypatch):  # noqa: F811
    client, identity, *_ = account_client

    def verify(token):
        raise Unauthorized("sessão ausente")

    monkeypatch.setattr(identity, "verify", verify)
    client.cookies.clear()
    r = client.get("/game/saves")
    assert r.status_code == 401
    (line,) = _lines(capsys, "auth.session_rejected")
    assert line["reason"] == "missing" and line["level"] == "debug"


def test_csrf_reason(account_client, capsys):  # noqa: F811
    client, *_ = account_client
    client.cookies.set("rpg_access", "a")
    r = client.post("/game/equip", json={"game_id": "x"})
    assert r.status_code == 403
    (line,) = _lines(capsys, "auth.csrf_rejected")
    assert line["reason"] == "csrf_missing" and line["origin_host"] == "localhost:5173"
    r = client.post(
        "/game/equip", json={"game_id": "x"}, headers={"Origin": "https://evil.example"}
    )
    assert r.status_code == 403
    (line,) = _lines(capsys, "auth.csrf_rejected")
    assert line["reason"] == "origin_denied" and line["origin_host"] == "other"
    assert "evil" not in json.dumps(line)


def test_turnstile_outage_reason_provider_unavailable(monkeypatch, capsys):
    from services import account_security

    monkeypatch.setenv("RPG_AUTH_CAPTCHA_MODE", "app")
    monkeypatch.setenv("RPG_AUTH_CAPTCHA_REQUIRED", "1")
    monkeypatch.setenv("RPG_TURNSTILE_SITE_KEY", "site")
    monkeypatch.setenv("RPG_TURNSTILE_SECRET", "secret-value-123")

    def down(url, **_kw):
        raise httpx.ConnectError("cloudflare down")

    monkeypatch.setattr(httpx, "post", down)
    with pytest.raises(Unauthorized) as exc:
        account_security.validate_captcha("tok", remote_ip="203.0.113.7", action="signup")
    assert public_auth_code(exc.value) == "captcha_invalid"
    (line,) = _lines(capsys, "auth.captcha_rejected")
    assert line["reason"] == "provider_unavailable" and line["op"] == "signup"
    assert "203.0.113.7" not in json.dumps(line) and "secret-value" not in json.dumps(line)


def test_turnstile_error_codes_and_mismatch(monkeypatch, capsys):
    from services import account_security

    monkeypatch.setenv("RPG_AUTH_CAPTCHA_MODE", "app")
    monkeypatch.setenv("RPG_AUTH_CAPTCHA_REQUIRED", "1")
    monkeypatch.setenv("RPG_TURNSTILE_SITE_KEY", "site")
    monkeypatch.setenv("RPG_TURNSTILE_SECRET", "secret-value-123")
    monkeypatch.setenv("RPG_CORS_ORIGINS", "https://ok.example")
    monkeypatch.setattr(
        httpx,
        "post",
        lambda url, **_kw: httpx.Response(
            200, json={"success": False, "error-codes": ["timeout-or-duplicate", "Weird Value!"]}
        ),
    )
    with pytest.raises(Unauthorized):
        account_security.validate_captcha("tok", remote_ip="1.1.1.1", action="signup")
    (line,) = _lines(capsys, "auth.captcha_rejected")
    assert line["reason"] == "turnstile_error:timeout-or-duplicate"
    monkeypatch.setattr(
        httpx,
        "post",
        lambda url, **_kw: httpx.Response(
            200, json={"success": True, "hostname": "evil.example", "action": "signup"}
        ),
    )
    with pytest.raises(Unauthorized):
        account_security.validate_captcha("tok", remote_ip="1.1.1.1", action="signup")
    assert _lines(capsys, "auth.captcha_rejected")[0]["reason"] == "hostname_mismatch"


def test_lockout_logged_with_key_ref(capsys):
    from types import SimpleNamespace

    from fastapi import HTTPException

    from infrastructure.local_adapters import MemoryRateLimiter
    from observability.telemetry import pseudonym
    from services.account_security import LOGIN_EMAIL_FAILURES, _login_failure_key, auth_limit

    runtime = SimpleNamespace(rate_limiter=MemoryRateLimiter())
    request = SimpleNamespace(headers={}, client=SimpleNamespace(host="198.51.100.9"), cookies={})
    for _ in range(LOGIN_EMAIL_FAILURES[0]):
        auth_limit(runtime, request, action="login", email=EMAIL, stage="failure")
    blocked = 0
    for _ in range(3):
        with pytest.raises(HTTPException) as exc:
            auth_limit(runtime, request, action="login", email=EMAIL, stage="failure")
        assert exc.value.status_code == 429
        blocked += 1
    lines = _lines(capsys, "auth.rate_limited")
    assert len(lines) == 1  # amostrado: 1 linha por key_ref por minuto
    line = lines[0]
    key = _login_failure_key(EMAIL, "198.51.100.9")
    assert line["key_ref"] == pseudonym(key) and key.split(":")[-1] not in json.dumps(line)
    assert line["op"] == "login" and line["bucket"] == "email" and line["retry_after_s"] > 0
    assert "198.51.100.9" not in json.dumps(line)
    from observability.metrics import metrics

    assert metrics.snapshot()["rpg_auth_rejections_total{'reason': 'rate_limited'}"] >= blocked


def test_no_email_in_any_auth_log(monkeypatch, capsys, account_client):  # noqa: F811
    client, identity, _, _ = account_client
    monkeypatch.setattr(httpx, "post", _gotrue(400, "invalid_credentials"))
    real = SupabaseIdentityProvider("https://auth.test", "publishable")
    with pytest.raises(Unauthorized):
        real.login(EMAIL, "password-123")
    client.post(
        "/auth/signup", json={"email": EMAIL, "password": "password-123", "age_confirmed": True}
    )
    _lines(capsys, "")  # a asserção de sentinela roda dentro de _lines
