"""SPEC-236 R5: audited reconciliation of an UNCERTAIN wallet hold. Operator CLI only.

Use it only after verifying with the provider (dashboard/invoice/support case) that the
attempts left ``unknown`` (timeout, cancellation, 5xx) were NOT charged. Exact usage already
persisted for the same operation is settled (debited) — never waived; the rest is released.

Dry-run is the default; ``--apply`` plus a matching ``--confirm-owner`` is required to write.
``--actor`` (UUID) and ``--evidence`` (provider proof reference, the replay key) are audited
in the reservation receipt (``provider_no_charge:<actor>:<evidence>``).
"""
from __future__ import annotations

import argparse
import json
import os
from uuid import UUID


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--owner", type=UUID, required=True)
    parser.add_argument("--reservation", type=UUID, required=True)
    parser.add_argument("--actor", type=UUID, required=True, help="Operator identity (audit)")
    parser.add_argument("--evidence", required=True,
                        help="Provider no-charge proof reference (ticket/invoice id); replay key")
    parser.add_argument("--apply", action="store_true", help="Write (default is dry-run)")
    parser.add_argument("--confirm-owner", type=UUID)
    return parser


def validate(args, parser) -> None:
    evidence = args.evidence
    if not evidence.strip() or evidence != evidence.strip() or len(evidence) > 100:
        parser.error("--evidence must be 1..100 chars without edge whitespace")
    if args.apply and args.confirm_owner != args.owner:
        parser.error("--apply requires matching --confirm-owner")
    if args.confirm_owner and not args.apply:
        parser.error("--confirm-owner requires --apply")


def run(args, runtime) -> dict:
    """Preview (always) and, with --apply, reconcile through the wallet primitive."""
    from infrastructure.contracts import Principal
    from infrastructure.wallet import PostgresWallet
    pool = runtime.game_store.pool
    wallet = PostgresWallet(pool)
    principal = Principal(args.owner, "admin", str(args.owner))
    with pool.connection() as db:
        row = db.execute(
            """select r.status,r.ceiling_milli,r.fence_token,r.usage_operation_id,
                 (select count(*) from app.wallet_attempt_tickets t
                   where t.reservation_id=r.reservation_id) as tickets,
                 (select count(*) from app.usage_events u where u.operation_id=r.usage_operation_id
                   and u.owner_id=r.owner_id and u.billing_exact) as exact_events,
                 (select count(*) from app.usage_events u where u.operation_id=r.usage_operation_id
                   and u.owner_id=r.owner_id and not u.billing_exact) as unknown_events
               from app.wallet_reservations r where r.reservation_id=%s and r.owner_id=%s""",
            (args.reservation, args.owner)).fetchone()
    if row is None:
        raise SystemExit("reservation not found for owner")
    out = {"mode": "apply" if args.apply else "dry-run", "owner": str(args.owner),
           "reservation": str(args.reservation), "actor": str(args.actor),
           "evidence": args.evidence, "status_before": row["status"],
           "ceiling_milli": int(row["ceiling_milli"]), "tickets": int(row["tickets"]),
           "exact_events": int(row["exact_events"]), "unknown_events": int(row["unknown_events"])}
    if not args.apply:
        return out
    if row["status"] != "uncertain":
        # effect_started may still belong to a live worker: let the recovery sweep fence it first.
        raise SystemExit(f"reservation is {row['status']}; only 'uncertain' holds are reconciled")
    done = wallet.reconcile_proven_no_charge(
        principal, args.reservation, fence_token=row["fence_token"], actor_id=args.actor,
        evidence_reference=args.evidence)
    out.update(status_after=done.status, settled_milli=done.settled_milli,
               released_milli=done.released_milli)
    return out


def main(argv=None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    validate(args, parser)
    from infrastructure.runtime import RuntimeConfig, build_runtime
    config = RuntimeConfig.from_env()
    if config.profile != "hosted-supabase" and os.getenv("RPG_ADMIN_ALLOW_PROFILE") != "1":
        parser.error("wallet reconciliation requires the hosted-supabase runtime profile")
    print(json.dumps(run(args, build_runtime(config)), sort_keys=True, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
