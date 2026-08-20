"""Backup local: Postgres custom dump + Storage + migrations, com manifesto."""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from services.local_backup import copy_sources, write_manifest


DB_CONTAINER = "supabase_db_rpg-ia-master-local"
STORAGE_CONTAINER = "supabase_storage_rpg-ia-master-local"
LOCAL_PROJECT = "rpg-ia-master-local"


def _assert_local_container(container: str) -> None:
    project = subprocess.run(
        ["docker", "inspect", container, "--format",
         '{{ index .Config.Labels "com.supabase.cli.project" }}'],
        check=True, capture_output=True, text=True,
    ).stdout.strip()
    if project != LOCAL_PROJECT:
        raise RuntimeError(f"container fora do laboratório local: {container}")


def run(destination: Path) -> dict:
    _assert_local_container(DB_CONTAINER)
    _assert_local_container(STORAGE_CONTAINER)
    copy_sources(destination, [
        (Path("supabase/migrations"), "config/migrations"),
        (Path("data/dynamic_art_profiles.json"), "config/dynamic_art_profiles.json"),
    ])
    app_dump = subprocess.run(
        ["docker", "exec", DB_CONTAINER, "pg_dump", "-Fc", "-U", "postgres",
         "--schema", "app", "postgres"],
        check=True, capture_output=True,
    ).stdout
    platform_dump = subprocess.run(
        ["docker", "exec", DB_CONTAINER, "pg_dump", "-Fc", "-a", "-U", "postgres",
         "--schema", "auth", "--schema", "storage",
         "--exclude-table-data", "auth.schema_migrations",
         "--exclude-table-data", "auth.audit_log_entries",
         "--exclude-table-data", "storage.migrations",
         "--exclude-table-data", "storage.buckets",
         "--exclude-table-data", "storage.buckets_vectors",
         "--exclude-table-data", "storage.vector_indexes",
         "postgres"],
        check=True, capture_output=True,
    ).stdout
    (destination / "database_app.dump").write_bytes(app_dump)
    (destination / "database_platform_data.dump").write_bytes(platform_dump)
    objects = destination / "objects"
    objects.mkdir()
    subprocess.run(
        ["docker", "cp", f"{STORAGE_CONTAINER}:/mnt/.", str(objects)], check=True,
        capture_output=True,
    )
    return write_manifest(destination)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("destination", type=Path)
    parser.add_argument("--confirm-local", action="store_true")
    args = parser.parse_args()
    if not args.confirm_local:
        parser.error("backup exige --confirm-local")
    manifest = run(args.destination.resolve())
    print(f"backup completo: {len(manifest['files'])} arquivos")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
