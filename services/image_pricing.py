"""Versioned Standard direct Images API prices, distinct from commercial quote profiles."""
from __future__ import annotations

import json
from dataclasses import replace
from datetime import datetime, timedelta, timezone, UTC
from decimal import ROUND_UP, Decimal, localcontext
from hashlib import sha256
from pathlib import Path

from services.shard_pricing import PricingUnavailable, rate_card_max_age
from services.usage_metering import UsageEvent

_BYTES = (Path(__file__).resolve().parents[1] / "data/pricing/image_rate_card_2026-10-12.json").read_bytes()
_CARD = json.loads(_BYTES)
IMAGE_PRICING_VERSION = _CARD["version"] + "-" + sha256(_BYTES).hexdigest()[:16]


def require_image_prices(model: str, at: datetime) -> None:
    observed = datetime.fromisoformat(_CARD["observed_at"])
    age = at.astimezone(UTC) - observed
    if model != _CARD["model"] or not timedelta(0) <= age <= rate_card_max_age():
        raise PricingUnavailable("image model/rate card unavailable or stale")


def price_image_event(event: UsageEvent, usage: dict) -> UsageEvent:
    """Price observed tokens only; incomplete/malformed counters remain non-exact."""
    if event.cost_basis == "provider_reported":
        return event
    if event.provider != "openai" or event.model != _CARD["model"] or usage.get("image_counter_error"):
        return event
    keys = ("input_tokens", "output_tokens", "text_input_tokens", "image_input_tokens")
    if any(not isinstance(usage.get(key), int) or isinstance(usage.get(key), bool) or usage[key] < 0 for key in keys):
        return event
    if usage["input_tokens"] != usage["text_input_tokens"] + usage["image_input_tokens"]:
        return event
    # The pinned model only outputs images. Future output detail shapes must
    # corroborate that fact; text output or a partial breakdown is not billable.
    if ("image_output_tokens" in usage or "text_output_tokens" in usage) and (
            usage.get("image_output_tokens") != usage["output_tokens"]
            or usage.get("text_output_tokens") != 0):
        return event
    with localcontext() as context:
        context.prec = 100
        cost = ((Decimal(usage["text_input_tokens"]) * Decimal(_CARD["text_input_per_million"])
                 + Decimal(usage["image_input_tokens"]) * Decimal(_CARD["image_input_per_million"])
                 + Decimal(usage["output_tokens"]) * Decimal(_CARD["image_output_per_million"]))
                / Decimal(1_000_000)).quantize(Decimal("0.000000001"), rounding=ROUND_UP)
    return replace(event, cost_usd=cost, cost_basis="rate_card", billing_exact=True,
                   pricing_version=IMAGE_PRICING_VERSION)
