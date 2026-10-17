"""Read-only preview and fenced release of expired durable operations."""

from __future__ import annotations
from infrastructure.db_roles import admin_connection

from typing import Any
from uuid import UUID

from infrastructure.postgres import PostgresPool


def orphan_operations(pool: PostgresPool, *, owner_id: UUID | None = None) -> list[dict[str, Any]]:
    params: list[Any] = []
    owner_clause = ""
    if owner_id is not None:
        owner_clause = " and owner_id=%s"
        params.append(owner_id)
    with admin_connection(pool) as connection:
        rows = connection.execute(
            f"""select id,owner_id,game_id,kind,status,base_game_version,
                       started_at,heartbeat_at,lease_until,error_code
                from app.operations
                where status='running' and lease_until < now(){owner_clause}
                order by started_at""",
            params,
        ).fetchall()
    return [dict(row) for row in rows]


def abandon_expired(pool: PostgresPool, operation_id: UUID) -> bool:
    """Release exactly one expired operation; completed receipts are immutable."""
    with admin_connection(pool) as connection, connection.transaction():
        row = connection.execute(
            """update app.operations set status='abandoned',error_code='operator_abandoned',
                   lease_token=null,lease_until=null,finished_at=now()
               where id=%s and status='running' and lease_until < now()
               returning game_id""",
            (operation_id,),
        ).fetchone()
        if not row:
            return False
        if row["game_id"]:
            connection.execute(
                """update app.games set active_operation_id=null,
                     active_lease_token=null,active_lease_until=null
                   where id=%s and active_operation_id=%s""",
                (row["game_id"], operation_id),
            )
        return True


def recover_expired(pool: PostgresPool, max_items: int) -> dict[str, int]:
    """Bounded cron sweep: release expired-lease operations (idempotent, conditional UPDATE)."""
    expired = orphan_operations(pool)
    released = sum(1 for row in expired[:max_items] if abandon_expired(pool, row["id"]))
    return {"orphans_seen": len(expired), "released": released}
