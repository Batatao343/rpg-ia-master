"""SPEC-222 R6: DELETE de campanha (perfil DB) apaga os objetos de Storage da campanha."""

from __future__ import annotations

import os
from contextlib import nullcontext
from uuid import uuid4

import pytest

from infrastructure.contracts import Principal
from workers.blob_purge_jobs import KIND, purge_game_blobs_job


class _FakeResult:
    def __init__(self, rows):
        self.rows = rows

    def fetchone(self):
        return self.rows[0] if self.rows else None

    def fetchall(self):
        return self.rows


class _NoStorageDb:
    def execute(self, sql, params=None):
        return _FakeResult([{"r": None}])


class _Pool:
    def __init__(self, db):
        self.db = db

    def connection(self):
        return nullcontext(self.db)


class _Blobs:
    bucket = "rpg-dynamic"

    def __init__(self, fail=False):
        self.deleted, self.fail = [], fail

    def delete(self, key):
        self.deleted.append(key)
        return not self.fail


def test_handler_only_deletes_inside_the_campaign_prefix_and_is_idempotent():
    owner, game = uuid4(), uuid4()
    own = f"users/{owner}/games/{game}/player/hero/full.webp"
    foreign = f"users/{uuid4()}/games/{game}/player/hero/full.webp"
    blobs = _Blobs()
    payload = {"owner_id": str(owner), "game_id": str(game), "object_keys": [own, foreign, own]}
    assert purge_game_blobs_job(_Pool(_NoStorageDb()), blobs, payload) == {
        "status": "purged",
        "deleted": 1,
    }
    assert (
        purge_game_blobs_job(_Pool(_NoStorageDb()), blobs, payload)["deleted"] == 1
    )  # replay is safe
    assert blobs.deleted == [own, own]


def test_handler_failure_raises_so_the_queue_retries():
    owner, game = uuid4(), uuid4()
    payload = {
        "owner_id": str(owner),
        "game_id": str(game),
        "object_keys": [f"users/{owner}/games/{game}/x.webp"],
    }
    with pytest.raises(RuntimeError):
        purge_game_blobs_job(_Pool(_NoStorageDb()), _Blobs(fail=True), payload)


def test_replay_on_file_store_treats_already_absent_object_as_purged(tmp_path):
    """Retry after a partial purge (or an asset row whose upload never landed) must not
    wedge the job: the file store reports ``False`` for a missing key."""
    import hashlib
    from io import BytesIO

    from infrastructure.contracts import BlobMetadata
    from infrastructure.file_blob import FileBlobStore

    owner, game = uuid4(), uuid4()
    store = FileBlobStore(tmp_path)
    present = f"users/{owner}/games/{game}/npc/a.webp"
    missing = f"users/{owner}/games/{game}/npc/never-uploaded.webp"
    store.put(
        present,
        BytesIO(b"x"),
        BlobMetadata(owner, game, "image/webp", hashlib.sha256(b"x").hexdigest(), "npc"),
    )
    payload = {"owner_id": str(owner), "game_id": str(game), "object_keys": [present, missing]}
    assert purge_game_blobs_job(_Pool(_NoStorageDb()), store, payload)["status"] == "purged"
    assert purge_game_blobs_job(_Pool(_NoStorageDb()), store, payload)["status"] == "purged"
    with pytest.raises(FileNotFoundError):
        store.open(present)


def test_handler_rejects_traversal_keys_even_inside_the_prefix():
    owner, game = uuid4(), uuid4()
    prefix = f"users/{owner}/games/{game}/"
    blobs = _Blobs()
    payload = {
        "owner_id": str(owner),
        "game_id": str(game),
        "object_keys": [prefix + "../../../" + str(uuid4()) + "/x.webp", prefix + "ok.webp"],
    }
    assert purge_game_blobs_job(_Pool(_NoStorageDb()), blobs, payload)["deleted"] == 1
    assert blobs.deleted == [prefix + "ok.webp"]


@pytest.mark.infra_local
def test_delete_campaign_then_drain_leaves_no_object_in_prefix():
    psycopg = pytest.importorskip("psycopg")
    from psycopg.rows import dict_row
    from psycopg.types.json import Jsonb

    from infrastructure.postgres_jobs import PostgresJobQueue
    from infrastructure.postgres_turns import PostgresTurnCoordinator
    from workers.job_worker import JobWorker

    dsn = os.getenv("RPG_TEST_DATABASE_URL")
    if not dsn:
        pytest.skip("RPG_TEST_DATABASE_URL ausente")
    db = psycopg.connect(dsn, row_factory=dict_row)
    try:
        db.execute("select 1")  # implicit tx: every db.transaction() below is a savepoint
        pool = _Pool(db)
        owner = Principal(uuid4(), "test", "owner")
        game = uuid4()
        prefix = f"users/{owner.user_id}/games/{game}/"
        registered, unregistered = prefix + "player/hero/full.webp", prefix + "npc/x/orphan.webp"
        db.execute(
            """insert into app.games(id,owner_id,schema_version,state,state_sha256,status,
            player_name,class_name,player_level,location_name,world_day,game_over,combat_simulation)
            values(%s,%s,1,%s,%s,'active','n','Devoto',1,'Porto',1,false,false)""",
            (game, owner.user_id, Jsonb({"game_id": str(game)}), "a" * 64),
        )
        db.execute(
            """insert into app.assets(id,owner_id,game_id,entity_id,asset_kind,variant,status,
            visibility,bucket,object_key,mime_type,bytes,width,height,sha256)
            values(%s,%s,%s,'hero','player','full','ready','public','rpg-dynamic',%s,'image/webp',10,1,1,%s)""",
            (uuid4(), owner.user_id, game, registered, "b" * 64),
        )
        for key in (registered, unregistered):
            db.execute(
                "insert into storage.objects(bucket_id,name) values('rpg-dynamic',%s)", (key,)
            )

        class StorageBlobs:
            bucket = "rpg-dynamic"

            def delete(self, key):
                # Emulates the Storage transport's controlled delete.
                db.execute("select set_config('storage.allow_delete_query','true',true)")
                db.execute(
                    "delete from storage.objects where bucket_id='rpg-dynamic' and name=%s", (key,)
                )
                return True

        coordinator = PostgresTurnCoordinator(pool)
        claim = coordinator.claim(
            owner, uuid4(), game_id=None, kind="delete", request_hash="c" * 64, base_version=None
        )
        coordinator.commit_delete(owner, claim, game, receipt={"ok": True})
        assert (
            db.execute("select count(*) n from app.assets where game_id=%s", (game,)).fetchone()[
                "n"
            ]
            == 0
        )
        job = db.execute(
            "select * from app.jobs where kind=%s and dedupe_key=%s", (KIND, f"game:{game}")
        ).fetchone()
        assert job["status"] == "queued" and job["game_id"] is None
        assert job["payload"]["object_keys"] == [registered]

        worker = JobWorker(
            PostgresJobQueue(pool),
            {KIND: lambda payload: purge_game_blobs_job(pool, StorageBlobs(), payload)},
            worker_id="t",
        )
        while worker.run_once(limit=1):
            pass
        left = db.execute(
            "select count(*) n from storage.objects where starts_with(name,%s)", (prefix,)
        ).fetchone()["n"]
        assert left == 0
        status = db.execute("select status from app.jobs where id=%s", (job["id"],)).fetchone()[
            "status"
        ]
        assert status == "succeeded"
    finally:
        db.rollback()
        db.close()
