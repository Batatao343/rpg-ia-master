"""FinOps alert evaluators + low-cardinality Prometheus publishing (SPEC-196 R3/R5/R6).

Evaluators are pure (inputs in, ``Alert`` list out). Metric labels are limited to
``kind, channel, sku_id, provider, model``; any value that looks like an identifier
(UUID, long hex, e-mail) is replaced by ``other`` so a user/game/order id can never
become a label, even by accident.

Pricing safety: an UNKNOWN pricing (usage with no rate card) or a STALE rate card
is a *blocking* alert. ``require_paid_effect`` refuses new paid effects while the
relevant card is stale; cost is never assumed to be zero.
"""
from __future__ import annotations

import os
import re
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from typing import Iterable, Mapping, Sequence

from observability.metrics import metrics
from services.finops import SkuMargin, TARGET_MARGIN

UNKNOWN_PRICING_VERSIONS = {"unknown-conservative-v1"}
SUCCESS_OUTCOMES = {"success", "ok", "completed"}
_ID_LIKE = re.compile(r"^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-|^[0-9a-fA-F]{24,}$|@")
_SAFE = re.compile(r"^[A-Za-z0-9_.:/+-]{1,60}$")
ALERT_KINDS = ("unknown_pricing", "stale_rate_card", "cost_spike", "expensive_fallback",
               "wallet_mismatch", "webhook_backlog", "provider_failure", "margin_below_target",
               "finops_unknown_purchase_pricing")


def safe_label(value: object) -> str:
    text = str(value or "")
    if not text:
        return ""
    return text if _SAFE.fullmatch(text) and not _ID_LIKE.search(text) else "other"


@dataclass(frozen=True)
class Alert:
    kind: str
    message: str
    channel: str = ""
    sku_id: str = ""
    provider: str = ""
    model: str = ""
    value: float = 1.0
    blocking: bool = False

    def labels(self) -> dict[str, str]:
        return {"kind": self.kind, "channel": safe_label(self.channel),
                "sku_id": safe_label(self.sku_id), "provider": safe_label(self.provider),
                "model": safe_label(self.model)}


@dataclass(frozen=True)
class UsageGroup:
    provider: str
    model: str
    category: str
    pricing_version: str
    cost_basis: str
    outcome: str
    count: int
    cost_usd: Decimal


@dataclass(frozen=True)
class Freshness:
    name: str  # 'fx', 'llm', 'image', 'speech' (low-cardinality)
    observed_at: datetime
    max_age: timedelta


@dataclass(frozen=True)
class Backlog:
    channel: str
    count: int
    oldest_age_seconds: float


@dataclass(frozen=True)
class Thresholds:
    cost_spike_factor: float = 3.0
    cost_spike_min_usd: float = 1.0
    fallback_share: float = 0.25
    fallback_min_usd: float = 0.5
    primary_providers: frozenset = frozenset({"deepseek", "groq"})
    failure_ratio: float = 0.30
    failure_min_attempts: int = 20
    backlog_age_seconds: float = 3600.0

    @classmethod
    def from_env(cls) -> "Thresholds":
        e = os.getenv
        return cls(
            float(e("RPG_FINOPS_SPIKE_FACTOR", "3")), float(e("RPG_FINOPS_SPIKE_MIN_USD", "1")),
            float(e("RPG_FINOPS_FALLBACK_SHARE", "0.25")),
            float(e("RPG_FINOPS_FALLBACK_MIN_USD", "0.5")),
            frozenset(p.strip() for p in e("RPG_FINOPS_PRIMARY_PROVIDERS", "deepseek,groq").split(",")
                      if p.strip()),
            float(e("RPG_FINOPS_FAILURE_RATIO", "0.3")), int(e("RPG_FINOPS_FAILURE_MIN", "20")),
            float(e("RPG_FINOPS_BACKLOG_SECONDS", "3600")))


@dataclass(frozen=True)
class AlertInputs:
    usage_groups: Sequence[UsageGroup] = ()
    freshness: Sequence[Freshness] = ()
    wallet_mismatch_accounts: int = 0
    wallet_mismatch_abs_milli: int = 0
    backlogs: Sequence[Backlog] = ()
    baseline_cost_by_provider: Sequence[Mapping[str, Decimal]] = ()  # previous windows
    skus: Sequence[SkuMargin] = ()
    switches_off: Sequence[str] = ()
    unpriced_purchases: int = 0
    unpriced_versions: Sequence[str] = ()


def unknown_pricing(groups: Iterable[UsageGroup]) -> list[Alert]:
    seen: dict[tuple, int] = {}
    for g in groups:
        if g.pricing_version in UNKNOWN_PRICING_VERSIONS:
            seen[(g.provider, g.model)] = seen.get((g.provider, g.model), 0) + g.count
    return [Alert("unknown_pricing", f"{n} usage event(s) without a rate card for {p}/{m}",
                  provider=p, model=m, value=float(n), blocking=True)
            for (p, m), n in sorted(seen.items())]


def stale_rate_cards(items: Iterable[Freshness], now: datetime) -> list[Alert]:
    out = []
    for f in items:
        age = now - f.observed_at
        if age < timedelta(0) or age > f.max_age:
            out.append(Alert("stale_rate_card",
                             f"{f.name} stale: age {age.total_seconds() / 86400:.1f}d "
                             f"> {f.max_age.total_seconds() / 86400:.1f}d",
                             provider=f.name, value=age.total_seconds() / 86400, blocking=True))
    return out


def _by_provider(groups: Iterable[UsageGroup]) -> dict[str, Decimal]:
    totals: dict[str, Decimal] = {}
    for g in groups:
        totals[g.provider] = totals.get(g.provider, Decimal("0")) + g.cost_usd
    return totals


def cost_spike(groups: Iterable[UsageGroup], baselines: Sequence[Mapping[str, Decimal]],
               t: Thresholds) -> list[Alert]:
    current = _by_provider(groups)
    out = []
    for provider, usd in sorted(current.items()):
        history = [b.get(provider, Decimal("0")) for b in baselines]
        mean = (sum(history, Decimal("0")) / len(history)) if history else None
        if mean is None or usd < Decimal(str(t.cost_spike_min_usd)):
            continue
        # a provider with no history at all counts as a spike once above the floor
        if mean == 0 or usd > mean * Decimal(str(t.cost_spike_factor)):
            out.append(Alert("cost_spike", f"{provider} cost ${usd} vs baseline ${mean:.4f}",
                             provider=provider, value=float(usd)))
    return out


def expensive_fallback(groups: Iterable[UsageGroup], t: Thresholds) -> list[Alert]:
    llm = [g for g in groups if g.category in {"llm", "decision"}]
    total = sum((g.cost_usd for g in llm), Decimal("0"))
    if total < Decimal(str(t.fallback_min_usd)):
        return []
    out = []
    by_model: dict[tuple, Decimal] = {}
    for g in llm:
        if g.provider not in t.primary_providers:
            by_model[(g.provider, g.model)] = by_model.get((g.provider, g.model), Decimal("0")) + g.cost_usd
    for (provider, model), usd in sorted(by_model.items()):
        share = usd / total
        if share > Decimal(str(t.fallback_share)):
            out.append(Alert("expensive_fallback",
                             f"non-primary {provider}/{model} is {share:.0%} of LLM cost",
                             provider=provider, model=model, value=float(share)))
    return out


def wallet_mismatch(accounts: int, abs_milli: int) -> list[Alert]:
    if accounts <= 0 and abs_milli == 0:
        return []
    return [Alert("wallet_mismatch", f"{accounts} wallet account(s) differ from ledger "
                  f"(abs {abs_milli} milli)", value=float(max(accounts, 1)), blocking=False)]


def webhook_backlog(backlogs: Iterable[Backlog], t: Thresholds) -> list[Alert]:
    return [Alert("webhook_backlog", f"{b.count} unprocessed {b.channel} event(s), oldest "
                  f"{b.oldest_age_seconds:.0f}s", channel=b.channel, value=b.oldest_age_seconds)
            for b in backlogs if b.count > 0 and b.oldest_age_seconds > t.backlog_age_seconds]


def provider_failures(groups: Iterable[UsageGroup], t: Thresholds) -> list[Alert]:
    totals: dict[str, list[int]] = {}
    for g in groups:
        pair = totals.setdefault(g.provider, [0, 0])
        pair[0] += g.count
        pair[1] += g.count if g.outcome not in SUCCESS_OUTCOMES else 0
    return [Alert("provider_failure", f"{p}: {bad}/{n} attempts failed", provider=p,
                  value=bad / n)
            for p, (n, bad) in sorted(totals.items())
            if n >= t.failure_min_attempts and bad / n >= t.failure_ratio]


def margin_below_target(skus: Iterable[SkuMargin], target: Decimal = TARGET_MARGIN) -> list[Alert]:
    return [Alert("margin_below_target",
                  f"{s.channel}/{s.sku_id}@{s.pricing_version}: margin {s.margin_pct} < {target}",
                  channel=s.channel, sku_id=s.sku_id,
                  value=float(s.margin_pct) if s.margin_pct is not None else 0.0)
            for s in skus if s.meets_target is False]


def unknown_purchase_pricing(count: int, versions: Sequence[str]) -> list[Alert]:
    """Purchases whose pricing version (or channel fee) is unknown are excluded from margins;
    that must page, never silently look like a healthy report."""
    if count <= 0:
        return []
    shown = ",".join(safe_label(v) for v in list(versions)[:3])
    return [Alert("finops_unknown_purchase_pricing",
                  f"{count} purchase(s) skipped from margin: unknown pricing version(s) {shown}",
                  value=float(count), blocking=True)]


def evaluate_alerts(inputs: AlertInputs, now: datetime,
                    thresholds: Thresholds | None = None) -> list[Alert]:
    t = thresholds or Thresholds.from_env()
    return [*unknown_pricing(inputs.usage_groups), *stale_rate_cards(inputs.freshness, now),
            *cost_spike(inputs.usage_groups, inputs.baseline_cost_by_provider, t),
            *expensive_fallback(inputs.usage_groups, t),
            *wallet_mismatch(inputs.wallet_mismatch_accounts, inputs.wallet_mismatch_abs_milli),
            *webhook_backlog(inputs.backlogs, t), *provider_failures(inputs.usage_groups, t),
            *margin_below_target(inputs.skus),
            *unknown_purchase_pricing(inputs.unpriced_purchases, inputs.unpriced_versions)]


# --- installed card freshness + paid-effect guard (R5) -----------------------------------
def installed_freshness() -> list[Freshness]:
    """Freshness of the three rate cards shipped in data/pricing (observed_at based)."""
    from services.image_pricing import _CARD as image_card
    from services.shard_pricing import INSTALLED_RATE_CARD_OBSERVED_AT
    from services.speech_pricing import _CARD as speech_card

    def seen(card) -> datetime:
        return datetime.fromisoformat(card["observed_at"]).replace(tzinfo=timezone.utc) \
            if "T" not in card["observed_at"] else datetime.fromisoformat(card["observed_at"])

    llm_days = int(os.getenv("RPG_FINOPS_LLM_CARD_MAX_AGE_DAYS", "30"))
    return [Freshness("llm", INSTALLED_RATE_CARD_OBSERVED_AT, timedelta(days=llm_days)),
            Freshness("image", seen(image_card), timedelta(days=7)),
            Freshness("speech", seen(speech_card), timedelta(days=7))]


def require_paid_effect(category: str, *, now: datetime | None = None) -> None:
    """Refuse a NEW paid effect when its rate card is stale (never assume zero cost).

    ``category`` is ``image`` or ``stt``; ``RPG_FINOPS_BLOCK_STALE=0`` downgrades to alert-only.
    Raises ``PricingUnavailable`` (callers already map it to 503).
    """
    if os.getenv("RPG_FINOPS_BLOCK_STALE", "1") == "0":
        return
    name = {"image": "image", "stt": "speech", "llm": "llm"}[category]
    moment = (now or datetime.now(timezone.utc)).astimezone(timezone.utc)
    stale = [a for a in stale_rate_cards(
        [f for f in installed_freshness() if f.name == name], moment)]
    if stale:
        from services.shard_pricing import PricingUnavailable
        raise PricingUnavailable(f"{name} rate card stale")


# --- Prometheus publishing ----------------------------------------------------------------
_published: dict[str, set[tuple]] = {}


def publish_alert_metrics(alerts: Sequence[Alert]) -> None:
    keys: set[tuple] = set()
    for a in alerts:
        labels = a.labels()
        metrics.set_gauge("rpg_finops_alert_active", labels, 1.0)
        keys.add(tuple(sorted(labels.items())))
    for old in _published.get("alert", set()) - keys:
        metrics.set_gauge("rpg_finops_alert_active", dict(old), 0.0)
    _published["alert"] = keys


def publish_margin_metrics(skus: Iterable[SkuMargin], unit) -> None:
    """Margin gauge per (channel, SKU) = worst pricing version in the window. SKUs that left the
    window are cleared so a stale low value can never keep FinopsMarginBelowTarget firing."""
    worst: dict[tuple, float] = {}
    for s in skus:
        if s.margin_pct is not None:
            key = (safe_label(s.channel), safe_label(s.sku_id))
            worst[key] = min(worst.get(key, float("inf")), float(s.margin_pct))
    for (channel, sku_id), value in worst.items():
        metrics.set_gauge("rpg_finops_margin_ratio", {"channel": channel, "sku_id": sku_id}, value)
    for channel, sku_id in _published.get("margin", set()) - set(worst):
        metrics.clear_gauge("rpg_finops_margin_ratio", {"channel": channel, "sku_id": sku_id})
    _published["margin"] = set(worst)
    for kind, value in (("turn", unit.cost_per_turn_usd), ("image", unit.cost_per_image_usd),
                        ("voice_minute", unit.cost_per_voice_minute_usd)):
        if value is not None:
            metrics.set_gauge("rpg_finops_unit_cost_usd", {"kind": kind}, float(value))
        else:
            metrics.clear_gauge("rpg_finops_unit_cost_usd", {"kind": kind})


_last_evaluation: list[float] = []


def publish_evaluation_age(now: float | None = None, *, evaluated: bool = False) -> None:
    """``rpg_finops_evaluation_age_seconds{kind="finops"}``: seconds since the last completed
    evaluation. Called with ``evaluated=True`` at the end of a run (age 0) and on every /metrics
    scrape so a process that stopped receiving the cron shows growing age."""
    import time as _time
    moment = _time.time() if now is None else now
    if evaluated:
        _last_evaluation[:] = [moment]
    if _last_evaluation:
        metrics.set_gauge("rpg_finops_evaluation_age_seconds", {"kind": "finops"},
                          max(0.0, moment - _last_evaluation[0]))


def publish_switch_metrics(off_keys: Iterable[str]) -> None:
    families: dict[str, int] = {}
    for key in off_keys:
        family = key.split(":", 1)[0]
        families[family] = families.get(family, 0) + 1
    for family in ("image_generation", "stt_fallback_expensive", "model", "decision_backend",
                   "new_purchases"):
        metrics.set_gauge("rpg_finops_kill_switch_off", {"kind": family},
                          float(families.get(family, 0)))
