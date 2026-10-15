"""Migration history tooling for the staging project (psycopg, no Supabase CLI needed).

DSN: RPG_STAGING_DB_URL (direct or session pooler). Local files:
supabase/migrations/<version>_<name>.sql. History table: supabase_migrations.schema_migrations
(version text pk, statements text[], name text), same shape the Supabase CLI writes.
Note: the whole file is stored as a single element of `statements` (CLI splits per statement).
"""

from __future__ import annotations

import argparse
import os
import re
from pathlib import Path
from typing import Any

from scripts.staging import common

MIGRATIONS_DIR = common.ROOT / "supabase" / "migrations"
_FILE = re.compile(r"^(\d{14})_(.+)\.sql$")


def local_migrations(directory: Path = MIGRATIONS_DIR) -> list[dict]:
    rows = []
    for path in sorted(directory.glob("*.sql")):
        m = _FILE.match(path.name)
        if m:
            rows.append({"version": m.group(1), "name": m.group(2), "path": path})
    return rows


def plan_repair(local: list[dict], remote: list[dict]) -> dict:
    """Remote rows applied with server timestamps but same names -> local filename version."""
    local_by_name = {r["name"]: r["version"] for r in local}
    local_versions = set(local_by_name.values())
    renames, orphans = [], []
    for row in sorted(remote, key=lambda r: r["version"]):
        want = local_by_name.get(row["name"])
        if want is None:
            orphans.append(row["version"])
        elif want != row["version"]:
            if want in {r["version"] for r in remote}:
                orphans.append(row["version"])  # collision: refuse to touch
            else:
                renames.append({"name": row["name"], "from": row["version"], "to": want})
    pending = [r["version"] for r in local
               if r["version"] not in {x["version"] for x in remote}
               and r["name"] not in {x["name"] for x in remote}]
    return {"renames": renames, "remote_only": orphans, "pending": pending,
            "local_versions": sorted(local_versions)}


def plan_status(local: list[dict], remote: list[dict]) -> dict:
    p = plan_repair(local, remote)
    applied = {r["version"] for r in remote}
    return {
        "local_count": len(local), "remote_count": len(remote),
        "in_sync": not p["renames"] and not p["pending"] and not p["remote_only"],
        "version_mismatch": p["renames"], "pending": p["pending"], "remote_only": p["remote_only"],
        "applied_matching": sorted(v for v in applied if v in p["local_versions"]),
    }


def fetch_remote(cur: Any) -> list[dict]:
    # psycopg Connection.execute and Cursor.execute both return a cursor.
    rows = cur.execute("select version, name from supabase_migrations.schema_migrations order by version").fetchall()
    return [{"version": v, "name": n} for v, n in rows]


def ensure_history(cur: Any) -> None:
    cur.execute("create schema if not exists supabase_migrations")
    cur.execute("create table if not exists supabase_migrations.schema_migrations "
                "(version text primary key, statements text[], name text)")


def apply_repair(cur: Any, renames: list[dict]) -> int:
    for r in renames:
        cur.execute("update supabase_migrations.schema_migrations set version=%s where version=%s and name=%s",
                    (r["to"], r["from"], r["name"]))
    return len(renames)


def apply_push(conn: Any, local: list[dict], pending: list[str]) -> list[str]:
    done = []
    for row in local:
        if row["version"] not in pending:
            continue
        sql = row["path"].read_text(encoding="utf-8")
        with conn.transaction():
            conn.execute(sql)
            conn.execute("insert into supabase_migrations.schema_migrations (version, statements, name) "
                         "values (%s, %s, %s)", (row["version"], [sql], row["name"]))
        done.append(row["version"])
    return done


def run(mode: str, dsn: str, apply: bool = False, directory: Path = MIGRATIONS_DIR) -> dict:
    import psycopg
    local = local_migrations(directory)
    with psycopg.connect(dsn, autocommit=True) as conn:
        if mode == "push":
            conn.execute("create schema if not exists supabase_migrations")
            ensure_history(conn)
        try:
            remote = fetch_remote(conn)
        except psycopg.errors.UndefinedTable:
            remote = []
        result: dict[str, Any] = {"mode": mode, "applied": False, "status": plan_status(local, remote)}
        plan = plan_repair(local, remote)
        if mode == "repair":
            result["plan"] = plan["renames"]
            if apply and plan["renames"]:
                with conn.transaction():
                    result["repaired"] = apply_repair(conn, plan["renames"])
                result["applied"] = True
                result["status_after"] = plan_status(local, fetch_remote(conn))
        elif mode == "push":
            if plan["renames"]:
                raise common.GuardError("versoes divergentes: rode `repair --apply` antes de `push`")
            result["plan"] = plan["pending"]
            if apply and plan["pending"]:
                result["pushed"] = apply_push(conn, local, plan["pending"])
                result["applied"] = True
                result["status_after"] = plan_status(local, fetch_remote(conn))
    return result


def main(argv: list[str] | None = None) -> int:
    common.load_dotenv_quietly()
    p = argparse.ArgumentParser(description="Staging migration history tools")
    p.add_argument("mode", choices=["status", "repair", "push"])
    common.add_guard_args(p)
    p.add_argument("--apply", action="store_true", help="execute (default: print plan only)")
    p.add_argument("--out")
    a = p.parse_args(argv)
    common.require_staging(a.confirm_staging)
    dsn = common.env_required("RPG_STAGING_DB_URL")
    if common.require_staging(a.confirm_staging) not in dsn:
        raise common.GuardError("RPG_STAGING_DB_URL nao contem o ref de staging")
    result = run(a.mode, dsn, apply=a.apply)
    print(common.write_evidence(f"migrations_{a.mode}", result, a.out))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
