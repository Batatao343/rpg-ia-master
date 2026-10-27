"""SPEC-337: fixtures/helpers HTTP de segurança (dois principals, SPA, headers, vazamento).

Sem testes aqui (nome sem ``test_``): só reutilizável por SPEC-337/SPEC-338.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from types import SimpleNamespace
from typing import Any
from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient

import api
from infrastructure.contracts import Conflict, NotFound, Principal, Unauthorized
from infrastructure.local_adapters import (
    FileGameStore,
    InProcessTurnCoordinator,
    JsonRuntimeCatalogStore,
    MemoryRateLimiter,
)
from services.auth_sessions import CsrfSigner

ORIGIN = "http://localhost:5173"
SECRET = "s" * 32
SEED_NAME = "Heroi-Semente-A"


class FakeIdentity:
    """Verificador falso: tokens ``a``/``b`` mapeiam para dois donos distintos."""

    def __init__(self) -> None:
        self.a = Principal(uuid4(), "auth", "a")
        self.b = Principal(uuid4(), "auth", "b")

    def verify(self, token):
        if token == "a":
            return self.a
        if token == "b":
            return self.b
        raise Unauthorized("token inválido")

    # SPEC-338: o fuzz de /auth/* passa da validação e chega ao provedor; o fake nega tudo.
    def login(self, email, password, captcha_token=None):
        raise Unauthorized("credenciais inválidas")

    def signup(self, email, password, captcha_token=None):
        raise Unauthorized("cadastro indisponível")

    def logout(self, token):
        return None


class FakeTurnCoordinator(InProcessTurnCoordinator):
    """Coordenador in-process com ``receipt``/``commit_delete`` na semântica do Postgres."""

    def __init__(self, store: FileGameStore) -> None:
        super().__init__()
        self._store = store
        self.calls: list[tuple[str, Any]] = []

    def receipt(self, principal, operation_id, *, game_id=None, kind=None, request_hash=None):
        self.calls.append(("receipt", operation_id))
        row = self._claims.get(operation_id)
        if not row or row[0] != principal:
            return None
        _, claim, row_kind, value = row
        if kind is not None and (
            row_kind != kind
            or claim.request_hash != request_hash
            or (kind != "new_game" and claim.game_id != game_id)
        ):
            raise Conflict("operation_request_mismatch")
        if isinstance(value, dict) and set(value) == {"error"}:
            return None  # operação falhada: o Postgres só devolve recibo 'completed'
        return value

    def commit_game(self, principal, claim, state, *, receipt, **_kwargs):
        """SPEC-338: commit do turno/mutação sobre o ``FileGameStore`` (sem eventos nem custo)."""
        self.calls.append(("commit_game", claim.game_id))
        payload = {k: v for k, v in state.items() if k != "_storage_version"}
        stored = self._store.save(principal, claim.game_id, claim.base_version, payload)
        value = self.complete(claim, committed_version=stored.version, receipt=receipt)
        return stored.version, value

    def commit_delete(self, principal, claim, game_id, *, receipt):
        self.calls.append(("commit_delete", game_id))
        if claim.game_id is not None:
            raise ValueError("delete usa operação desacoplada para preservar o recibo")
        if not self._store.delete(principal, game_id):
            raise NotFound("campanha não encontrada")
        persisted = dict(receipt)
        with self._lock:
            row = self._claims[claim.operation_id]
            self._claims[claim.operation_id] = (row[0], row[1], row[2], persisted)
        return persisted


class _NoRowsConnection:
    """Conexão fake do gate de falhas pendentes: nenhuma operação falhada no Postgres."""

    def __enter__(self):
        return self

    def __exit__(self, *_exc):
        return False

    def execute(self, *_a, **_k):
        return self

    def fetchone(self):
        return None

    def fetchall(self):
        return []


@dataclass
class TwoPrincipals:
    client_a: TestClient
    client_b: TestClient
    a: Principal
    b: Principal
    store: FileGameStore
    coordinator: FakeTurnCoordinator
    game_a: UUID
    seed_name: str
    runtime: Any = field(default=None)


def _client(token: str) -> TestClient:
    client = TestClient(api.app, raise_server_exceptions=False)
    csrf = CsrfSigner(SECRET).issue()
    client.cookies.set("rpg_access", token)
    client.cookies.set("rpg_csrf", csrf)
    client.headers["Origin"] = ORIGIN
    client.headers["X-CSRF-Token"] = csrf
    return client


@pytest.fixture
def two_principals(monkeypatch, tmp_path) -> TwoPrincipals:
    import persistence

    monkeypatch.setenv("RPG_SESSION_SECRET", SECRET)
    monkeypatch.setenv("RPG_AUTH_CAPTCHA_REQUIRED", "0")
    saves = tmp_path / "legacy_saves"
    saves.mkdir()
    monkeypatch.setattr(persistence, "SAVES_DIR", str(saves))

    # Fase 1: estado válido via /game/new legacy (MockLLM).
    monkeypatch.setenv("RPG_RUNTIME_PROFILE", "legacy")
    seed = TestClient(api.app)
    response = seed.post(
        "/game/new",
        json={
            "name": SEED_NAME,
            "race": "Humano",
            "class_name": "Devoto do Abismo",
            "region": "Nova Arcádia",
            "level": 1,
        },
    )
    assert response.status_code == 200, response.text
    game_id = UUID(response.json()["game_id"])
    state = persistence.load_game_state(persistence.save_path(str(game_id)))
    assert state

    # Fase 2: perfil DB offline com store em arquivo.
    identity = FakeIdentity()
    from services.game_serialization import deserialize_game_state, serialize_game_state

    store = FileGameStore(
        tmp_path / "games", encode=serialize_game_state, decode=deserialize_game_state
    )
    coordinator = FakeTurnCoordinator(store)
    runtime = SimpleNamespace(
        identity_verifier=identity,
        rate_limiter=MemoryRateLimiter(),
        game_store=store,
        turn_coordinator=coordinator,
        resources=(SimpleNamespace(connection=_NoRowsConnection),),
        memory_store=None,
        blob_store=object(),
        runtime_catalog=JsonRuntimeCatalogStore(tmp_path / "runtime_catalog.json"),
    )
    monkeypatch.setenv("RPG_RUNTIME_PROFILE", "local")
    monkeypatch.setattr("infrastructure.runtime.get_runtime", lambda: runtime)
    state.pop("_storage_version", None)
    store.create(identity.a, state)
    return TwoPrincipals(
        client_a=_client("a"),
        client_b=_client("b"),
        a=identity.a,
        b=identity.b,
        store=store,
        coordinator=coordinator,
        game_a=game_id,
        seed_name=SEED_NAME,
        runtime=runtime,
    )


# --- helpers puros (reutilizados pela SPEC-338) ------------------------------

_LEAK_PATTERNS = (
    "Traceback",
    'File "',
    "site-packages",
    "C:\\",
    "/home/",
    "/tmp/",
    "psycopg",
    "SQLSTATE",
)


def forbidden_leak(body: str) -> list[str]:
    """Trechos proibidos (R11) presentes no corpo de uma resposta de erro."""
    import os

    found = [p for p in _LEAK_PATTERNS if p in body]
    if re.search(r"select ", body, re.IGNORECASE):
        found.append("select ")
    secret = os.getenv("RPG_SESSION_SECRET")
    if secret and secret in body:
        found.append("RPG_SESSION_SECRET")
    return found


HSTS_VALUE = "max-age=63072000; includeSubDomains"


def assert_security_headers(response, *, path: str, hsts: bool) -> None:
    """R1 + R3: conjunto mínimo de headers de segurança numa resposta."""
    h = response.headers
    assert h.get("x-request-id"), f"{path}: X-Request-ID ausente"
    assert h.get("x-content-type-options") == "nosniff", path
    assert h.get("referrer-policy") == "same-origin", path
    assert h.get("permissions-policy") == "camera=(), microphone=(self), geolocation=()", path
    assert h.get("x-frame-options") == "DENY", path
    if path in api._DOCS_PATHS:
        assert "content-security-policy" not in h, path
    else:
        assert h.get("content-security-policy") == api.CONTENT_SECURITY_POLICY, path
    if hsts:
        assert h.get("strict-transport-security") == HSTS_VALUE, path
    else:
        assert "strict-transport-security" not in h, path


@pytest.fixture
def spa_mount(tmp_path):
    """Garante um mount estático de SPA em ``/`` (web/dist pode não existir no CI)."""
    from starlette.routing import Mount
    from starlette.staticfiles import StaticFiles

    existing = [r for r in api.app.router.routes if getattr(r, "name", None) == "frontend"]
    if existing:
        yield existing[0]
        return
    dist = tmp_path / "dist"
    (dist / "assets").mkdir(parents=True)
    (dist / "index.html").write_text("<html><body>spa</body></html>", encoding="utf-8")
    (dist / "assets" / "x.js").write_text("console.log(1)", encoding="utf-8")
    mount = Mount("/", app=StaticFiles(directory=str(dist), html=True), name="frontend")
    api.app.router.routes.append(mount)
    try:
        yield mount
    finally:
        api.app.router.routes.remove(mount)
