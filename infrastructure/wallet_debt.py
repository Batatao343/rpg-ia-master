"""SPEC-195 refund debt (financial hold) helpers. Callers hold the owner's wallet account lock.

Debt is an append-only ledger (app.wallet_debt_entries); the balance is the sum of debt_delta.
Every function degrades to a no-op when the SPEC-195 migration is absent (older test fixtures).
"""

from __future__ import annotations

from uuid import UUID, uuid4

from services.purchase_reconciliation import settlement_amount


def _enabled(db) -> bool:
    return (
        db.execute("select to_regclass('app.wallet_debt_entries') as r").fetchone()["r"] is not None
    )


def owner_debt(db, owner_id: UUID) -> int:
    if not _enabled(db):
        return 0
    row = db.execute(
        "select coalesce(sum(debt_delta),0) as d from app.wallet_debt_entries where owner_id=%s",
        (owner_id,),
    ).fetchone()
    return int(row["d"])


def insert_debt_entry(
    db,
    owner_id: UUID,
    kind: str,
    purchase_key: str | None,
    amount: int,
    reference_id: str,
    *,
    wallet_entry_id: UUID | None = None,
    actor_id: UUID | None = None,
    reason: str | None = None,
) -> None:
    delta = amount if kind == "open" else 0 if kind == "forgive_close" else -amount
    db.execute(
        """insert into app.wallet_debt_entries
        (debt_entry_id,owner_id,kind,purchase_key,amount_milli,debt_delta,reference_id,
         wallet_entry_id,actor_id,reason) values (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)""",
        (
            uuid4(),
            owner_id,
            kind,
            purchase_key,
            amount,
            delta,
            reference_id,
            wallet_entry_id,
            actor_id,
            reason,
        ),
    )


def _attribute(db, owner_id: UUID, kind: str, amount: int, reference: str, **audit) -> None:
    """FIFO attribution of settled/forgiven debt to the purchases that opened it."""
    rows = db.execute(
        """select purchase_key, sum(debt_delta) as outstanding
        from app.wallet_debt_entries where owner_id=%s and purchase_key is not null
        group by purchase_key having sum(debt_delta) > 0 order by min(created_at), purchase_key""",
        (owner_id,),
    ).fetchall()
    left = amount
    for row in rows:
        take = min(left, int(row["outstanding"]))
        if take > 0:
            insert_debt_entry(
                db,
                owner_id,
                kind,
                row["purchase_key"],
                take,
                f"{reference}:{row['purchase_key']}",
                **audit,
            )
            left -= take
        if left == 0:
            break


def settle_owner_debt(db, owner_id: UUID) -> int:
    """Pay debt from available credits (new purchases/releases settle first). Returns milli."""
    from infrastructure.wallet import PostgresWallet

    if not _enabled(db):
        return 0
    debt = owner_debt(db, owner_id)
    if debt <= 0:
        return 0
    account = db.execute(
        "select available_milli from app.wallet_accounts where owner_id=%s for update", (owner_id,)
    ).fetchone()
    amount = settlement_amount(debt, int(account["available_milli"]))
    if amount <= 0:
        return 0
    entry_id = uuid4()
    PostgresWallet._post(
        db, owner_id, "debt_settlement", "debt_settlement", str(entry_id), amount, -amount, 0
    )
    db.execute(
        "update app.wallet_accounts set available_milli=available_milli-%s,updated_at=now() "
        "where owner_id=%s",
        (amount, owner_id),
    )
    _attribute(db, owner_id, "settle", amount, str(entry_id))
    return amount


def forgive_replay(db, owner_id: UUID, reference: str) -> dict | None:
    """Prior forgive(s) under this reference: {actor_id, reason, total_milli} or None.

    starts_with (not LIKE): '%'/'_' in a reference must never widen the match."""
    if not _enabled(db):
        return None
    row = db.execute(
        """select min(actor_id::text) as actor, min(reason) as reason,
        count(distinct reason) as reasons, sum(amount_milli) as total
        from app.wallet_debt_entries where owner_id=%s and kind='forgive'
        and starts_with(reference_id, %s)""",
        (owner_id, reference + ":"),
    ).fetchone()
    if not row or row["total"] is None:
        return None
    return {
        "actor_id": UUID(row["actor"]),
        "reason": row["reason"],
        "total_milli": int(row["total"]),
    }


def forgive_debt(
    db, owner_id: UUID, amount: int, *, reference: str, actor_id: UUID, reason: str
) -> int:
    """Audited admin write-off (CLI only). Capped at the current debt; replay-safe by reference."""
    if not _enabled(db):
        raise ValueError("debt_ledger_absent")
    if not isinstance(actor_id, UUID) or not reason or len(reason) > 500 or not reference:
        raise ValueError("admin_audit_fields_required")
    prior = forgive_replay(db, owner_id, reference)
    if prior:
        if prior["actor_id"] != actor_id:
            raise ValueError("admin_replay_divergent")
        return 0
    amount = min(amount, owner_debt(db, owner_id))
    if amount <= 0:
        return 0
    _attribute(db, owner_id, "forgive", amount, reference, actor_id=actor_id, reason=reason)
    return amount
