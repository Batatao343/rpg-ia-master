"""SPEC-207 Etapa 4: endpoint de auditoria contra Postgres REAL local.

Uma conexão única por teste; tudo é desfeito com ROLLBACK no fim (nenhum dado
fica no banco local). Só roda com RPG_TEST_DATABASE_URL (Supabase local).
"""
from __future__ import annotations

import io
import json
import os
import uuid
import zipfile
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

import persistence

pytestmark = pytest.mark.infra_local

ORIGIN = "http://localhost:5173"


class SingleConnectionPool:
    def __init__(self, connection):
        self.db = connection

    def connection(self):
        db = self.db

        class Context:
            def __enter__(self_inner):
                return db

            def __exit__(self_inner, *_args):
                return False
        return Context()


def _played_state(monkeypatch) -> dict:
    """Campanha MockLLM real (perfil legacy) com 2 turnos — vira o fixture do banco."""
    import api
    monkeypatch.setenv("RPG_RATE_LIMIT", "0")
    api._rate_hits.clear()
    client = TestClient(api.app)
    r = client.post("/game/new", json={"name": "Auditada", "race": "Humano",
                                       "class_name": "Sangromante", "region": "Nova Arcádia",
                                       "level": 1, "backstory": ""})
    assert r.status_code == 200, r.text
    gid = r.json()["game_id"]
    for text in ("Olho ao redor.", "Meu email é dono.fixture@example.com, anote."):
        assert client.post("/game/action", json={"input_text": text, "game_id": gid,
                                                 "action_id": str(uuid.uuid4())}).status_code == 200
    return persistence.load_game_state(persistence.save_path(gid))


@pytest.fixture()
def pg(monkeypatch):
    psycopg = pytest.importorskip("psycopg")
    from psycopg.rows import dict_row
    dsn = os.getenv("RPG_TEST_DATABASE_URL")
    if not dsn:
        pytest.skip("RPG_TEST_DATABASE_URL ausente")
    state = _played_state(monkeypatch)
    connection = psycopg.connect(dsn, row_factory=dict_row)
    try:
        if connection.execute("select to_regclass('app.usage_events') as r").fetchone()["r"] is None:
            pytest.skip("migrations locais ausentes")
        yield connection, state
    finally:
        connection.rollback()
        connection.close()


@pytest.fixture()
def world(pg, monkeypatch):
    from infrastructure.contracts import Principal, Unauthorized
    from infrastructure.local_adapters import MemoryRateLimiter
    from infrastructure.postgres import PostgresGameStore
    from services.account_security import proof
    from services.auth_sessions import CsrfSigner
    import api

    connection, state = pg
    a, b, c = uuid.uuid4(), uuid.uuid4(), uuid.uuid4()
    tokens = {"tok-a": a, "tok-b": b, "tok-c": c}

    class Identity:
        def verify(self, token):
            if token not in tokens:
                raise Unauthorized("invalid")
            owner = tokens[token]
            return Principal(owner, "auth", str(owner))

    pool = SingleConnectionPool(connection)
    store = PostgresGameStore(pool)
    runtime = SimpleNamespace(identity_verifier=Identity(), rate_limiter=MemoryRateLimiter(),
                              game_store=store)
    monkeypatch.setenv("RPG_SESSION_SECRET", "s" * 32)
    monkeypatch.setattr(api, "_database_profile", lambda: True)
    monkeypatch.setattr("infrastructure.runtime.get_runtime", lambda: runtime)

    game_id = uuid.UUID(str(state["game_id"]))
    stored = store.create(Principal(a, "auth", str(a)), state)
    narrator = [row for row in state["presentation_history"] if row["role"] == "narrator"][-1]
    operation = uuid.uuid4()
    connection.execute(
        """insert into app.operations(id,owner_id,game_id,kind,status,request_sha256)
           values (%s,%s,%s,'turn','completed',%s)""", (operation, a, game_id, "0" * 64))
    connection.execute(
        """insert into app.turns(operation_id,game_id,owner_id,sequence,timeline_epoch,route,
           input_sha256,state_version_before,latency_ms,llm_cost_usd,presentation_entry_id)
           values (%s,%s,%s,1,0,'storyteller',%s,%s,321,0.000100000,%s)""",
        (operation, game_id, a, "0" * 64, stored.version, narrator["id"]))
    for ordinal, cost in enumerate(("0.000041550", "0.000020000")):
        connection.execute(
            """insert into app.usage_events(event_id,operation_id,owner_id,game_id,component,
               attempt_ordinal,category,provider,model,outcome,cost_usd,cost_basis,
               pricing_version,billing_exact,event_sha256)
               values (%s,%s,%s,%s,'llm:test',%s,'llm','test','test','success',%s,
                       'estimated','test',false,%s)""",
            (uuid.uuid4(), operation, a, game_id, ordinal, cost, str(ordinal) * 64))
    failed = uuid.uuid4()
    connection.execute(
        """insert into app.operations(id,owner_id,game_id,kind,status,request_sha256,error_code)
           values (%s,%s,%s,'turn','failed',%s,'TimeoutError')""", (failed, a, game_id, "1" * 64))

    def client_for(token: str, *, recent: bool = True) -> TestClient:
        client = TestClient(api.app)
        client.headers["Origin"] = ORIGIN
        csrf = CsrfSigner("s" * 32).issue()
        client.cookies.set("rpg_access", token)
        client.cookies.set("rpg_csrf", csrf)
        client.headers["X-CSRF-Token"] = csrf
        if recent:
            client.cookies.set("rpg_recent", proof(tokens[token], "recent", token))
        return client

    return SimpleNamespace(connection=connection, game_id=game_id, a=a, b=b, c=c,
                           operation=operation, failed=failed, client_for=client_for,
                           runtime=runtime, state=state)


def _files(data: bytes) -> dict:
    with zipfile.ZipFile(io.BytesIO(data)) as archive:
        return {n: archive.read(n) for n in archive.namelist()}


def test_owner_can_export_own_game(world):
    from services.audit_export import verify_audit_zip
    before = world.connection.execute("select count(*) as n from app.usage_events").fetchone()["n"]
    r = world.client_for("tok-a").post(f"/game/{world.game_id}/audit-export")
    assert r.status_code == 200, r.text
    assert r.headers["content-type"] == "application/zip"
    assert r.headers["cache-control"] == "no-store"
    assert r.headers["content-disposition"].startswith("attachment;")
    owner_values = {str(world.a), "dono.fixture@example.com"}
    assert verify_audit_zip(r.content, owner_values=owner_values) == []
    blob = b"".join(_files(r.content).values()).decode(errors="ignore")
    for needle in (str(world.a), world.a.hex, str(world.game_id), str(world.operation),
                   str(world.failed), "dono.fixture@example.com"):
        assert needle not in blob
    after = world.connection.execute("select count(*) as n from app.usage_events").fetchone()["n"]
    assert after == before  # R12: export não gera usage_events


def test_cost_sums_usage_events(world):
    from observability.telemetry import pseudonym
    r = world.client_for("tok-a").post(f"/game/{world.game_id}/audit-export")
    files = _files(r.content)
    rows = [json.loads(x) for x in files["sessions/0.jsonl"].decode().splitlines()]
    priced = [row for row in rows if row["sequence"] == 1]
    assert len(priced) == 1
    assert priced[0]["cost_usd"] == "0.00006155"
    assert priced[0]["action_ref"] == pseudonym(world.operation)
    timings = [json.loads(x) for x in files["timings.jsonl"].decode().splitlines()]
    assert any(t.get("latency_ms") == 321 for t in timings)
    errors = [json.loads(x) for x in files["errors.jsonl"].decode().splitlines()]
    assert any(e.get("code") == "turn_failed" and e.get("error_class") == "TimeoutError"
               for e in errors)


def test_cross_account_404(world):
    other = world.client_for("tok-b")
    foreign = other.post(f"/game/{world.game_id}/audit-export")
    missing = other.post(f"/game/{uuid.uuid4()}/audit-export")
    assert foreign.status_code == missing.status_code == 404
    assert foreign.content == missing.content
    assert foreign.headers.get("content-type") == missing.headers.get("content-type")


def test_requires_recent_proof_403(world):
    r = world.client_for("tok-a", recent=False).post(f"/game/{world.game_id}/audit-export")
    assert r.status_code == 403 and r.json()["detail"] == "recent_session_required"
    # prova de OUTRO dono não serve
    client = world.client_for("tok-a", recent=False)
    from services.account_security import proof
    client.cookies.set("rpg_recent", proof(world.b, "recent", "tok-a"))
    assert client.post(f"/game/{world.game_id}/audit-export").status_code == 403
    # Revisão Astra: prova do próprio dono porém EXPIRADA (> 300 s) também é 403.
    import time
    expired = world.client_for("tok-a", recent=False)
    expired.cookies.set("rpg_recent", proof(world.a, "recent", "tok-a", now=int(time.time()) - 301))
    assert expired.post(f"/game/{world.game_id}/audit-export").status_code == 403


def test_csrf_required(world):
    client = world.client_for("tok-a")
    del client.headers["X-CSRF-Token"]
    assert client.post(f"/game/{world.game_id}/audit-export").status_code == 401


def test_deleted_account_401(world):
    world.connection.execute("insert into app.account_deletions(owner_id) values (%s)", (world.c,))
    r = world.client_for("tok-c").post(f"/game/{uuid.uuid4()}/audit-export")
    assert r.status_code == 401 and r.json()["detail"] == "account_deleted"


def test_rate_limit_429(world):
    client = world.client_for("tok-a")
    codes = [client.post(f"/game/{world.game_id}/audit-export").status_code for _ in range(4)]
    assert codes == [200, 200, 200, 429]
    # balde é por dono: B não é afetado
    assert world.client_for("tok-b").post(f"/game/{uuid.uuid4()}/audit-export").status_code == 404
