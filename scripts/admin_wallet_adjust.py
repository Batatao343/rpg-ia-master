"""SPEC-195 audited wallet/debt adjustment. Operator CLI only (no HTTP endpoint exists).

Dry-run is the default; ``--apply`` plus a matching ``--confirm-owner`` is required to write.
Every adjustment needs --actor (UUID), --reason and --reference (replay key, audited).
"""

from __future__ import annotations

import argparse
import json
import os
from uuid import UUID

COMMANDS = ("credit", "debit", "forgive-debt")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=COMMANDS)
    parser.add_argument("--owner", type=UUID, required=True)
    parser.add_argument("--amount-milli", type=int, required=True)
    parser.add_argument("--actor", type=UUID, required=True, help="Operator identity (audit)")
    parser.add_argument("--reason", required=True)
    parser.add_argument(
        "--reference", required=True, help="Stable id (ticket/incident); replay key"
    )
    parser.add_argument("--apply", action="store_true", help="Write (default is dry-run)")
    parser.add_argument("--confirm-owner", type=UUID)
    return parser


def validate(args, parser) -> None:
    if not 0 < args.amount_milli < 2**62:
        parser.error("--amount-milli must be a positive integer")
    if not args.reason.strip() or args.reason != args.reason.strip() or len(args.reason) > 500:
        parser.error("--reason must be 1..500 chars without edge whitespace")
    if (
        not args.reference.strip()
        or len(args.reference) > 120
        or args.reference != args.reference.strip()
    ):
        parser.error("--reference must be 1..120 chars without edge whitespace")
    if any(c in args.reference for c in "%_*\\:"):
        parser.error("--reference must not contain %, _, *, : or backslash")
    if args.apply and args.confirm_owner != args.owner:
        parser.error("--apply requires matching --confirm-owner")
    if args.confirm_owner and not args.apply:
        parser.error("--confirm-owner requires --apply")


def run(args, runtime) -> dict:
    """Preview (always) and, with --apply, write through the audited primitives."""
    from infrastructure.contracts import Principal
    from infrastructure.wallet import PostgresWallet
    from infrastructure.wallet_debt import forgive_debt, forgive_replay, owner_debt

    pool = runtime.game_store.pool
    wallet = PostgresWallet(pool)
    principal = Principal(args.owner, "admin", str(args.owner))
    before = wallet.balance(principal)
    with pool.connection() as db:
        debt_before = owner_debt(db, args.owner)
    out = {
        "mode": "apply" if args.apply else "dry-run",
        "command": args.command,
        "owner": str(args.owner),
        "amount_milli": args.amount_milli,
        "actor": str(args.actor),
        "reference": args.reference,
        "available_before": before.available_milli,
        "debt_before": debt_before,
    }
    if not args.apply:
        return out
    if args.command in ("credit", "debit"):
        signed = args.amount_milli if args.command == "credit" else -args.amount_milli
        # credit + debt settlement commit atomically (a crash cannot leave credit unsettled)
        with pool.connection() as db, db.transaction():
            from infrastructure.wallet_debt import settle_owner_debt

            after = wallet.adjust_admin(
                principal,
                adjustment_id=args.reference,
                signed_milli=signed,
                actor_id=args.actor,
                reason=args.reason,
                connection=db,
            )
            settled = settle_owner_debt(db, args.owner) if signed > 0 else 0
        out.update(available_after=after.available_milli - settled, debt_settled=settled)
    else:
        with pool.connection() as db, db.transaction():
            PostgresWallet._locked_account(db, args.owner)
            prior = forgive_replay(db, args.owner, args.reference)
            out["forgiven"] = forgive_debt(
                db,
                args.owner,
                args.amount_milli,
                reference=args.reference,
                actor_id=args.actor,
                reason=args.reason,
            )
            if prior:
                out["replay"] = True
                out["replay_divergent"] = (
                    prior["reason"] != args.reason or prior["total_milli"] != args.amount_milli
                )
    return out


def main(argv=None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    validate(args, parser)
    from infrastructure.runtime import RuntimeConfig, build_runtime

    config = RuntimeConfig.from_env()
    if config.profile != "hosted-supabase" and os.getenv("RPG_ADMIN_ALLOW_PROFILE") != "1":
        parser.error("wallet adjustment requires the hosted-supabase runtime profile")
    print(json.dumps(run(args, build_runtime(config)), sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
