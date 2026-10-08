"""Normalized, content-free usage records for one logical operation.

Prices are versioned observations, not provider invoices. Unknown or variable
prices are conservative estimates and cannot authorize exact wallet billing.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal, InvalidOperation, ROUND_UP
import json
from pathlib import Path
from typing import Any, Literal, Mapping, Sequence
from uuid import UUID, uuid5


_CARD = json.loads((Path(__file__).resolve().parents[1] /
                    "data/pricing/rate_card_2026-10-08.json").read_text(encoding="utf-8"))
RATE_CARD_VERSION: str = _CARD["version"]
_MODELS: dict[str, dict[str, Any]] = _CARD["models"]
_UNKNOWN_MIN_USD = Decimal("1.00")
_UNKNOWN_PER_MILLION = Decimal("100.00")
_MONEY_QUANTUM = Decimal("0.000000001")
_EVENT_NAMESPACE = UUID("0fd267e9-c99d-48a1-9235-02bcde642da8")

CostBasis = Literal["provider_reported", "token_priced", "rate_card", "estimated"]


@dataclass(frozen=True)
class UsageEvent:
    event_id: UUID
    operation_id: UUID
    component: str
    attempt_ordinal: int
    category: str
    provider: str
    model: str
    outcome: str
    input_units: int | None
    output_units: int | None
    cached_units: int | None
    audio_units: int | None
    image_units: int | None
    cost_usd: Decimal
    cost_basis: CostBasis
    pricing_version: str
    billing_exact: bool


def _nonnegative_int(value: object) -> int | None:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        return None
    return value


def _money(value: object) -> Decimal | None:
    if isinstance(value, bool) or value is None:
        return None
    try:
        amount = Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError):
        return None
    return amount if amount.is_finite() and amount >= 0 else None


def safe_provider_usage(value: object, *, image_generated: bool = False) -> dict[str, int | str]:
    """Whitelist provider counters before they cross into jobs, logs or storage."""
    if not isinstance(value, Mapping):
        value = {}
    aliases = {
        "input_tokens": ("input_tokens", "prompt_tokens"),
        "output_tokens": ("output_tokens", "completion_tokens"),
        "cached_tokens": ("cached_tokens", "prompt_cache_hit_tokens"),
        "audio_units": ("audio_units",),
        "image_units": ("image_units", "images"),
    }
    safe: dict[str, int | str] = {}
    for field, keys in aliases.items():
        reading = next((value[key] for key in keys if key in value), None)
        valid = _nonnegative_int(reading)
        if valid is not None:
            safe[field] = valid
    if image_generated:
        safe["image_units"] = max(1, int(safe.get("image_units", 0)))
    reported = _money(value.get("provider_cost_usd", value.get("cost_usd")))
    if reported is not None:
        safe["provider_cost_usd"] = str(reported)
    return safe


def _priced_cost(card: Mapping[str, Any], inputs: int, outputs: int,
                 cached: int) -> Decimal:
    amount = (
        Decimal(inputs - cached) * Decimal(card["input_per_million"])
        + Decimal(cached) * Decimal(card["cached_input_per_million"])
        + Decimal(outputs) * Decimal(card["output_per_million"])
    ) / Decimal(1_000_000)
    return amount.quantize(_MONEY_QUANTUM, rounding=ROUND_UP)


def reserve_next_attempt(provider: str, model: str) -> Decimal | None:
    """Worst published-card bound, or None to make a wallet fail closed."""
    card = _MODELS.get(f"{provider}:{model}")
    if card is None:
        return None
    return _priced_cost(card, int(card["max_input_units"]),
                        int(card["max_output_units"]), 0)


def normalize_attempts(
    attempts: Sequence[Mapping[str, Any]], *, operation_id: UUID,
    component: str = "llm", category: str = "llm",
) -> list[UsageEvent]:
    """One content-free event per network attempt, including known billable errors.

    Skipped candidates never reached a provider. Missing usage on a network
    attempt becomes a marked estimate so unknown charges cannot become zero.
    """
    events: list[UsageEvent] = []
    for ordinal, attempt in enumerate(attempts):
        if attempt.get("network_attempted") is False or attempt.get("outcome") in {
            "build_error", "circuit_open",
        }:
            continue
        reading = safe_provider_usage(attempt.get("usage"), image_generated=category == "image")
        provider = str(attempt.get("provider") or "unknown")[:100]
        model = str(attempt.get("model") or "unknown")[:150]
        inputs = _nonnegative_int(reading.get("input_tokens"))
        outputs = _nonnegative_int(reading.get("output_tokens"))
        cached = _nonnegative_int(reading.get("cached_tokens"))
        audio = _nonnegative_int(reading.get("audio_units"))
        image = _nonnegative_int(reading.get("image_units"))
        if inputs is not None and cached is not None and cached > inputs:
            cached = None
        card = _MODELS.get(f"{provider}:{model}")
        reported = _money(reading.get("provider_cost_usd"))
        if reported is not None:
            cost, basis, exact, version = (
                reported, "provider_reported", True, "provider-reported-v1",
            )
        elif card and inputs is not None and outputs is not None:
            cost = _priced_cost(card, inputs, outputs, cached or 0)
            peak = card["pricing_mode"] == "conservative_peak"
            basis, exact, version = (
                "estimated" if peak else "token_priced",
                not peak, RATE_CARD_VERSION,
            )
        else:
            measured = (inputs or 0) + (outputs or 0) + (audio or 0) + (image or 0)
            by_units = Decimal(measured) * _UNKNOWN_PER_MILLION / Decimal(1_000_000)
            cost = max(_UNKNOWN_MIN_USD, by_units).quantize(
                _MONEY_QUANTUM, rounding=ROUND_UP,
            )
            basis, exact, version = "estimated", False, "unknown-conservative-v1"
        events.append(UsageEvent(
            event_id=uuid5(_EVENT_NAMESPACE, f"{operation_id}:{component}:{ordinal}"),
            operation_id=operation_id,
            component=component,
            attempt_ordinal=ordinal,
            category=category,
            provider=provider,
            model=model,
            outcome=str(attempt.get("outcome") or "unknown")[:40],
            input_units=inputs,
            output_units=outputs,
            cached_units=cached,
            audio_units=audio,
            image_units=image,
            cost_usd=cost,
            cost_basis=basis,
            pricing_version=version,
            billing_exact=exact,
        ))
    return events


def operation_cost(events: Sequence[UsageEvent]) -> Decimal:
    return sum((item.cost_usd for item in events), Decimal("0"))


def exact_billable_cost(events: Sequence[UsageEvent]) -> Decimal | None:
    """Future wallet settlement may only use fully supported cost readings."""
    if any(not item.billing_exact for item in events):
        return None
    return operation_cost(events)


def decision_attempt(result: object) -> dict[str, Any]:
    """Jev's typed telemetry into the same content-free attempt contract."""
    model = getattr(result, "model", None)
    input_tokens = getattr(result, "input_tokens", None)
    output_tokens = getattr(result, "output_tokens", None)
    usage = getattr(result, "usage", None)
    if usage is not None:
        input_tokens = getattr(usage, "input_tokens", input_tokens)
        output_tokens = getattr(usage, "output_tokens", output_tokens)
    return {
        "provider": "typesafe", "model": model or "unknown",
        "outcome": "success" if getattr(result, "error_code", None) is None else "error",
        "network_attempted": True,
        "usage": safe_provider_usage({
            "input_tokens": input_tokens, "output_tokens": output_tokens,
            "provider_cost_usd": getattr(result, "cost_usd", None),
        }),
    }
