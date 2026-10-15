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
WALLET_EXPECTED = common.ROOT / ".tmp" / "spec191" / "wallet_expected.json"
# 1x1 lossless WebP; two distinct payloads (trailing byte differs inside a padding-free chunk is risky,
# so the second object is simply the same bytes under another path -> checksums still verified per path).
TINY_WEBP = base64.b64decode("UklGRhoAAABXRUJQVlA4TA0AAAAvAAAAEAcQERGIiP4HAA==")


def build_manifest(users: list[dict]) -> dict:
    """Pure: secret-free manifest (no emails/passwords)."""
    return {"users": [{"id": u["id"], "game_id": u["game_id"], "memory_doc": u["memory_doc"],
                       "objects": u["objects"]} for u in users]}


WALLET_PRICING = "spec197-restore-b"
WALLET_SKU = "spec197-restore-b-sku"
WALLET_SHARDS = 311
SPENT_MILLI = 200
DEBT_MILLI = 75


def seed_wallet_prereqs(dsn: str) -> None:
    """Idempotent synthetic pricing version + web SKU (append-only rows, staging only)."""
    import psycopg
    from psycopg.types.json import Jsonb
    from services.shard_pricing import INSTALLED_RATE_CARD_OBSERVED_AT, INSTALLED_RATE_CARD_SHA256
    from services.usage_metering import RATE_CARD_VERSION
    with psycopg.connect(dsn, autocommit=True, prepare_threshold=None) as c:
        c.execute("""insert into app.pricing_versions
            (version_id,shard_budget_unit_brl,fx_usd_brl,fx_source,fx_observed_at,fx_max_age_seconds,
             fx_buffer_rate,rate_card_version,rate_card_sha256,rate_card_source,rate_card_observed_at,
             rate_card_max_age_seconds,channel_fees)
            values (%s,0.03,5,'spec197 synthetic',now() - interval '10 minutes',31536000,0.10,%s,%s,'spec197 synthetic',%s,31536000,%s)
            on conflict (version_id) do nothing""",
                  (WALLET_PRICING, RATE_CARD_VERSION, INSTALLED_RATE_CARD_SHA256,
                   INSTALLED_RATE_CARD_OBSERVED_AT, Jsonb({"web": {"percentage": "0.04", "fixed_brl": "0.20"}})))
        c.execute("""insert into app.purchase_skus (sku_id,pricing_version_id,channel,store_product_id,gross_brl,shard_milli)
            values (%s,%s,'web',%s,10.50,%s) on conflict (sku_id) do nothing""",
                  (WALLET_SKU, WALLET_PRICING, WALLET_SKU, WALLET_SHARDS))


def seed_wallet(dsn: str, owner_id: str) -> dict:
    """Synthetic Stripe-test-like purchase + reservation/release + admin spend + refund-debt event for
    ONE owner (SPEC-197 R5 restore drill). wallet_*/debt facts are append-only: the rows stay in
    staging under this synthetic owner (see docs/spec197/evidence/restore_wallet.json). Idempotent
    prerequisites (pricing version with a long rate-card window so reserve() is not 'stale')."""
    import psycopg
    from psycopg.types.json import Jsonb
    from infrastructure.contracts import Principal
    from infrastructure.postgres import PostgresPool
    from infrastructure.wallet import PostgresWallet
    from infrastructure.wallet_debt import insert_debt_entry
    from services.shard_pricing import INSTALLED_RATE_CARD_OBSERVED_AT, INSTALLED_RATE_CARD_SHA256
    from services.usage_metering import RATE_CARD_VERSION
    seed_wallet_prereqs(dsn)
    pool = PostgresPool(dsn)
    try:
        wallet = PostgresWallet(pool)
        pr = Principal(UUID(owner_id), "supabase", owner_id)
        wallet.credit_verified_purchase(pr, channel="web", payment_id="pi_spec197_" + uuid4().hex[:16],
                                        sku_id=WALLET_SKU, verified=True)
        fence = uuid4()
        res = wallet.reserve(pr, reference_type="other", reference_id=str(uuid4()),
                             pricing_version_id=WALLET_PRICING, ceiling_milli=50, fence_token=fence)
        wallet.release_pre_effect(pr, res.reservation_id, fence_token=fence)
        wallet.adjust_admin(pr, adjustment_id="spec197-" + uuid4().hex[:12], signed_milli=-SPENT_MILLI,
                            actor_id=uuid4(), reason="spec197 synthetic spend")
        with pool.connection() as db, db.transaction():
            insert_debt_entry(db, UUID(owner_id), "open", "pi_spec197_debt", DEBT_MILLI,
                              "spec197-debt-" + uuid4().hex[:8])
    finally:
        pool.close()
    return wallet_snapshot(dsn, [owner_id])


def wallet_snapshot(dsn: str, owner_ids: list[str]) -> dict:
    """Per-owner ledger facts used to compare staging vs restored lab (no emails, ids hashed by caller)."""
    import psycopg
    out: dict[str, Any] = {}
    with psycopg.connect(dsn, autocommit=True, prepare_threshold=None) as c:
        for oid in owner_ids:
            acc = c.execute("select available_milli,reserved_milli from app.wallet_accounts where owner_id=%s",
                            (oid,)).fetchone()
            led = c.execute("""select count(*), coalesce(sum(available_delta),0), coalesce(sum(reserved_delta),0)
                from app.wallet_entries where owner_id=%s""", (oid,)).fetchone()
            kinds = c.execute("select entry_type,count(*) from app.wallet_entries where owner_id=%s "
                              "group by 1 order by 1", (oid,)).fetchall()
            debt = c.execute("select count(*), coalesce(sum(debt_delta),0) from app.wallet_debt_entries "
                             "where owner_id=%s", (oid,)).fetchone()
            out[oid] = {"available_milli": int(acc[0]) if acc else None, "reserved_milli": int(acc[1]) if acc else None,
                        "ledger_entries": int(led[0]), "ledger_available_sum": int(led[1]),
                        "ledger_reserved_sum": int(led[2]), "entry_types": {k: int(n) for k, n in kinds},
                        "debt_entries": int(debt[0]), "debt_total_milli": int(debt[1])}
        out["_global"] = {"wallet_accounts": c.execute("select count(*) from app.wallet_accounts").fetchone()[0],
                          "wallet_entries": c.execute("select count(*) from app.wallet_entries").fetchone()[0],
                          "debt_entries": c.execute("select count(*) from app.wallet_debt_entries").fetchone()[0]}
    return out


def compare_wallet(expected: Mapping[str, Any], actual: Mapping[str, Any]) -> dict:
    """Pure: ledger sums must equal account balances and expected == actual."""
    diffs = {k: {"expected": expected[k], "actual": actual.get(k)} for k in expected if expected[k] != actual.get(k)}
    consistent = all(v["available_milli"] == v["ledger_available_sum"] and v["reserved_milli"] == v["ledger_reserved_sum"]
                     for k, v in actual.items() if not k.startswith("_") and v["available_milli"] is not None)
    return {"ok": not diffs and consistent, "diffs": diffs, "ledger_matches_accounts": consistent}


def seed(env: Mapping[str, str], client: httpx.Client | None = None, *, wallet: bool = False) -> dict:
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
    out = {"users": len(users), "games": len(users), "memory_docs": len(users),
           "objects": sum(len(u["objects"]) for u in users)}
    if wallet:
        snap = seed_wallet(dsn, users[0]["id"])
        WALLET_EXPECTED.write_text(json.dumps(snap, indent=2), encoding="utf-8")
        out["wallet_owner_entries"] = snap[users[0]["id"]]["ledger_entries"]
    return out


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
    p.add_argument("mode", choices=["seed", "cleanup", "wallet-compare"])
    p.add_argument("--confirm-staging", metavar="REF")  # required for seed/cleanup (guard below)
    p.add_argument("--out")
    p.add_argument("--wallet", action="store_true", help="seed: also create synthetic wallet/debt facts (SPEC-197)")
    p.add_argument("--target-dsn", help="wallet-compare: disposable lab DSN (localhost only)")
    a = p.parse_args(argv)
    if a.mode == "wallet-compare":
        from scripts.staging.backup_restore import assert_disposable
        assert_disposable(a.target_dsn or "", True)
        exp = json.loads(WALLET_EXPECTED.read_text(encoding="utf-8"))
        res = compare_wallet(exp, wallet_snapshot(a.target_dsn, [k for k in exp if not k.startswith("_")]) | {
            "_global": wallet_snapshot(a.target_dsn, [])["_global"]})
        print(common.write_evidence("wallet_compare", {"expected": exp, **res}, a.out))
        return 0 if res["ok"] else 1
    ref = common.require_staging(a.confirm_staging)
    common.assert_ref_in(ref, SUPABASE_URL=common.env_required("SUPABASE_URL"),
                         RPG_STAGING_DB_URL=common.env_required("RPG_STAGING_DB_URL"))
    result = seed(os.environ, wallet=a.wallet) if a.mode == "seed" else cleanup(os.environ)
    print(common.write_evidence(f"synthetic_{a.mode}", {"project_ref": ref, **result}, a.out))
    return 0 if result.get("ok", True) else 1


if __name__ == "__main__":
    raise SystemExit(main())
