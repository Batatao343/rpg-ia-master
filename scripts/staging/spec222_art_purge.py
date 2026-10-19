"""SPEC-222 R6 on staging: deleting a campaign with real art removes its objects from the bucket.

Flow (real user path, one paid image ~US$ 0.04):
  synthetic user (generate_link + /auth/verify) -> /game/new -> wallet admin credit (synthetic, append-only)
  -> /art/quote -> /art/confirm -> cron /internal/cron/jobs generates the image (OpenAI) -> object in bucket
  -> DELETE /game/save/{id} -> cron drains ``purge_blobs`` -> object gone.

Evidence: docs/staging-wave-2026-10-17/evidence/spec222_art_purge.json (ids hashed, no PII, no secrets).
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
import time
from uuid import UUID, uuid4

import httpx

from scripts.staging import common, s192

EVIDENCE = common.ROOT / "docs" / "staging-wave-2026-10-17" / "evidence"
BUCKET = "rpg-dynamic"
MAX_QUOTE_USD = 0.20  # task ceiling


def _h(base: str, csrf: str | None = None, **extra) -> dict:
    h = {"Origin": base, "Content-Type": "application/json", **extra}
    if csrf:
        h["X-CSRF-Token"] = csrf
    return h


def _hash(value: str) -> str:
    return hashlib.sha256(value.encode()).hexdigest()[:12]


def _objects(env: dict, prefix: str) -> list[dict]:
    return s192.query(env, lambda c: [dict(r) for r in c.execute(
        "select name, (metadata->>'size')::bigint as bytes, created_at from storage.objects "
        "where bucket_id=%s and starts_with(name,%s) order by name", (BUCKET, prefix)).fetchall()])


def _cron(base: str, env: dict, path: str) -> dict:
    r = httpx.post(f"{base}{path}", headers={"Authorization": f"Bearer {env['RPG_CRON_SECRET']}",
                                             "Content-Type": "application/json"}, json={}, timeout=120)
    try:
        body = r.json()
    except ValueError:
        body = {}
    return {"status": r.status_code, "at": s192.now_iso(),
            "summary": {k: v for k, v in body.items() if isinstance(v, (int, float, str, bool))} if isinstance(body, dict) else {}}


def run(base: str, env: dict, wait_s: int) -> dict:
    from infrastructure.contracts import Principal
    from infrastructure.postgres import PostgresPool
    from infrastructure.wallet import PostgresWallet

    admin = s192.Admin(env)
    out: dict = {"base": base, "at": s192.now_iso(), "checks": {}, "timeline": []}
    ck, tl = out["checks"], out["timeline"]
    user = admin.create_user()
    uid = user["id"]
    c = httpx.Client(timeout=60, transport=httpx.HTTPTransport(retries=3))
    game_id = ""
    try:
        r = s192.app_login(c, base, user)
        csrf = (r.json() if r.status_code == 200 else {}).get("csrf_token") or c.cookies.get("rpg_csrf") or ""
        ck["login"] = {"status": r.status_code, "ok": r.status_code == 200 and bool(csrf)}
        origins = json.loads((common.ROOT / "data" / "origins.json").read_text(encoding="utf-8"))
        body = {"name": "Spec222 Heroi", "race": origins["races"][0]["name"], "class_name": "Devoto do Abismo",
                "region": origins["regions"][0]["name"], "level": 1, "action_id": str(uuid4())}
        r = c.post(f"{base}/game/new", headers=_h(base, csrf), json=body, timeout=180)
        game_id = (r.json() if r.status_code == 200 else {}).get("game_id", "")
        ck["new_game"] = {"status": r.status_code, "ok": bool(game_id)}
        if not game_id:
            raise RuntimeError(f"new game failed {r.status_code}")
        prefix = f"users/{uid}/games/{game_id}/"
        tl.append({"step": "game_created", "at": s192.now_iso()})

        r = c.post(f"{base}/game/{game_id}/art/quote", headers=_h(base, csrf), json={"image_type": "player"})
        quote = r.json() if r.status_code == 200 else {}
        ck["quote"] = {"status": r.status_code, "detail": None if quote else (r.json() if r.content else {}).get("detail"),
                       "credits_milli": quote.get("credits_milli"), "ok": r.status_code == 200}
        if r.status_code != 200:
            raise RuntimeError(f"quote failed {r.status_code}")
        need = int(quote.get("credits_milli") or 0)
        pool = PostgresPool(env["RPG_STAGING_DB_URL"], max_size=2)
        try:
            pr = Principal(UUID(uid), "supabase", uid)
            bal = PostgresWallet(pool).adjust_admin(
                pr, adjustment_id="spec222-art-" + uuid4().hex[:12], signed_milli=need + 1000,
                actor_id=UUID(int=0), reason="spec222 staging smoke: synthetic credit for 1 portrait")
        finally:
            pool.close()
        ck["wallet_credit"] = {"credited_milli": need + 1000, "available_milli": bal.available_milli, "ok": True}
        r = c.post(f"{base}/game/{game_id}/art/confirm", headers=_h(base, csrf),
                   json={"action_id": str(uuid4()), "quote_id": quote["quote_id"], "confirmed": True}, timeout=120)
        conf = r.json() if r.status_code == 200 else {}
        gen_id = conf.get("generation_id", "")
        ck["confirm"] = {"status": r.status_code, "generation_status": conf.get("status"),
                         "detail": None if conf else (r.json() if r.content else {}).get("detail"),
                         "ok": r.status_code == 200 and bool(gen_id)}
        if not gen_id:
            raise RuntimeError(f"confirm failed {r.status_code}")
        tl.append({"step": "confirmed", "at": s192.now_iso()})

        status, art = "pending", {}
        deadline = time.time() + wait_s
        while time.time() < deadline:
            r = c.get(f"{base}/game/{game_id}/art/{gen_id}")
            art = r.json() if r.status_code == 200 else {}
            status = art.get("status")
            if status == "ready" or str(status).startswith("failed") or status == "reconcile_required":
                break
            time.sleep(15)
        objs = _objects(env, prefix)
        cost = s192.query(env, lambda conn: [dict(x) for x in conn.execute(
            "select provider, outcome, cost_usd, cost_basis, counts_as_spend from app.usage_events "
            "where owner_id=%s and category ilike '%%image%%'", (uid,)).fetchall()])
        ck["image_ready"] = {"status": status, "financial_status": art.get("financial_status"),
                             "assets": len(art.get("assets") or []), "objects_in_bucket": len(objs),
                             "object_bytes": [o["bytes"] for o in objs], "usage_events": cost,
                             "ok": status == "ready" and len(objs) >= 1}
        tl.append({"step": "image_ready", "at": s192.now_iso()})
        if status != "ready":
            raise RuntimeError(f"image not ready: {status}")
        asset_rows = s192.query(env, lambda conn: conn.execute(
            "select count(*) n from app.assets where game_id=%s", (game_id,)).fetchone()["n"])

        r = c.delete(f"{base}/game/save/{game_id}", headers=_h(base, csrf, **{"Idempotency-Key": str(uuid4())}))
        deleted_at = s192.now_iso()
        job = s192.query(env, lambda conn: [dict(x) for x in conn.execute(
            "select status, attempts, payload->'object_keys' as keys from app.jobs where kind='purge_blobs' "
            "and dedupe_key=%s", (f"game:{game_id}",)).fetchall()])
        ck["delete_game"] = {"status": r.status_code, "asset_rows_before": asset_rows,
                             "purge_job": [{"status": j["status"], "attempts": j["attempts"],
                                            "keys": len(j["keys"] or [])} for j in job],
                             "objects_right_after_delete": len(_objects(env, prefix)),
                             "ok": r.status_code in (200, 204) and len(job) == 1}
        tl.append({"step": "game_deleted", "at": deleted_at})

        # Wait for the scheduled pg_cron run (every minute) -- no manual trigger: proves "<= 1 cron cycle".
        gone_at, polls = None, 0
        deadline = time.time() + 180
        while time.time() < deadline:
            polls += 1
            if not _objects(env, prefix):
                gone_at = s192.now_iso()
                break
            time.sleep(10)
        job = s192.query(env, lambda conn: [dict(x) for x in conn.execute(
            "select status, attempts, updated_at from app.jobs where kind='purge_blobs' and dedupe_key=%s",
            (f"game:{game_id}",)).fetchall()])
        cron_runs = s192.query(env, lambda conn: [dict(x) for x in conn.execute(
            "select r.created_at, h.status_code from app.cron_requests r left join net._http_response h "
            "on h.id=r.request_id where r.job_name='rpg-cron-jobs' and r.created_at >= %s::timestamptz "
            "order by r.created_at limit 5", (deleted_at,)).fetchall()])
        ck["purged"] = {"objects_left": len(_objects(env, prefix)), "gone_at": gone_at, "polls": polls,
                        "job": [{"status": j["status"], "attempts": j["attempts"], "updated_at": j["updated_at"]}
                                for j in job],
                        "scheduled_cron_runs_after_delete": cron_runs,
                        "manual_cron_trigger": False,
                        "ok": gone_at is not None and all(j["status"] == "succeeded" for j in job)}
        tl.append({"step": "objects_gone", "at": gone_at})
        out["ids"] = {"owner": _hash(uid), "game": _hash(game_id), "generation": _hash(gen_id)}
    finally:
        out["cleanup"] = {"user_delete_status": admin.delete_user(uid)}
    out["ok"] = all(v.get("ok") for v in ck.values())
    return out


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--base", default=s192.BASE)
    ap.add_argument("--wait", type=int, default=420, help="seconds to wait for the image job")
    a = ap.parse_args(argv)
    env = s192.load_env()
    res = run(a.base, env, a.wait)
    path = common.write_evidence("spec222_art_purge", res, EVIDENCE / "spec222_art_purge.json")
    print(json.dumps({"ok": res["ok"], **{k: v.get("ok") for k, v in res["checks"].items()}, "evidence": str(path)}))
    return 0 if res["ok"] else 1


if __name__ == "__main__":
    sys.exit(main())
