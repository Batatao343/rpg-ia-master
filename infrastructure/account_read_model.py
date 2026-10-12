"""SPEC-185 read-only account projections. Every query carries the verified owner.

Commercial units are milli-Estilhas. Only settled wallet entries count as spend;
usage telemetry is activity, not a charge.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from decimal import Decimal
from uuid import UUID

from infrastructure.contracts import Principal
from infrastructure.postgres import PostgresPool


def _category_sql(alias: str = "u") -> str:
    return (f"case when {alias}.category='image' then 'image' "
            f"when {alias}.category='speech_to_text' then 'voice' else 'game' end")


def _page_limit(limit: int) -> int:
    if not 1 <= limit <= 50:
        raise ValueError("limit deve estar entre 1 e 50")
    return limit


def _usd(value) -> str | None:
    return format(Decimal(str(value)), "f") if value is not None else None


def _cursor(cursor: str | None) -> tuple[datetime, UUID] | None:
    if not cursor:
        return None
    try:
        at_text, id_text = cursor.split("|", 1)
        at = datetime.fromisoformat(at_text)
        if at.tzinfo is None:
            raise ValueError
        return at, UUID(id_text)
    except ValueError as exc:
        raise ValueError("cursor inválido") from exc


def _page(rows: list[dict], limit: int, id_field: str) -> dict:
    has_more = len(rows) > limit
    selected = rows[:limit]
    cursor = None
    if has_more:
        last = selected[-1]
        cursor = f"{last['created_at'].isoformat()}|{last[id_field]}"
    return {"items": selected, "next_cursor": cursor}


class PostgresAccountReader:
    def __init__(self, pool: PostgresPool) -> None:
        self.pool = pool

    def balance(self, principal: Principal) -> dict:
        with self.pool.connection() as connection:
            row = connection.execute(
                "select available_milli,reserved_milli from app.wallet_accounts where owner_id=%s",
                (principal.user_id,),
            ).fetchone()
        return {"available_milli": str(row["available_milli"]) if row else "0",
                "reserved_milli": str(row["reserved_milli"]) if row else "0"}

    def purchases(self, principal: Principal, *, cursor: str | None = None,
                  limit: int = 20) -> dict:
        limit = _page_limit(limit)
        after = _cursor(cursor)
        with self.pool.connection() as connection:
            rows = connection.execute(
                """select entry_id,entry_type,amount_milli,created_at from app.wallet_entries
                where owner_id=%s and entry_type in ('purchase','refund','reversal')
                  and (%s::timestamptz is null or (created_at,entry_id) < (%s,%s::uuid))
                order by created_at desc,entry_id desc limit %s""",
                (principal.user_id, after[0] if after else None,
                 after[0] if after else None, after[1] if after else None, limit + 1),
            ).fetchall()
        page = _page(rows, limit, "entry_id")
        page["items"] = [{"id": str(r["entry_id"]), "kind": r["entry_type"],
                          "amount_milli": str(r["amount_milli"]),
                          "created_at": r["created_at"].isoformat()} for r in page["items"]]
        return page

    def usage(self, principal: Principal, *, cursor: str | None = None,
              limit: int = 20) -> dict:
        limit = _page_limit(limit)
        after = _cursor(cursor)
        with self.pool.connection() as connection:
            rows = connection.execute(
                f"""select u.event_id,u.created_at,u.game_id,{_category_sql()} as category,
                           o.kind as operation_kind
                    from app.usage_events u join app.operations o
                      on o.id=u.operation_id and o.owner_id=u.owner_id
                    where u.owner_id=%s
                      and (%s::timestamptz is null or (u.created_at,u.event_id) < (%s,%s::uuid))
                    order by u.created_at desc,u.event_id desc limit %s""",
                (principal.user_id, after[0] if after else None,
                 after[0] if after else None, after[1] if after else None, limit + 1),
            ).fetchall()
        page = _page(rows, limit, "event_id")
        page["items"] = [{"id": str(r["event_id"]), "category": r["category"],
                          "operation": r["operation_kind"],
                          "created_at": r["created_at"].isoformat()} for r in page["items"]]
        return page

    def series(self, principal: Principal, period: str, *, now: datetime | None = None) -> dict:
        if period not in {"24h", "7d", "30d"}:
            raise ValueError("período inválido")
        now = (now or datetime.now(timezone.utc)).astimezone(timezone.utc)
        hourly = period == "24h"
        unit = timedelta(hours=1) if hourly else timedelta(days=1)
        end = now.replace(minute=0, second=0, microsecond=0) if hourly else now.replace(
            hour=0, minute=0, second=0, microsecond=0)
        count = {"24h": 24, "7d": 7, "30d": 30}[period]
        start = end - unit * (count - 1)
        with self.pool.connection() as connection:
            rows = connection.execute(
                """select date_trunc(%s,e.created_at at time zone 'UTC') at time zone 'UTC' as bucket,
                  case when r.reference_type='image' or o.kind='art' then 'image'
                       when r.reference_type='speech_to_text' then 'voice' else 'game' end as category,
                  sum(e.amount_milli) as amount_milli
                from app.wallet_entries e
                join app.wallet_reservations r on r.reservation_id=e.reservation_id
                  and r.owner_id=e.owner_id
                left join app.operations o on o.id=r.usage_operation_id
                  and o.owner_id=e.owner_id
                where e.owner_id=%s and e.entry_type='settle' and e.created_at >= %s
                  and e.created_at < %s
                group by 1,2""",
                ("hour" if hourly else "day", principal.user_id, start, end + unit),
            ).fetchall()
        totals = {(r["bucket"].astimezone(timezone.utc), r["category"]):
                  int(r["amount_milli"]) for r in rows}
        points = []
        category_totals = {cat: 0 for cat in ("game", "image", "voice")}
        for i in range(count):
            bucket = start + unit * i
            amounts = {cat: totals.get((bucket, cat), 0) for cat in category_totals}
            for cat, amount in amounts.items():
                category_totals[cat] += amount
            points.append({"start": bucket.isoformat(),
                           **{cat: str(amount) for cat, amount in amounts.items()},
                           "total": str(sum(amounts.values()))})
        return {"period": period, "unit": "milli_shard",
                "totals": {cat: str(amount) for cat, amount in category_totals.items()},
                "points": points}

    def history_costs(self, principal: Principal, game_id: UUID,
                      entries: list[dict]) -> dict[str, dict]:
        narrators = {str(e["id"]): int(e.get("epoch", 0)) for e in entries
                     if e.get("role") == "narrator" and e.get("id")}
        if not narrators:
            return {}
        with self.pool.connection() as connection:
            rows = connection.execute(
                """with selected as (
                  select t.operation_id,t.presentation_entry_id,t.timeline_epoch,t.llm_cost_usd
                  from app.turns t where t.owner_id=%s and t.game_id=%s
                    and t.presentation_entry_id=any(%s)
                ), settled as (
                  select r.usage_operation_id as operation_id,sum(e.amount_milli) as cost_milli
                  from app.wallet_reservations r
                  join selected s on s.operation_id=r.usage_operation_id
                  join app.wallet_entries e on e.reservation_id=r.reservation_id
                    and e.owner_id=r.owner_id and e.entry_type='settle'
                  where r.owner_id=%s group by r.usage_operation_id
                ), usage_basis as (
                  select u.operation_id,count(*) as events,bool_and(u.billing_exact) as exact
                  from app.usage_events u join selected s on s.operation_id=u.operation_id
                  where u.owner_id=%s group by u.operation_id
                )
                select s.presentation_entry_id,s.timeline_epoch,s.llm_cost_usd,
                  settled.cost_milli,usage_basis.events,usage_basis.exact
                from selected s left join settled on settled.operation_id=s.operation_id
                  left join usage_basis on usage_basis.operation_id=s.operation_id""",
                (principal.user_id, game_id, list(narrators),
                 principal.user_id, principal.user_id),
            ).fetchall()
        return {r["presentation_entry_id"]: {
                    "cost_milli": str(r["cost_milli"]) if r["cost_milli"] is not None else None,
                    "technical_cost_usd": _usd(r["llm_cost_usd"]),
                    "technical_cost_basis": "usage_ledger" if r["events"] else "turn_fallback",
                    "technical_cost_exact": bool(r["events"] and r["exact"]),
                }
                for r in rows if narrators.get(r["presentation_entry_id"]) == r["timeline_epoch"]}

    def operation_cost(self, principal: Principal, game_id: UUID,
                       operation_id: UUID) -> dict | None:
        with self.pool.connection() as connection:
            row = connection.execute(
                """with selected as (
                  select t.operation_id,t.presentation_entry_id,t.timeline_epoch,t.llm_cost_usd
                  from app.turns t where t.owner_id=%s and t.game_id=%s and t.operation_id=%s
                ), settled as (
                  select r.usage_operation_id as operation_id,sum(e.amount_milli) as cost_milli
                  from app.wallet_reservations r
                  join selected s on s.operation_id=r.usage_operation_id
                  join app.wallet_entries e on e.reservation_id=r.reservation_id
                    and e.owner_id=r.owner_id and e.entry_type='settle'
                  where r.owner_id=%s group by r.usage_operation_id
                ), usage_basis as (
                  select u.operation_id,count(*) as events,bool_and(u.billing_exact) as exact
                  from app.usage_events u join selected s on s.operation_id=u.operation_id
                  where u.owner_id=%s group by u.operation_id
                )
                select s.presentation_entry_id,s.timeline_epoch,s.llm_cost_usd,
                  settled.cost_milli,usage_basis.events,usage_basis.exact
                from selected s left join settled on settled.operation_id=s.operation_id
                  left join usage_basis on usage_basis.operation_id=s.operation_id""",
                (principal.user_id, game_id, operation_id,
                 principal.user_id, principal.user_id),
            ).fetchone()
        if row is None:
            return None
        return {"history_id": row["presentation_entry_id"],
                "epoch": row["timeline_epoch"],
                "cost_milli": str(row["cost_milli"]) if row["cost_milli"] is not None else None,
                "technical_cost_usd": _usd(row["llm_cost_usd"]),
                "technical_cost_basis": "usage_ledger" if row["events"] else "turn_fallback",
                "technical_cost_exact": bool(row["events"] and row["exact"])}
