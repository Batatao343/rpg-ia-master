"""Daily variable-spend cap (SPEC-197 R7). Opt-in: feature is OFF without RPG_DAILY_SPEND_CAP_BRL.

When today's variable spend (``app.usage_events.cost_usd`` x FX, in BRL) exceeds the cap, the
cron sets the *expensive* kill switches off (actor ``system:finops``, audited by
``app.set_kill_switch``). It is idempotent (already-off switches are not rewritten) and NEVER
re-enables anything: a human resets with ``scripts/admin_kill_switch.py on ... --apply``.
Purchases are deliberately not touched (revenue path); existing campaigns stay readable.
"""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from decimal import Decimal, InvalidOperation

from services.finops_alerts import Alert
from services.kill_switches import IMAGE, STT_FALLBACK

ACTOR = "system:finops"
CAP_SWITCHES = (IMAGE, STT_FALLBACK)
DEFAULT_FX = Decimal("6")  # conservative USD->BRL when no pricing version exists


def cap_from_env() -> Decimal | None:
    raw = os.getenv("RPG_DAILY_SPEND_CAP_BRL", "").strip()
    if not raw:
        return None
    try:
        cap = Decimal(raw)
    except InvalidOperation:
        return None
    return cap if cap > 0 else None


def day_start(now: datetime) -> datetime:
    """Start of the current day in the cap timezone (default America/Sao_Paulo, UTC-3 fixed:
    Brazil has no DST), expressed in UTC."""
    hours = int(os.getenv("RPG_DAILY_SPEND_TZ_OFFSET_HOURS", "-3"))
    tz = timezone(timedelta(hours=hours))
    local = now.astimezone(tz)
    return local.replace(hour=0, minute=0, second=0, microsecond=0).astimezone(timezone.utc)


@dataclass
class CapResult:
    enabled: bool = False
    cap_brl: Decimal | None = None
    spent_brl: Decimal = Decimal("0")
    exceeded: bool = False
    switched_off: list[str] = field(default_factory=list)
    already_off: list[str] = field(default_factory=list)
    error: str = ""
    alerts: list[Alert] = field(default_factory=list)

    def summary(self) -> dict:
        return {"daily_cap_enabled": self.enabled, "daily_spent_brl": float(round(self.spent_brl, 4)),
                "daily_cap_brl": None if self.cap_brl is None else float(self.cap_brl),
                "daily_cap_exceeded": self.exceeded, "daily_cap_switched_off": ",".join(self.switched_off),
                "daily_cap_error": self.error}


def evaluate_daily_cap(reader, store, now: datetime, fx_usd_brl: Decimal | None,
                       cap_brl: Decimal | None = None) -> CapResult:
    cap = cap_brl if cap_brl is not None else cap_from_env()
    res = CapResult(enabled=cap is not None, cap_brl=cap)
    if cap is None:
        return res
    fx = fx_usd_brl or DEFAULT_FX
    usd = sum((g.cost_usd for g in reader.usage_groups(day_start(now), now)), Decimal("0"))
    res.spent_brl = usd * fx
    res.exceeded = res.spent_brl > cap
    if not res.exceeded:
        return res
    state = store.load() if store is not None else {}
    reason = f"daily spend cap exceeded: {res.spent_brl:.2f} > {cap} BRL"
    for key in CAP_SWITCHES:
        if state.get(key, True) is False:
            res.already_off.append(key)
            continue
        if store is None:
            res.error = "no_switch_store"
            continue
        store.set(key, False, actor_id=ACTOR, reason=reason)
        res.switched_off.append(key)
    res.alerts.append(Alert(
        "daily_spend_cap", reason + "; switches off: " + ",".join(res.switched_off + res.already_off),
        value=float(res.spent_brl), blocking=True))
    return res
