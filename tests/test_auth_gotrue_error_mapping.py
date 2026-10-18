"""Auth debug 2026-10-18: GoTrue error codes reach the client as stable, non-enumerating codes.

Staging evidence: an unconfirmed account logged in with the right password and got the raw
``credentials_invalid``; a stale Turnstile token on login was also reported as wrong credentials
(and counted toward the per-address lockout). Neither case depends on account existence for
captcha, and ``email_not_confirmed`` is only returned by GoTrue after the password matched.
"""
from datetime import UTC, datetime, timedelta

import httpx
import pytest

from infrastructure.contracts import AUTH_ERROR_CODES, Unauthorized, public_auth_code
from infrastructure.supabase_identity import AuthEmailDeliveryError, SupabaseIdentityProvider
from services.account_security import GENERIC_MESSAGE
from services.auth_sessions import SessionTokens
from tests.test_account_lifecycle_security import account_client  # noqa: F401  (fixture)


def gotrue(status, error_code, msg="x"):
    return lambda url, **_kwargs: httpx.Response(status, json={"code": status, "error_code": error_code, "msg": msg})


@pytest.mark.parametrize("error_code,expected", [
    ("email_not_confirmed", "email_not_confirmed"),
    ("captcha_failed", "captcha_invalid"),
    ("invalid_credentials", "credentials_invalid"),
    ("unexpected_failure", "credentials_invalid"),
])
def test_login_maps_gotrue_error_codes(monkeypatch, error_code, expected):
    monkeypatch.setattr(httpx, "post", gotrue(400, error_code))
    identity = SupabaseIdentityProvider("https://auth.test", "publishable")
    with pytest.raises(Unauthorized) as exc:
        identity.login("a@example.test", "password-123", captcha_token="t")
    assert public_auth_code(exc.value) == expected


def test_login_non_json_failure_is_credentials_invalid(monkeypatch):
    monkeypatch.setattr(httpx, "post", lambda url, **_kw: httpx.Response(502, text="<html>bad gateway</html>"))
    with pytest.raises(Unauthorized) as exc:
        SupabaseIdentityProvider("https://auth.test", "publishable").login("a@example.test", "pw-12345678")
    assert public_auth_code(exc.value) == "credentials_invalid"


def test_signup_and_email_requests_surface_captcha_failure(monkeypatch):
    monkeypatch.setattr(httpx, "post", gotrue(400, "captcha_failed"))
    identity = SupabaseIdentityProvider("https://auth.test", "publishable")
    with pytest.raises(Unauthorized) as signup:
        identity.signup("a@example.test", "password-123", captcha_token="t")
    assert public_auth_code(signup.value) == "captcha_invalid"
    for recovery in (True, False):
        with pytest.raises(Unauthorized) as email:
            identity.request_email("a@example.test", recovery=recovery, captcha_token="t")
        assert public_auth_code(email.value) == "captcha_invalid"


def test_email_request_smtp_failure_stays_a_delivery_error(monkeypatch):
    monkeypatch.setattr(httpx, "post", gotrue(500, "unexpected_failure", '535 "Authentication credentials invalid"'))
    with pytest.raises(AuthEmailDeliveryError) as exc:
        SupabaseIdentityProvider("https://auth.test", "publishable").request_email(
            "a@example.test", recovery=True, captcha_token="t")
    assert exc.value.status_class == "5xx"


def test_new_codes_are_public():
    assert {"email_not_confirmed", "captcha_invalid"} <= AUTH_ERROR_CODES


def _gotrue_mode(monkeypatch):
    monkeypatch.setenv("RPG_AUTH_CAPTCHA_MODE", "gotrue")
    monkeypatch.setenv("RPG_AUTH_CAPTCHA_REQUIRED", "1")
    monkeypatch.setenv("RPG_TURNSTILE_SITE_KEY", "public-site-key")


def test_login_route_reports_unconfirmed_and_captcha_without_lockout(account_client, monkeypatch):  # noqa: F811
    client, identity, _, _ = account_client
    _gotrue_mode(monkeypatch)
    outcome = {"code": "email_not_confirmed"}

    def login(email, password, *, captcha_token):
        if outcome["code"]:
            raise Unauthorized(outcome["code"])
        return SessionTokens("a", "refresh-private", datetime.now(UTC) + timedelta(hours=1),
                             identity.verify("a").user_id)
    monkeypatch.setattr(identity, "login", login)
    body = {"email": "a@test.test", "password": "password-123", "captcha_token": "t"}
    # Many non-credential failures must not lock the address out (only credential failures count).
    for _ in range(8):
        r = client.post("/auth/login", json=body)
        assert r.status_code == 401 and {k: v for k, v in r.json().items() if k != "request_id"} == {"detail": "email_not_confirmed"}
    outcome["code"] = "captcha_invalid"
    for _ in range(8):
        r = client.post("/auth/login", json=body)
        assert r.status_code == 403 and {k: v for k, v in r.json().items() if k != "request_id"} == {"detail": "captcha_invalid"}
    outcome["code"] = None
    assert client.post("/auth/login", json=body).status_code == 200


def test_signup_and_reset_routes_report_captcha_failure_not_generic_success(account_client, monkeypatch):  # noqa: F811
    client, identity, _, _ = account_client
    _gotrue_mode(monkeypatch)

    def captcha_failed(*_args, **_kwargs):
        raise Unauthorized("captcha_invalid")
    monkeypatch.setattr(identity, "signup", captcha_failed)
    monkeypatch.setattr(identity, "request_email", captcha_failed)
    r = client.post("/auth/signup", json={"email": "a@test.test", "password": "password-123",
                                          "age_confirmed": True, "captcha_token": "t"})
    assert r.status_code == 403 and {k: v for k, v in r.json().items() if k != "request_id"} == {"detail": "captcha_invalid"}
    for path in ("/auth/reset/request", "/auth/verify/request"):
        r = client.post(path, json={"email": "a@test.test", "captcha_token": "t"})
        assert r.status_code == 403 and {k: v for k, v in r.json().items() if k != "request_id"} == {"detail": "captcha_invalid"}

    def other_failure(*_args, **_kwargs):
        raise Unauthorized("não foi possível criar a conta")
    monkeypatch.setattr(identity, "signup", other_failure)
    r = client.post("/auth/signup", json={"email": "a@test.test", "password": "password-123",
                                          "age_confirmed": True, "captcha_token": "t"})
    assert r.status_code == 202 and r.json()["message"] == GENERIC_MESSAGE
