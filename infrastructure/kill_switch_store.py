"""Postgres store for SPEC-196 kill switches (privileged backend pool only)."""

from __future__ import annotations

from infrastructure.db_roles import admin_connection
from services.kill_switches import validate_change


class PostgresSwitchStore:
    def __init__(self, pool) -> None:
        self.pool = pool

    def load(self) -> dict[str, bool]:
        with admin_connection(self.pool) as db:
            rows = db.execute("select key, enabled from app.kill_switches").fetchall()
        return {r["key"]: bool(r["enabled"]) for r in rows}

    def set(self, key: str, enabled: bool, *, actor_id: str, reason: str) -> None:
        validate_change(key, actor_id, reason)
        with admin_connection(self.pool) as db, db.transaction():
            db.execute(
                "select app.set_kill_switch(%s,%s,%s,%s)", (key, bool(enabled), actor_id, reason)
            )

    def audit(self, limit: int = 50) -> list[dict]:
        with admin_connection(self.pool) as db:
            rows = db.execute(
                "select key,previous_enabled,enabled,actor_id,reason,created_at "
                "from app.kill_switch_audit order by audit_id desc limit %s",
                (limit,),
            ).fetchall()
        return [dict(r) for r in rows]
