"""SPEC-192 gate (R9): an interrupted account deletion is finished by pg_cron without user action.

Flow: synthetic user with a game + a storage object -> real ``PostgresAccountLifecycle.begin``
(sessions revoked, tombstone written) -> crash simulated by NOT calling ``finish`` -> wait for the
pg_cron-triggered ``/internal/cron/account-deletions`` -> verify tombstone ``deleted``, Auth user,
private rows and storage objects gone. A second, permanently failing tombstone proves persistent
failure does not block others and surfaces as ``rpg.cron`` ERROR / ``failed`` count.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from types import SimpleNamespace
from uuid import uuid4

import httpx

from scripts.staging import s192
from scripts.staging.e2e_session import _h

BUCKET = "rpg-dynamic"


def owner_footprint(conn, uid: str) -> dict:
    """Row counts per private app table plus session/object counts for one owner."""
    tables = [r["table_name"] for r in conn.execute(
        """select table_name from information_schema.columns where table_schema='app' and column_name='owner_id'
           and table_name <> 'account_deletions' order by 1""").fetchall()]
    counts = {}
    for t in tables:
        n = conn.execute(f"select count(*) n from app.{t} where owner_id=%s", (uid,)).fetchone()["n"]
        if n:
            counts[t] = n
    return {"private_rows": counts,
            "sessions": conn.execute("select count(*) n from auth.sessions where user_id=%s", (uid,)).fetchone()["n"],
            "storage_objects": conn.execute("select count(*) n from storage.objects where bucket_id=%s and starts_with(name,%s)",
                                            (BUCKET, f"users/{uid}/")).fetchone()["n"],
            "auth_user": conn.execute("select count(*) n from auth.users where id=%s", (uid,)).fetchone()["n"]}


def recovered(fp: dict, tombstone_status: str | None) -> bool:
    return tombstone_status == "deleted" and not fp["private_rows"] and fp["storage_objects"] == 0 \
        and fp["auth_user"] == 0 and fp["sessions"] == 0


def log_message(line: str) -> str:
    """Short, redacted message of one `vercel logs --json` line."""
    try:
        data = json.loads(line).get("data", {})
        return s192.common.redact_text(f"{data.get('level')} {data.get('message') or data.get('requestPath')}")[:300]
    except ValueError:
        return s192.common.redact_text(line)[:200]


def cron_call(base: str, secret: str, path: str) -> dict:
    r = None
    for attempt in range(4):  # local network resets idle connections now and then
        try:
            r = httpx.post(base + path, headers={"Authorization": f"Bearer {secret}"}, timeout=90)
            break
        except httpx.HTTPError:
            time.sleep(2 + attempt)
    if r is None:
        return {"status": None, "error": "transport"}
    try:
        body = {k: v for k, v in r.json().items() if isinstance(v, (int, float, str, bool))}
    except ValueError:
        body = {}
    return {"status": r.status_code, **body}


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--base", default=s192.BASE)
    ap.add_argument("--wait", type=int, default=420)
    a = ap.parse_args(argv)
    env = s192.load_env()
    admin = s192.Admin(env)
    from psycopg.rows import dict_row
    from psycopg_pool import ConnectionPool
    from infrastructure.account_lifecycle import PostgresAccountLifecycle
    pool = ConnectionPool(env["RPG_STAGING_DB_URL"], min_size=1, max_size=2, kwargs={"row_factory": dict_row}, open=True)
    life = PostgresAccountLifecycle(pool, SimpleNamespace(), SimpleNamespace(bucket=BUCKET))
    out: dict = {"at": s192.now_iso(), "checks": {}}
    ck = out["checks"]
    user = admin.create_user()
    uid, fake = user["id"], str(uuid4())
    c = httpx.Client(timeout=120, transport=httpx.HTTPTransport(retries=3))
    try:
        r = s192.app_login(c, a.base, user)
        csrf = r.json()["csrf_token"]
        origins = json.loads((s192.common.ROOT / "data" / "origins.json").read_text(encoding="utf-8"))
        g = c.post(a.base + "/game/new", headers=_h(a.base, csrf), json={
            "name": "Spec192 Del", "race": origins["races"][0]["name"], "class_name": "Devoto do Abismo",
            "region": origins["regions"][0]["name"], "level": 1, "action_id": str(uuid4())})
        up = c.post(f"{admin.url}/storage/v1/object/{BUCKET}/users/{uid}/spec192.webp",
                    headers={**admin.headers, "Content-Type": "image/webp"}, content=b"RIFF" + bytes(4) + b"WEBPVP8 ")
        with s192.db(env) as conn:
            pre = owner_footprint(conn, uid)
        life.begin(uid)  # real code path: sessions revoked + tombstone; then the "process crashes"
        with s192.db(env) as conn:
            mid = owner_footprint(conn, uid)
            ts = conn.execute("select status, sessions_revoked_at is not null revoked from app.account_deletions where owner_id=%s",
                              (uid,)).fetchone()
            conn.execute("insert into app.account_deletions(owner_id, blob_keys, sessions_revoked_at) values (%s, %s, now())",
                         (fake, ["bad/not-owned-key"]))  # permanent failure: invalid_blob_owner
        ck["setup"] = {"game_status": g.status_code, "upload_status": up.status_code, "before": pre, "after_crash": mid,
                       "tombstone": dict(ts or {}),
                       "ok": g.status_code == 200 and bool(pre["private_rows"]) and pre["storage_objects"] == 1
                       and mid["sessions"] == 0 and bool(mid["private_rows"]) and ts["status"] == "deleting" and ts["revoked"]}
        t0 = time.monotonic()
        final_fp, status = mid, "deleting"
        while time.monotonic() - t0 < a.wait:
            time.sleep(15)
            def probe(conn):
                row = conn.execute("select status from app.account_deletions where owner_id=%s", (uid,)).fetchone()
                return owner_footprint(conn, uid), (row["status"] if row else None)
            final_fp, status = s192.query(env, probe)
            if recovered(final_fp, status):
                break
        elapsed = round(time.monotonic() - t0)
        def evidence_rows(conn):
            return (conn.execute("select status, recovery_attempted_at is not null attempted from app.account_deletions "
                                 "where owner_id=%s", (fake,)).fetchone(),
                    conn.execute("""select d.status, d.start_time, d.end_time from cron.job_run_details d join cron.job j using(jobid)
                where j.jobname='rpg-cron-account-deletions' order by d.start_time desc limit 5""").fetchall(),
                    conn.execute("""select status_code, left(content, 160) content from net._http_response
                where content like '%%"claimed"%%' order by created desc limit 5""").fetchall())
        bad, runs, resp = s192.query(env, evidence_rows)
        ck["recovered_by_cron"] = {"elapsed_s": elapsed, "final": final_fp, "tombstone_status": status,
                                   "auth_user_via_admin_api": admin.user_exists(uid),
                                   "cron_runs": [dict(x) for x in runs], "http_responses": [dict(x) for x in resp],
                                   "ok": recovered(final_fp, status) and not admin.user_exists(uid)}
        ck["persistent_failure_isolated"] = {"bad_tombstone": dict(bad or {}),
                                             "ok": bool(bad) and bad["status"] == "deleting" and bad["attempted"]
                                             and ck["recovered_by_cron"]["ok"]}
        # alert signal: 3 consecutive failing sweeps on the same instance -> rpg.cron ERROR; response body shows failed>0
        secret = env["RPG_CRON_SECRET"]
        calls = [cron_call(a.base, secret, "/internal/cron/account-deletions") for _ in range(4)]
        time.sleep(20)
        lg = s192.vercel(["logs", "--environment", "production", "--since", "10m", "--query", "level:error",
                          "--limit", "50"], env, timeout=240)
        lines = [ln for ln in ((lg.stdout or "") + "\n" + (lg.stderr or "")).splitlines() if "rpg.cron" in ln]
        ck["failure_alerting"] = {
            "sweeps": calls, "error_log_lines": len(lines),
            "error_log_sample": [log_message(ln) for ln in lines[:3]],
            "ok": all(x.get("failed", 0) >= 1 and x.get("ok") is False for x in calls) and bool(lines)}
    finally:
        s192.query(env, lambda conn: conn.execute(
            "delete from app.account_deletions where owner_id = any(%s::uuid[])", ([uid, fake],)))
        out["cleanup"] = {"user_delete_status": admin.delete_user(uid), "tombstones_removed": True}
        pool.close()
        s192.evidence("account_deletion_recovery", {**out, "partial": True})
    out["ok"] = all(v.get("ok") for v in ck.values())
    s192.evidence("account_deletion_recovery", out)
    print(json.dumps({"ok": out["ok"], **{k: v.get("ok") for k, v in ck.items()}}))
    return 0 if out["ok"] else 1


if __name__ == "__main__":
    sys.exit(main())
