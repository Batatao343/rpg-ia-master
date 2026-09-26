"""Handler idempotente para jobs de embedding."""

from __future__ import annotations

from collections.abc import Callable, Sequence

from infrastructure.pgvector_memory import PgVectorMemoryStore


def embed_memory_job(store: PgVectorMemoryStore, payload: dict,
                     embedder: Callable[[str], Sequence[float]]) -> dict:
    memory_id = str(payload["memory_id"])
    with store.pool.connection() as connection:
        row = connection.execute(
            "select content,content_sha256,embedding_status from app.memory_documents where id=%s",
            (memory_id,),
        ).fetchone()
    if not row:
        return {"status": "missing"}
    if row['embedding_status'] == 'discarded':
        return {'status': 'discarded'}
    if row["embedding_status"] == "ready":
        return {"status": "already_ready"}
    values = embedder(row["content"])
    store.set_embedding(memory_id, values, content_sha256=row["content_sha256"])
    return {"status": "ready", "dimensions": len(values)}
