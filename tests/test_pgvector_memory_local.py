from __future__ import annotations

import hashlib
import os
from uuid import uuid4

import pytest

from infrastructure.contracts import (
    JobRequest, LeasedJob, MemoryDocument, MemoryQuery, MemoryWriteIntent, Principal,
)


pytestmark = pytest.mark.infra_local


def test_pending_fts_embedding_namespace_e_restore():
    pytest.importorskip("psycopg")
    from infrastructure.pgvector_memory import PgVectorMemoryStore
    from infrastructure.postgres import PostgresGameStore, PostgresPool
    dsn = os.getenv("RPG_TEST_DATABASE_URL")
    if not dsn:
        pytest.skip("RPG_TEST_DATABASE_URL ausente")
    pool = PostgresPool(dsn)
    owner_id, other_id, game_id = uuid4(), uuid4(), uuid4()
    principal = Principal(owner_id, "test", str(owner_id), local=True)
    other = Principal(other_id, "test", str(other_id), local=True)
    state = {"game_id": str(game_id), "messages": [], "event_log": [], "player": {}, "world": {}}
    PostgresGameStore(pool).create(principal, state)
    store = PgVectorMemoryStore(pool, embedder=lambda _text: [1.0] + [0.0] * 1023)
    try:
        intent = MemoryWriteIntent(
            MemoryDocument("memory-local", "A coroa rubra caiu no poço", "session",
                           {"visibility": "public", "commit_version": 2}),
            principal, game_id, timeline_epoch=0,
        )
        store.stage(intent)
        pending = store.query(MemoryQuery("coroa rubra", "session", principal, game_id, k=3))
        assert [doc.document_id for doc in pending] == ["memory-local"]
        assert store.query(MemoryQuery("coroa rubra", "session", other, game_id, k=3)) == []
        digest = hashlib.sha256(intent.document.text.encode()).hexdigest()
        store.set_embedding("memory-local", [1.0] + [0.0] * 1023, content_sha256=digest)
        assert store.query(MemoryQuery("qualquer", "session", principal, game_id))[0].document_id == "memory-local"
        assert store.discard_after(game_id=game_id, timeline_epoch=0, commit_version=1) == 1
        assert store.query(MemoryQuery("coroa", "session", principal, game_id)) == []
    finally:
        PostgresGameStore(pool).delete(principal, game_id)
        pool.close()


def test_embedding_job_retries_record_every_provider_attempt_once():
    pytest.importorskip("psycopg")
    dsn = os.getenv("RPG_TEST_DATABASE_URL")
    if not dsn:
        pytest.skip("RPG_TEST_DATABASE_URL ausente")
    from infrastructure.postgres import PostgresGameStore, PostgresPool
    from infrastructure.postgres_jobs import PostgresJobQueue
    from infrastructure.usage_events import append_embedding_job_attempt
    from psycopg.types.json import Jsonb

    pool = PostgresPool(dsn)
    owner_id, game_id = uuid4(), uuid4()
    principal = Principal(owner_id, "test", str(owner_id), local=True)
    PostgresGameStore(pool).create(principal, {
        "game_id": str(game_id), "messages": [], "event_log": [], "player": {}, "world": {},
    })
    memory_id = f"memory-{uuid4()}"
    job_id, lease_token = uuid4(), uuid4()
    try:
        with pool.connection() as connection, connection.transaction():
            connection.execute(
                """insert into app.jobs
                  (id,owner_id,game_id,kind,dedupe_key,status,payload,max_attempts,
                   lease_token,lease_owner,lease_until)
                values (%s,%s,%s,'embed_memory',%s,'running',%s,3,%s,'metering-test',
                        now()+interval '1 minute')""",
                (job_id, owner_id, game_id, memory_id, Jsonb({"memory_id": memory_id}),
                 lease_token),
            )
        queue = PostgresJobQueue(pool)
        job = LeasedJob(job_id, lease_token, JobRequest(
            "embed_memory", memory_id, {"memory_id": memory_id},
            owner_id=owner_id, game_id=game_id), 1)
        attempts = [
            {"provider": "jina", "model": "jina-embeddings-v3",
             "outcome": "http_error", "network_attempted": True, "usage": {}},
            {"provider": "jina", "model": "jina-embeddings-v3",
             "outcome": "response", "network_attempted": True,
             "usage": {"input_tokens": 17}},
        ]
        append_embedding_job_attempt(pool, job, attempts[:1])
        append_embedding_job_attempt(pool, job, attempts)
        append_embedding_job_attempt(pool, job, attempts)
        with pool.connection() as connection:
            rows = connection.execute(
                """select attempt_ordinal,input_units,category,cost_basis
                from app.usage_events where operation_id=%s order by attempt_ordinal""",
                (job.job_id,),
            ).fetchall()
        assert len(rows) == 2
        assert [row["attempt_ordinal"] for row in rows] == [0, 1]
        assert rows[1]["input_units"] == 17
        assert all(row["category"] == "embedding" for row in rows)
        assert "SECRET_MEMORY_TEXT" not in repr(rows)
        queue.complete(job.job_id, job.lease_token, {"ok": True})
    finally:
        PostgresGameStore(pool).delete(principal, game_id)
        pool.close()
