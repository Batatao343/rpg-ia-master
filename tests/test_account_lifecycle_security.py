"""SPEC-190 adversarial API/adapter checks; no outbound mail or paid calls."""

from contextlib import nullcontext
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from uuid import uuid4

import httpx
import pytest
from fastapi.testclient import TestClient

import api
from infrastructure.contracts import Principal, Unauthorized
from infrastructure.local_adapters import MemoryRateLimiter
from infrastructure.supabase_identity import AuthEmailDeliveryError, SupabaseIdentityProvider
from services.account_security import GENERIC_MESSAGE, proof, proof_owner
from services.auth_sessions import CsrfSigner, SessionTokens


@pytest.fixture
def account_client(monkeypatch):
    a, b = uuid4(), uuid4()

    class Identity(SupabaseIdentityProvider):
        def __init__(self):
            super().__init__("http://auth.test", "publishable")
            self.revoked = set()
            self.emails = []

        def verify(self, token):
            if token not in {"a", "b"} or token in self.revoked:
                raise Unauthorized("revoked")
            owner = a if token == "a" else b
            return Principal(owner, "auth", str(owner))

        def login(self, email, password):
            token = "a" if email.startswith("a") else "b"
            return SessionTokens(
                token,
                "refresh-private",
                datetime.now(UTC) + timedelta(hours=1),
                a if token == "a" else b,
            )

        def signup(self, email, password):
            if email.startswith("exists"):
                raise Unauthorized("exists")
            return None

        def request_email(self, email, *, recovery):
            self.emails.append((email, recovery))

        def reset_password(self, token_hash, password):
            if token_hash != "valid-hash-123":
                raise Unauthorized("link_invalid_or_expired")

        def reauthenticate(self, access, password):
            if password != "correct-password":
                raise Unauthorized("invalid")
            return self.verify(access).user_id

    identity = Identity()
    tombstones = set()

    class DB:
        def execute(self, _statement, params):
            return SimpleNamespace(fetchone=lambda: (1,) if params[0] in tombstones else None)

    runtime = SimpleNamespace(
        identity_verifier=identity,
        rate_limiter=MemoryRateLimiter(),
        game_store=SimpleNamespace(pool=SimpleNamespace(connection=lambda: nullcontext(DB()))),
        blob_store=object(),
    )
    monkeypatch.setenv("RPG_SESSION_SECRET", "s" * 32)
    monkeypatch.setenv("RPG_AUTH_CAPTCHA_REQUIRED", "0")
    monkeypatch.setenv("RPG_AUTH_EMAIL_CONFIRMATION_REQUIRED", "1")
    monkeypatch.setattr(api, "_database_profile", lambda: True)
    monkeypatch.setattr("infrastructure.runtime.get_runtime", lambda: runtime)
    client = TestClient(api.app)
    client.headers["Origin"] = "http://localhost:5173"
    identity.tombstones = tombstones
    return client, identity, a, b


def test_verify_signup_and_reset_messages_do_not_enumerate(account_client):
    client, identity, _, _ = account_client
    for email in ("exists@test.test", "absent@test.test"):
        signup = client.post(
            "/auth/signup",
            json={"email": email, "password": "long-password", "age_confirmed": True},
        )
        assert signup.status_code == 202 and signup.json() == {
            "authenticated": False,
            "message": GENERIC_MESSAGE,
        }
        assert "rpg_access" not in signup.cookies
        for path in ("/auth/reset/request", "/auth/verify/request"):
            result = client.post(path, json={"email": email})
            assert result.status_code == 202 and result.json() == {"message": GENERIC_MESSAGE}
    assert len(identity.emails) == 4


@pytest.mark.parametrize(
    "action,status_class", [("reset", "5xx"), ("verify", "4xx"), ("reset", "network")]
)
def test_email_delivery_failure_is_observable_without_public_enumeration(
    account_client, monkeypatch, caplog, action, status_class
):
    from observability.metrics import metrics

    client, identity, _, _ = account_client

    def fail(email, *, recovery):
        if status_class == "network":
            raise httpx.ConnectError("private SMTP host and address must not enter logs")
        raise AuthEmailDeliveryError(status_class)

    monkeypatch.setattr(identity, "request_email", fail)
    path = "/auth/reset/request" if action == "reset" else "/auth/verify/request"
    result = client.post(path, json={"email": "private@example.test"})
    assert result.status_code == 202 and result.json() == {"message": GENERIC_MESSAGE}
    records = [
        record.message
        for record in caplog.records
        if "auth.email_delivery_failed" in record.message
    ]
    assert len(records) == 1 and f'"status_class": "{status_class}"' in records[0]
    assert '"flow": "' + action + '"' in records[0]
    assert "private@example.test" not in records[0] and "SMTP host" not in records[0]
    assert any(
        "rpg_auth_email_delivery_failures_total" in key and action in key and status_class in key
        for key in metrics.snapshot()
    )


def test_required_captcha_fails_closed_and_address_limits_apply(account_client, monkeypatch):
    client, identity, _, _ = account_client
    monkeypatch.setenv("RPG_AUTH_CAPTCHA_REQUIRED", "1")
    monkeypatch.delenv("RPG_TURNSTILE_SECRET", raising=False)
    assert client.post("/auth/reset/request", json={"email": "a@test.test"}).status_code == 503
    assert identity.emails == []
    monkeypatch.setenv("RPG_AUTH_CAPTCHA_REQUIRED", "0")
    for _ in range(4):
        assert client.post("/auth/reset/request", json={"email": "A@Test.Test"}).status_code == 202
    assert client.post("/auth/reset/request", json={"email": "a@test.test"}).status_code == 429


def test_gotrue_mode_requires_config_and_forwards_fresh_tokens_without_proxy_consumption(
    account_client, monkeypatch
):
    client, identity, _, _ = account_client
    monkeypatch.setenv("RPG_AUTH_CAPTCHA_MODE", "gotrue")
    monkeypatch.setenv("RPG_AUTH_CAPTCHA_REQUIRED", "1")
    monkeypatch.delenv("RPG_TURNSTILE_SITE_KEY", raising=False)
    assert (
        client.post(
            "/auth/signup",
            json={
                "email": "a@test.test",
                "password": "password-123",
                "age_confirmed": True,
                "captcha_token": "signup-token",
            },
        ).status_code
        == 503
    )
    monkeypatch.setenv("RPG_TURNSTILE_SITE_KEY", "public-site-key")
    assert (
        client.post(
            "/auth/signup",
            json={"email": "a@test.test", "password": "password-123", "age_confirmed": True},
        ).status_code
        == 403
    )
    sent = []
    monkeypatch.setattr(
        httpx, "post", lambda *_args, **_kwargs: pytest.fail("proxy must not consume token")
    )

    def signup(email, password, *, captcha_token):
        sent.append(("signup", captcha_token))
        return None

    def request_email(email, *, recovery, captcha_token):
        sent.append(("recover" if recovery else "resend", captcha_token))

    def login(email, password, *, captcha_token):
        sent.append(("login", captcha_token))
        return SessionTokens(
            "a",
            "refresh-private",
            datetime.now(UTC) + timedelta(hours=1),
            identity.verify("a").user_id,
        )

    monkeypatch.setattr(identity, "signup", signup)
    monkeypatch.setattr(identity, "request_email", request_email)
    monkeypatch.setattr(identity, "login", login)
    assert (
        client.post(
            "/auth/signup",
            json={
                "email": "a@test.test",
                "password": "password-123",
                "age_confirmed": True,
                "captcha_token": "signup-token",
            },
        ).status_code
        == 202
    )
    assert (
        client.post(
            "/auth/reset/request", json={"email": "a@test.test", "captcha_token": "recover-token"}
        ).status_code
        == 202
    )
    assert (
        client.post(
            "/auth/verify/request", json={"email": "a@test.test", "captcha_token": "resend-token"}
        ).status_code
        == 202
    )
    assert (
        client.post(
            "/auth/login",
            json={
                "email": "a@test.test",
                "password": "password-123",
                "captcha_token": "login-token",
            },
        ).status_code
        == 200
    )
    csrf = client.cookies["rpg_csrf"]

    def reauthenticate(access, password, *, captcha_token):
        sent.append(("reauth", captcha_token))
        return identity.verify(access).user_id

    monkeypatch.setattr(identity, "reauthenticate", reauthenticate)
    assert (
        client.post(
            "/auth/reauth", json={"password": "password-123"}, headers={"X-CSRF-Token": csrf}
        ).status_code
        == 403
    )
    reauth = client.post(
        "/auth/reauth",
        json={"password": "password-123", "captcha_token": "reauth-token"},
        headers={"X-CSRF-Token": csrf},
    )
    assert reauth.status_code == 200, reauth.json()
    assert sent == [
        ("signup", "signup-token"),
        ("recover", "recover-token"),
        ("resend", "resend-token"),
        ("login", "login-token"),
        ("reauth", "reauth-token"),
    ]
    monkeypatch.setenv("RPG_AUTH_CAPTCHA_REQUIRED", "0")
    assert (
        client.post(
            "/auth/reset/request", json={"email": "other@test.test", "captcha_token": "token"}
        ).status_code
        == 503
    )
    monkeypatch.setenv("RPG_AUTH_CAPTCHA_MODE", "invalid")
    assert (
        client.post(
            "/auth/login", json={"email": "a@test.test", "password": "password-123"}
        ).status_code
        == 503
    )


def test_reset_confirm_has_no_bearer_and_clears_cookies(account_client):
    client, _, _, _ = account_client
    client.post("/auth/login", json={"email": "a@test.test", "password": "long-password"})
    result = client.post(
        "/auth/reset/confirm", json={"token_hash": "valid-hash-123", "new_password": "new-password"}
    )
    assert result.status_code == 200 and result.json()["authenticated"] is False
    assert not any(key in client.cookies for key in ("rpg_access", "rpg_refresh", "rpg_recent"))
    assert "refresh-private" not in result.text
    assert (
        client.post(
            "/auth/reset/confirm",
            json={"token_hash": "expired-hash", "new_password": "new-password"},
        ).status_code
        == 400
    )


def test_delete_receipt_is_restricted_and_account_switch_clears_it(account_client, monkeypatch):
    client, identity, a, b = account_client
    calls = []
    finishes = []

    class Lifecycle:
        def __init__(self, *_):
            pass

        def begin(self, owner):
            calls.append(owner)
            identity.tombstones.add(owner)
            identity.revoked.add("a" if owner == a else "b")

        def finish(self, owner):
            finishes.append(owner)
            return "deleting" if finishes.count(owner) == 1 else "deleted"

    monkeypatch.setattr("infrastructure.account_lifecycle.PostgresAccountLifecycle", Lifecycle)
    client.post("/auth/login", json={"email": "a@test.test", "password": "long-password"})
    csrf = client.cookies["rpg_csrf"]
    first = client.post(
        "/account/delete", json={"confirmation": "EXCLUIR"}, headers={"X-CSRF-Token": csrf}
    )
    assert first.status_code == 202 and first.json()["status"] == "deleting"
    assert client.get("/account/balance").status_code == 401
    # A concurrent stale refresh response must not destroy retry authorization.
    client.cookies.set("rpg_access", "a", domain="testserver.local", path="/")
    assert (
        client.post(
            "/account/delete", json={"confirmation": "EXCLUIR"}, headers={"X-CSRF-Token": csrf}
        ).json()["status"]
        == "deleted"
    )
    assert calls == [a]
    assert finishes == [a, a]
    assert (
        client.post(
            "/auth/login", json={"email": "b@test.test", "password": "long-password"}
        ).status_code
        == 200
    )
    assert "rpg_deletion" not in client.cookies
    csrf = client.cookies["rpg_csrf"]
    client.post("/account/delete", json={"confirmation": "EXCLUIR"}, headers={"X-CSRF-Token": csrf})
    assert calls[-1] == b


def test_recent_proof_can_resume_only_existing_matching_tombstone(account_client, monkeypatch):
    client, identity, a, b = account_client
    calls = []

    class Lifecycle:
        def __init__(self, *_args):
            pass

        def begin(self, _owner):
            pytest.fail("stale proof must not initiate deletion")

        def finish(self, owner):
            calls.append(owner)
            return "deleted"

    monkeypatch.setattr("infrastructure.account_lifecycle.PostgresAccountLifecycle", Lifecycle)
    client.cookies.set("rpg_access", "a")
    csrf = CsrfSigner("s" * 32).issue()
    client.cookies.set("rpg_csrf", csrf)
    client.cookies.set("rpg_recent", proof(a, "recent", "a"))
    identity.revoked.add("a")
    headers = {"X-CSRF-Token": csrf}
    assert (
        client.post(
            "/account/delete", json={"confirmation": "EXCLUIR"}, headers=headers
        ).status_code
        == 401
    )
    assert calls == []
    identity.tombstones.add(b)
    assert (
        client.post(
            "/account/delete", json={"confirmation": "EXCLUIR"}, headers=headers
        ).status_code
        == 401
    )
    identity.tombstones.add(a)
    assert (
        client.post(
            "/account/delete", json={"confirmation": "EXCLUIR"}, headers=headers
        ).status_code
        == 200
    )
    assert calls == [a]


def test_export_delete_require_recent_owner_bound_proof(account_client, monkeypatch):
    client, _, a, b = account_client
    client.cookies.set("rpg_access", "a")
    csrf = CsrfSigner("s" * 32).issue()
    client.cookies.set("rpg_csrf", csrf)
    assert client.get("/account/export").status_code == 403
    client.cookies.set("rpg_recent", proof(b, "recent", "a"))
    assert (
        client.post(
            "/account/delete", json={"confirmation": "EXCLUIR"}, headers={"X-CSRF-Token": csrf}
        ).status_code
        == 403
    )
    client.cookies.set(
        "rpg_recent", proof(a, "recent", "a", now=int(datetime.now(UTC).timestamp()) - 301)
    )
    assert client.get("/account/export").status_code == 403
    with pytest.raises(Unauthorized):
        proof_owner(proof(a, "recent", "a"), "recent", "refreshed-a")


def test_captcha_checks_hostname_and_flow_and_does_not_send_provider_key(monkeypatch):
    from services.account_security import validate_captcha

    monkeypatch.setenv("RPG_AUTH_CAPTCHA_REQUIRED", "1")
    monkeypatch.setenv("RPG_TURNSTILE_SITE_KEY", "public")
    monkeypatch.setenv("RPG_TURNSTILE_SECRET", "secret")
    result = {"success": True, "hostname": "localhost", "action": "reset"}
    monkeypatch.setattr(httpx, "post", lambda *_args, **_kwargs: httpx.Response(200, json=result))
    validate_captcha("token", remote_ip="127.0.0.1", action="reset")
    for changes in ({"hostname": "evil.test"}, {"action": "signup"}, {"success": False}):
        result.update({"success": True, "hostname": "localhost", "action": "reset"})
        result.update(changes)
        with pytest.raises(Unauthorized):
            validate_captcha("token", remote_ip="127.0.0.1", action="reset")


def _set_cookie_headers(resp, name):
    return [h for h in resp.headers.get_list("set-cookie") if h.startswith(name + "=")]


def test_android_client_gets_max_age_on_refresh_and_csrf_cookies_only(account_client, monkeypatch):
    """SPEC-193: header X-RPG-Client nao e fronteira de seguranca; so ajusta Max-Age."""
    client, *_ = account_client
    body = {"email": "a@test.test", "password": "password-123"}
    web = client.post("/auth/login", json=body)
    assert "max-age" not in _set_cookie_headers(web, "rpg_refresh")[0].lower()
    droid = client.post("/auth/login", json=body, headers={"X-RPG-Client": "android"})
    assert "Max-Age=1209600" in _set_cookie_headers(droid, "rpg_refresh")[0]
    assert "max-age" not in _set_cookie_headers(droid, "rpg_access")[0].lower()
    assert "Max-Age=1209600" in _set_cookie_headers(droid, "rpg_csrf")[0]
    assert "max-age" not in _set_cookie_headers(web, "rpg_csrf")[0].lower()
    monkeypatch.setenv("RPG_ANDROID_REFRESH_MAX_AGE_SECONDS", "10")  # clamp 3600..2592000
    low = client.post("/auth/login", json=body, headers={"X-RPG-Client": "android"})
    assert "Max-Age=3600" in _set_cookie_headers(low, "rpg_refresh")[0]
    monkeypatch.setenv("RPG_ANDROID_REFRESH_MAX_AGE_SECONDS", "99999999")
    high = client.post("/auth/login", json=body, headers={"X-RPG-Client": "android"})
    assert "Max-Age=2592000" in _set_cookie_headers(high, "rpg_refresh")[0]


def test_logout_clears_android_refresh_cookie(account_client):
    client, identity, *_ = account_client
    identity.logout = lambda access: identity.revoked.add(access)
    client.post(
        "/auth/login",
        json={"email": "a@test.test", "password": "password-123"},
        headers={"X-RPG-Client": "android"},
    )
    out = client.post(
        "/auth/logout",
        headers={"X-CSRF-Token": client.cookies["rpg_csrf"], "X-RPG-Client": "android"},
    )
    assert out.status_code == 204
    assert "Max-Age=0" in _set_cookie_headers(out, "rpg_refresh")[0]
    assert "Max-Age=0" in _set_cookie_headers(out, "rpg_csrf")[0]
    assert "Max-Age=0" in _set_cookie_headers(out, "rpg_access")[0]


def test_permissions_policy_allows_microphone_for_self(account_client):
    client, *_ = account_client
    pp = client.get("/health").headers["permissions-policy"]
    assert "microphone=(self)" in pp and "camera=()" in pp
    # getUserMedia depende de Permissions-Policy; CSP nao tem diretiva de microfone.
    csp = client.get("/health").headers.get("content-security-policy", "")
    assert "microphone" not in csp


def test_signup_requires_server_side_age_confirmation(account_client, monkeypatch):
    """SPEC-222 R9 (D-D): a declaração de 18+ é exigida pela API, não só pela UI."""
    client, identity, _, _ = account_client
    calls = []
    original = identity.signup
    monkeypatch.setattr(identity, "signup", lambda *a, **k: calls.append(1) or original(*a, **k))
    for body in ({}, {"age_confirmed": False}, {"age_confirmed": "sim"}):
        denied = client.post(
            "/auth/signup", json={"email": "minor@test.test", "password": "long-password", **body}
        )
        assert denied.status_code == 422
        assert not calls
    ok = client.post(
        "/auth/signup",
        json={"email": "adult@test.test", "password": "long-password", "age_confirmed": True},
    )
    assert ok.status_code == 202 and calls == [1]
