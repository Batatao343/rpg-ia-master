"""SPEC-237: immutable embedding price card (separate from the pinned text rate card).

Embedding calls only report input tokens, so they cannot use the text card's
input+output pricing. A new card is a new file/version; the pinned
``rate_card_2026-10-08.json`` is never mutated.
"""
from __future__ import annotations

import json
from decimal import ROUND_UP, Decimal
from hashlib import sha256
from pathlib import Path
from typing import Any

_BYTES = (Path(__file__).resolve().parents[1] /
          "data/pricing/embedding_rate_card_2026-10-17.json").read_bytes()
_CARD = json.loads(_BYTES)
EMBEDDING_PRICING_VERSION: str = _CARD["version"] + "-" + sha256(_BYTES).hexdigest()[:16]
_MODELS: dict[str, dict[str, Any]] = _CARD["models"]
_QUANTUM = Decimal("0.000000001")


def embedding_cost(provider: str, model: str, input_tokens: int) -> Decimal | None:
    """Cost in USD for ``input_tokens``, or None when the model is not on the card."""
    card = _MODELS.get(f"{provider}:{model}")
    if card is None or card.get("mode") != "tokens":
        return None
    amount = Decimal(input_tokens) * Decimal(card["input_per_million"]) / Decimal(1_000_000)
    return amount.quantize(_QUANTUM, rounding=ROUND_UP)
