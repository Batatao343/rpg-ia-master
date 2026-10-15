"""Seed / cleanup of synthetic rows for the backup->restore gate (staging only).

seed   : 2 users (admin API), 1 game + 1 pgvector memory doc + 2 webp objects each; manifest (no secrets)
         written to .tmp/spec191/synthetic_manifest.json.
cleanup: removes objects, rows and users listed in the manifest and verifies nothing remains.
"""

from __future__ import annotations

import argparse
import base64
import json
import os
import secrets
from pathlib import Path
from typing import Any, Mapping
from uuid import UUID, uuid4

import httpx

from scripts.staging import common

BUCKET = "rpg-dynamic"
MANIFEST = common.ROOT / ".tmp" / "spec191" / "synthetic_manifest.json"
# 1x1 lossless WebP; two distinct payloads (trailing byte differs inside a padding-free chunk is risky,
# so the second object is simply the same bytes under another path -> checksums still verified per path).
TINY_WEBP = base64.b64decode("UklGRhoAAABXRUJQVlA4TA0AAAAvAAAAEAcQERGIiP4HAA==")


def build_manifest(users: list[dict]) -> dict:
    """Pure: secret-free manifest (no emails/passwords)."""
    return {"users": [{"id": u["id"], "game_id": u["game_id"], "memory_doc": u["memory_doc"],
                       "objects": u["objects"]} for u in users]}


def seed(env: Mapping[str, str], client: httpx.Client | None = None) -> dict:
    import psycopg
    from infrastructure.contracts import MemoryDocument, MemoryWriteIntent, Principal
    from infrastructure.pgvector_memory import PgVectorMemoryStore
    from infrastructure.postgres import PostgresGameStore, PostgresPool
    url = common.env_required("SUPABASE_URL", env).rstrip("/")
    key = common.env_required("SUPABASE_SERVICE_ROLE_KEY", env)
    dsn = common.env_required("RPG_STAGING_DB_URL", env)
    h = {"apikey": key, "Authorization": f"Bearer {key}"}
    http = client or httpx.Client(timeout=30)
    pool = PostgresPool(dsn)
    store = PgVectorMemoryStore(pool, embedder=lambda _t: [1.0] + [0.0] * 1023)
    users: list[dict] = []
    try:
        for who in ("a", "b"):
            r = http.post(f"{url}/auth/v1/admin/users", headers=h, json={
                "email": f"spec191-backup-{uuid4().hex[:10]}@example.invalid",
                "password": secrets.token_urlsafe(24), "email_confirm": True})
            r.raise_for_status()
            uid = r.json()["id"]
            u: dict[str, Any] = {"id": uid, "game_id": str(uuid4()), "memory_doc": f"spec191-backup-{who}", "objects": []}
            users.append(u)
            pr = Principal(UUID(uid), "supabase", uid)
            state = {"game_id": u["game_id"], "messages": [], "event_log": [], "player": {}, "world": {}}
            PostgresGameStore(pool).create(pr, state)
            store.stage(MemoryWriteIntent(MemoryDocument(u["memory_doc"], f"Memoria sintetica {who}", "session",
                                                         {"visibility": "public", "commit_version": 1}),
                                          pr, UUID(u["game_id"]), timeline_epoch=0))
            for i in (1, 2):
                path = f"users/{uid}/spec191-backup-{i}.webp"
                up = http.post(f"{url}/storage/v1/object/{BUCKET}/{path}",
                               headers={**h, "Content-Type": "image/webp"}, content=TINY_WEBP)
                up.raise_for_status()
                u["objects"].append(path)
    finally:
        pool.close()
        MANIFEST.parent.mkdir(parents=True, exist_ok=True)
        MANIFEST.write_text(json.dumps(build_manifest(users), indent=2), encoding="utf-8")
    return {"users": len(users), "games": len(users), "memory_docs": len(users),
            "objects": sum(len(u["objects"]) for u in users)}


def cleanup(env: Mapping[str, str], client: httpx.Client | None = None) -> dict:
    import psycopg
    url = common.env_required("SUPABASE_URL", env).rstrip("/")
    key = common.env_required("SUPABASE_SERVICE_ROLE_KEY", env)
    dsn = common.env_required("RPG_STAGING_DB_URL", env)
    h = {"apikey": key, "Authorization": f"Bearer {key}"}
    http = client or httpx.Client(timeout=30)
    man = json.loads(MANIFEST.read_text(encoding="utf-8"))
    uids = [u["id"] for u in man["users"]]
    gids = [u["game_id"] for u in man["users"]]
    objs = [p for u in man["users"] for p in u["objects"]]
    if objs:
        http.request("DELETE", f"{url}/storage/v1/object/{BUCKET}", headers=h, json={"prefixes": objs})
    with psycopg.connect(dsn, autocommit=True) as conn:
        conn.execute("delete from app.games where id = any(%s::uuid[])", (gids,))
    for uid in uids:
        http.delete(f"{url}/auth/v1/admin/users/{uid}", headers=h)
    with psycopg.connect(dsn, autocommit=True) as conn:
        left_users = conn.execute("select count(*) from auth.users where id = any(%s::uuid[])", (uids,)).fetchone()[0]
        left_games = conn.execute("select count(*) from app.games where id = any(%s::uuid[])", (gids,)).fetchone()[0]
        left_objs = conn.execute("select count(*) from storage.objects where bucket_id=%s and name = any(%s)",
                                 (BUCKET, objs)).fetchone()[0]
    res = {"users_left": left_users, "games_left": left_games, "objects_left": left_objs}
    res["ok"] = not any(res.values())
    return res


def main(argv: list[str] | None = None) -> int:
    common.load_dotenv_quietly()
    p = argparse.ArgumentParser(description="Synthetic staging data for backup/restore")
    p.add_argument("mode", choices=["seed", "cleanup"])
    common.add_guard_args(p)
    p.add_argument("--out")
    a = p.parse_args(argv)
    ref = common.require_staging(a.confirm_staging)
    common.assert_ref_in(ref, SUPABASE_URL=common.env_required("SUPABASE_URL"),
                         RPG_STAGING_DB_URL=common.env_required("RPG_STAGING_DB_URL"))
    result = seed(os.environ) if a.mode == "seed" else cleanup(os.environ)
    print(common.write_evidence(f"synthetic_{a.mode}", {"project_ref": ref, **result}, a.out))
    return 0 if result.get("ok", True) else 1


if __name__ == "__main__":
    raise SystemExit(main())
