"""Versioned, server-side Estilha pricing. One unit is one shard_milli.

This module calculates quotes only. SPEC-184 owns the wallet and settlement.
No value here is a commercial offer until an operator publishes a verified
pricing version and channel SKU outside this repository.
"""

from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
from datetime import datetime, time, timedelta, timezone
from decimal import Decimal, ROUND_CEILING, localcontext
import json
from pathlib import Path
from typing import Mapping, Sequence

from services.usage_metering import RATE_CARD_VERSION, UsageEvent


SHARD_MILLI_PER_SHARD = 1000
TARGET_MARGIN_RATE = Decimal("0.05")
BRL_CENT = Decimal("0.01")
MAX_SHARD_MILLI = 2**63 - 1
_INSTALLED_CARD_PATH = (Path(__file__).resolve().parents[1] /
                        "data/pricing/rate_card_2026-10-08.json")
_INSTALLED_CARD_BYTES = _INSTALLED_CARD_PATH.read_bytes()
INSTALLED_RATE_CARD_SHA256 = sha256(_INSTALLED_CARD_BYTES).hexdigest()
INSTALLED_RATE_CARD_OBSERVED_AT = datetime.combine(
    datetime.fromisoformat(json.loads(_INSTALLED_CARD_BYTES)["observed_at"]).date(),
    time.min, tzinfo=timezone.utc,
)


class PricingUnavailable(ValueError):
    """A quote cannot safely authorize a purchase or usage debit."""


def _decimal(value: Decimal, *, positive: bool = False) -> Decimal:
    if not isinstance(value, Decimal) or not value.is_finite():
        raise PricingUnavailable("valor financeiro deve ser Decimal finito")
    if (positive and value <= 0) or (not positive and value < 0):
        raise PricingUnavailable("valor financeiro fora do intervalo")
    return value


def _numeric(value: Decimal, precision: int, scale: int) -> Decimal:
    """Enforce the matching Postgres NUMERIC bound without Decimal rounding."""
    _decimal(value)
    numerator, denominator = value.as_integer_ratio()
    if numerator * 10**scale % denominator or numerator >= denominator * 10**(precision - scale):
        raise PricingUnavailable("valor fora da escala/precisão financeira")
    return value


def _ratio_units(amount: Decimal, unit: Decimal, *, ceiling: bool) -> int:
    """Exact rational floor/ceil: Decimal division may round before integral conversion."""
    amount_numerator, amount_denominator = amount.as_integer_ratio()
    unit_numerator, unit_denominator = unit.as_integer_ratio()
    numerator = amount_numerator * unit_denominator
    denominator = amount_denominator * unit_numerator
    units = (numerator + denominator - 1) // denominator if ceiling else numerator // denominator
    if units > MAX_SHARD_MILLI:
        raise PricingUnavailable("quantidade excede bigint do ledger")
    return units


def _utc(value: datetime) -> datetime:
    if not isinstance(value, datetime) or value.tzinfo is None or value.utcoffset() is None:
        raise PricingUnavailable("data precisa de timezone")
    return value.astimezone(timezone.utc)


@dataclass(frozen=True)
class ChannelFee:
    channel: str
    percentage: Decimal
    fixed_brl: Decimal

    def __post_init__(self) -> None:
        if not self.channel or len(self.channel) > 40:
            raise PricingUnavailable("canal inválido")
        _decimal(self.percentage)
        _numeric(self.percentage, 8, 6)
        _numeric(self.fixed_brl, 18, 2)
        if self.percentage >= 1:
            raise PricingUnavailable("fee inválida")


@dataclass(frozen=True)
class PricingVersion:
    version_id: str
    shard_budget_unit_brl: Decimal  # BRL per shard_milli, not per whole shard
    fx_usd_brl: Decimal
    fx_source: str
    fx_observed_at: datetime
    fx_max_age: timedelta
    fx_buffer_rate: Decimal
    rate_card_version: str
    rate_card_sha256: str
    rate_card_source: str
    rate_card_observed_at: datetime
    rate_card_max_age: timedelta
    channel_fees: tuple[ChannelFee, ...]

    def __post_init__(self) -> None:
        if not isinstance(self.version_id, str) or not self.version_id or len(self.version_id) > 80:
            raise PricingUnavailable("versão inválida")
        _decimal(self.shard_budget_unit_brl, positive=True)
        _decimal(self.fx_usd_brl, positive=True)
        _numeric(self.shard_budget_unit_brl, 20, 10)
        _numeric(self.fx_usd_brl, 20, 10)
        _numeric(self.fx_buffer_rate, 8, 6)
        if self.fx_buffer_rate > 1:
            raise PricingUnavailable("buffer FX inválido")
        if any(not isinstance(item, str) or not item for item in (
            self.fx_source, self.rate_card_source, self.rate_card_version,
        )):
            raise PricingUnavailable("fonte FX/rate card ausente")
        if (not isinstance(self.rate_card_sha256, str) or len(self.rate_card_sha256) != 64
                or any(char not in "0123456789abcdef" for char in self.rate_card_sha256)):
            raise PricingUnavailable("hash do rate card inválido")
        _utc(self.fx_observed_at)
        _utc(self.rate_card_observed_at)
        if self.fx_max_age <= timedelta(0) or self.rate_card_max_age <= timedelta(0):
            raise PricingUnavailable("prazo de frescor inválido")
        if not isinstance(self.channel_fees, tuple) or not self.channel_fees:
            raise PricingUnavailable("fees ausentes")
        channels = [fee.channel for fee in self.channel_fees]
        if len(channels) != len(set(channels)):
            raise PricingUnavailable("fee de canal duplicada")
        object.__setattr__(self, "channel_fees", tuple(sorted(
            self.channel_fees, key=lambda fee: fee.channel,
        )))

    def require_fresh(self, at: datetime) -> None:
        if self.rate_card_version != RATE_CARD_VERSION:
            raise PricingUnavailable("rate card versionado não instalado")
        if self.rate_card_sha256 != INSTALLED_RATE_CARD_SHA256:
            raise PricingUnavailable("conteúdo do rate card divergiu")
        if _utc(self.rate_card_observed_at) != INSTALLED_RATE_CARD_OBSERVED_AT:
            raise PricingUnavailable("instante do rate card divergiu da fonte")
        now = _utc(at)
        for label, observed, max_age in (
            ("FX", self.fx_observed_at, self.fx_max_age),
            ("rate card", self.rate_card_observed_at, self.rate_card_max_age),
        ):
            age = now - _utc(observed)
            if age < timedelta(0) or age > max_age:
                raise PricingUnavailable(f"{label} ausente ou stale")

    def fee_for(self, channel: str) -> ChannelFee:
        return next((fee for fee in self.channel_fees if fee.channel == channel), None) or _missing_fee()


def _missing_fee() -> ChannelFee:
    raise PricingUnavailable("fee de canal ausente")


@dataclass(frozen=True)
class PurchaseSku:
    sku_id: str
    channel: str
    gross_brl: Decimal
    shard_milli: int
    pricing_version: str

    def __post_init__(self) -> None:
        if not self.sku_id or not self.channel or not self.pricing_version:
            raise PricingUnavailable("SKU incompleto")
        _decimal(self.gross_brl, positive=True)
        _numeric(self.gross_brl, 18, 2)
        if (isinstance(self.shard_milli, bool) or not isinstance(self.shard_milli, int)
                or not 0 < self.shard_milli <= MAX_SHARD_MILLI):
            raise PricingUnavailable("quantidade de Estilhas inválida")


@dataclass(frozen=True)
class PurchaseQuote:
    pricing_version: str
    sku_id: str
    channel: str
    gross_brl: Decimal
    channel_fee_brl: Decimal
    target_margin_brl: Decimal
    tax_brl: Decimal
    variable_budget_brl: Decimal
    shard_milli_granted: int
    allocated_budget_brl: Decimal
    rounding_reserve_brl: Decimal
    contribution_margin_brl: Decimal


@dataclass(frozen=True)
class UsageQuote:
    pricing_version: str
    usage_event_ids: tuple[str, ...]
    usage_rate_versions: tuple[str, ...]
    provider_cost_usd: Decimal
    fx_with_buffer: Decimal
    variable_cost_brl: Decimal
    shard_milli_debited: int
    debit_budget_brl: Decimal
    rounding_reserve_brl: Decimal


def quote_purchase(sku: PurchaseSku, version: PricingVersion, *, at: datetime) -> PurchaseQuote:
    """Validate a server/store SKU and grant exactly floor(budget/unit)."""
    version.require_fresh(at)
    if sku.pricing_version != version.version_id:
        raise PricingUnavailable("SKU e versão divergem")
    fee = version.fee_for(sku.channel)
    # Round liabilities upward, never the budget or granted units upward.
    # DB scales bound all coefficients; 100 digits preserves products and sums.
    with localcontext() as context:
        context.prec = 100
        channel_fee = (sku.gross_brl * fee.percentage + fee.fixed_brl).quantize(
            BRL_CENT, rounding=ROUND_CEILING,
        )
        target_margin = (sku.gross_brl * TARGET_MARGIN_RATE).quantize(
            BRL_CENT, rounding=ROUND_CEILING,
        )
        tax = Decimal("0")
        budget = sku.gross_brl - channel_fee - target_margin - tax
        if budget <= 0:
            raise PricingUnavailable("pacote impossível: fee e margem esgotam o bruto")
        grant = _ratio_units(budget, version.shard_budget_unit_brl, ceiling=False)
        if grant <= 0 or grant != sku.shard_milli:
            raise PricingUnavailable("SKU não corresponde às Estilhas calculadas")
        allocated = version.shard_budget_unit_brl * grant
        reserve = budget - allocated
        return PurchaseQuote(
            version.version_id, sku.sku_id, sku.channel, sku.gross_brl,
            channel_fee, target_margin, tax, budget, grant, allocated, reserve,
            sku.gross_brl - channel_fee - tax - allocated,
        )


def quote_attempt_ceiling(cost_usd: Decimal, version: PricingVersion, *, at: datetime) -> int:
    """Authorize one provider attempt against immutable pricing before dispatch."""
    version.require_fresh(at)
    _numeric(cost_usd, 18, 9)
    with localcontext() as context:
        context.prec = 100
        buffered_brl = cost_usd * version.fx_usd_brl * (Decimal("1") + version.fx_buffer_rate)
        return max(1, _ratio_units(buffered_brl, version.shard_budget_unit_brl, ceiling=True))


def quote_usage(events: Sequence[UsageEvent], version: PricingVersion, *, at: datetime,
                authorized_snapshot: bool = False) -> UsageQuote:
    """Debit ceil(exact provider cost converted with versioned buffered FX)."""
    # A previously authorized reservation may settle after FX/card expiry. Its
    # immutable pricing row and persisted exact usage, not a current quote,
    # determine the debit. Freshness is mandatory when authorizing new spend.
    if not authorized_snapshot:
        version.require_fresh(at)
    if not events or any(not event.billing_exact for event in events):
        raise PricingUnavailable("usage exato indisponível")
    if len({event.event_id for event in events}) != len(events):
        raise PricingUnavailable("usage duplicado")
    if len({event.operation_id for event in events}) != 1:
        raise PricingUnavailable("usage de operações diferentes")
    for event in events:
        if event.cost_basis == "token_priced" and event.pricing_version != version.rate_card_version:
            raise PricingUnavailable("rate card de usage diverge da versão")
        if event.cost_basis not in {"token_priced", "provider_reported"}:
            raise PricingUnavailable("origem de custo não faturável")
        _numeric(event.cost_usd, 18, 9)
    with localcontext() as context:
        context.prec = max(100, 80 + len(str(len(events))))
        total_usd = sum((event.cost_usd for event in events), Decimal("0"))
        buffered_fx = version.fx_usd_brl * (Decimal("1") + version.fx_buffer_rate)
        variable_brl = total_usd * buffered_fx
        debit = _ratio_units(variable_brl, version.shard_budget_unit_brl, ceiling=True)
        reserved = version.shard_budget_unit_brl * debit
        return UsageQuote(
            version.version_id, tuple(str(event.event_id) for event in events),
            tuple(sorted({event.pricing_version for event in events})), total_usd,
            buffered_fx, variable_brl, debit, reserved, reserved - variable_brl,
        )


def contribution_report(quotes: Sequence[PurchaseQuote], *, fixed_infra_brl: Decimal) -> dict:
    """Per-transaction margin stays separate from monthly fixed infrastructure."""
    _numeric(fixed_infra_brl, 18, 2)
    with localcontext() as context:
        context.prec = max(100, 50 + len(str(len(quotes))))
        return {
            "gross_brl": sum((q.gross_brl for q in quotes), Decimal("0")),
            "channel_fee_brl": sum((q.channel_fee_brl for q in quotes), Decimal("0")),
            "variable_budget_allocated_brl": sum((q.allocated_budget_brl for q in quotes), Decimal("0")),
            "contribution_margin_brl": sum((q.contribution_margin_brl for q in quotes), Decimal("0")),
            "fixed_infra_brl": fixed_infra_brl,
        }


def version_from_record(record: Mapping) -> PricingVersion:
    """Read the immutable DB row or a CLI simulation document, never client input."""
    fees = record["channel_fees"]
    if not isinstance(fees, Mapping):
        raise PricingUnavailable("fees de canal inválidas")

    def decimal_text(value: object) -> Decimal:
        if not isinstance(value, (str, Decimal)):
            raise PricingUnavailable("decimal financeiro deve ser texto")
        try:
            return Decimal(value)
        except Exception as exc:
            raise PricingUnavailable("decimal financeiro inválido") from exc

    def when(value: object) -> datetime:
        if isinstance(value, datetime):
            return value
        if isinstance(value, str):
            try:
                return datetime.fromisoformat(value.replace("Z", "+00:00"))
            except ValueError as exc:
                raise PricingUnavailable("data inválida") from exc
        raise PricingUnavailable("data inválida")

    def seconds(value: object) -> timedelta:
        if isinstance(value, bool) or not isinstance(value, int):
            raise PricingUnavailable("idade máxima inválida")
        return timedelta(seconds=value)

    channel_fees = tuple(ChannelFee(
        str(channel), decimal_text(fee["percentage"]), decimal_text(fee["fixed_brl"]),
    ) for channel, fee in sorted(fees.items()))
    return PricingVersion(
        version_id=record["version_id"],
        shard_budget_unit_brl=decimal_text(record["shard_budget_unit_brl"]),
        fx_usd_brl=decimal_text(record["fx_usd_brl"]),
        fx_source=record["fx_source"],
        fx_observed_at=when(record["fx_observed_at"]),
        fx_max_age=seconds(record["fx_max_age_seconds"]),
        fx_buffer_rate=decimal_text(record["fx_buffer_rate"]),
        rate_card_version=record["rate_card_version"],
        rate_card_sha256=record["rate_card_sha256"],
        rate_card_source=record["rate_card_source"],
        rate_card_observed_at=when(record["rate_card_observed_at"]),
        rate_card_max_age=seconds(record["rate_card_max_age_seconds"]),
        channel_fees=channel_fees,
    )
