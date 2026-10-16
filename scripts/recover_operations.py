"""Preview-first recovery for expired durable operations."""

from __future__ import annotations

import argparse
import json
import os
from uuid import UUID

from infrastructure.postgres import PostgresPool
from services.dsn_cli import add_dsn_arguments, resolve_dsn
from services.operation_recovery import abandon_expired, orphan_operations


def main() -> int:
    parser = argparse.ArgumentParser()
    add_dsn_arguments(parser)
    parser.add_argument("--owner", type=UUID)
    parser.add_argument("--abandon", type=UUID)
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()
    pool = PostgresPool(resolve_dsn(parser, args))
    try:
        before = orphan_operations(pool, owner_id=args.owner)
        if args.abandon and args.apply:
            changed = abandon_expired(pool, args.abandon)
        else:
            changed = False
        print(json.dumps({
            "mode": "apply" if args.apply else "preview",
            "orphan_count": len(before),
            "operations": before,
            "changed": changed,
        }, ensure_ascii=False, indent=2, default=str))
    finally:
        pool.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
