"""CLI preview-first for legacy JSON saves -> Postgres."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
from uuid import UUID

from infrastructure.contracts import Principal
from infrastructure.postgres import PostgresPool
from services.game_transfer import import_saves, scan_saves, write_report


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("command", choices=("scan", "dry-run", "import", "verify"))
    parser.add_argument("source", type=Path)
    parser.add_argument("--owner", required=True, type=UUID)
    parser.add_argument("--dsn", default=os.getenv("DATABASE_URL"))
    parser.add_argument("--journal", type=Path, default=Path("data/runtime/save-import.jsonl"))
    parser.add_argument("--report", type=Path)
    args = parser.parse_args()
    if args.command == "scan":
        rows = [row.__dict__ for row in scan_saves(args.source)]
    else:
        if not args.dsn:
            parser.error("--dsn ou DATABASE_URL obrigatório")
        pool = PostgresPool(args.dsn)
        try:
            rows = import_saves(
                pool, Principal(args.owner, "migration", str(args.owner), local=True),
                args.source, dry_run=args.command == "dry-run",
                journal_path=args.journal,
            )
            if args.command == "verify":
                bad = [row for row in rows if row["status"] not in {"already_present", "journal_skip"}]
                if bad:
                    print(json.dumps(rows, ensure_ascii=False, indent=2))
                    return 1
        finally:
            pool.close()
    if args.report:
        write_report(rows, args.report)
    print(json.dumps(rows, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
