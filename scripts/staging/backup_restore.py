"""Portable export / disposable restore / verify for the staging project.

export : pg_dump (app schema + auth/storage data) over RPG_STAGING_DB_URL (session or direct DSN,
         NOT the transaction pooler) + Storage objects of bucket rpg-dynamic with sha256 manifest.
restore: only into a DISPOSABLE local database (--confirm-disposable, host localhost/127.0.0.1).
verify : compare table row counts and object checksums against the export manifest.
pg_dump comes from PATH, else `docker run --rm postgres:17`.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import subprocess
from pathlib import Path
from typing import Any, Mapping
from urllib.parse import urlparse

import httpx

from scripts.staging import common
from services.local_backup import sha256_file, verify_manifest, write_manifest

BUCKET = "rpg-dynamic"
LOCAL_HOSTS = {"localhost", "127.0.0.1", "::1"}
EXCLUDES = ["auth.schema_migrations", "auth.audit_log_entries", "storage.migrations",
            "storage.buckets", "storage.buckets_vectors", "storage.vector_indexes"]


def assert_disposable(dsn: str, confirmed: bool) -> None:
    if not confirmed:
        raise common.GuardError("restore exige --confirm-disposable")
    if (urlparse(dsn).hostname or "") not in LOCAL_HOSTS:
        raise common.GuardError("restore so e permitido em host localhost/127.0.0.1")


def _run(cmd: list[str], env: Mapping[str, str] | None = None) -> subprocess.CompletedProcess:
    """subprocess.run that surfaces (redacted) stderr instead of a bare CalledProcessError."""
    r = subprocess.run(cmd, env=env, capture_output=True)
    if r.returncode:
        raise common.GuardError(f"comando falhou ({r.returncode}): "
                                + common.redact_text(r.stderr.decode(errors='replace'))[-600:])
    return r


def _dump_command(dsn: str, args: list[str], have_pg_dump: bool) -> tuple[list[str], dict[str, str]]:
    """Build the pg_dump command. The password is NEVER on argv: it goes through PGPASSWORD (env)."""
    clean, password = common.split_dsn_password(dsn)
    env = {**os.environ}
    if password is not None:
        env["PGPASSWORD"] = password
    if have_pg_dump:
        return ["pg_dump", "-Fc", *args, "--dbname", clean], env
    env["PGDSN"] = clean
    cmd = ["docker", "run", "--rm", "-e", "PGDSN", "-e", "PGPASSWORD", "postgres:17", "sh", "-c",
           'pg_dump "$PGDSN" -Fc ' + " ".join(args)]
    return cmd, env


def _dump(dest: Path, dsn: str, args: list[str]) -> None:
    cmd, env = _dump_command(dsn, args, bool(shutil.which("pg_dump")))
    dest.write_bytes(_run(cmd, env).stdout)


def list_objects(client: httpx.Client, base: str, headers: Mapping[str, str], prefix: str = "") -> list[str]:
    """Recursive listing through POST /storage/v1/object/list/<bucket> (folders have id == null)."""
    found, offset = [], 0
    while True:
        r = client.post(f"{base}/storage/v1/object/list/{BUCKET}", headers=headers,
                        json={"prefix": prefix, "limit": 100, "offset": offset})
        r.raise_for_status()
        rows = r.json()
        for row in rows:
            name = f"{prefix}{row['name']}"
            if row.get("id") is None:
                found += list_objects(client, base, headers, name + "/")
            else:
                found.append(name)
        if len(rows) < 100:
            return found
        offset += 100


def download_objects(client: httpx.Client, base: str, headers: Mapping[str, str], dest: Path) -> list[str]:
    names = list_objects(client, base, headers)
    for name in names:
        r = client.get(f"{base}/storage/v1/object/{BUCKET}/{name}", headers=headers)
        r.raise_for_status()
        target = dest / "objects" / BUCKET / name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(r.content)
    return names


def app_tables(conn: Any) -> list[str]:
    rows = conn.execute("select table_schema||'.'||table_name from information_schema.tables "
                        "where table_schema='app' and table_type='BASE TABLE' order by 1").fetchall()
    return [r[0] for r in rows]


def count_rows(conn: Any, tables: list[str] | None = None) -> dict[str, int | None]:
    counts: dict[str, int | None] = {}
    tables = app_tables(conn) if tables is None else tables
    for table in tables:
        try:
            counts[table] = conn.execute(f"select count(*) from {table}").fetchone()[0]  # noqa: S608 - constants
        except Exception:  # noqa: BLE001
            counts[table] = None
            try:
                conn.rollback()
            except Exception:  # noqa: BLE001
                pass
    return counts


def compare_state(expected: Mapping[str, Any], actual_counts: Mapping[str, Any], actual_objects: Mapping[str, str]) -> dict:
    """Pure: expected = {'row_counts': {...}, 'objects': {path: sha256}}."""
    row_mismatch = {t: {"expected": n, "actual": actual_counts.get(t)}
                    for t, n in expected.get("row_counts", {}).items() if n != actual_counts.get(t)}
    exp_obj = expected.get("objects", {})
    missing = sorted(set(exp_obj) - set(actual_objects))
    extra = sorted(set(actual_objects) - set(exp_obj))
    bad_hash = sorted(p for p in set(exp_obj) & set(actual_objects) if exp_obj[p] != actual_objects[p])
    return {"ok": not (row_mismatch or missing or extra or bad_hash), "row_mismatch": row_mismatch,
            "objects_missing": missing, "objects_extra": extra, "objects_hash_mismatch": bad_hash}


def object_hashes(root: Path) -> dict[str, str]:
    base = root / "objects" / BUCKET
    return {p.relative_to(base).as_posix(): sha256_file(p) for p in sorted(base.rglob("*")) if p.is_file()} if base.exists() else {}


def export(dest: Path, env: Mapping[str, str], client: httpx.Client | None = None) -> dict:
    import psycopg
    dsn = common.env_required("RPG_STAGING_DB_URL", env)
    url = common.env_required("SUPABASE_URL", env).rstrip("/")
    key = common.env_required("SUPABASE_SERVICE_ROLE_KEY", env)
    if dest.exists() and any(dest.iterdir()):
        raise common.GuardError("destino do export precisa estar vazio")
    dest.mkdir(parents=True, exist_ok=True)
    _dump(dest / "database_app.dump", dsn, ["--schema", "app"])
    _dump(dest / "database_platform_data.dump", dsn,
          ["-a", "--schema", "auth", "--schema", "storage", *[x for t in EXCLUDES for x in ("--exclude-table-data", t)]])
    http = client or httpx.Client(timeout=60)
    names = download_objects(http, url, {"apikey": key, "Authorization": f"Bearer {key}"}, dest)
    with psycopg.connect(dsn, autocommit=True) as conn:
        counts = count_rows(conn)
    (dest / "state.json").write_text(json.dumps({"row_counts": counts, "objects": object_hashes(dest)}, indent=2),
                                     encoding="utf-8")
    manifest = write_manifest(dest)
    return {"files": len(manifest["files"]), "objects": len(names), "row_counts": counts}


def _storage_headers(env: Mapping[str, str]) -> tuple[str, dict[str, str]]:
    url = common.env_required("LOCAL_SUPABASE_URL", env).rstrip("/")
    key = common.env_required("LOCAL_SERVICE_ROLE_KEY", env)
    return url, {"apikey": key, "Authorization": f"Bearer {key}"}


def restore(src: Path, target_dsn: str, objects_dir: Path, confirmed: bool,
            env: Mapping[str, str] | None = None, client: httpx.Client | None = None) -> dict:
    """Data-only restore on top of a DB already built from supabase/migrations (proves migrations-from-zero
    + data), then bytes re-uploaded through the local Storage API (metadata rows from the dump are dropped first)."""
    assert_disposable(target_dsn, confirmed)
    assert_disposable(common.env_required("LOCAL_SUPABASE_URL", env or os.environ), True)
    verify_manifest(src)
    import psycopg
    with psycopg.connect(target_dsn, autocommit=True) as conn:  # rows seeded by migrations would collide
        conn.execute("delete from app.embedding_profiles")
    clean_dsn, password = common.split_dsn_password(target_dsn)
    renv = {**os.environ, **({"PGPASSWORD": password} if password is not None else {})}
    for dump in ("database_platform_data.dump", "database_app.dump"):
        flags = ["--no-owner", "--data-only", "--disable-triggers", "--dbname", clean_dsn]
        if shutil.which("pg_restore"):
            cmd = ["pg_restore", *flags, str(src / dump)]
        else:
            cmd = ["docker", "run", "--rm", "--network", "host", "-e", "PGPASSWORD", "-v",
                   f"{src.resolve()}:/b:ro", "postgres:17", "pg_restore", *flags, f"/b/{dump}"]
        _run(cmd, renv)
    # restored storage.objects rows point at file versions that do not exist in the fresh backend; drop the
    # metadata and let the Storage API recreate row + bytes.
    with psycopg.connect(target_dsn, autocommit=True) as conn:
        conn.execute("set storage.allow_delete_query = 'true'")
        conn.execute("delete from storage.objects where bucket_id = %s", (BUCKET,))
    uploaded = 0
    if (src / "objects" / BUCKET).exists():
        url, h = _storage_headers(env or os.environ)
        http = client or httpx.Client(timeout=30)
        for name, _sha in object_hashes(src).items():
            f = src / "objects" / BUCKET / name
            r = http.post(f"{url}/storage/v1/object/{BUCKET}/{name}", content=f.read_bytes(),
                          headers={**h, "Content-Type": "image/webp"})
            r.raise_for_status()
            uploaded += 1
    return {"restored": True, "objects_uploaded": uploaded}


def verify(src: Path, target_dsn: str, objects_dir: Path, env: Mapping[str, str] | None = None,
           client: httpx.Client | None = None) -> dict:
    """Row counts from the target DB; object checksums computed from bytes DOWNLOADED from the local Storage."""
    import psycopg
    assert_disposable(target_dsn, True)
    expected = json.loads((src / "state.json").read_text(encoding="utf-8"))
    with psycopg.connect(target_dsn, autocommit=True) as conn:
        counts = count_rows(conn, list(expected["row_counts"]))
    url, h = _storage_headers(env or os.environ)
    http = client or httpx.Client(timeout=30)
    actual: dict[str, str] = {}
    for name in list_objects(http, url, h):
        r = http.get(f"{url}/storage/v1/object/{BUCKET}/{name}", headers=h)
        r.raise_for_status()
        actual[name] = hashlib.sha256(r.content).hexdigest()
    return compare_state(expected, counts, actual)


def main(argv: list[str] | None = None) -> int:
    common.load_dotenv_quietly()
    p = argparse.ArgumentParser(description="Staging backup/restore (export, restore, verify)")
    sub = p.add_subparsers(dest="mode", required=True)
    e = sub.add_parser("export")
    common.add_guard_args(e)
    e.add_argument("dest", type=Path)
    for name in ("restore", "verify"):
        s = sub.add_parser(name)
        s.add_argument("src", type=Path)
        s.add_argument("--target-dsn", required=True)
        s.add_argument("--objects-dir", type=Path, default=Path("."), help="(legado, ignorado)")
        s.add_argument("--confirm-disposable", action="store_true")
    for s in sub.choices.values():
        s.add_argument("--out")
    a = p.parse_args(argv)
    if a.mode == "export":
        ref = common.require_staging(a.confirm_staging)
        common.assert_ref_in(ref, SUPABASE_URL=common.env_required("SUPABASE_URL"),
                             RPG_STAGING_DB_URL=common.env_required("RPG_STAGING_DB_URL"))
        result = {"project_ref": ref, **export(a.dest.resolve(), os.environ)}
    elif a.mode == "restore":
        result = restore(a.src, a.target_dsn, a.objects_dir, a.confirm_disposable, os.environ)
    else:
        result = verify(a.src, a.target_dsn, a.objects_dir, os.environ)
    print(common.write_evidence(f"backup_{a.mode}", result, a.out))
    return 0 if result.get("ok", True) else 1


if __name__ == "__main__":
    raise SystemExit(main())
