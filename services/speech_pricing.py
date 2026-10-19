"""Immutable speech prices, observed bounds and content-free usage normalization."""
from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone, UTC
from decimal import ROUND_UP, Decimal, InvalidOperation
from hashlib import sha256
from pathlib import Path
from uuid import UUID, uuid5

from services.usage_metering import UsageEvent

_BYTES = (Path(__file__).resolve().parents[1] /
          "data/pricing/speech_rate_card_2026-10-12.json").read_bytes()
_CARD = json.loads(_BYTES)
SPEECH_PRICING_VERSION = _CARD["version"] + "-" + sha256(_BYTES).hexdigest()[:16]
_MODELS = _CARD["models"]
_NAMESPACE = UUID("8e46a1b5-6a92-44d0-b25d-5c476f90806d")
_QUANTUM = Decimal("0.000000001")


def speech_bound(provider: str, model: str) -> Decimal | None:
    card = _MODELS.get(f"{provider}:{model}")
    return Decimal(card["max_cost_usd"]) if card else None


def require_speech_prices(at: datetime) -> None:
    observed = datetime.fromisoformat(_CARD["observed_at"]).replace(tzinfo=UTC)
    age = at.astimezone(UTC) - observed
    from services.shard_pricing import PricingUnavailable, rate_card_max_age
    if age < timedelta(0) or age > rate_card_max_age():
        raise PricingUnavailable("speech rate card stale")


def _decimal(value: object) -> Decimal | None:
    if isinstance(value, bool) or value is None:
        return None
    try:
        result = Decimal(str(value))
    except (InvalidOperation, ValueError, TypeError):
        return None
    return result if result.is_finite() and result >= 0 else None


def _integer(value: object) -> int | None:
    return value if isinstance(value, int) and not isinstance(value, bool) and value >= 0 else None


def is_definitive_no_charge(status: int) -> bool:
    """SPEC-236 R5 (D-C default): a received HTTP 4xx (incl. 429) is a definitive rejection
    without charge. 5xx, timeouts and cancellations stay ``unknown`` (held)."""
    return isinstance(status, int) and not isinstance(status, bool) and 400 <= status <= 499


def speech_event(operation_id: UUID, ordinal: int, provider: str, model: str,
                 outcome: str, usage: dict, *, duration: Decimal | None = None,
                 definitive_no_charge: bool = False) -> UsageEvent:
    """Unknown attempts remain nonbillable estimates; no transcript enters this DTO.

    A definitive provider rejection is an EXACT zero (it can settle), never spend."""
    if definitive_no_charge:
        return UsageEvent(uuid5(_NAMESPACE, f"{operation_id}:{ordinal}"), operation_id,
                          "speech", ordinal, "speech_to_text", provider, model, outcome,
                          None, None, None, None, None, Decimal("0"), "definitive_no_charge",
                          SPEECH_PRICING_VERSION, True, False)
    card = _MODELS.get(f"{provider}:{model}")
    inputs, outputs = _integer(usage.get("input_tokens")), _integer(usage.get("output_tokens"))
    audio = _integer(usage.get("audio_tokens"))
    if usage.get('type') == 'duration':
        seconds = _decimal(usage.get('seconds'))
        if seconds is not None and seconds <= 60:
            audio = int((seconds * 1000).to_integral_value(rounding=ROUND_UP))
    reported = _decimal(usage.get("provider_cost_usd"))
    bound = speech_bound(provider, model) or Decimal("1")
    cost, exact, basis = bound, False, "estimated"
    if reported is not None and reported <= bound:
        cost, exact, basis = reported, True, "provider_reported"
    elif card and card["mode"] == "duration" and duration is not None and Decimal("0") < duration <= 60:
        cost = (max(duration, Decimal(card["minimum_seconds"])) *
                Decimal(card["usd_per_hour"]) / 3600).quantize(_QUANTUM, rounding=ROUND_UP)
        audio = int((duration * 1000).to_integral_value(rounding=ROUND_UP))
        exact, basis = True, "rate_card"
    elif (card and card["mode"] == "tokens" and inputs is not None and outputs is not None
          and inputs <= card["max_input_tokens"] and outputs <= card["max_output_tokens"]
          and audio == inputs and usage.get("text_tokens") == 0):
        cost = ((Decimal(inputs) * Decimal(card["input_per_million"]) +
                 Decimal(outputs) * Decimal(card["output_per_million"])) /
                1_000_000).quantize(_QUANTUM, rounding=ROUND_UP)
        exact, basis = True, "rate_card"
    return UsageEvent(uuid5(_NAMESPACE, f"{operation_id}:{ordinal}"), operation_id,
                      "speech", ordinal, "speech_to_text", provider, model, outcome,
                      inputs, outputs, None, audio, None, cost, basis,
                      SPEECH_PRICING_VERSION, exact)
