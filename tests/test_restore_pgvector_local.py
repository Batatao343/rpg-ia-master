import copy
from uuid import uuid4

import pytest

from infrastructure.contracts import MemoryDocument, MemoryWriteIntent, Principal
from infrastructure.pgvector_memory import PgVectorMemoryStore
from services.turn_effects import effect_scope
from tests.test_postgres_jobs_local import infra, _state  # noqa: F401

pytestmark = pytest.mark.infra_local


def test_atomic_memory_rollback_and_restore(infra):
    store, queue, coordinator, _ = infra
    gid, owner = uuid4(), uuid4()
    principal = Principal(owner, 'test', str(owner), local=True)
    first = _state(gid)
    first['continuity'] = {'timeline_epoch': 0}
    version = store.create(principal, first).version
    memory = PgVectorMemoryStore(store.pool)

    def commit(state, name, *, checkpoint=False, abort=False):
        nonlocal version
        claim = coordinator.claim(principal, uuid4(), game_id=gid, kind='turn',
                                  request_hash='a' * 64, base_version=version)
        try:
            with effect_scope() as effects:
                memory.stage(MemoryWriteIntent(MemoryDocument(name, name, 'session', {}), principal, gid))
                if abort:
                    effects.defer(lambda *_: (_ for _ in ()).throw(RuntimeError('injected')))
                version, _ = coordinator.commit_game(principal, claim, state,
                    receipt={'response': {}}, input_sha256='a' * 64, latency_ms=0,
                    llm_cost_usd=0, checkpoint=checkpoint)
        except Exception:
            coordinator.fail(claim, 'injected')
            raise

    try:
        commit(first, f'early-{gid}', checkpoint=True)
        with pytest.raises(RuntimeError, match='injected'):
            commit(first, f'aborted-{gid}', abort=True)
        with store.pool.connection() as conn:
            assert conn.execute('select count(*) n from app.memory_documents where game_id=%s', (gid,)).fetchone()['n'] == 1
            assert conn.execute('select count(*) n from app.jobs where game_id=%s', (gid,)).fetchone()['n'] == 1
        later = copy.deepcopy(first)
        later['world']['turn_count'] = 5
        commit(later, f'late-{gid}')
        restored = copy.deepcopy(first)
        restored['continuity']['timeline_epoch'] = 1
        commit(restored, f'restored-{gid}')
        with store.pool.connection() as conn:
            rows = conn.execute('select content,embedding_status,commit_version from app.memory_documents where game_id=%s', (gid,)).fetchall()
        by_text = {r['content']: r for r in rows}
        assert by_text[f'early-{gid}']['embedding_status'] == 'pending'
        assert by_text[f'late-{gid}']['embedding_status'] == 'discarded'
        assert by_text[f'restored-{gid}']['commit_version'] == version
    finally:
        store.delete(principal, gid)
