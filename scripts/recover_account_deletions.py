"""Preview or resume an already requested Supabase account deletion.

This is an operator recovery tool, never an account-delete initiation path.
"""

from __future__ import annotations

import argparse
import json
import os
from uuid import UUID

from infrastructure.account_lifecycle import PostgresAccountLifecycle
from infrastructure.runtime import RuntimeConfig, build_runtime


def claim_pending(pool, limit: int) -> list[dict]:
    """Rotate failed tombstones so one unavailable owner cannot starve others (2 min re-claim cooldown)."""
    with pool.connection() as db, db.transaction():
        return db.execute(
            """with due as (
            select owner_id from app.account_deletions where status='deleting'
            and (recovery_attempted_at is null
                 or recovery_attempted_at < now() - interval '2 minutes')
            order by coalesce(recovery_attempted_at,requested_at),requested_at,owner_id
            limit %s for update skip locked
        ) update app.account_deletions d set recovery_attempted_at=clock_timestamp()
          from due where d.owner_id=due.owner_id
          returning d.owner_id,d.status,d.requested_at,d.completed_at""",
            (limit,),
        ).fetchall()


def run_recovery_batch(runtime, max_items: int, *, rows: list[dict] | None = None) -> dict:
    """Bounded sweep shared by the CLI and the cron endpoint.

    Concurrency-safe: ``claim_pending`` uses FOR UPDATE SKIP LOCKED while claiming and stamps
    ``recovery_attempted_at``; an owner stamped within the last 2 minutes is not re-claimed, so a
    sweep that starts while another is still finishing never repeats the same owner.
    """
    pool = runtime.game_store.pool
    if rows is None:
        rows = claim_pending(pool, max_items)
    lifecycle = PostgresAccountLifecycle(pool, runtime.identity_verifier, runtime.blob_store)
    with pool.connection() as db, db.transaction():
        purged = db.execute("""delete from app.rate_limit_buckets
            where bucket_key like 'auth:%' and updated_at < now() - interval '24 hours'""").rowcount
    results = []
    for row in rows:
        try:
            status = lifecycle.finish(row["owner_id"])
        except Exception as exc:
            from observability.telemetry import log_event, pseudonym

            log_event(
                "cron",
                "item_failed",
                level="warning",
                task="account_deletions",
                item_kind="account_deletion",
                item_ref=pseudonym(row["owner_id"]),
                error_type=type(exc).__name__,
            )
            results.append(
                {
                    "owner_id": str(row["owner_id"]),
                    "status": "deleting",
                    "error_type": type(exc).__name__,
                }
            )
            continue
        results.append({"owner_id": str(row["owner_id"]), "status": status})
    return {"count": len(results), "auth_buckets_purged": purged, "results": results}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--owner", type=UUID, help="Show one deletion request")
    parser.add_argument("--apply", action="store_true", help="Resume cleanup for --owner")
    parser.add_argument("--confirm-owner", type=UUID, help="Repeat owner UUID to authorize apply")
    parser.add_argument(
        "--batch", action="store_true", help="Scheduled bounded sweep of pending tombstones"
    )
    parser.add_argument("--max", type=int, default=10, help="Maximum owners per scheduled sweep")
    args = parser.parse_args()
    if args.batch and (
        args.owner
        or args.confirm_owner
        or not args.apply
        or not 1 <= args.max <= 100
        or os.getenv("RPG_ACCOUNT_RECOVERY_BATCH") != "1"
    ):
        parser.error("--batch requires --apply, RPG_ACCOUNT_RECOVERY_BATCH=1 and --max 1..100")
    if args.apply and not args.batch and (args.owner is None or args.confirm_owner != args.owner):
        parser.error("--apply requires --owner and matching --confirm-owner")
    if args.confirm_owner and not args.apply:
        parser.error("--confirm-owner requires --apply")
    config = RuntimeConfig.from_env()
    if config.profile != "hosted-supabase":
        parser.error("account recovery requires hosted-supabase runtime")
    runtime = build_runtime(config)
    try:
        if args.batch:
            rows = claim_pending(runtime.game_store.pool, args.max)
        else:
            with runtime.game_store.pool.connection() as db:
                if args.owner:
                    rows = db.execute(
                        """select owner_id,status,requested_at,completed_at
                        from app.account_deletions where owner_id=%s""",
                        (args.owner,),
                    ).fetchall()
                else:
                    rows = db.execute("""select owner_id,status,requested_at,completed_at
                        from app.account_deletions where status='deleting'
                        order by requested_at limit 100""").fetchall()
        if args.batch:
            payload = run_recovery_batch(runtime, args.max, rows=rows)
            print(json.dumps({"mode": "batch", **payload}, sort_keys=True))
            results = payload["results"]
            return 0 if all(item["status"] == "deleted" for item in results) else 2
        if args.apply:
            if not rows:
                parser.error("no existing deletion request for owner")
            lifecycle = PostgresAccountLifecycle(
                runtime.game_store.pool, runtime.identity_verifier, runtime.blob_store
            )
            status = lifecycle.finish(args.owner)
            print(json.dumps({"owner_id": str(args.owner), "status": status}, sort_keys=True))
            return 0 if status == "deleted" else 2
        print(json.dumps({"mode": "preview", "deletions": rows}, default=str, ensure_ascii=False))
        return 0
    finally:
        for resource in runtime.resources:
            resource.close()


if __name__ == "__main__":
    raise SystemExit(main())
