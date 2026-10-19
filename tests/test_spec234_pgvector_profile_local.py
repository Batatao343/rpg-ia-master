"""SPEC-234 R9 contra Postgres/pgvector REAL (Supabase local, `-m infra_local`).

Cobre `_ensure_profile`, recusa de dimensão != 1024, `migrate_legacy_profile`
idempotente e isolamento de vetores por `embedding_profile_id`. Usa um perfil
de teste único e desfaz qualquer rename de documentos alheios ao teste.
"""
from __future__ import annotations

import hashlib
import os
from uuid import uuid4

import pytest

from infrastructure.contracts import (
    Conflict,
    MemoryDocument,
    MemoryQuery,
    MemoryWriteIntent,
    Principal,
)

pytestmark = pytest.mark.infra_local

_VEC_A = [1.0] + [0.0] * 1023


def _intent(doc_id: str, text: str, principal, game_id) -> MemoryWriteIntent:
    return MemoryWriteIntent(
        MemoryDocument(doc_id, text, "session", {"visibility": "public", "commit_version": 1}),
        principal, game_id, timeline_epoch=0,
    )


def test_spec234_profile_ensure_migrate_and_isolation():
    pytest.importorskip("psycopg")
    dsn = os.getenv("RPG_TEST_DATABASE_URL")
    if not dsn:
        pytest.skip("RPG_TEST_DATABASE_URL ausente")
    from infrastructure.pgvector_memory import PgVectorMemoryStore
    from infrastructure.postgres import PostgresGameStore, PostgresPool

    with pytest.raises(ValueError):
        PgVectorMemoryStore(object(), dimensions=768)

    pool = PostgresPool(dsn)
    profile = f"spec234test-m{uuid4().hex[:8]}-1024"
    other_profile = f"spec234test-o{uuid4().hex[:8]}-1024"
    owner_id, game_id = uuid4(), uuid4()
    principal = Principal(owner_id, "test", str(owner_id), local=True)
    PostgresGameStore(pool).create(principal, {
        "game_id": str(game_id), "messages": [], "event_log": [], "player": {}, "world": {},
    })
    legacy = PgVectorMemoryStore(pool)
    store = PgVectorMemoryStore(pool, profile_id=profile)
    other = PgVectorMemoryStore(pool, profile_id=other_profile)
    with pool.connection() as connection:
        foreign_legacy = {row["id"] for row in connection.execute(
            "select id from app.memory_documents where embedding_profile_id='local-1024'",
        ).fetchall()}
    try:
        # _ensure_profile: a linha do perfil nasce no primeiro stage
        doc_new = f"spec234-new-{uuid4().hex[:8]}"
        store.stage(_intent(doc_new, "A lanterna azul de Brekmar", principal, game_id))
        with pool.connection() as connection:
            row = connection.execute(
                "select provider,model,dimensions,status from app.embedding_profiles where id=%s",
                (profile,),
            ).fetchone()
        assert row is not None and row["dimensions"] == 1024 and row["status"] == "active"

        # doc legado (local-1024) -> migração renomeia, e é idempotente
        doc_old = f"spec234-old-{uuid4().hex[:8]}"
        legacy.stage(_intent(doc_old, "O sino rachado de Vorr", principal, game_id))
        changed = store.migrate_legacy_profile()
        assert changed >= 1
        assert store.migrate_legacy_profile() == 0
        with pool.connection() as connection:
            prof = connection.execute(
                "select embedding_profile_id from app.memory_documents where id=%s", (doc_old,),
            ).fetchone()["embedding_profile_id"]
        assert prof == profile

        # isolamento: vetor do perfil A nunca é servido a consulta do perfil B
        for doc_id, text in ((doc_new, "A lanterna azul de Brekmar"), (doc_old, "O sino rachado de Vorr")):
            store.set_embedding(doc_id, _VEC_A,
                                content_sha256=hashlib.sha256(text.encode()).hexdigest())
        hits = store.query(MemoryQuery("", "session", principal, game_id, k=5, vector=tuple(_VEC_A),
                                       embedding_profile_id=profile))
        assert {d.document_id for d in hits} == {doc_new, doc_old}
        assert other.query(MemoryQuery("", "session", principal, game_id, k=5,
                                       vector=tuple(_VEC_A))) == []
        # perfil divergente entre stage e set_embedding é recusado (não mistura)
        with pytest.raises(Conflict):
            other.set_embedding(doc_new, _VEC_A, content_sha256=hashlib.sha256(
                "A lanterna azul de Brekmar".encode()).hexdigest())
    finally:
        with pool.connection() as connection, connection.transaction():
            if foreign_legacy:
                connection.execute(
                    "update app.memory_documents set embedding_profile_id='local-1024' "
                    "where id = any(%s)", (list(foreign_legacy),),
                )
        PostgresGameStore(pool).delete(principal, game_id)
        with pool.connection() as connection, connection.transaction():
            connection.execute(
                "delete from app.memory_documents where embedding_profile_id = any(%s)",
                ([profile, other_profile],),
            )
            connection.execute(
                "delete from app.embedding_profiles where id = any(%s)",
                ([profile, other_profile],),
            )
        pool.close()

