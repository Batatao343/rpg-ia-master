"""Pure FinOps aggregators (SPEC-196 R1/R2).

Per channel x SKU x pricing_version x cohort (ISO week of the OWNER's first purchase):

  gross                    SKU gross price (BRL), no tax mixed in (tax_rate = 0 in this version)
  refund_brl/dispute_brl   amount reversed by SPEC-195 reconciliation (clawback + debt - releases,
                           and legacy SPEC-189 refund/reversal entries); net revenue = gross -
                           refund - dispute. Margin % and the 5% target use NET revenue.
  channel_fee              ACTUAL (purchase_fee_records) when reconciled, else ESTIMATED from the
                           pricing version fee (pct * gross + fixed, rounded up to the cent)
  variable_cost            usage_events cost converted at the purchase's pricing-version FX,
                           allocated to the owner's purchases pro rata by shard_milli
  contribution_margin      gross - channel_fee - variable_cost
  margin_pct               contribution_margin / gross; target = 5% per (channel, SKU, version)

Fixed infrastructure is a SEPARATE report line (``data/finops_fixed_costs.json``); it is never
allocated into SKUs. Usage of owners with no purchase in the window is reported as
``unallocated_variable_cost_brl`` instead of disappearing.
No function here performs I/O except ``load_fixed_costs``.
"""
from __future__ import annotations

import json
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timezone, UTC
from decimal import ROUND_CEILING, ROUND_HALF_EVEN, Decimal
from pathlib import Path
from collections.abc import Iterable, Mapping, Sequence

TARGET_MARGIN = Decimal("0.05")
_CENT = Decimal("0.01")
_Q4 = Decimal("0.0001")
_Q6 = Decimal("0.000001")
FIXED_COSTS_PATH = Path(__file__).resolve().parents[1] / "data/finops_fixed_costs.json"
CHANNEL_NAMES = {"web": "stripe", "stripe": "stripe", "google_play": "google_play"}
COST_GROUPS = {"llm": "llm", "decision": "llm", "embedding": "embedding",
               "speech_to_text": "stt", "image": "image", "other": "other"}


def report_channel(sku_channel: str) -> str:
    """SKU channel ('web') to the reporting channel ('stripe'); unknown stays itself."""
    return CHANNEL_NAMES.get(sku_channel, sku_channel)


def week_cohort(moment: datetime) -> str:
    utc = moment.astimezone(UTC) if moment.tzinfo else moment.replace(tzinfo=UTC)
    year, week, _ = utc.isocalendar()
    return f"{year}-W{week:02d}"


def _q(value: Decimal, quantum: Decimal = _Q4) -> Decimal:
    return value.quantize(quantum, rounding=ROUND_HALF_EVEN)


@dataclass(frozen=True)
class FeeRate:
    percentage: Decimal
    fixed_brl: Decimal


@dataclass(frozen=True)
class PricingRef:
    """Subset of an immutable pricing version needed by FinOps (no I/O)."""
    version_id: str
    fx_usd_brl: Decimal
    fees: Mapping[str, FeeRate]  # keyed by SKU channel ('web', 'google_play')


@dataclass(frozen=True)
class PurchaseFact:
    purchase_ref: str
    sku_channel: str
    sku_id: str
    pricing_version_id: str
    owner_key: str  # opaque; used for cohort/allocation only, never emitted
    at: datetime
    gross_brl: Decimal
    shard_milli: int
    fee_actual_brl: Decimal | None = None
    first_purchase_at: datetime | None = None  # owner's first purchase over all history
    refund_brl: Decimal = Decimal("0")   # reversed because of refunds / voids / revocations
    dispute_brl: Decimal = Decimal("0")  # reversed because of disputes (open or lost)


@dataclass(frozen=True)
class OwnerUsage:
    """Window usage of one owner, in USD, by cost group (llm/embedding/stt/image/other)."""
    cost_usd: Mapping[str, Decimal]

    @property
    def total_usd(self) -> Decimal:
        return sum(self.cost_usd.values(), Decimal("0"))


@dataclass(frozen=True)
class MarginRow:
    channel: str
    sku_id: str
    pricing_version: str
    cohort: str
    purchases: int
    gross_brl: Decimal
    channel_fee_brl: Decimal
    fee_basis: str  # 'actual' | 'estimated' | 'mixed'
    fee_estimated_purchases: int
    variable_cost_brl: Decimal
    variable_cost_by_group_brl: Mapping[str, Decimal]
    contribution_margin_brl: Decimal
    margin_pct: Decimal | None
    refund_brl: Decimal = Decimal("0")
    dispute_brl: Decimal = Decimal("0")

    @property
    def net_revenue_brl(self) -> Decimal:
        return self.gross_brl - self.refund_brl - self.dispute_brl


@dataclass(frozen=True)
class SkuMargin:
    channel: str
    sku_id: str
    pricing_version: str
    purchases: int
    gross_brl: Decimal
    channel_fee_brl: Decimal
    fee_basis: str
    variable_cost_brl: Decimal
    contribution_margin_brl: Decimal
    margin_pct: Decimal | None
    meets_target: bool | None  # None = no net revenue and no loss yet
    refund_brl: Decimal = Decimal("0")
    dispute_brl: Decimal = Decimal("0")

    @property
    def net_revenue_brl(self) -> Decimal:
        return self.gross_brl - self.refund_brl - self.dispute_brl


@dataclass(frozen=True)
class UnitCosts:
    cost_per_turn_usd: Decimal | None
    cost_per_image_usd: Decimal | None
    cost_per_voice_minute_usd: Decimal | None
    turns: int
    images: int
    voice_minutes: Decimal


@dataclass(frozen=True)
class FixedInfra:
    currency: str
    monthly_total: Decimal
    items: tuple[tuple[str, Decimal], ...]
    prorated_total: Decimal  # for the report window, shown separately


@dataclass(frozen=True)
class FinopsReport:
    rows: tuple[MarginRow, ...]
    skus: tuple[SkuMargin, ...]
    totals: Mapping[str, Decimal]
    unallocated_variable_cost_brl: Decimal
    unit_costs: UnitCosts
    fixed_infra: FixedInfra
    operating_result_brl: Decimal  # contribution - unallocated usage - fixed (explicit, labelled)
    missing_pricing: tuple[str, ...] = field(default_factory=tuple)
    unpriced_purchases: int = 0  # purchases skipped because their pricing version is unknown


def estimate_fee(gross_brl: Decimal, rate: FeeRate) -> Decimal:
    return (gross_brl * rate.percentage + rate.fixed_brl).quantize(_CENT, rounding=ROUND_CEILING)


def newest_pricing(pricing: Mapping[str, PricingRef]) -> PricingRef | None:
    """Newest pricing version. Readers return versions ordered oldest -> newest (created_at),
    so the last one wins; used for FX of unallocated usage and fixed-infra BRL conversion."""
    return next(reversed(list(pricing.values())), None)


def margin_pct(contribution: Decimal, gross: Decimal) -> Decimal | None:
    return None if gross <= 0 else _q(contribution / gross, _Q6)


def meets_target(pct: Decimal | None, target: Decimal = TARGET_MARGIN) -> bool | None:
    return None if pct is None else pct >= target


def cohorts_by_owner(purchases: Iterable[PurchaseFact]) -> dict[str, str]:
    first: dict[str, datetime] = {}
    for p in purchases:
        moment = min(p.at, p.first_purchase_at) if p.first_purchase_at else p.at
        if p.owner_key not in first or moment < first[p.owner_key]:
            first[p.owner_key] = moment
    return {k: week_cohort(v) for k, v in first.items()}


def compute_margins(
    purchases: Sequence[PurchaseFact], pricing: Mapping[str, PricingRef],
    usage: Mapping[str, OwnerUsage], *, cohort_origin: Mapping[str, str] | None = None,
) -> tuple[list[MarginRow], Decimal, tuple[str, ...]]:
    """Return (rows, unallocated_variable_cost_brl, versions_missing).

    ``cohort_origin`` lets a caller supply the first-purchase cohort computed over a longer
    history than the window; default derives it from ``purchases``.
    A purchase whose pricing version is unknown is skipped and reported, never costed at zero.
    """
    cohorts = dict(cohort_origin) if cohort_origin is not None else cohorts_by_owner(purchases)
    missing: set[str] = set()
    usable = []
    for p in purchases:
        ref = pricing.get(p.pricing_version_id)
        if ref is None or p.sku_channel not in ref.fees:
            missing.add(p.pricing_version_id)
            continue
        usable.append((p, ref))
    shards: dict[str, int] = defaultdict(int)
    for p, _ in usable:
        shards[p.owner_key] += p.shard_milli
    buckets: dict[tuple, dict] = {}
    for p, ref in usable:
        channel = report_channel(p.sku_channel)
        cohort = cohorts.get(p.owner_key) or week_cohort(p.at)
        key = (channel, p.sku_id, p.pricing_version_id, cohort)
        b = buckets.setdefault(key, {
            "n": 0, "gross": Decimal("0"), "fee": Decimal("0"), "est": 0,
            "refund": Decimal("0"), "dispute": Decimal("0"), "groups": defaultdict(Decimal)})
        b["n"] += 1
        b["gross"] += p.gross_brl
        refund = min(max(p.refund_brl, Decimal("0")), p.gross_brl)
        b["refund"] += refund
        b["dispute"] += min(max(p.dispute_brl, Decimal("0")), p.gross_brl - refund)
        if p.fee_actual_brl is not None:
            b["fee"] += p.fee_actual_brl
        else:
            b["fee"] += estimate_fee(p.gross_brl, ref.fees[p.sku_channel])
            b["est"] += 1
        owner_usage = usage.get(p.owner_key)
        if owner_usage and shards[p.owner_key]:
            share = Decimal(p.shard_milli) / Decimal(shards[p.owner_key])
            for group, usd in owner_usage.cost_usd.items():
                brl = usd * share * ref.fx_usd_brl
                b["groups"][group] += brl
    rows: list[MarginRow] = []
    for (channel, sku_id, version, cohort), b in sorted(buckets.items()):
        variable = sum(b["groups"].values(), Decimal("0"))
        net = b["gross"] - b["refund"] - b["dispute"]
        cm = net - b["fee"] - variable
        basis = ("estimated" if b["est"] == b["n"] else "actual" if b["est"] == 0 else "mixed")
        rows.append(MarginRow(
            channel, sku_id, version, cohort, b["n"], _q(b["gross"]), _q(b["fee"]), basis,
            b["est"], _q(variable), {g: _q(v) for g, v in sorted(b["groups"].items())},
            _q(cm), margin_pct(cm, net), _q(b["refund"]), _q(b["dispute"])))
    # Usage of owners without a (priced) purchase in the window: reported, never dropped.
    paid_owners = {p.owner_key for p, _ in usable}
    newest = newest_pricing(pricing)
    ref_fx = newest.fx_usd_brl if newest else Decimal("0")
    unalloc = sum((u.total_usd * ref_fx for o, u in usage.items() if o not in paid_owners),
                  Decimal("0"))
    return rows, _q(unalloc), tuple(sorted(missing))


def sku_summary(rows: Iterable[MarginRow], target: Decimal = TARGET_MARGIN) -> list[SkuMargin]:
    """Target check per (channel, SKU, pricing_version): cohorts are summed, versions never mixed."""
    acc: dict[tuple, dict] = {}
    for r in rows:
        a = acc.setdefault((r.channel, r.sku_id, r.pricing_version), {
            "n": 0, "gross": Decimal("0"), "fee": Decimal("0"), "var": Decimal("0"),
            "cm": Decimal("0"), "est": 0, "refund": Decimal("0"), "dispute": Decimal("0")})
        a["n"] += r.purchases
        a["gross"] += r.gross_brl
        a["fee"] += r.channel_fee_brl
        a["var"] += r.variable_cost_brl
        a["cm"] += r.contribution_margin_brl
        a["est"] += r.fee_estimated_purchases
        a["refund"] += r.refund_brl
        a["dispute"] += r.dispute_brl
    out = []
    for (channel, sku, version), a in sorted(acc.items()):
        net = a["gross"] - a["refund"] - a["dispute"]
        pct = margin_pct(a["cm"], net)
        basis = "estimated" if a["est"] == a["n"] else "actual" if a["est"] == 0 else "mixed"
        meets = meets_target(pct, target)
        if pct is None and a["cm"] < 0:  # fully reversed but still paid fees/usage: a loss
            meets = False
        out.append(SkuMargin(channel, sku, version, a["n"], a["gross"], a["fee"], basis, a["var"],
                             a["cm"], pct, meets, a["refund"], a["dispute"]))
    return out


def unit_costs(cost_usd: Mapping[str, Decimal], *, turns: int, images: int,
               voice_ms: int, voice_cost_usd: Decimal | None = None) -> UnitCosts:
    """Cost per turn (llm + embedding), per image and per voice minute from window totals.

    ``voice_cost_usd`` must cover the same (duration-metered) events as ``voice_ms``;
    default is the whole stt group."""
    turn_cost = cost_usd.get("llm", Decimal("0")) + cost_usd.get("embedding", Decimal("0"))
    minutes = Decimal(voice_ms) / Decimal(60000)
    return UnitCosts(
        _q(turn_cost / turns, _Q6) if turns > 0 else None,
        _q(cost_usd.get("image", Decimal("0")) / images, _Q6) if images > 0 else None,
        _q((voice_cost_usd if voice_cost_usd is not None else cost_usd.get("stt", Decimal("0")))
           / minutes, _Q6) if minutes > 0 else None,
        turns, images, _q(minutes, _Q4))


def load_fixed_costs(path: Path | None = None, *, window_days: int = 30,
                     fx_usd_brl: Decimal | None = None) -> FixedInfra:
    """Fixed infra read from config; never allocated to SKUs. Converted to BRL if fx given."""
    target = path or FIXED_COSTS_PATH
    try:
        doc = json.loads(Path(target).read_text(encoding="utf-8"))
    except FileNotFoundError:
        doc = {"currency": "USD", "items": []}
    items = tuple((str(i["name"]), Decimal(str(i["monthly_usd"]))) for i in doc.get("items", []))
    total = sum((v for _, v in items), Decimal("0"))
    factor = fx_usd_brl if fx_usd_brl is not None else Decimal("1")
    prorated = _q(total * factor * Decimal(window_days) / Decimal(30))
    return FixedInfra(doc.get("currency", "USD") if fx_usd_brl is None else "BRL", total, items, prorated)


def build_report(
    purchases: Sequence[PurchaseFact], pricing: Mapping[str, PricingRef],
    usage: Mapping[str, OwnerUsage], *, window_cost_usd: Mapping[str, Decimal],
    turns: int, images: int, voice_ms: int, fixed: FixedInfra,
    voice_cost_usd: Decimal | None = None, cohort_origin: Mapping[str, str] | None = None, target: Decimal = TARGET_MARGIN,
) -> FinopsReport:
    rows, unalloc, missing = compute_margins(purchases, pricing, usage,
                                              cohort_origin=cohort_origin)
    skus = sku_summary(rows, target)
    zero = Decimal("0")
    totals = {
        "gross_brl": sum((r.gross_brl for r in rows), zero),
        "refund_brl": sum((r.refund_brl for r in rows), zero),
        "dispute_brl": sum((r.dispute_brl for r in rows), zero),
        "net_revenue_brl": sum((r.net_revenue_brl for r in rows), zero),
        "channel_fee_brl": sum((r.channel_fee_brl for r in rows), zero),
        "variable_cost_brl": sum((r.variable_cost_brl for r in rows), zero),
        "contribution_margin_brl": sum((r.contribution_margin_brl for r in rows), zero),
    }
    operating = totals["contribution_margin_brl"] - unalloc - fixed.prorated_total
    return FinopsReport(tuple(rows), tuple(skus), totals, unalloc,
                        unit_costs(window_cost_usd, turns=turns, images=images, voice_ms=voice_ms,
                   voice_cost_usd=voice_cost_usd),
                        fixed, _q(operating), missing,
                        len(purchases) - sum(r.purchases for r in rows))


def report_to_dict(report: FinopsReport) -> dict:
    """JSON-safe, owner-free view for the admin dashboard / cron response."""
    def conv(v):
        if isinstance(v, Decimal):
            return str(v)
        if isinstance(v, Mapping):
            return {k: conv(x) for k, x in v.items()}
        if isinstance(v, (list, tuple)):
            return [conv(x) for x in v]
        if hasattr(v, "__dataclass_fields__"):
            return {k: conv(getattr(v, k)) for k in v.__dataclass_fields__}
        return v
    return conv(report)
