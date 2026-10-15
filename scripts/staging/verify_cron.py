"""SPEC-192: evidence that pg_cron -> pg_net -> Vercel runs succeed (job_run_details + net._http_response)."""

from __future__ import annotations

import argparse
import json
import sys

from scripts.staging import s192


def summarize_responses(rows: list[dict]) -> dict:
    """Counts of HTTP statuses and the body-level failure flag the status code alone would hide."""
    by_status: dict[str, int] = {}
    body_failed = 0
    for r in rows:
        key = str(r.get("status_code"))
        by_status[key] = by_status.get(key, 0) + 1
        try:
            if json.loads(r.get("content") or "{}").get("ok") is False:
                body_failed += 1
        except ValueError:
            pass
    return {"n": len(rows), "by_status": by_status, "ok_false_in_2xx_body": body_failed}


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--minutes", type=int, default=30)
    a = ap.parse_args(argv)
    env = s192.load_env()
    with s192.db(env) as conn:
        runs = conn.execute("""select j.jobname, d.status, count(*) n, min(d.start_time) first, max(d.start_time) last,
            round(avg(extract(epoch from (d.end_time - d.start_time)))::numeric, 3) avg_s
            from cron.job_run_details d join cron.job j using(jobid)
            where d.start_time > now() - make_interval(mins => %s) group by 1, 2 order by 1, 2""", (a.minutes,)).fetchall()
        resp = conn.execute("""select status_code, left(content, 300) content, timed_out, error_msg, created
            from net._http_response where created > now() - make_interval(mins => %s) order by created""",
                            (a.minutes,)).fetchall()
        sched = conn.execute("select jobname, schedule, active from cron.job where jobname like 'rpg-cron-%%' order by 1").fetchall()
    res = {"at": s192.now_iso(), "window_min": a.minutes, "schedule": [dict(x) for x in sched],
           "runs": [dict(x) for x in runs], "responses": summarize_responses([dict(x) for x in resp]),
           "non_2xx_sample": [dict(x) for x in resp if not (x["status_code"] and 200 <= x["status_code"] < 300)][:5]}
    res["ok"] = all(r["status"] == "succeeded" for r in res["runs"]) and bool(res["runs"]) \
        and set(res["responses"]["by_status"]) <= {"200"}
    s192.evidence("cron_runs", res)
    print(json.dumps({"ok": res["ok"], "runs": [(r["jobname"], r["status"], r["n"]) for r in res["runs"]],
                      "responses": res["responses"]}, default=str))
    return 0 if res["ok"] else 1


if __name__ == "__main__":
    sys.exit(main())
