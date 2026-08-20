from uuid import uuid4

import pytest

from infrastructure.contracts import MemoryDocument, MemoryWriteIntent, Principal
from infrastructure.pgvector_memory import vector_literal
from services.memory_intents import MemoryIntentCollector


def test_vector_recusa_dimensao_incorreta():
    with pytest.raises(ValueError):
        vector_literal([0.1] * 3)


def test_collector_dedupe_idempotente_e_conflito():
    principal = Principal(uuid4(), "test", "subject")
    game_id = uuid4()
    one = MemoryWriteIntent(MemoryDocument("m1", "  fato   real ", "session"), principal, game_id)
    collector = MemoryIntentCollector()
    collector.add(one)
    collector.add(one)
    assert len(collector.drain()) == 1
    collector.add(one)
    with pytest.raises(Exception):
        collector.add(MemoryWriteIntent(MemoryDocument("m1", "outro", "session"), principal, game_id))
