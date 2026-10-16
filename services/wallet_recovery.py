"""SPEC-236 R4: bounded sweep that gives every orphan wallet reservation an automatic exit.

``PostgresWallet.recover`` used to run only inside the STT request that created the hold; a
process dying between ``reserve`` and ``finish`` (or a dead image job) left Estilhas held
forever. This sweep (cron ``/internal/cron/operations``) resolves, per reservation:

* ``reserved`` (no provider ticket) whose operation is no longer live -> released
  (``recovery_pre_dispatch``), the money goes back to the player;
* ``effect_started`` whose persisted usage is exact and matches the tickets 1:1 -> settled;
* anything else with a ticket -> ``uncertain`` (held for ``scripts/admin_wallet_reconcile.py``;
  FinOps raises ``wallet_uncertain_hold``). Real uncertainty is never refunded automatically.

Image reservations belong to their ``generate_dynamic_art`` job: only a dead/cancelled job
(e.g. lease expired at max attempts) hands its reservation to this sweep.
A grace period keeps the sweep away from requests that are still finishing normally.
"""
from __future__ import annotations

import os
from datetime import datetime, timedelta, timezone
from typing import Any
from uuid import UUID, uuid4

from infrastructure.contracts import Principal

DEFAULT_GRACE_SECONDS = 900


def grace_seconds() -> int:
    try:
        value = int(os.getenv("RPG_WALLET_RECOVERY_GRACE_SECONDS", str(DEFAULT_GRACE_SECONDS)))
    except ValueError:
        value = DEFAULT_GRACE_SECONDS
    return max(60, value)


def _candidates(pool, max_items: int, owner_id: UUID | None, grace: int) -> list[dict[str, Any]]:
    params: list[Any] = [timedelta(seconds=grace)]
    owner_clause = ""
    if owner_id is not None:
        owner_clause = " and r.owner_id=%s"
        params.append(owner_id)
    params.append(max_items)
    with pool.connection() as connection:
        rows = connection.execute(
            f"""select r.reservation_id,r.owner_id,r.reference_type,r.status,r.fence_token,
                       r.usage_operation_id,o.status as op_status,o.lease_until
                from app.wallet_reservations r
                left join app.operations o on o.id=r.usage_operation_id
                where r.status in ('reserved','effect_started')
                  and r.created_at < now() - %s{owner_clause}
                order by r.created_at limit %s""",
            params,
        ).fetchall()
    return [dict(row) for row in rows]


def _resolve_image(pool, wallet, principal: Principal, row: dict) -> str:
    with pool.connection() as connection, connection.transaction():
        art = connection.execute(
            """select g.generation_id,g.status,j.status as job_status
               from app.art_generations g
               left join app.jobs j on j.kind='generate_dynamic_art'
                 and j.dedupe_key='art:'||g.generation_id::text
               where g.wallet_reservation_id=%s""",
            (row["reservation_id"],),
        ).fetchone()
        if art is None or art["job_status"] not in ("dead", "cancelled"):
            return "skipped"  # a live job (queued/retry/running) owns this reservation
        current = wallet._locked_reservation(connection, principal, row["reservation_id"])
        if current["status"] == "reserved":
            wallet.release_pre_effect(principal, row["reservation_id"],
                                      fence_token=current["fence_token"], connection=connection)
            outcome, code = "released", "job_dead_pre_dispatch"
        elif current["status"] == "effect_started":
            wallet.mark_uncertain(principal, row["reservation_id"],
                                  reason="image_job_dead_after_dispatch", connection=connection)
            outcome, code = "uncertain", "external_result_uncertain"
        else:
            return "skipped"
        connection.execute(
            """update app.art_generations set status='failed',error_code=%s,updated_at=now()
               where generation_id=%s and status in ('pending','generating')""",
            (code, art["generation_id"]),
        )
        return outcome


def _resolve_operation(pool, wallet, principal: Principal, row: dict) -> str:
    from infrastructure.wallet import UncertainEffect
    if row["status"] == "reserved":
        try:
            done = wallet.recover(principal, row["reservation_id"], new_fence_token=uuid4())
        except UncertainEffect:
            return "skipped"  # lease still live
        return "released" if done.status == "released" else done.status
    # effect_started: never touch a reservation whose operation still holds a live lease (the
    # worker owns it and may still issue a ticket); settle only when every ticket has exact usage.
    lease_until = row.get("lease_until")
    if (row.get("op_status") == "running" and lease_until is not None
            and lease_until > datetime.now(timezone.utc)):
        return "skipped"
    with pool.connection() as connection:
        tickets = connection.execute(
            "select count(*) as n from app.wallet_attempt_tickets where reservation_id=%s",
            (row["reservation_id"],)).fetchone()["n"]
        events = connection.execute(
            "select event_id,billing_exact from app.usage_events where operation_id=%s "
            "and owner_id=%s order by event_id",
            (row["usage_operation_id"], row["owner_id"])).fetchall()
    if events and len(events) == int(tickets) and all(e["billing_exact"] for e in events):
        try:
            wallet.settle_usage(principal, row["reservation_id"], fence_token=row["fence_token"],
                                usage_event_ids=[e["event_id"] for e in events])
            return "settled"
        except Exception:
            pass  # fall through: keep the funds held for reconciliation
    try:
        done = wallet.recover(principal, row["reservation_id"], new_fence_token=uuid4())
    except UncertainEffect:
        return "skipped"
    return done.status


def recover_wallet_reservations(pool, max_items: int = 50, *, owner_id: UUID | None = None,
                                grace: int | None = None) -> dict[str, int]:
    """Idempotent, owner-free counts (safe for the cron response and logs)."""
    from infrastructure.wallet import PostgresWallet
    wallet = PostgresWallet(pool)
    counts = {"wallet_seen": 0, "wallet_released": 0, "wallet_settled": 0,
              "wallet_uncertain": 0, "wallet_skipped": 0, "wallet_errors": 0}
    for row in _candidates(pool, max_items, owner_id, grace if grace is not None else grace_seconds()):
        counts["wallet_seen"] += 1
        principal = Principal(row["owner_id"], "recovery", str(row["owner_id"]))
        try:
            if row["reference_type"] == "image":
                outcome = _resolve_image(pool, wallet, principal, row)
            elif row["usage_operation_id"] is None or row["op_status"] is None:
                outcome = "skipped"  # no durable operation to prove the effect is over
            else:
                outcome = _resolve_operation(pool, wallet, principal, row)
        except Exception:
            counts["wallet_errors"] += 1
            continue
        key = f"wallet_{outcome}"
        counts[key if key in counts else "wallet_skipped"] += 1
    return counts
