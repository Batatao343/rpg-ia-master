"""Kill only spawned test children, checking durable local Postgres boundaries."""
from __future__ import annotations

import multiprocessing
import os
from uuid import UUID, uuid4

import pytest

from infrastructure.contracts import JobRequest, Principal
from tests.test_postgres_jobs_local import infra, _state  # noqa: F401

pytestmark = pytest.mark.infra_local


def _worker_child(dsn, kind, signal):
    from infrastructure.postgres import PostgresPool
    from infrastructure.postgres_jobs import PostgresJobQueue
    from workers.job_worker import JobWorker
    pool = PostgresPool(dsn, max_size=2)
    queue = PostgresJobQueue(pool, lease_seconds=30)
    def interrupted_handler(payload):
        signal.send('handler_started')
        signal.recv()  # Parent deliberately kills us before publication.
        return {'unexpected': True}
    JobWorker(queue, {kind: interrupted_handler}, worker_id='crash-child').run_once()


def _art_child(dsn, generation, signal):
    from types import SimpleNamespace
    from infrastructure.postgres import PostgresPool
    from services.dynamic_art import DynamicArtRepository
    from tests.fakes.fake_image_generator import FakeImageGenerator
    pool = PostgresPool(dsn, max_size=2)
    repository = DynamicArtRepository(pool, model='fake-only', profile_version='crash-test')
    assert repository.begin(UUID(generation))
    generator = FakeImageGenerator()
    generator.generate(SimpleNamespace(model='fake-only'))
    signal.send('fake_provider_returned_once')
    signal.recv()  # Crash after external result, before durable publication.


def _transaction_child(dsn, owner, game, version, operation, signal):
    from infrastructure.postgres import PostgresPool
    from infrastructure.postgres_turns import PostgresTurnCoordinator
    from services.turn_effects import effect_scope
    pool = PostgresPool(dsn, max_size=2)
    coordinator = PostgresTurnCoordinator(pool, lease_seconds=30)
    principal = Principal(UUID(owner), 'test', owner, local=True)
    claim = coordinator.claim(principal, UUID(operation), game_id=UUID(game),
        kind='turn', request_hash='a' * 64, base_version=version)
    changed = _state(UUID(game))
    changed['world']['turn_count'] = 99
    def before_commit(connection, epoch, committed_version):
        from services.dynamic_art import DynamicArtRepository
        from services.art_triggers import ArtGenerationRequest
        repository = DynamicArtRepository(pool, model='fake-only', profile_version='crash-test')
        repository.reserve(principal, UUID(game), timeline_epoch=epoch, generation_id=uuid4(),
            request=ArtGenerationRequest('player_portrait', operation, 'player', 'player', None, operation),
            brief={'subject': 'Teste', 'canon': ['Valoria'], 'player_description': 'adulto',
                   'composition': ['natural pose'], 'exclusions': [], 'reference_asset_ids': [],
                   'profile_version': 'crash-test', 'size': '1024x1536'}, connection=connection)
        signal.send('state_written_uncommitted')
        signal.recv()
    with effect_scope() as effects:
        effects.defer(before_commit)
        coordinator.commit_game(principal, claim, changed, receipt={'ok': True},
            input_sha256='b' * 64, latency_ms=0, llm_cost_usd=0, checkpoint=True)


def _kill_at_boundary(target, args, expected):
    context = multiprocessing.get_context('spawn')
    parent, child = context.Pipe()
    process = context.Process(target=target, args=(*args, child))
    process.start()
    child.close()
    try:
        assert parent.poll(30), f'child did not reach {expected}; exit={process.exitcode}'
        assert parent.recv() == expected
        process.kill()
        process.join(10)
        assert not process.is_alive()
        assert process.exitcode != 0
    finally:
        if process.is_alive():
            process.kill()
            process.join(10)
        parent.close()
        process.close()


def test_killed_worker_job_can_be_reclaimed_and_completed(infra):
    from workers.job_worker import JobWorker
    _, queue, _, _ = infra
    kind = f'process-crash-{uuid4()}'
    job_id = queue.enqueue(JobRequest(kind, kind, {}))
    try:
        _kill_at_boundary(_worker_child, (os.environ['RPG_TEST_DATABASE_URL'], kind), 'handler_started')
        assert queue.lease('too-early', {kind}, 1) == []
        with queue.pool.connection() as connection, connection.transaction():
            connection.execute("update app.jobs set lease_until=now()-interval '1 second' where id=%s", (job_id,))
        calls = []
        def recover(payload):
            calls.append(payload)
            return {'recovered': True}
        assert JobWorker(queue, {kind: recover}, worker_id='replacement').run_once() == 1
        assert calls == [{}]
        with queue.pool.connection() as connection:
            row = connection.execute('select status, attempts from app.jobs where id=%s', (job_id,)).fetchone()
        assert row['status'] == 'succeeded'
        assert row['attempts'] == 2
    finally:
        with queue.pool.connection() as connection, connection.transaction():
            connection.execute('delete from app.jobs where id=%s', (job_id,))


def test_kill_during_turn_commit_rolls_back_state_turn_and_checkpoint(infra):
    store, _, coordinator, _ = infra
    owner, game, operation = uuid4(), uuid4(), uuid4()
    principal = Principal(owner, 'test', str(owner), local=True)
    created = store.create(principal, _state(game))
    try:
        _kill_at_boundary(_transaction_child,
            (os.environ['RPG_TEST_DATABASE_URL'], str(owner), str(game), created.version, str(operation)),
            'state_written_uncommitted')
        loaded = store.get(principal, game)
        assert loaded.version == created.version
        assert loaded.state['world']['turn_count'] == 0
        assert coordinator.receipt(principal, operation) is None
        with coordinator.pool.connection() as connection:
            assert connection.execute('select count(*) as n from app.turns where operation_id=%s', (operation,)).fetchone()['n'] == 0
            assert connection.execute('select count(*) as n from app.game_checkpoints where game_id=%s', (game,)).fetchone()['n'] == 0
            assert connection.execute('select count(*) as n from app.art_generations where game_id=%s', (game,)).fetchone()['n'] == 0
    finally:
        store.delete(principal, game)


def test_art_crash_after_provider_requires_reconciliation_without_regeneration(infra):
    from types import SimpleNamespace
    from infrastructure.contracts import Conflict
    from services.dynamic_art import DynamicArtRepository
    from services.art_triggers import ArtGenerationRequest
    from tests.fakes.fake_image_generator import FakeImageGenerator
    store, _, _, _ = infra
    owner, game, generation = uuid4(), uuid4(), uuid4()
    principal = Principal(owner, 'test', str(owner), local=True)
    store.create(principal, _state(game))
    repository = DynamicArtRepository(store.pool, model='fake-only', profile_version='crash-test')
    try:
        repository.reserve(principal, game, timeline_epoch=0, generation_id=generation,
            request=ArtGenerationRequest('player_portrait', str(generation), 'player', 'player', None, str(generation)),
            brief={'subject': 'Teste', 'canon': ['Valoria'], 'player_description': 'adulto',
                   'composition': ['natural pose'], 'exclusions': [], 'reference_asset_ids': [],
                   'profile_version': 'crash-test', 'size': '1024x1536'})
        _kill_at_boundary(_art_child, (os.environ['RPG_TEST_DATABASE_URL'], str(generation)),
                          'fake_provider_returned_once')
        row = repository.get(principal, generation)
        assert row['status'] == 'generating' and row['worker_inactive']
        replacement = FakeImageGenerator()
        with pytest.raises(Conflict):
            if repository.begin(generation):
                replacement.generate(SimpleNamespace(model='fake-only'))
        assert replacement.calls == 0
        assert repository.assets(principal, generation) == []
    finally:
        store.delete(principal, game)
