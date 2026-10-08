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


def test_creation_commits_usage_with_new_game_attribution(infra):
    store, _, coordinator, _ = infra
    owner_id, game_id, operation_id = uuid4(), uuid4(), uuid4()
    principal = Principal(owner_id, "test", str(owner_id), local=True)
    claim = coordinator.claim(principal, operation_id, game_id=None,
                              kind="new_game", request_hash="a" * 64,
                              base_version=None)
    usage = normalize_attempts([{
        "provider": "groq", "model": "openai/gpt-oss-20b",
        "outcome": "success", "network_attempted": True,
        "usage": {"input_tokens": 30, "output_tokens": 5},
    }], operation_id=operation_id, component=f"llm:{claim.lease_token}")
    coordinator.commit_create(principal, claim, _state(game_id),
                              receipt={"status": "ok"}, usage_events=usage)
    with coordinator.pool.connection() as connection:
        row = connection.execute(
            "select owner_id,game_id from app.usage_events where operation_id=%s",
            (operation_id,),
        ).fetchone()
    assert row == {"owner_id": owner_id, "game_id": game_id}
    store.delete(principal, game_id)


def test_metered_search_does_not_reserve_turn_slot(infra):
    store, _, coordinator, _ = infra
    owner_id, game_id = uuid4(), uuid4()
    principal = Principal(owner_id, "test", str(owner_id), local=True)
    created = store.create(principal, _state(game_id))
    turn = coordinator.claim(principal, uuid4(), game_id=game_id, kind="turn",
                             request_hash="a" * 64, base_version=created.version)
    search = coordinator.claim(principal, uuid4(), game_id=game_id,
                               kind="chronicle_search", request_hash="b" * 64,
                               base_version=None, exclusive=False)
    usage = normalize_attempts([{
        "provider": "jina", "model": "jina-embeddings-v3",
        "outcome": "response", "network_attempted": True,
        "usage": {"input_tokens": 8},
    }], operation_id=search.operation_id,
        component=f"embedding:{search.lease_token}", category="embedding")
    coordinator.complete(search, committed_version=None,
                         receipt={"status": "completed"}, usage_events=usage)
    with coordinator.pool.connection() as connection:
        active = connection.execute(
            "select active_operation_id from app.games where id=%s", (game_id,),
        ).fetchone()["active_operation_id"]
    assert active == turn.operation_id
    coordinator.complete(turn, committed_version=created.version, receipt={})
    store.delete(principal, game_id)


def test_chronicle_worker_records_each_paid_attempt(infra):
    from infrastructure.usage_events import append_chronicle_job_attempt

    store, queue, _, _ = infra
    owner_id, game_id = uuid4(), uuid4()
    principal = Principal(owner_id, "test", str(owner_id), local=True)
    store.create(principal, _state(game_id))
    job_id = queue.enqueue(JobRequest(
        "compress_chronicle", f"compress-{uuid4()}", {},
        owner_id=owner_id, game_id=game_id))
    leased = queue.lease("usage-test", {"compress_chronicle"}, 100)
    job = next(item for item in leased if item.job_id == job_id)
    first = {"provider": "groq", "model": "openai/gpt-oss-20b",
             "outcome": "invoke_error", "network_attempted": True,
             "usage": {"input_tokens": 10, "output_tokens": 1}}
    second = {"provider": "groq", "model": "openai/gpt-oss-120b",
              "outcome": "success", "network_attempted": True,
              "usage": {"input_tokens": 12, "output_tokens": 3}}
    append_chronicle_job_attempt(queue.pool, job, [first])
    append_chronicle_job_attempt(queue.pool, job, [first, second])
    with queue.pool.connection() as connection:
        rows = connection.execute(
            "select attempt_ordinal,game_id,category from app.usage_events "
            "where operation_id=%s order by attempt_ordinal", (job_id,),
        ).fetchall()
    assert [(row["attempt_ordinal"], row["game_id"], row["category"])
            for row in rows] == [(0, game_id, "llm"), (1, game_id, "llm")]
    queue.complete(job_id, job.lease_token, {})
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


def test_failed_attempts_survive_retry_and_join_turn_cost(infra):
    store, _, coordinator, _ = infra
    owner_id, game_id, operation_id = uuid4(), uuid4(), uuid4()
    principal = Principal(owner_id, "test", str(owner_id), local=True)
    created = store.create(principal, _state(game_id))
    claim = coordinator.claim(
        principal, operation_id, game_id=game_id, kind="turn",
        request_hash="f" * 64, base_version=created.version,
    )
    attempt = {
        "provider": "groq", "model": "openai/gpt-oss-20b", "outcome": "invoke_error",
        "network_attempted": True, "usage": {"input_tokens": 100, "output_tokens": 10},
    }
    attempts = normalize_attempts([attempt], operation_id=operation_id,
                                  component=f"llm:{claim.lease_token}")
    coordinator.fail(claim, "graph_error", usage_events=attempts)
    with coordinator.pool.connection() as connection:
        assert connection.execute(
            "select count(*) as n from app.turns where operation_id=%s",
            (operation_id,),
        ).fetchone()["n"] == 0
        assert connection.execute(
            "select count(*) as n from app.usage_events where operation_id=%s",
            (operation_id,),
        ).fetchone()["n"] == 1
    retry = coordinator.claim(
        principal, operation_id, game_id=game_id, kind="turn",
        request_hash="f" * 64, base_version=created.version,
    )
    assert retry.lease_token != claim.lease_token
    retried = normalize_attempts([{
        **attempt, "usage": {"input_tokens": 101, "output_tokens": 11},
    }], operation_id=operation_id, component=f"llm:{retry.lease_token}")
    coordinator.fail(retry, "graph_error_again", usage_events=retried)
    successful = coordinator.claim(
        principal, operation_id, game_id=game_id, kind="turn",
        request_hash="f" * 64, base_version=created.version,
    )
    coordinator.commit_game(
        principal, successful, _state(game_id), receipt={"response": {"ok": True}},
        input_sha256="f" * 64, latency_ms=5, llm_cost_usd=Decimal("0"),
    )
    with coordinator.pool.connection() as connection:
        assert connection.execute(
            "select count(*) as n from app.usage_events where operation_id=%s",
            (operation_id,),
        ).fetchone()["n"] == 2
        turn = connection.execute(
            "select llm_cost_usd from app.turns where operation_id=%s",
            (operation_id,),
        ).fetchone()
        assert turn["llm_cost_usd"] == operation_cost([*attempts, *retried])
        assert connection.execute(
            "select status from app.operations where id=%s", (operation_id,),
        ).fetchone()["status"] == "completed"
    store.delete(principal, game_id)


def test_rls_insert_cannot_attribute_foreign_operation_to_claimed_owner(infra):
    psycopg = pytest.importorskip("psycopg")
    store, _, coordinator, _ = infra
    owner_a, owner_b, game_a, game_b, foreign_op = (
        uuid4(), uuid4(), uuid4(), uuid4(), uuid4())
    principal_a = Principal(owner_a, "test", str(owner_a), local=True)
    principal_b = Principal(owner_b, "test", str(owner_b), local=True)
    store.create(principal_a, _state(game_a))
    created_b = store.create(principal_b, _state(game_b))
    coordinator.claim(principal_b, foreign_op, game_id=game_b, kind="turn",
                      request_hash="b" * 64, base_version=created_b.version)
    try:
        with coordinator.pool.connection() as connection:
            with pytest.raises(psycopg.errors.CheckViolation), connection.transaction():
                connection.execute("set local role rpg_api")
                connection.execute("select set_config('request.jwt.claim.sub',%s,true)",
                                   (str(owner_a),))
                connection.execute(
                    """insert into app.usage_events
                      (event_id,operation_id,owner_id,game_id,component,attempt_ordinal,
                       category,provider,model,outcome,cost_usd,cost_basis,
                       pricing_version,billing_exact,event_sha256)
                    values (%s,%s,%s,%s,'llm',0,'llm','groq','fake','success',
                            1,'estimated','test',false,%s)""",
                    (uuid4(), foreign_op, owner_a, game_b, "a" * 64),
                )
    finally:
        store.delete(principal_a, game_a)
        store.delete(principal_b, game_b)


def test_rate_limit_compartilhado(infra):
    _, _, _, limiter = infra
    key = f"owner:{uuid4()}"
    assert limiter.consume(key, limit=2, window_seconds=60).allowed
    assert limiter.consume(key, limit=2, window_seconds=60).allowed
    denied = limiter.consume(key, limit=2, window_seconds=60)
    assert not denied.allowed and denied.retry_after_seconds > 0
