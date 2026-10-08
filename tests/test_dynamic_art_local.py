from __future__ import annotations

import os
from uuid import uuid4

import pytest

from infrastructure.contracts import JobRequest, LeaseHeld, Principal
from infrastructure.file_blob import FileBlobStore
from services.art_triggers import ArtGenerationRequest
from tests.fakes.fake_image_generator import FakeImageGenerator
from workers.dynamic_art_jobs import generate_dynamic_art_job


pytestmark = pytest.mark.infra_local


def test_reserva_worker_e_promocao_de_arte_no_postgres_local(tmp_path):
    pytest.importorskip("psycopg")
    dsn = os.getenv("RPG_TEST_DATABASE_URL")
    if not dsn:
        pytest.skip("RPG_TEST_DATABASE_URL ausente")
    from infrastructure.postgres import PostgresGameStore, PostgresPool
    from infrastructure.postgres_jobs import PostgresJobQueue
    from services.job_fence import job_scope
    from services.dynamic_art import DynamicArtRepository

    pool = PostgresPool(dsn)
    store = PostgresGameStore(pool)
    owner_id, game_id = uuid4(), uuid4()
    principal = Principal(owner_id, "test", str(owner_id), local=True)
    store.create(principal, {
        "game_id": str(game_id), "messages": [], "event_log": [],
        "player": {"name": "Iria", "class_name": "Devoto", "level": 1},
        "world": {"current_location": "Teste", "turn_count": 0,
                  "world_clock": {"day": 1}},
    })
    repository = DynamicArtRepository(
        pool, model="gpt-image-2-2026-04-21", profile_version="test-v1",
    )
    generation_id, asset_id = uuid4(), uuid4()
    request = ArtGenerationRequest(
        "player_portrait", "create-1", "player", "player", None, "create-1",
    )
    brief = {
        "subject": "Iria", "canon": ["Valoria"],
        "player_description": "adulta", "composition": ["natural spine"],
        "exclusions": ["no text"], "reference_asset_ids": [],
        "profile_version": "test-v1", "size": "1024x1536",
    }
    repository.reserve(
        principal, game_id, timeline_epoch=0, generation_id=generation_id,
        request=request, brief=brief,
    )
    queue = PostgresJobQueue(pool)
    kind = f'art-fence-{generation_id}'
    job_id = queue.enqueue(JobRequest(kind, kind, {}, owner_id=owner_id, game_id=game_id))
    first = queue.lease('first', {kind}, 1)[0]
    assert repository.begin(generation_id) is True
    result = generate_dynamic_art_job(
        generator=FakeImageGenerator(), blob_store=FileBlobStore(tmp_path),
        generation={
            "private_brief": brief, "model": "gpt-image-2-2026-04-21",
            "subject_type": "player", "subject_id": "player",
            "trigger_kind": "player_portrait",
        },
        owner_id=owner_id, game_id=game_id, asset_id=asset_id,
    )
    with pool.connection() as connection, connection.transaction():
        connection.execute("update app.jobs set lease_until=now()-interval '1 second' where id=%s", (job_id,))
    second = queue.lease('second', {kind}, 1)[0]
    with job_scope(first), pytest.raises(LeaseHeld):
        repository.complete(generation_id, asset_id=asset_id, result=result)
    assert repository.assets(principal, generation_id) == []
    with job_scope(second):
        repository.record_usage(
            generation_id, model=result["model"], usage=result["usage"])
        with pool.connection() as connection:
            assert connection.execute(
                "select count(*) as n from app.usage_events where operation_id=%s",
                (generation_id,),
            ).fetchone()["n"] == 1
        repository.complete(generation_id, asset_id=asset_id, result=result)
    queue.complete(second.job_id, second.lease_token, {'ready': True})
    assert repository.get(principal, generation_id)["status"] == "ready"
    assert {row["variant"] for row in repository.assets(principal, generation_id)} == {
        "full", "thumb",
    }
    with pool.connection() as connection:
        row = connection.execute(
            """select u.category,u.provider,u.model,u.image_units,u.cost_basis,u.cost_usd,
                      o.kind from app.usage_events u join app.operations o on o.id=u.operation_id
               where u.operation_id=%s""", (generation_id,),
        ).fetchone()
    assert row is not None
    assert row["category"] == "image" and row["kind"] == "art"
    assert row["provider"] == "openai" and row["model"] == "gpt-image-2-2026-04-21"
    assert row["image_units"] == 1 and row["cost_basis"] == "provider_reported"
    # A retry after promotion must not call the expensive provider again.
    assert repository.begin(generation_id) is False
    store.delete(principal, game_id)
    pool.close()
