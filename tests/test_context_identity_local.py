"""Principal propagation through real RAG readers and local pgvector storage."""
import asyncio
import os
from types import SimpleNamespace
from uuid import uuid4

import pytest

from infrastructure.contracts import MemoryDocument, MemoryWriteIntent, Principal
from infrastructure.request_context import principal_scope
from services.context_sources import EmbeddedContextQuery, acquire_context_sources, acquire_context_sources_async

pytestmark = pytest.mark.infra_local


@pytest.mark.parametrize('mode', ['serial', 'parallel', 'async'])
def test_authenticated_context_reads_only_own_campaign(monkeypatch, mode):
    pytest.importorskip('psycopg')
    dsn = os.getenv('RPG_TEST_DATABASE_URL')
    if not dsn:
        pytest.skip('RPG_TEST_DATABASE_URL required')
    import rag
    from infrastructure.pgvector_memory import PgVectorMemoryStore
    from infrastructure.postgres import PostgresGameStore, PostgresPool
    from tests.test_postgres_jobs_local import _state

    pool = PostgresPool(dsn)
    store, memory = PostgresGameStore(pool), PgVectorMemoryStore(pool)
    principals = [Principal(uuid4(), 'test', 'audit') for _ in range(2)]
    games = [uuid4(), uuid4()]
    monkeypatch.setenv('RPG_RUNTIME_PROFILE', 'local')
    monkeypatch.setattr('infrastructure.runtime.get_runtime', lambda: SimpleNamespace(memory_store=memory))
    try:
        for index, (principal, game) in enumerate(zip(principals, games)):
            store.create(principal, _state(game))
            for scope in ('session', 'npc'):
                memory.stage(MemoryWriteIntent(
                    MemoryDocument(f'{game}:{scope}', f'ambar owner{index} {scope}', scope),
                    principal, game, 'npc_a' if scope == 'npc' else None,
                ))
        args = dict(game_id=str(games[0]), npc_id='npc_a', readers={
            'session': lambda: rag.query_session_memory('ambar', str(games[0])),
            'npc': lambda: rag.query_npc_memory(str(games[0]), 'npc_a', 'ambar'),
        })
        with principal_scope(principals[0]):
            query = EmbeddedContextQuery('ambar', None, None, None)
            rows = (asyncio.run(acquire_context_sources_async(query, **args)) if mode == 'async'
                    else acquire_context_sources(query, max_workers=1 if mode == 'serial' else 3, **args))
        assert all(row.status == 'ok' and 'owner0' in row.text and 'owner1' not in row.text for row in rows)
        with principal_scope(principals[1]):
            assert not rag.query_session_memory('ambar', str(games[0]))
    finally:
        for principal, game in zip(principals, games):
            store.delete(principal, game)
        pool.close()
