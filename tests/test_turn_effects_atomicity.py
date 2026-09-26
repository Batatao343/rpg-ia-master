from uuid import uuid4

import pytest

from infrastructure.contracts import MemoryDocument, MemoryWriteIntent, Principal


def test_collected_memory_is_not_written_until_commit_and_discarded_on_exception():
    from services.turn_effects import effect_scope, current_effects
    principal, gid = Principal(uuid4(), 'test', 'test'), uuid4()
    intent = MemoryWriteIntent(MemoryDocument('id', 'Chove.', 'session', {}), principal, gid)
    with pytest.raises(RuntimeError):
        with effect_scope() as effects:
            effects.memory.add(intent)
            assert current_effects() is effects
            raise RuntimeError('turn aborted')
    assert current_effects() is None


def test_commit_assigns_real_version_epoch_and_normalizes_provenance():
    from services.turn_effects import effect_scope
    owner, gid = Principal(uuid4(), 'test', 'test'), uuid4()
    captured = []
    class Store:
        def stage_on(self, connection, intent):
            captured.append((connection, intent))
    with effect_scope() as effects:
        effects.memory.add(MemoryWriteIntent(MemoryDocument('id', 'Chove.', 'session', {
            'memory_provenance': 'engine', 'memory_source_turn': 3,
            'memory_source_id': 'event-3', 'memory_confidence': 'confirmed',
            'memory_entity_ids': 'npc_a, location_b',
        }), owner, gid))
        effects.flush('transaction', memory_store=Store(), principal=owner,
                      game_id=gid, epoch=2, version=17)
    assert captured[0][0] == 'transaction'
    record = captured[0][1]
    assert record.timeline_epoch == 2
    assert record.document.metadata['commit_version'] == 17
    assert record.document.metadata['source_turn'] == 3
    assert record.document.metadata['source_id'] == 'event-3'
    assert record.document.metadata['canonical_entity_ids'] == ['npc_a', 'location_b']


def test_collector_rejects_wrong_campaign():
    from services.turn_effects import effect_scope
    from infrastructure.contracts import Conflict
    owner = Principal(uuid4(), 'test', 'test')
    with effect_scope() as effects:
        effects.memory.add(MemoryWriteIntent(MemoryDocument('id', 'Chove.', 'session', {}), owner, uuid4()))
        with pytest.raises(Conflict):
            effects.flush(None, memory_store=None, principal=owner, game_id=uuid4(), epoch=0, version=1)
