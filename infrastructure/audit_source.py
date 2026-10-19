"""SPEC-207: leitura owner-scoped para o pacote de auditoria.

Toda consulta filtra `owner_id = principal.user_id` (nenhum owner vindo do
cliente). Jogo alheio e inexistente são indistinguíveis (None). Falha de uma
fonte secundária vira `unavailable` com motivo — o export continua.
"""
from __future__ import annotations

from decimal import Decimal
from typing import Any, Dict, List, Optional
from uuid import UUID

from infrastructure.contracts import Principal, Unauthorized
from infrastructure.db_roles import admin_connection
from services.audit_export import AuditSource


class AccountDeleted(Unauthorized):
    pass


def _to_str_decimal(value: Any) -> str:
    return format(Decimal(str(value)).normalize(), "f") if value is not None else "0"


class PostgresAuditSource:
    def __init__(self, pool, game_store, principal: Principal) -> None:
        self.pool, self.store, self.principal = pool, game_store, principal

    def load(self, game_id: UUID, *, owner_email: str | None = None) -> AuditSource | None:
        owner = self.principal.user_id
        with admin_connection(self.pool) as db:
            if db.execute("select 1 from app.account_deletions where owner_id=%s",
                          (owner,)).fetchone():
                raise AccountDeleted("account_deleted")
        stored = self.store.get(self.principal, game_id)
        if stored is None:
            return None
        source = AuditSource(game_id=str(game_id), state=stored.state,
                             state_version=int(stored.version))
        source.owner_values = {str(owner), str(self.principal.subject or ""),
                               *( [owner_email] if owner_email else [])}
        if owner_email is None:
            try:
                with admin_connection(self.pool) as db, db.transaction():
                    row = db.execute("select app.runtime_auth_email(%s) as email",
                                     (owner,)).fetchone()
                owner_email = (row or {}).get("email") or None
            except Exception:
                owner_email = None
            if owner_email:
                source.owner_values.add(str(owner_email))
        source.owner_values.discard("")
        try:
            with admin_connection(self.pool) as db, db.transaction():
                rows = db.execute(
                    """select operation_id, sequence, timeline_epoch, route, latency_ms,
                              llm_cost_usd, presentation_entry_id
                       from app.turns where owner_id=%s and game_id=%s order by sequence""",
                    (owner, game_id)).fetchall()
            source.turns = [dict(r) for r in rows]
        except Exception as exc:
            source.turns_reason = f"turns_read_failed:{type(exc).__name__}"
        try:
            with admin_connection(self.pool) as db, db.transaction():
                rows = db.execute(
                    """select operation_id, sum(cost_usd) as cost from app.usage_events
                       where owner_id=%s and game_id=%s group by operation_id""",
                    (owner, game_id)).fetchall()
            source.usage_cost = {str(r["operation_id"]): _to_str_decimal(r["cost"]) for r in rows}
        except Exception as exc:
            source.usage_reason = f"usage_read_failed:{type(exc).__name__}"
        try:
            with admin_connection(self.pool) as db, db.transaction():
                rows = db.execute(
                    """select event_id, turn from app.game_events
                       where owner_id=%s and game_id=%s order by turn, event_id""",
                    (owner, game_id)).fetchall()
            events: dict[int, list[str]] = {}
            for row in rows:
                events.setdefault(int(row["turn"]), []).append(str(row["event_id"]))
            source.events_by_turn = events
        except Exception as exc:
            source.events_reason = f"events_read_failed:{type(exc).__name__}"
        try:
            with admin_connection(self.pool) as db, db.transaction():
                rows = db.execute(
                    """select id, error_code from app.operations
                       where owner_id=%s and game_id=%s and kind='turn'
                         and status in ('failed','abandoned') order by started_at, id""",
                    (owner, game_id)).fetchall()
            source.failed_operations = [
                {"operation_id": str(r["id"]),
                 "error_class": _safe_class(r.get("error_code"))} for r in rows]
        except Exception:
            source.failed_operations = []
        return source


def _safe_class(value: Any) -> str | None:
    import re
    text = str(value or "")
    return text if re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]{0,60}", text) else None
