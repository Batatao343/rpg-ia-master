"""SPEC-192: idempotent pg_cron + pg_net scheduling of the internal cron endpoints on staging.

Enables extensions, stores RPG_CRON_SECRET in Vault (create or update), then
unschedules-by-name and schedules each job. Secrets are never printed.
"""

from __future__ import annotations

import argparse
import json
import sys

from scripts.staging import s192

JOBS = (
    ("rpg-cron-jobs", "* * * * *", "/internal/cron/jobs"),
    ("rpg-cron-account-deletions", "*/5 * * * *", "/internal/cron/account-deletions"),
    ("rpg-cron-operations", "*/5 * * * *", "/internal/cron/operations"),
    ("rpg-cron-reconciliation", "*/15 * * * *", "/internal/cron/reconciliation"),  # SPEC-195
    ("rpg-cron-finops", "0 * * * *", "/internal/cron/finops"),  # SPEC-196
)
SECRET_NAME = "rpg_cron_secret"
EXTENSIONS = ("pg_cron", "pg_net")


WATCHDOG = ("rpg-cron-health", "*/15 * * * *", "select app.cron_health_check()")


def job_command(url: str, name: str = "") -> str:
    """SQL executed by pg_cron; the bearer comes from Vault at run time.

    The pg_net request id is logged in ``app.cron_requests`` so the watchdog can join it with
    ``net._http_response`` (which has no URL column).
    """
    safe = url.replace("'", "''")
    label = name.replace("'", "''")
    return (
        "with r as (select net.http_post("
        f"url := '{safe}', "
        "headers := jsonb_build_object('Authorization', 'Bearer ' || "
        f"(select decrypted_secret from vault.decrypted_secrets where name = '{SECRET_NAME}'), "
        "'Content-Type', 'application/json'), "
        "body := '{}'::jsonb, timeout_milliseconds := 58000) as id) "
        f"insert into app.cron_requests (request_id, job_name) select id, '{label}' from r"
    )


def plan(base: str) -> list[tuple[str, str, str]]:
    base = base.rstrip("/")
    return [(name, schedule, job_command(base + path, name)) for name, schedule, path in JOBS] + [
        WATCHDOG
    ]


def apply(conn, base: str, cron_secret: str) -> dict:
    out: dict = {"extensions": {}, "jobs": []}
    for ext in EXTENSIONS:
        conn.execute(f"create extension if not exists {ext}")
    out["extensions"] = {
        r["extname"]: r["extversion"]
        for r in conn.execute(
            "select extname, extversion from pg_extension where extname = any(%s)",
            (list(EXTENSIONS),),
        ).fetchall()
    }
    row = conn.execute("select id from vault.secrets where name = %s", (SECRET_NAME,)).fetchone()
    if row:
        conn.execute("select vault.update_secret(%s, %s)", (row["id"], cron_secret))
        out["vault"] = "updated"
    else:
        conn.execute(
            "select vault.create_secret(%s, %s, %s)",
            (cron_secret, SECRET_NAME, "SPEC-192 cron bearer"),
        )
        out["vault"] = "created"
    for name, schedule, command in plan(base):
        conn.execute("select cron.unschedule(jobid) from cron.job where jobname = %s", (name,))
        jid = conn.execute(
            "select cron.schedule(%s, %s, %s) as jobid", (name, schedule, command)
        ).fetchone()["jobid"]
        out["jobs"].append({"name": name, "schedule": schedule, "jobid": jid})
    return out


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--base", default=s192.BASE)
    a = ap.parse_args(argv)
    env = s192.load_env()
    with s192.db(env) as conn:
        res = apply(conn, a.base, env["RPG_CRON_SECRET"])
        res["scheduled_rows"] = [
            dict(r)
            for r in conn.execute(
                "select jobname, schedule, active from cron.job where jobname like 'rpg-cron-%' order by jobname"
            ).fetchall()
        ]
    res.update({"at": s192.now_iso(), "base": a.base})
    s192.evidence("cron_schedule", res)
    print(
        json.dumps({k: v for k, v in res.items() if k in ("extensions", "vault", "scheduled_rows")})
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
