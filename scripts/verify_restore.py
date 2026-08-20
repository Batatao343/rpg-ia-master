"""Verifica constraints/hashes essenciais depois do restore."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from infrastructure.postgres import PostgresPool


def run(dsn: str) -> dict[str, int]:
    pool = PostgresPool(dsn)
    try:
        with pool.connection() as connection:
            counts = {}
            for table in ("games", "game_checkpoints", "memory_documents", "assets", "jobs"):
                counts[table] = int(connection.execute(
                    f"select count(*) as n from app.{table}",  # tabela é allowlist fixa
                ).fetchone()["n"])
            invalid = connection.execute(
                "select count(*) as n from app.games where length(state_sha256)<>64",
            ).fetchone()["n"]
            if invalid:
                raise RuntimeError("hash de game inválido")
            return counts
    finally:
        pool.close()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dsn", default="postgresql://postgres:postgres@127.0.0.1:55322/postgres")
    args = parser.parse_args()
    print(run(args.dsn))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
