"""Restore local fechado: valida hashes e exige stack local explicitamente."""

from __future__ import annotations

import argparse
import re
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from services.local_backup import verify_manifest
from scripts.backup_local import (
    DB_CONTAINER, STORAGE_CONTAINER, _assert_local_container,
)


def _assert_empty_target() -> None:
    query = """
    select
      (select count(*) from app.games) +
      (select count(*) from app.memory_documents) +
      (select count(*) from app.assets) +
      (select count(*) from app.jobs) +
      (select count(*) from auth.users) +
      (select count(*) from storage.objects)
    """
    result = subprocess.run(
        ["docker", "exec", DB_CONTAINER, "psql", "-At", "-U", "postgres",
         "-d", "postgres", "-c", query],
        check=True, capture_output=True, text=True,
    )
    if int(result.stdout.strip()) != 0:
        raise RuntimeError("restore recusado: alvo local não está vazio")


def run(backup: Path) -> None:
    verify_manifest(backup)
    _assert_local_container(DB_CONTAINER)
    _assert_local_container(STORAGE_CONTAINER)
    _assert_empty_target()
    for dump_name, clean in (
        ("database_app.dump", True),
        ("database_platform_data.dump", False),
    ):
        command = ["docker", "exec", "-i", DB_CONTAINER, "pg_restore"]
        if clean:
            command += ["--clean", "--if-exists"]
        command += ["--no-owner", "-U", "postgres", "-d", "postgres"]
        result = subprocess.run(
            command, input=(backup / dump_name).read_bytes(),
            check=False, capture_output=True,
        )
        if result.returncode:
            detail = result.stderr.decode(errors="replace")
            detail = re.sub(r"[\w.+-]+@[\w.-]+", "[EMAIL]", detail)[:4000]
            errors = re.findall(r"ERROR:\s+([^\r\n]+)", detail)
            tolerated = {
                "permission denied for table buckets_vectors",
                "permission denied for table vector_indexes",
            }
            if dump_name != "database_platform_data.dump" or not errors or any(
                error not in tolerated for error in errors
            ):
                raise RuntimeError(f"restore falhou em {dump_name}: {detail}")
    subprocess.run(
        ["docker", "exec", STORAGE_CONTAINER, "sh", "-c", "find /mnt -mindepth 1 -delete"],
        check=True, capture_output=True,
    )
    subprocess.run(
        ["docker", "cp", str((backup / "objects").resolve()) + "/.",
         f"{STORAGE_CONTAINER}:/mnt"],
        check=True, capture_output=True,
    )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("backup", type=Path)
    parser.add_argument("--confirm-local-empty-target", action="store_true")
    args = parser.parse_args()
    if not args.confirm_local_empty_target:
        parser.error("restore exige --confirm-local-empty-target")
    run(args.backup.resolve())
    print("restore local concluído; execute verify_restore.py")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
