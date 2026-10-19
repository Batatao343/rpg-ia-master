"""SPEC-220 contra GoTrue + Postgres LOCAIS (Supabase CLI). Nunca staging/produção."""

from __future__ import annotations

from contextlib import contextmanager
from types import SimpleNamespace
from uuid import uuid4

import httpx
import pytest

pytestmark = pytest.mark.infra_local

DB = "postgresql://postgres:postgres@127.0.0.1:55322/postgres"
ORIGIN = "http://localhost:5173"


@pytest.fixture
def local_stack():
    psycopg = pytest.importorskip("psycopg")
    from psycopg.rows import dict_row

    try:
        from scripts.start_local_api import _supabase_status

        status = _supabase_status()
    except Exception as exc:  # pragma: no cover - stack ausente
        pytest.skip(f"Supabase local indisponível: {type(exc).__name__}")
    url = status["API_URL"].rstrip("/")
    assert url == "http://127.0.0.1:55321"  # nunca alvo remoto
    try:
        psycopg.connect(DB, connect_timeout=3).close()
    except psycopg.OperationalError:
        pytest.skip("Postgres local indisponível")

    class Pool:
        @contextmanager
        def connection(self):
            # Conexão própria e autocommit: GoTrue lê o mesmo banco em outra conexão.
            with psycopg.connect(DB, autocommit=True, row_factory=dict_row) as conn:
                yield conn

    service = status["SERVICE_ROLE_KEY"]
    admin = {"apikey": service, "Authorization": f"Bearer {service}"}
    created = []

    def user(password: str):
        email = f"spec220-{uuid4().hex}@example.test"
        response = httpx.post(
            f"{url}/auth/v1/admin/users",
            headers=admin,
            timeout=10,
            json={"email": email, "password": password, "email_confirm": True},
        )
        response.raise_for_status()
        created.append(response.json()["id"])
        return email

    yield SimpleNamespace(
        url=url,
        publishable=status.get("PUBLISHABLE_KEY") or status["ANON_KEY"],
        service=service,
        pool=Pool(),
        user=user,
    )
    for owner in created:
        httpx.delete(f"{url}/auth/v1/admin/users/{owner}", headers=admin, timeout=10)


def _client(monkeypatch, identity, pool):
    from fastapi.testclient import TestClient

    import api
    from infrastructure.postgres_turns import PostgresRateLimiter

    runtime = SimpleNamespace(identity_verifier=identity, rate_limiter=PostgresRateLimiter(pool))
    monkeypatch.setenv("RPG_SESSION_SECRET", "s" * 32)
    monkeypatch.setenv("RPG_AUTH_CAPTCHA_MODE", "app")
    monkeypatch.setenv("RPG_AUTH_CAPTCHA_REQUIRED", "0")
    monkeypatch.setattr(api, "_database_profile", lambda: True)
    monkeypatch.setattr("infrastructure.runtime.get_runtime", lambda: runtime)
    client = TestClient(api.app, raise_server_exceptions=False)
    client.headers["Origin"] = ORIGIN
    return client


def test_logout_with_expired_access_revokes_refresh_on_local_gotrue(local_stack, monkeypatch):
    from infrastructure.contracts import Unauthorized
    from infrastructure.supabase_identity import SupabaseIdentityProvider

    s = local_stack
    identity = SupabaseIdentityProvider(s.url, s.publishable, pool=s.pool, service_key=s.service)
    email = s.user("spec220-Senha-Local-1")
    client = _client(monkeypatch, identity, s.pool)
    login = client.post("/auth/login", json={"email": email, "password": "spec220-Senha-Local-1"})
    assert login.status_code == 200, login.text
    refresh_token = client.cookies.get("rpg_refresh")
    other_device = identity.login(email, "spec220-Senha-Local-1")  # outra sessão, mesma conta
    # Access "vencido": o cookie de acesso não é mais aceito (simulado por valor inválido).
    client.cookies.set("rpg_access", "expired.access.token")
    out = client.post("/auth/refresh/logout", headers={"X-CSRF-Token": login.json()["csrf_token"]})
    assert out.status_code == 204, out.text
    with pytest.raises(Unauthorized):
        identity.refresh(refresh_token)  # refresh antigo morto no servidor
    with pytest.raises(Unauthorized):
        identity.refresh(other_device.refresh_token)  # revogação global (D-A)
    with pytest.raises(Unauthorized):
        identity.verify(other_device.access_token)


def test_postgres_rate_limiter_peek_and_reset_and_login_lockout(local_stack, monkeypatch):
    from infrastructure.postgres_turns import PostgresRateLimiter
    from infrastructure.supabase_identity import SupabaseIdentityProvider

    s = local_stack
    limiter = PostgresRateLimiter(s.pool)
    key = f"spec220-test:{uuid4().hex}"
    try:
        assert limiter.peek(key, limit=2, window_seconds=60).allowed
        limiter.consume(key, limit=2, window_seconds=60)
        limiter.consume(key, limit=2, window_seconds=60)
        assert not limiter.peek(key, limit=2, window_seconds=60).allowed
        assert limiter.peek(key, limit=3, window_seconds=60).allowed  # peek não consome
        limiter.reset(key)
        assert limiter.peek(key, limit=2, window_seconds=60).remaining == 2
    finally:
        limiter.reset(key)

    identity = SupabaseIdentityProvider(s.url, s.publishable, pool=s.pool, service_key=s.service)
    email = s.user("spec220-Lockout-Local-1")
    client = _client(monkeypatch, identity, s.pool)
    from services.account_security import auth_email_bucket_keys

    try:
        for _ in range(5):  # sucessos não consomem
            assert (
                client.post(
                    "/auth/login", json={"email": email, "password": "spec220-Lockout-Local-1"}
                ).status_code
                == 200
            )
        for _ in range(3):
            assert (
                client.post(
                    "/auth/login", json={"email": email, "password": "wrong-password"}
                ).status_code
                == 401
            )
        assert (
            client.post(
                "/auth/login", json={"email": email, "password": "spec220-Lockout-Local-1"}
            ).status_code
            == 200
        )
        with s.pool.connection() as db:
            assert not db.execute(
                "select 1 from app.rate_limit_buckets where bucket_key=any(%s)",
                (list(auth_email_bucket_keys(email)),),
            ).fetchone()  # zerado
    finally:
        with s.pool.connection() as db:
            db.execute("delete from app.rate_limit_buckets where bucket_key like 'auth:login:%'")
