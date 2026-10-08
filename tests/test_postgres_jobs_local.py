from __future__ import annotations

import os
from uuid import uuid4
from decimal import Decimal

import pytest

from infrastructure.contracts import JobRequest, LeaseHeld, Principal
from infrastructure.contracts import Conflict
from services.usage_metering import normalize_attempts, operation_cost


pytestmark = pytest.mark.infra_local


@pytest.fixture
def infra():
    pytest.importorskip("psycopg")
    from infrastructure.postgres import PostgresGameStore, PostgresPool
    from infrastructure.postgres_jobs import PostgresJobQueue
    from infrastructure.postgres_turns import PostgresRateLimiter, PostgresTurnCoordinator

    dsn = os.getenv("RPG_TEST_DATABASE_URL")
    if not dsn:
        pytest.skip("RPG_TEST_DATABASE_URL ausente")
    pool = PostgresPool(dsn, max_size=3)
    yield (
        PostgresGameStore(pool), PostgresJobQueue(pool, lease_seconds=2),
        PostgresTurnCoordinator(pool, lease_seconds=2), PostgresRateLimiter(pool),
    )
    pool.close()


def _state(game_id):
    return {
        "game_id": str(game_id), "messages": [], "event_log": [],
        "player": {"name": "Fila", "class_name": "Devoto", "level": 1},
        "world": {"current_location": "Teste", "turn_count": 0,
                  "world_clock": {"day": 1}},
    }


def test_job_dedupe_lease_fencing_retry_e_complete(infra):
    _, queue, _, _ = infra
    request = JobRequest("test_job", f"d-{uuid4()}", {"x": 1}, max_attempts=2)
    job_id = queue.enqueue(request)
    assert queue.enqueue(request) == job_id
    first = queue.lease("w1", {"test_job"}, 1)[0]
    with pytest.raises(LeaseHeld):
        queue.complete(first.job_id, uuid4(), {})
    queue.fail(first.job_id, first.lease_token, "retry")
    with queue.pool.connection() as connection, connection.transaction():
        connection.execute("update app.jobs set available_at=now() where id=%s", (job_id,))
    second = queue.lease("w2", {"test_job"}, 1)[0]
    queue.complete(second.job_id, second.lease_token, {"ok": True})
    assert queue.lease("w3", {"test_job"}, 1) == []


def test_coordinator_exclui_mesmo_jogo_e_receipt_idempotente(infra):
    store, _, coordinator, _ = infra
    owner_id, game_id = uuid4(), uuid4()
    principal = Principal(owner_id, "test", str(owner_id), local=True)
    created = store.create(principal, _state(game_id))
    op = uuid4()
    claim = coordinator.claim(
        principal, op, game_id=game_id, kind="turn",
        request_hash="a" * 64, base_version=created.version,
    )
    with pytest.raises(LeaseHeld):
        coordinator.claim(
            principal, uuid4(), game_id=game_id, kind="turn",
            request_hash="b" * 64, base_version=created.version,
        )
    coordinator.complete(claim, committed_version=created.version, receipt={"ok": True})
    assert coordinator.receipt(principal, op) == {"ok": True}
    store.delete(principal, game_id)


def test_commit_de_turno_confirma_estado_eventos_e_receipt_na_mesma_transacao(infra):
    store, _, coordinator, _ = infra
    owner_id, game_id = uuid4(), uuid4()
    principal = Principal(owner_id, "test", str(owner_id), local=True)
    created = store.create(principal, _state(game_id))
    operation_id = uuid4()
    claim = coordinator.claim(
        principal, operation_id, game_id=game_id, kind="turn",
        request_hash="c" * 64, base_version=created.version,
    )
    changed = _state(game_id)
    changed["world"]["turn_count"] = 1
    changed["event_log"] = [{
        "event_id": "evt-commit", "type": "quest_completed", "turn": 1,
        "payload": {"quest_title": "Teste"}, "source": "test",
    }]
    usage_events = normalize_attempts([
        {"provider": "groq", "model": "openai/gpt-oss-20b", "outcome": "invalid_structured",
         "network_attempted": True, "usage": {"input_tokens": 1000, "output_tokens": 100}},
        {"provider": "groq", "model": "openai/gpt-oss-120b", "outcome": "success",
         "network_attempted": True, "usage": {"input_tokens": 800, "output_tokens": 200}},
    ], operation_id=operation_id)
    version, receipt = coordinator.commit_game(
        principal, claim, changed, receipt={"response": {"game_id": str(game_id)}},
        input_sha256="d" * 64, latency_ms=12,
        llm_cost_usd=operation_cost(usage_events), usage_events=usage_events,
        checkpoint=True,
    )
    assert version == created.version + 1
    assert receipt["committed_version"] == version
    assert coordinator.receipt(principal, operation_id) == receipt
    reloaded = store.get(principal, game_id)
    assert reloaded and reloaded.version == version
    assert reloaded.state["world"]["turn_count"] == 1
    with coordinator.pool.connection() as connection:
        assert connection.execute(
            "select count(*) as n from app.turns where operation_id=%s", (operation_id,),
        ).fetchone()["n"] == 1
        assert connection.execute(
            "select count(*) as n from app.game_checkpoints where game_id=%s", (game_id,),
        ).fetchone()["n"] == 1
        turn = connection.execute(
            "select llm_cost_usd from app.turns where operation_id=%s", (operation_id,),
        ).fetchone()
        assert turn["llm_cost_usd"] == operation_cost(usage_events)
        ledger = connection.execute(
            "select cost_usd,cost_basis,pricing_version,input_units from app.usage_events "
            "where operation_id=%s order by attempt_ordinal", (operation_id,),
        ).fetchall()
        assert len(ledger) == 2
        assert sum((row["cost_usd"] for row in ledger), Decimal("0")) == turn["llm_cost_usd"]
        assert all(row["cost_basis"] == "token_priced" for row in ledger)
        assert all(row["pricing_version"] for row in ledger)
    store.delete(principal, game_id)


def test_usage_ledger_replay_is_idempotent_and_divergence_rolls_back(infra):
    store, _, coordinator, _ = infra
    from infrastructure.usage_events import append_usage_events

    owner_id, game_id, operation_id = uuid4(), uuid4(), uuid4()
    principal = Principal(owner_id, "test", str(owner_id), local=True)
    created = store.create(principal, _state(game_id))
    coordinator.claim(principal, operation_id, game_id=game_id, kind="turn",
                      request_hash="e" * 64, base_version=created.version)
    original = normalize_attempts([{
        "provider": "groq", "model": "openai/gpt-oss-20b", "outcome": "success",
        "network_attempted": True, "usage": {"input_tokens": 20, "output_tokens": 5},
    }], operation_id=operation_id)
    changed = normalize_attempts([{
        "provider": "groq", "model": "openai/gpt-oss-20b", "outcome": "success",
        "network_attempted": True, "usage": {"input_tokens": 21, "output_tokens": 5},
    }], operation_id=operation_id)
    with coordinator.pool.connection() as connection:
        with connection.transaction():
            append_usage_events(connection, owner_id=owner_id, operation_id=operation_id,
                                game_id=game_id, events=original)
            append_usage_events(connection, owner_id=owner_id, operation_id=operation_id,
                                game_id=game_id, events=original)
            assert connection.execute(
                "select count(*) as n from app.usage_events where operation_id=%s",
                (operation_id,),
            ).fetchone()["n"] == 1
        with pytest.raises(Conflict), connection.transaction():
            append_usage_events(connection, owner_id=owner_id, operation_id=operation_id,
                                game_id=game_id, events=changed)
        with pytest.raises(Conflict), connection.transaction():
            append_usage_events(connection, owner_id=uuid4(), operation_id=operation_id,
                                game_id=game_id, events=original)
        assert connection.execute(
            "select input_units from app.usage_events where operation_id=%s",
            (operation_id,),
        ).fetchone()["input_units"] == 20
        with connection.transaction():
            connection.execute("set local role rpg_api")
            connection.execute("select set_config('request.jwt.claim.sub',%s,true)",
                               (str(owner_id),))
            assert connection.execute(
                "select count(*) as n from app.usage_events where operation_id=%s",
                (operation_id,),
            ).fetchone()["n"] == 1
            assert connection.execute(
                "select has_table_privilege('rpg_api','app.usage_events','UPDATE') as allowed",
            ).fetchone()["allowed"] is False
        with connection.transaction():
            connection.execute("set local role rpg_api")
            connection.execute("select set_config('request.jwt.claim.sub',%s,true)",
                               (str(uuid4()),))
            assert connection.execute(
                "select count(*) as n from app.usage_events where operation_id=%s",
                (operation_id,),
            ).fetchone()["n"] == 0
    store.delete(principal, game_id)


def test_rate_limit_compartilhado(infra):
    _, _, _, limiter = infra
    key = f"owner:{uuid4()}"
    assert limiter.consume(key, limit=2, window_seconds=60).allowed
    assert limiter.consume(key, limit=2, window_seconds=60).allowed
    denied = limiter.consume(key, limit=2, window_seconds=60)
    assert not denied.allowed and denied.retry_after_seconds > 0
