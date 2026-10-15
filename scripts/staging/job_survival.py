"""SPEC-192 gate: jobs survive worker crash and a production redeploy (exactly-once, fenced).

A: emulated crash - a job is leased straight in the DB with a short lease by a worker that never
   completes; pg_cron's drain must wait for lease expiry, re-lease (new fencing token) and complete
   it once. The stale token must be rejected (LeaseHeld).
B: real redeploy - ``vercel deploy --prod`` runs while embed_memory jobs are enqueued every ~20 s
   and drained by the per-minute pg_cron ticks; every job must end succeeded exactly once.
Jobs are ``session`` memory documents of a synthetic user's game (the usage metering of a job
requires an owner); the user, game and rows are purged at the end.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
import threading
import time
from uuid import uuid4

from psycopg.types.json import Jsonb

from scripts.staging import s192

PROFILE = "local-1024"


def make_owner(env) -> dict:
    """Synthetic user + game created through the deployed API (same path as the web client)."""
    import httpx
    from scripts.staging.e2e_session import _h
    admin = s192.Admin(env)
    user = admin.create_user()
    c = httpx.Client(timeout=120, transport=httpx.HTTPTransport(retries=3))
    r = c.post(s192.BASE + "/auth/login", headers=_h(s192.BASE), json={
        "email": user["email"], "password": user["password"], "captcha_token": s192.CAPTCHA_TEST})
    csrf = r.json()["csrf_token"]
    origins = json.loads((s192.common.ROOT / "data" / "origins.json").read_text(encoding="utf-8"))
    g = c.post(s192.BASE + "/game/new", headers=_h(s192.BASE, csrf), json={
        "name": "Spec192 Job", "race": origins["races"][0]["name"], "class_name": "Devoto do Abismo",
        "region": origins["regions"][0]["name"], "level": 1, "action_id": str(uuid4())})
    g.raise_for_status()
    return {"uid": user["id"], "game_id": g.json()["game_id"], "admin": admin}


def purge_owner(env, owner: dict) -> dict:
    def go(conn):
        n = {}
        tables = [r["table_name"] for r in conn.execute(
            """select table_name from information_schema.columns where table_schema='app'
               and column_name='owner_id' and table_name <> 'account_deletions'""").fetchall()]
        for _ in range(3):  # FK order is unknown: retry until stable
            for t in tables:
                try:
                    n[t] = n.get(t, 0) + conn.execute(f"delete from app.{t} where owner_id=%s", (owner["uid"],)).rowcount
                except Exception:  # noqa: BLE001
                    pass
        return {k: v for k, v in n.items() if v}
    rows = s192.query(env, go)
    return {"rows_deleted": rows, "user_delete_status": owner["admin"].delete_user(owner["uid"])}


def make_job(conn, owner: dict, text: str | None = None) -> dict:
    doc_id = f"spec192-{uuid4().hex}"
    text = text or f"Registro sintetico de teste {doc_id}."
    digest = hashlib.sha256(text.encode()).hexdigest()
    conn.execute("""insert into app.memory_documents(id,owner_id,game_id,scope,content,content_sha256,metadata,
                    canonical_entity_ids,visibility,timeline_epoch,embedding_profile_id)
                    values (%s,%s,%s,'session',%s,%s,'{}'::jsonb,'{}','public',0,%s)""",
                 (doc_id, owner["uid"], owner["game_id"], text, digest, PROFILE))
    job_id = conn.execute("""insert into app.jobs(id,owner_id,game_id,kind,dedupe_key,status,payload,max_attempts)
        values (gen_random_uuid(),%s,%s,'embed_memory',%s,'queued',%s,5) returning id""",
                          (owner["uid"], owner["game_id"], doc_id, Jsonb({"memory_id": doc_id, "content_sha256": digest, "profile_id": PROFILE,
                                          "timeline_epoch": 0}))).fetchone()["id"]
    return {"doc_id": doc_id, "job_id": job_id}


def job_state(conn, ref: dict) -> dict:
    j = conn.execute("select status,attempts,lease_token is not null leased,last_error_code from app.jobs where id=%s",
                     (ref["job_id"],)).fetchone() or {}
    d = conn.execute("select embedding_status from app.memory_documents where id=%s", (ref["doc_id"],)).fetchall()
    n = conn.execute("select count(*) n from app.jobs where kind='embed_memory' and dedupe_key=%s",
                     (ref["doc_id"],)).fetchone()["n"]
    return {**{k: v for k, v in j.items()}, "documents": len(d), "embedding_status": d[0]["embedding_status"] if d else None,
            "jobs_for_doc": n}


def exactly_once(state: dict, max_attempts: int = 2) -> bool:
    return (state.get("status") == "succeeded" and not state.get("leased") and state.get("documents") == 1
            and state.get("embedding_status") == "ready" and state.get("jobs_for_doc") == 1
            and 1 <= state.get("attempts", 0) <= max_attempts)


def wait_for(env, ref: dict, timeout: int) -> dict:
    t0 = time.monotonic()
    st: dict = {}
    while time.monotonic() - t0 < timeout:
        with s192.db(env) as conn:
            st = job_state(conn, ref)
        if st.get("status") in ("succeeded", "dead"):
            break
        time.sleep(5)
    return {**st, "waited_s": round(time.monotonic() - t0)}


def phase_a(env, owner: dict) -> dict:
    from psycopg.rows import dict_row
    from psycopg_pool import ConnectionPool
    from infrastructure.contracts import LeaseHeld
    from infrastructure.postgres_jobs import PostgresJobQueue
    with s192.db(env) as conn:
        ref = make_job(conn, owner)
        stale = conn.execute("""update app.jobs set status='running',attempts=1,lease_token=gen_random_uuid(),
            lease_owner='spec192-crashed-worker',lease_until=now()+interval '25 seconds'
            where id=%s returning lease_token""", (ref["job_id"],)).fetchone()["lease_token"]
    time.sleep(12)
    with s192.db(env) as conn:
        during = job_state(conn, ref)  # cron ticked inside the lease window -> must not steal it
    final = wait_for(env, ref, 180)
    pool = ConnectionPool(env["RPG_STAGING_DB_URL"], min_size=1, max_size=1, kwargs={"row_factory": dict_row}, open=True)
    queue = PostgresJobQueue(pool)
    fenced = {}
    for name, call in (("complete", lambda: queue.complete(ref["job_id"], stale, {"zombie": True})),
                       ("fail", lambda: queue.fail(ref["job_id"], stale, "zombie")),
                       ("heartbeat", lambda: queue.heartbeat(ref["job_id"], stale))):
        try:
            call()
            fenced[name] = "ACCEPTED"
        except LeaseHeld:
            fenced[name] = "LeaseHeld"
        except Exception as exc:  # noqa: BLE001
            fenced[name] = type(exc).__name__
    pool.close()
    with s192.db(env) as conn:
        final_row = job_state(conn, ref)
        conn.execute("delete from app.jobs where id=%s", (ref["job_id"],))
        conn.execute("delete from app.memory_documents where id=%s", (ref["doc_id"],))
    return {"during_lease_window": during, "after_expiry": final, "stale_token_calls": fenced,
            "ok": during.get("status") == "running" and during.get("attempts") == 1 and exactly_once(final_row)
            and final_row["attempts"] == 2 and all(v == "LeaseHeld" for v in fenced.values())}


def phase_b(env, owner: dict, n_jobs: int = 4) -> dict:
    refs: list[dict] = []
    deploy: dict = {}

    def run_deploy():
        t0 = time.monotonic()
        for attempt in range(3):
            r = s192.vercel(["deploy", "--prod", "--yes"], env, timeout=1200)
            deploy.update({"returncode": r.returncode, "attempts": attempt + 1})
            if r.returncode == 0:
                break
        deploy["seconds"] = round(time.monotonic() - t0)
        deploy["done"] = True

    with s192.db(env) as conn:
        w0 = conn.execute("select now() t").fetchone()["t"]
        refs.append(make_job(conn, owner))
    th = threading.Thread(target=run_deploy)
    th.start()
    while th.is_alive() or len(refs) < n_jobs:
        time.sleep(20)
        if len(refs) < n_jobs:
            with s192.db(env) as conn:
                refs.append(make_job(conn, owner))
        if not th.is_alive() and len(refs) >= n_jobs:
            break
    th.join()
    finals = [wait_for(env, r, 180) for r in refs]
    with s192.db(env) as conn:
        states = [job_state(conn, r) for r in refs]
        http = conn.execute("""select status_code, count(*) n from net._http_response where created >= %s
                               group by 1 order by 1""", (w0,)).fetchall()
        runs = conn.execute("""select d.status, count(*) n from cron.job_run_details d join cron.job j using(jobid)
                               where j.jobname='rpg-cron-jobs' and d.start_time >= %s group by 1""", (w0,)).fetchall()
        for r in refs:
            conn.execute("delete from app.jobs where id=%s", (r["job_id"],))
            conn.execute("delete from app.memory_documents where id=%s", (r["doc_id"],))
    return {"deploy": deploy, "jobs": states, "waited": [f["waited_s"] for f in finals],
            "http_status_counts_during_window": [dict(h) for h in http],
            "cron_runs_during_window": [dict(x) for x in runs],
            "ok": bool(deploy.get("returncode") == 0) and all(exactly_once(s, 2) for s in states)}


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--skip-redeploy", action="store_true")
    a = ap.parse_args(argv)
    env = s192.load_env()
    out: dict = {"at": s192.now_iso(), "checks": {}}
    owner = make_owner(env)
    try:
        out["checks"]["A_crash_lease_expiry"] = phase_a(env, owner)
        if not a.skip_redeploy:
            out["checks"]["B_real_redeploy"] = phase_b(env, owner)
    finally:
        out["cleanup"] = purge_owner(env, owner)
    out["ok"] = all(v["ok"] for v in out["checks"].values())
    s192.evidence("job_survival", out)
    print(json.dumps({"ok": out["ok"], **{k: v["ok"] for k, v in out["checks"].items()}}))
    return 0 if out["ok"] else 1


if __name__ == "__main__":
    sys.exit(main())
