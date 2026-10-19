"""SPEC-219 R7: pre-validacao local + cache curto do SupabaseIdentityProvider (sem rede para lixo)."""

from __future__ import annotations

import base64
import json
import time
from uuid import uuid4

import httpx
import pytest

from infrastructure.contracts import Unauthorized
from infrastructure.supabase_identity import SupabaseIdentityProvider

BASE = "https://auth.test"


def b64(data: dict) -> str:
    return base64.urlsafe_b64encode(json.dumps(data).encode()).decode().rstrip("=")


def jwt(*, exp=None, aud="authenticated", iss=f"{BASE}/auth/v1", **extra) -> str:
    claims = {"exp": time.time() + 600 if exp is None else exp, "aud": aud, "iss": iss, **extra}
    return f"{b64({'alg': 'HS256'})}.{b64(claims)}.sig"


@pytest.fixture
def provider(monkeypatch):
    monkeypatch.delenv("RPG_VERIFY_CACHE_SECONDS", raising=False)
    calls = {"get": [], "post": []}
    user = uuid4()

    def fake_get(url, **kwargs):
        calls["get"].append(url)
        return httpx.Response(200, json={"id": str(user), "email": "a@b.c"})

    def fake_post(url, **kwargs):
        calls["post"].append(url)
        return httpx.Response(200, json={})

    monkeypatch.setattr(httpx, "get", fake_get)
    monkeypatch.setattr(httpx, "post", fake_post)
    return SupabaseIdentityProvider(BASE + "/", "publishable"), calls, user


# Os JWTs contêm time.time(): ids explícitos e estáveis, senão o id muda a cada
# coleta e o pytest-xdist recusa a execução ("Different tests were collected").
_REJECTED_TOKENS = [
    "garbage",
    "a.b",
    "a.b.c.d",
    "..",
    "x." + b64({"no": "exp"}) + ".s",
    jwt(exp=time.time() - 3600),  # expirado alem do skew
    jwt(aud="anon"),
    jwt(aud=None),
    jwt(iss="https://evil.test/auth/v1"),
    jwt(iss=None),
    "x." + base64.urlsafe_b64encode(b"[1,2]").decode() + ".s",
    "x." + b64({"exp": "soon", "aud": "authenticated", "iss": f"{BASE}/auth/v1"}) + ".s",
]


@pytest.mark.parametrize(
    "token", _REJECTED_TOKENS, ids=[f"token{i}" for i in range(len(_REJECTED_TOKENS))]
)
def test_malformed_or_foreign_tokens_never_reach_the_network(provider, token):
    identity, calls, _user = provider
    for _ in range(50):
        with pytest.raises(Unauthorized):
            identity.verify(token)
    assert calls["get"] == []


def test_clock_skew_tolerance_accepts_just_expired(provider):
    identity, calls, _user = provider
    identity.verify(jwt(exp=time.time() - 30))
    assert len(calls["get"]) == 1


def test_same_valid_token_is_verified_remotely_once_per_ttl(provider):
    identity, calls, user = provider
    token = jwt()
    for _ in range(20):
        assert identity.verify(token).user_id == user
    assert len(calls["get"]) == 1


def test_cache_expires_and_can_be_disabled(provider, monkeypatch):
    identity, calls, _user = provider
    token = jwt()
    identity.verify(token)
    monkeypatch.setattr(time, "monotonic", lambda real=time.monotonic: real() + 25)
    identity.verify(token)
    assert len(calls["get"]) == 2
    monkeypatch.setenv("RPG_VERIFY_CACHE_SECONDS", "0")
    identity.verify(token)
    identity.verify(token)
    assert len(calls["get"]) == 4


def test_remote_rejection_is_not_cached(provider, monkeypatch):
    identity, calls, _user = provider
    monkeypatch.setattr(
        httpx, "get", lambda url, **k: (calls["get"].append(url), httpx.Response(401))[1]
    )
    token = jwt()
    for _ in range(3):
        with pytest.raises(Unauthorized):
            identity.verify(token)
    assert len(calls["get"]) == 3


def test_logout_and_refresh_invalidate_the_cache(provider, monkeypatch):
    identity, calls, user = provider
    token = jwt()
    identity.verify(token)
    identity.logout(token)
    identity.verify(token)  # voltou a consultar o GoTrue
    assert len(calls["get"]) == 2
    monkeypatch.setattr(
        httpx,
        "post",
        lambda url, **k: httpx.Response(
            200,
            json={
                "access_token": "x",
                "refresh_token": "y",
                "expires_in": 60,
                "user": {"id": str(user)},
            },
        ),
    )
    identity.refresh("r")
    identity.verify(token)
    assert len(calls["get"]) == 3


def test_account_removal_and_global_revoke_forget_the_user(provider):
    identity, calls, user = provider
    token = jwt()
    identity.verify(token)
    identity.verify(token)
    assert len(calls["get"]) == 1
    identity._forget(user_id=user)
    identity.verify(token)
    assert len(calls["get"]) == 2


def test_session_revocation_is_checked_in_db_even_on_cache_hit(monkeypatch):
    """O cache cobre so o GoTrue; a revogacao de sessao (banco local) vale na hora."""
    monkeypatch.delenv("RPG_VERIFY_CACHE_SECONDS", raising=False)
    user, session = uuid4(), uuid4()
    gets = []
    monkeypatch.setattr(
        httpx,
        "get",
        lambda url, **k: (gets.append(url), httpx.Response(200, json={"id": str(user)}))[1],
    )
    state = {"active": True}

    class Row:
        def fetchone(self):
            return {"ok": state["active"]}

    class Db:
        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

        def execute(self, *a):
            return Row()

    class Pool:
        def connection(self):
            return Db()

    identity = SupabaseIdentityProvider(BASE, "k", pool=Pool())
    token = jwt(session_id=str(session))
    assert identity.verify(token).user_id == user
    assert identity.verify(token).user_id == user and len(gets) == 1
    state["active"] = False
    with pytest.raises(Unauthorized):
        identity.verify(token)
    assert len(gets) == 1  # recusou sem nova chamada de rede


# --- revisao Sol (SPEC-219) ------------------------------------------------------------------


def test_deeply_nested_payload_is_unauthorized_not_500(provider):
    identity, calls, _user = provider
    nested = base64.urlsafe_b64encode(b"[" * 3000).decode().rstrip("=")
    with pytest.raises(Unauthorized):
        identity.verify(f"a.{nested}.c")
    with pytest.raises(Unauthorized):
        identity.verify("a." + "x" * 9000 + ".c")
    assert calls["get"] == []


def test_cache_never_outlives_the_token_exp(provider, monkeypatch):
    identity, calls, _user = provider
    token = jwt(exp=time.time() + 5)
    identity.verify(token)
    identity.verify(token)
    assert len(calls["get"]) == 1  # dentro do exp: cache
    real = time.time
    monkeypatch.setattr(time, "time", lambda: real() + 30)  # exp passou (dentro do skew)
    identity.verify(token)
    assert len(calls["get"]) == 2  # volta ao GoTrue, nao ao cache
