"""GoTrue transport contracts used by the account lifecycle endpoints."""
from datetime import UTC, datetime, timedelta
from uuid import uuid4

import httpx
import pytest

from infrastructure.contracts import Principal, Unauthorized
from infrastructure.supabase_identity import AuthEmailDeliveryError, SupabaseIdentityProvider
from services.auth_sessions import SessionTokens


def test_email_requests_have_fixed_endpoints_and_no_secret_or_bearer(monkeypatch):
    calls = []

    def post(url, **kwargs):
        calls.append((url, kwargs))
        return httpx.Response(404, json={"msg": "account absent"})

    monkeypatch.setattr(httpx, "post", post)
    identity = SupabaseIdentityProvider("https://auth.test/", "publishable")
    with pytest.raises(AuthEmailDeliveryError) as first:
        identity.request_email("absent@example.test", recovery=False)
    with pytest.raises(AuthEmailDeliveryError) as second:
        identity.request_email("absent@example.test", recovery=True)
    assert first.value.status_class=="4xx" and second.value.status_class=="4xx"
    assert "absent@example.test" not in str(first.value)
    assert [url.rsplit("/", 1)[-1] for url, _ in calls] == ["resend", "recover"]
    assert [call["json"] for _, call in calls] == [
        {"email": "absent@example.test", "type": "signup"},
        {"email": "absent@example.test"},
    ]
    assert all(call["headers"] == {"apikey": "publishable", "Content-Type": "application/json"}
               for _, call in calls)


def test_native_captcha_token_is_forwarded_to_gotrue_for_all_public_password_and_email_flows(monkeypatch):
    owner=uuid4()
    calls=[]
    def post(url, **kwargs):
        calls.append((url,kwargs["json"]))
        if "grant_type=password" in url:
            return httpx.Response(200,json={"access_token":"access","refresh_token":"refresh",
                                             "expires_in":3600,"user":{"id":str(owner)}})
        return httpx.Response(200,json={"user":{"id":str(owner)}})
    monkeypatch.setattr(httpx,"post",post)
    identity=SupabaseIdentityProvider("https://auth.test","publishable")
    assert identity.signup("a@example.test","password-123",captcha_token="signup-token") is None
    identity.request_email("a@example.test",recovery=True,captcha_token="recover-token")
    identity.request_email("a@example.test",recovery=False,captcha_token="resend-token")
    assert identity.login("a@example.test","password-123",captcha_token="login-token").user_id==owner
    assert [url.split("/auth/v1/")[1] for url,_ in calls]==[
        "signup","recover","resend","token?grant_type=password"]
    assert [body["gotrue_meta_security"] for _,body in calls]==[
        {"captcha_token":"signup-token"},{"captcha_token":"recover-token"},
        {"captcha_token":"resend-token"},{"captcha_token":"login-token"}]


def test_recovery_consumes_hash_updates_password_and_revokes_temporary_session(monkeypatch):
    owner = uuid4()
    identity = SupabaseIdentityProvider("https://auth.test", "publishable")
    calls = []
    tokens = SessionTokens("temporary-access", "temporary-refresh", datetime.now(UTC) + timedelta(hours=1), owner)
    monkeypatch.setattr(identity, "verify_email", lambda token, *, recovery=False:
                        tokens if token == "valid-hash" and recovery else pytest.fail("wrong OTP flow"))
    monkeypatch.setattr(identity, "verify", lambda access:
                        Principal(owner, "auth", str(owner)) if access == "temporary-access" else pytest.fail("wrong session"))

    def put(url, **kwargs):
        calls.append(("put", url, kwargs))
        return httpx.Response(200, json={})

    def post(url, **kwargs):
        calls.append(("post", url, kwargs))
        return httpx.Response(204)

    monkeypatch.setattr(httpx, "put", put)
    monkeypatch.setattr(httpx, "post", post)
    identity.reset_password("valid-hash", "new-password")
    assert calls[0][0:2] == ("put", "https://auth.test/auth/v1/user")
    assert calls[0][2]["json"] == {"password": "new-password"}
    assert calls[0][2]["headers"]["Authorization"] == "Bearer temporary-access"
    assert calls[1][0:2] == ("post", "https://auth.test/auth/v1/logout?scope=global")


def test_reauthentication_revokes_only_password_grant_session(monkeypatch):
    owner = uuid4()
    identity = SupabaseIdentityProvider("https://auth.test", "publishable")
    calls = []
    monkeypatch.setattr(identity, "verify", lambda _access: Principal(owner, "auth", str(owner)))
    def grant(_email,_password,*,captcha_token=None):
        assert captcha_token=="fresh-reauth-token"
        return SessionTokens("password-grant", "refresh", datetime.now(UTC)+timedelta(hours=1), owner)
    monkeypatch.setattr(identity, "login", grant)
    monkeypatch.setattr(httpx, "get", lambda *_args, **_kwargs:
                        httpx.Response(200, json={"email": "a@example.test"}))

    def post(url, **kwargs):
        calls.append((url, kwargs))
        return httpx.Response(204)

    monkeypatch.setattr(httpx, "post", post)
    assert identity.reauthenticate("existing-access", "password",
                                   captcha_token="fresh-reauth-token") == owner
    assert calls[0][0].endswith("/auth/v1/logout?scope=local")
    assert calls[0][1]["headers"]["Authorization"] == "Bearer password-grant"


def test_reset_rejects_revoked_session_before_password_mutation(monkeypatch):
    owner = uuid4()
    identity = SupabaseIdentityProvider("https://auth.test", "publishable")
    tokens = SessionTokens("revoked", "refresh", datetime.now(UTC)+timedelta(hours=1), owner)
    monkeypatch.setattr(identity, "verify_email", lambda *_args, **_kwargs: tokens)
    monkeypatch.setattr(identity, "verify", lambda _access: (_ for _ in ()).throw(Unauthorized("revoked")))
    monkeypatch.setattr(httpx, "put", lambda *_args, **_kwargs: pytest.fail("password mutation after revocation"))
    with pytest.raises(Unauthorized):
        identity.reset_password("valid-hash", "new-password")
