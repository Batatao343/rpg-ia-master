"""Daily variable-spend cap (SPEC-197 R7). Opt-in: feature is OFF without RPG_DAILY_SPEND_CAP_BRL.

When today's variable spend (``app.usage_events.cost_usd`` x FX, in BRL) exceeds the cap, the
cron sets the *expensive* kill switches off (actor ``system:finops``, audited by
``app.set_kill_switch``). It is idempotent (already-off switches are not rewritten) and NEVER
re-enables anything: a human resets with ``scripts/admin_kill_switch.py on ... --apply``.
Purchases are deliberately not touched (revenue path); existing campaigns stay readable.

Coverage is honest: by default only image + STT-fallback are cut. Text-LLM spend is bounded by the
providers' prepaid balances (R-11), NOT by this cap. Opt in to also cutting expensive model fallbacks
with ``RPG_DAILY_SPEND_CAP_MODEL_SWITCHES=model:<provider>/<model>,...``.
A human re-enable the same day is respected (no re-trip) until the cap day rolls over.
"""

from __future__ import annotations

import os
import re
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone, UTC
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


class CapConfigError(ValueError):
    pass


def tz_offset_hours() -> int:
    raw = os.getenv("RPG_DAILY_SPEND_TZ_OFFSET_HOURS", "-3").strip() or "-3"
    try:
        hours = int(raw)
    except ValueError:
        raise CapConfigError(
            "RPG_DAILY_SPEND_TZ_OFFSET_HOURS must be an integer in -12..14"
        ) from None
    if not -12 <= hours <= 14:
        raise CapConfigError("RPG_DAILY_SPEND_TZ_OFFSET_HOURS must be an integer in -12..14")
    return hours


_MODEL_KEY = re.compile(r"^model:[a-z0-9_.-]+/[A-Za-z0-9_.:/-]+$")


def _text_model_keys() -> list[str]:
    """SPEC-219 R8: atalho ``text`` -> um kill switch por (provider, modelo) de ROUTES."""
    from llm_setup import _load_routes
    from services.kill_switches import model_key

    keys: list[str] = []
    for candidates in _load_routes().values():
        for provider, model in candidates:
            key = model_key(provider, model)
            if _MODEL_KEY.match(key) and key not in keys:
                keys.append(key)
    return keys


def cap_switches() -> tuple[str, ...]:
    extra = [
        k.strip()
        for k in os.getenv("RPG_DAILY_SPEND_CAP_MODEL_SWITCHES", "").split(",")
        if k.strip()
    ]
    expanded: list[str] = []
    for k in extra:
        expanded.extend(_text_model_keys() if k == "text" else [k])
    bad = [k for k in expanded if not _MODEL_KEY.match(k)]
    if bad:
        raise CapConfigError(
            "RPG_DAILY_SPEND_CAP_MODEL_SWITCHES entries must look like model:<provider>/<model>"
        )
    return CAP_SWITCHES + tuple(k for k in dict.fromkeys(expanded) if k not in CAP_SWITCHES)


# --- SPEC-219 R8: leitura barata do cap no caminho do turno (opt-in) --------------------------
TEXT_CAP_TTL_SECONDS = 30.0
_text_cap_cache: tuple[float, bool] | None = None


def text_cap_enabled() -> bool:
    return cap_from_env() is not None and os.getenv("RPG_DAILY_SPEND_CAP_TEXT", "").strip() == "1"


def reset_text_cap_cache() -> None:
    global _text_cap_cache
    _text_cap_cache = None


def text_cap_exceeded(reader_factory, *, now: datetime | None = None, clock=None) -> bool:
    """True quando o gasto do dia (BRL) estourou o cap E o cap de texto esta ligado.

    Cache de 30 s por processo; qualquer falha de leitura NAO bloqueia turnos (fail-open) -- o
    cron e os kill switches continuam sendo a fonte autoritativa."""
    global _text_cap_cache
    if not text_cap_enabled():
        return False
    import time as _time

    tick = (clock or _time.monotonic)()
    if _text_cap_cache is not None and tick < _text_cap_cache[0]:
        return _text_cap_cache[1]
    exceeded = False
    try:
        reader = reader_factory()
        moment = now or datetime.now(UTC)
        refs, _fresh = reader.pricing()
        fx = list(refs.values())[-1].fx_usd_brl if refs else DEFAULT_FX
        res = evaluate_daily_cap(reader, None, moment, fx)
        exceeded = bool(res.enabled and res.exceeded)
    except Exception:
        exceeded = False
    _text_cap_cache = (tick + TEXT_CAP_TTL_SECONDS, exceeded)
    return exceeded


def _ts(v) -> datetime | None:
    if isinstance(v, datetime):
        return v if v.tzinfo else v.replace(tzinfo=UTC)
    if isinstance(v, (int, float)):
        return datetime.fromtimestamp(v, UTC)
    return None


def _manually_reenabled(store, key: str, since: datetime) -> bool:
    """True when the latest audit row for ``key`` is a human re-enable that followed a system trip today."""
    rows = [a for a in store.audit(200) if a.get("key") == key]  # newest first
    if not rows:
        return False
    last = rows[0]
    at = _ts(last.get("at") or last.get("created_at"))
    if last.get("actor_id") == ACTOR or not last.get("enabled") or at is None or at < since:
        return False

    # SPEC-236 R3: the human re-enable only shields the cap day of the trip it answered. A trip
    # from a previous cap day plus a re-enable this morning must NOT disarm today's cap.
    def same_day_trip(row) -> bool:
        trip_at = _ts(row.get("at") or row.get("created_at"))
        return (
            row.get("actor_id") == ACTOR
            and row.get("enabled") is False
            and trip_at is not None
            and since <= trip_at <= at
            and trip_at < since + timedelta(days=1)
        )

    return any(same_day_trip(a) for a in rows[1:])


def day_start(now: datetime) -> datetime:
    """Start of the current day in the cap timezone (default America/Sao_Paulo, UTC-3 fixed:
    Brazil has no DST), expressed in UTC."""
    hours = tz_offset_hours()
    tz = timezone(timedelta(hours=hours))
    local = now.astimezone(tz)
    return local.replace(hour=0, minute=0, second=0, microsecond=0).astimezone(UTC)


@dataclass
class CapResult:
    enabled: bool = False
    cap_brl: Decimal | None = None
    spent_brl: Decimal = Decimal("0")
    exceeded: bool = False
    switched_off: list[str] = field(default_factory=list)
    already_off: list[str] = field(default_factory=list)
    manual_override: list[str] = field(default_factory=list)
    error: str = ""
    alerts: list[Alert] = field(default_factory=list)

    def summary(self) -> dict:
        return {
            "daily_cap_enabled": self.enabled,
            "daily_spent_brl": float(round(self.spent_brl, 4)),
            "daily_cap_brl": None if self.cap_brl is None else float(self.cap_brl),
            "daily_cap_exceeded": self.exceeded,
            "daily_cap_switched_off": ",".join(self.switched_off),
            "daily_cap_manual_override": ",".join(self.manual_override),
            "daily_cap_error": self.error,
        }


def evaluate_daily_cap(
    reader, store, now: datetime, fx_usd_brl: Decimal | None, cap_brl: Decimal | None = None
) -> CapResult:
    cap = cap_brl if cap_brl is not None else cap_from_env()
    res = CapResult(enabled=cap is not None, cap_brl=cap)
    if cap is None:
        return res
    fx = fx_usd_brl or DEFAULT_FX
    since = day_start(now)
    # SPEC-236 R2: a provider failure without usage is not spend; it can never trip the cap.
    usd = sum(
        (g.cost_usd for g in reader.usage_groups(since, now) if g.counts_as_spend), Decimal("0")
    )
    res.spent_brl = usd * fx
    res.exceeded = res.spent_brl > cap
    if not res.exceeded:
        return res
    state = store.load() if store is not None else {}
    reason = f"daily spend cap exceeded: {res.spent_brl:.2f} > {cap} BRL"
    for key in cap_switches():
        if state.get(key, True) is False:
            res.already_off.append(key)
            continue
        if store is None:
            res.error = "no_switch_store"
            continue
        if _manually_reenabled(store, key, since):
            res.manual_override.append(key)
            continue
        store.set(key, False, actor_id=ACTOR, reason=reason)
        res.switched_off.append(key)
    res.alerts.append(
        Alert(
            "daily_spend_cap",
            reason
            + "; switches off: "
            + ",".join(res.switched_off + res.already_off)
            + (
                "; manual re-enable respected: " + ",".join(res.manual_override)
                if res.manual_override
                else ""
            ),
            value=float(res.spent_brl),
            blocking=True,
        )
    )
    return res
