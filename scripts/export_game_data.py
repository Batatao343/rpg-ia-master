"""Export one owner-scoped Postgres game as a portable JSON bundle."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
from uuid import UUID

from infrastructure.contracts import Principal
from infrastructure.postgres import PostgresPool
from services.game_transfer import export_game, verify_export


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("game_id", type=UUID)
    parser.add_argument("--owner", required=True, type=UUID)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--dsn", default=os.getenv("DATABASE_URL"))
    args = parser.parse_args()
    if not args.dsn:
        parser.error("--dsn ou DATABASE_URL obrigatório")
    pool = PostgresPool(args.dsn)
    try:
        bundle = export_game(
            pool, Principal(args.owner, "export", str(args.owner), local=True), args.game_id,
        )
    finally:
        pool.close()
    errors = verify_export(bundle)
    if errors:
        raise RuntimeError(f"export inválido: {errors}")
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(bundle, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    print(json.dumps({"output": str(args.output), "state_sha256": bundle["state_sha256"]}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
