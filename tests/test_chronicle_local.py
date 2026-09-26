from __future__ import annotations

import os
from uuid import uuid4

import pytest
from langchain_core.messages import AIMessage

from infrastructure.contracts import MemoryQuery, Principal
from services.chronicle import append_entry, open_chapter
from workers.chronicle_jobs import compress_chronicle_job


pytestmark = pytest.mark.infra_local


class _Fallback:
    def with_structured_output(self, _schema):
        return self

    def invoke(self, _messages):
        return AIMessage(content="indisponível")


def test_compressao_overlay_e_busca_lexical_da_cronica_local():
    pytest.importorskip("psycopg")
    dsn = os.getenv("RPG_TEST_DATABASE_URL")
    if not dsn:
        pytest.skip("RPG_TEST_DATABASE_URL ausente")
    from infrastructure.pgvector_memory import PgVectorMemoryStore
    from infrastructure.postgres import PostgresGameStore, PostgresPool
    from infrastructure.postgres_jobs import PostgresJobQueue
    from services.chronicle_repository import ChronicleRepository

    pool = PostgresPool(dsn)
    store = PostgresGameStore(pool)
    memory = PgVectorMemoryStore(pool)
    repository = ChronicleRepository(pool, memory)
    owner_id, game_id = uuid4(), uuid4()
    principal = Principal(owner_id, "test", str(owner_id), local=True)
    chronicle = open_chapter([], title="Arco", turn=0, location="Cais")
    for turn in range(20):
        chronicle = append_entry(
            chronicle, text=f"O mercador negociou âmbar no cais {turn}.",
            turn=turn, kind="prose",
        )
    state = {
        "game_id": str(game_id), "messages": [], "event_log": [],
        "player": {"name": "Iria", "class_name": "Devoto", "level": 1},
        "world": {"current_location": "Cais", "turn_count": 20,
                  "world_clock": {"day": 1}},
        "continuity": {"timeline_epoch": 0}, "chronicle": chronicle,
    }
    store.create(principal, state)
    assert repository.enqueue_due(principal, state) == 1
    queue = PostgresJobQueue(pool)
    # Isolate this fixture from jobs left by an interrupted local smoke.
    kind = f"chronicle-test-{game_id}"
    with pool.connection() as connection, connection.transaction():
        connection.execute('update app.jobs set kind=%s where game_id=%s', (kind, game_id))
    job = queue.lease("chronicle-test", {kind}, 1)[0]
    digest = compress_chronicle_job(job.request.payload, llm=_Fallback())
    repository.complete(job.request.payload, digest)
    queue.complete(job.job_id, job.lease_token, {"status": digest["status"]})
    overlaid = repository.overlay(principal, state)
    assert overlaid["chronicle"][0]["digest"]["covered_entry_count"] == 20
    found = memory.query(MemoryQuery(
        "mercador âmbar", "chronicle", principal=principal, game_id=game_id, k=3,
    ))
    assert found and all(row.metadata["chapter_id"] for row in found)
    store.delete(principal, game_id)
    pool.close()
