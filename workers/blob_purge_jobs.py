"""SPEC-222 R6: apagar uma campanha também apaga seus arquivos no Storage.

``commit_delete`` captura as chaves dos assets (que somem por cascade com o jogo) e
enfileira ``purge_blobs`` na mesma transação. O worker/cron ``/internal/cron/jobs``
apaga os objetos; é idempotente (apagar objeto ausente é sucesso) e varre também o
prefixo da campanha para pegar uploads não registrados.
"""

from __future__ import annotations

from uuid import UUID, uuid4

from psycopg.types.json import Jsonb

from infrastructure.db_roles import admin_connection

KIND = "purge_blobs"
MAX_ATTEMPTS = 10


def game_prefix(owner_id: UUID, game_id: UUID) -> str:
    return f"users/{owner_id}/games/{game_id}/"


def _in_prefix(key: object, prefix: str) -> bool:
    # Keys are opaque for S3/Supabase, but a file store resolves ``..``; never let a
    # key that starts with the campaign prefix climb out of it.
    return (
        isinstance(key, str)
        and key.startswith(prefix)
        and ".." not in key.split("/")
        and "\\" not in key
    )


def _deleted_or_absent(blob_store, key: str) -> bool:
    if blob_store.delete(key):
        return True
    # The file store reports False for a key that is already gone (retry after a
    # partial purge, or an asset row whose upload never landed). Only a definite
    # FileNotFoundError counts as absent; any other failure keeps the job retrying.
    try:
        blob_store.open(key).close()
    except FileNotFoundError:
        return True
    except Exception as exc:
        from observability.telemetry import log_fallback

        log_fallback("blob_purge", "open_check_failed", exc)
        return False
    return False


def enqueue_game_blob_purge(
    connection, owner_id: UUID, game_id: UUID, object_keys: list[str]
) -> None:
    prefix = game_prefix(owner_id, game_id)
    keys = sorted({key for key in object_keys if _in_prefix(key, prefix)})
    # game_id stays NULL: jobs.game_id cascades with the game being deleted.
    connection.execute(
        """insert into app.jobs (id,owner_id,game_id,kind,dedupe_key,status,payload,max_attempts)
           values (%s,%s,null,%s,%s,'queued',%s,%s)
           on conflict (kind,dedupe_key) do nothing""",
        (
            uuid4(),
            owner_id,
            KIND,
            f"game:{game_id}",
            Jsonb({"owner_id": str(owner_id), "game_id": str(game_id), "object_keys": keys}),
            MAX_ATTEMPTS,
        ),
    )


def purge_game_blobs_job(pool, blob_store, payload: dict) -> dict:
    owner_id, game_id = UUID(str(payload["owner_id"])), UUID(str(payload["game_id"]))
    prefix = game_prefix(owner_id, game_id)
    keys = {key for key in payload.get("object_keys") or [] if _in_prefix(key, prefix)}
    bucket = getattr(blob_store, "bucket", None)
    if bucket:
        with admin_connection(pool) as connection:
            if connection.execute("select to_regclass('storage.objects') as r").fetchone()["r"]:
                keys.update(
                    row["name"]
                    for row in connection.execute(
                        "select name from storage.objects where bucket_id=%s and starts_with(name,%s)",
                        (bucket, prefix),
                    ).fetchall()
                    if _in_prefix(row["name"], prefix)
                )
    failed = [key for key in sorted(keys) if not _deleted_or_absent(blob_store, key)]
    if failed:
        raise RuntimeError("blob_purge_incomplete")  # retried by the queue
    return {"status": "purged", "deleted": len(keys)}


SHARED_KIND = "purge_shared_art"


def enqueue_shared_art_purge(connection, owner_id: UUID, object_keys: list[str]) -> None:
    """SPEC-352 R14: objetos compartilhados de retratos `game` de um jogo apagado."""
    import hashlib

    keys = sorted({key for key in object_keys if _in_prefix(key, "shared/creatures/")})
    if not keys:
        return
    digest = hashlib.sha256("\n".join(keys).encode()).hexdigest()[:32]
    connection.execute(
        """insert into app.jobs (id,owner_id,game_id,kind,dedupe_key,status,payload,max_attempts)
           values (%s,%s,null,%s,%s,'queued',%s,%s)
           on conflict (kind,dedupe_key) do nothing""",
        (
            uuid4(),
            owner_id,
            SHARED_KIND,
            f"shared:{digest}",
            Jsonb({"object_keys": keys}),
            MAX_ATTEMPTS,
        ),
    )


def purge_shared_art_job(shared_blob_store, payload: dict) -> dict:
    keys = [k for k in payload.get("object_keys") or [] if _in_prefix(k, "shared/creatures/")]
    failed = [k for k in keys if not _deleted_or_absent(shared_blob_store, k)]
    if failed:
        raise RuntimeError("shared_art_purge_incomplete")
    return {"status": "purged", "deleted": len(keys)}
