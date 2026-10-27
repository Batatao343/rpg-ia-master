"""SPEC-343: trava de falhas no reauth, balde por e-mail no login, RLS em app.*."""

from __future__ import annotations

import re
from pathlib import Path
from types import SimpleNamespace
from uuid import uuid4

import pytest
from fastapi import HTTPException

from infrastructure.contracts import Principal, Unauthorized
from infrastructure.local_adapters import MemoryRateLimiter
from infrastructure.supabase_identity import SupabaseIdentityProvider
from services.account_security import (
    LOGIN_EMAIL_ONLY_FAILURES,
    REAUTH_FAILURES,
    auth_email_bucket_keys,
    auth_limit,
    auth_success,
)
from tests.test_session_hardening import _csrf, hardened  # noqa: F401

MIGRATIONS = Path(__file__).resolve().parents[1] / "supabase" / "migrations"


class ReauthIdentity(SupabaseIdentityProvider):
    def __init__(self):
        super().__init__("http://auth.test", "publishable")
        self.owner = uuid4()
        self.reauth_calls = 0

    def verify(self, token):
        if token != "good":
            raise Unauthorized("token inválido")
        return Principal(self.owner, "auth", str(self.owner))

    def reauthenticate(self, access, password, **_kw):
        self.reauth_calls += 1
        if password != "correct-password":
            raise Unauthorized("credenciais inválidas")
        return self.owner


@pytest.fixture
def reauth(hardened):  # noqa: F811
    client, _, runtime = hardened
    identity = ReauthIdentity()
    runtime.identity_verifier = identity
    client.cookies.set("rpg_access", "good")
    return client, identity, runtime


def _reauth(client, password="wrong-password", csrf=True):
    headers = _csrf(client) if csrf else {}
    return client.post("/auth/reauth", json={"password": password}, headers=headers)


def test_reauth_sixth_failure_is_429(reauth):
    client, identity, _ = reauth
    for _ in range(REAUTH_FAILURES[0]):
        assert _reauth(client).status_code == 401
    out = _reauth(client)
    assert out.status_code == 429 and out.json()["detail"] == "auth_rate_limit"
    assert "Retry-After" in out.headers
    calls = identity.reauth_calls
    assert _reauth(client, "correct-password").status_code == 429  # antes do IdP
    assert identity.reauth_calls == calls


def test_reauth_success_resets_bucket(reauth):
    client, _, _ = reauth
    for _ in range(REAUTH_FAILURES[0] - 1):
        assert _reauth(client).status_code == 401
    assert _reauth(client, "correct-password").status_code == 200
    for _ in range(REAUTH_FAILURES[0]):
        assert _reauth(client).status_code == 401
    assert _reauth(client).status_code == 429


def test_reauth_csrf_failure_does_not_consume(reauth):
    client, identity, _ = reauth
    for _ in range(REAUTH_FAILURES[0] + 2):
        assert _reauth(client, csrf=False).status_code == 403
    assert identity.reauth_calls == 0
    assert _reauth(client, "correct-password").status_code == 200


def test_reauth_without_access_cookie_is_401_and_does_not_consume(reauth):
    client, identity, _ = reauth
    client.cookies.delete("rpg_access")
    for _ in range(REAUTH_FAILURES[0] + 2):
        assert _reauth(client).status_code == 401
    assert identity.reauth_calls == 0
    client.cookies.set("rpg_access", "good")
    assert _reauth(client, "correct-password").status_code == 200


def _req(ip):
    return SimpleNamespace(client=SimpleNamespace(host=ip))


def _fail(runtime, ip, email="v@test.test"):
    auth_limit(runtime, _req(ip), action="login", email=email, stage="failure")


def test_login_fifty_failures_from_distinct_ips_lock_email():
    runtime = SimpleNamespace(rate_limiter=MemoryRateLimiter())
    limit = LOGIN_EMAIL_ONLY_FAILURES[0]
    for index in range(limit - 1):
        _fail(runtime, f"10.2.{index // 200}.{index % 200}")
    auth_limit(runtime, _req("10.9.9.9"), action="login", email="v@test.test")  # 49: passa
    _fail(runtime, "10.9.9.8")  # a 50a falha consome o balde
    with pytest.raises(HTTPException) as exc:
        auth_limit(runtime, _req("10.9.9.7"), action="login", email="V@Test.Test")
    assert exc.value.status_code == 429


def test_login_success_resets_email_only_bucket():
    runtime = SimpleNamespace(rate_limiter=MemoryRateLimiter())
    for index in range(LOGIN_EMAIL_ONLY_FAILURES[0] - 1):
        _fail(runtime, f"10.3.0.{index}")
    auth_success(runtime, action="login", email="v@test.test", request=_req("10.3.1.1"))
    for index in range(LOGIN_EMAIL_ONLY_FAILURES[0] - 1):
        _fail(runtime, f"10.4.0.{index}")
    auth_limit(runtime, _req("10.5.0.1"), action="login", email="v@test.test")


def test_email_bucket_keys_include_login_email_only():
    from services.account_security import _digest

    assert f"auth:login:email:{_digest('v@test.test')}" in auth_email_bucket_keys("V@Test.Test")


def test_rate_limited_log_has_no_secrets(caplog):
    runtime = SimpleNamespace(rate_limiter=MemoryRateLimiter())
    caplog.set_level("DEBUG")
    for _ in range(REAUTH_FAILURES[0]):
        auth_limit(
            runtime, _req("1.1.1.1"), action="reauth", stage="failure", access="tok-secret-1"
        )
    with pytest.raises(HTTPException):
        auth_limit(runtime, _req("1.1.1.1"), action="reauth", access="tok-secret-1")
    assert "tok-secret-1" not in caplog.text


def test_embedding_profiles_migration_clauses():
    sql = (MIGRATIONS / "20261027120000_embedding_profiles_rls.sql").read_text(encoding="utf-8")
    low = " ".join(sql.lower().split())
    assert "alter table app.embedding_profiles enable row level security" in low
    assert "alter table app.embedding_profiles force row level security" in low
    assert "revoke all on app.embedding_profiles from public, anon, authenticated" in low
    assert "drop policy if exists embedding_profiles_read" in low
    assert "for select to rpg_api using (true)" in low


# rate_limit_buckets: sem RLS desde 20260819001850; so o backend a toca (rpg_api revogado) e nao ha
# banco local para provar o efeito de habilitar RLS no role rpg_runtime. Follow-up proprio.
RLS_EXCEPTIONS = {"rate_limit_buckets"}


def test_every_app_table_has_rls():
    created: set[str] = set()
    covered: set[str] = set()
    for path in sorted(MIGRATIONS.glob("*.sql")):
        text = path.read_text(encoding="utf-8").lower()
        created |= set(re.findall(r"create table (?:if not exists )?app\.([a-z_0-9]+)", text))
        covered |= set(
            re.findall(r"alter table (?:only )?app\.([a-z_0-9]+)\s+enable row level security", text)
        )
        if "enable row level security" in text and "execute format" in text:
            for block in re.findall(r"foreach \w+ in array array\[(.*?)\]", text, re.S):
                covered |= set(re.findall(r"'([a-z_0-9]+)'", block))
    assert not (created - covered - RLS_EXCEPTIONS), sorted(created - covered)
