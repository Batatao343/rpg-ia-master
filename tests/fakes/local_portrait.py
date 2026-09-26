"""Publish one synthetic portrait using real local storage, never a paid model."""
from uuid import UUID
from urllib.parse import urlsplit


def publish_portrait(game_id: str, generation_id: str):
    from scripts.start_local_api import _supabase_status
    from infrastructure.postgres import PostgresPool
    from infrastructure.supabase_blob import SupabaseBlobStore
    from services.dynamic_art import DynamicArtRepository
    from tests.fakes.fake_image_generator import FakeImageGenerator
    from workers.dynamic_art_jobs import generate_dynamic_art_job

    status = _supabase_status()
    assert urlsplit(status['API_URL']).hostname in {'localhost', '127.0.0.1'}
    assert urlsplit(status['DB_URL']).hostname in {'localhost', '127.0.0.1'}
    blob = SupabaseBlobStore(status['API_URL'], status['SERVICE_ROLE_KEY'])
    pool = PostgresPool(status['DB_URL'])
    keys = []
    try:
        with pool.connection() as conn:
            row = conn.execute(
                """select id,payload from app.jobs where game_id=%s and kind='generate_dynamic_art'
                and payload->'generation'->>'generation_id'=%s and status='queued'""",
                (UUID(game_id), generation_id),
            ).fetchone()
        assert row, 'confirmed portrait must have one durable outbox job'
        payload = row['payload']
        generation = payload['generation']
        repository = DynamicArtRepository(pool, model=generation['model'], profile_version=generation['profile_version'])
        assert repository.begin(UUID(generation_id))
        generator = FakeImageGenerator()
        result = generate_dynamic_art_job(
            generator=generator, blob_store=blob, generation=generation,
            owner_id=UUID(payload['owner_id']), game_id=UUID(game_id), asset_id=UUID(payload['asset_id']),
        )
        keys.extend(variant['key'] for variant in result['variants'])
        repository.complete(UUID(generation_id), asset_id=UUID(payload['asset_id']), result=result)
        with pool.connection() as conn, conn.transaction():
            conn.execute("update app.jobs set status='succeeded' where id=%s and status='queued'", (row['id'],))
        assert generator.calls == 1
    except BaseException:
        for key in keys:
            blob.delete(key)
        raise
    finally:
        pool.close()

    def cleanup():
        for key in keys:
            assert blob.delete(key), 'synthetic blob cleanup failed'
    return cleanup
