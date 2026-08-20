from __future__ import annotations

import hashlib
import os
from uuid import uuid4

import pytest

from infrastructure.contracts import MemoryDocument, MemoryQuery, MemoryWriteIntent, Principal


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
