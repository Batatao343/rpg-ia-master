from __future__ import annotations

import os
from copy import deepcopy
from uuid import uuid4

import pytest

from infrastructure.contracts import Conflict, Principal, StaleVersion


pytestmark = pytest.mark.infra_local


@pytest.fixture
def postgres_store():
    pytest.importorskip("psycopg")
    from infrastructure.postgres import PostgresGameStore, PostgresPool

    dsn = os.getenv("RPG_TEST_DATABASE_URL")
    if not dsn:
        pytest.skip("RPG_TEST_DATABASE_URL ausente")
    pool = PostgresPool(dsn, max_size=2)
    store = PostgresGameStore(pool)
    yield store
    pool.close()


def _state(game_id):
    return {
        "game_id": str(game_id),
        "player": {
            "name": "Teste", "class_name": "Devoto", "level": 1,
            "virtudes": {"corpo": 2}, "vitalidade": 20, "max_vitalidade": 20,
        },
        "world": {
            "current_location": "Nova Arcádia", "turn_count": 0,
            "world_clock": {"day": 1, "period": "Manhã"},
        },
        "messages": [],
        "event_log": [],
    }


def test_postgres_store_owner_version_checkpoint_e_evento(postgres_store):
    game_id, owner_id = uuid4(), uuid4()
    principal = Principal(owner_id, "test", str(owner_id), local=True)
    other_id = uuid4()
    other = Principal(other_id, "test", str(other_id), local=True)
    state = _state(game_id)
    created = postgres_store.create(principal, state)
    assert postgres_store.get(other, game_id) is None
    state = deepcopy(state)
    state["player"]["gold"] = 7
    state["event_log"] = [{
        "event_id": "evt-1", "turn": 1, "type": "reputation_changed",
        "payload": {"delta": 1}, "source": "test",
    }]
    saved = postgres_store.save(principal, game_id, created.version, state)
    assert saved.version == 2
    with pytest.raises(StaleVersion):
        postgres_store.save(principal, game_id, created.version, state)
    postgres_store.save_checkpoint(principal, saved, state)
    assert postgres_store.get_checkpoint(principal, game_id)["player"]["gold"] == 7
    divergent = deepcopy(state)
    divergent["event_log"][0]["payload"]["delta"] = 99
    with pytest.raises(Conflict):
        postgres_store.save(principal, game_id, saved.version, divergent)
    assert postgres_store.delete(principal, game_id)
