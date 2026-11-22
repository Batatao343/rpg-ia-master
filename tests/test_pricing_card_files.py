"""SPEC-409 R1: structure and immutability of the versioned rate-card files (no network).

The old cards stay byte-identical (history); each renewed card has a version that matches its
file name, an ``observed_at`` the readers can parse, positive ``Decimal`` prices and an https
source. Prices themselves are checked against the provider pages by hand (docs/spec409/).
"""

from __future__ import annotations

import json
from datetime import UTC, date, datetime
from decimal import ROUND_UP, Decimal
from hashlib import sha256
from pathlib import Path

import pytest

PRICING = Path(__file__).resolve().parents[1] / "data" / "pricing"

OLD_CARD_SHA256 = {
    "rate_card_2026-10-08.json": "3f62239b04748a6a11a1dc938670a3e9874f718ba84af85d7e07ef1db5f53e99",
    "image_rate_card_2026-10-12.json": "0e1c3d4bea9f865b13a58b070540b58f8cef0fc2eb9a85d4623de5e19faefcb6",
    "speech_rate_card_2026-10-12.json": "103f6069b645695f6ffde3a3b722e5f4ba8e2b8c5117ee02480c1ca9c0781b59",
    "embedding_rate_card_2026-10-17.json": "8e04a9bb33e8be9b0c8a0c068c527c217ee8af1b73f9d9baa643b83fd68a55a7",
}
NEW_CARDS = {
    "llm": "rate_card_2026-11-13.json",
    "image": "image_rate_card_2026-11-13.json",
    "speech": "speech_rate_card_2026-11-13.json",
    "embedding": "embedding_rate_card_2026-11-13.json",
}
_QUANTUM = Decimal("0.000000001")


def _load(name: str) -> dict:
    return json.loads((PRICING / name).read_bytes())


def _positive(value: object) -> Decimal:
    assert isinstance(value, str), f"price must be a decimal string, got {value!r}"
    amount = Decimal(value)
    assert amount > 0
    return amount


@pytest.mark.parametrize("name,expected", sorted(OLD_CARD_SHA256.items()))
def test_old_cards_are_byte_identical(name, expected):
    assert sha256((PRICING / name).read_bytes()).hexdigest() == expected


@pytest.mark.parametrize("kind", sorted(NEW_CARDS))
def test_new_card_version_observed_at_and_source(kind):
    name = NEW_CARDS[kind]
    card = _load(name)
    stamp = name.rsplit("_", 1)[1].removesuffix(".json")
    assert card["version"].startswith(
        {
            "llm": "",
            "image": "openai-image-standard-",
            "speech": "speech-",
            "embedding": "embedding-",
        }[kind]
        + stamp
    )
    observed = datetime.fromisoformat(card["observed_at"])
    if kind == "image":  # require_image_prices subtracts from an aware datetime
        assert observed.tzinfo is not None and observed.utcoffset().total_seconds() == 0
    else:
        assert "T" not in card["observed_at"]
        observed = observed.replace(tzinfo=UTC)
    # A card dated in the future has a negative age and counts as stale: the real-clock guard
    # of tests/test_rate_card_freshness.py catches it, so no wall clock is read here (SPEC-416).
    assert observed.date() == date.fromisoformat(stamp)
    sources = card.get("sources") or [
        m["source"] for m in card.get("models", {}).values() if m.get("source")
    ]
    assert sources and all("https://" in s for s in sources)


def test_image_card_same_model_and_positive_decimals():
    card, old = _load(NEW_CARDS["image"]), _load("image_rate_card_2026-10-12.json")
    assert card["model"] == old["model"] == "gpt-image-2-2026-04-21"
    for key in ("text_input_per_million", "image_input_per_million", "image_output_per_million"):
        assert _positive(card[key]) == Decimal(old[key])  # SPEC-409: no price moved on 13/11
    assert card["cached_input_discount"] is False
    assert "2026-11-10" in card["derivation"] and "2027-02-10" in card["derivation"]


def test_speech_card_max_cost_matches_the_ceilings():
    models = _load(NEW_CARDS["speech"])["models"]
    groq = models["groq:whisper-large-v3-turbo"]
    assert _positive(groq["usd_per_hour"]) == Decimal("0.04")
    assert Decimal(groq["minimum_seconds"]) == 10
    # speech_pricing bounds a clip at 60 s
    groq_bound = (Decimal(groq["usd_per_hour"]) * 60 / 3600).quantize(_QUANTUM, ROUND_UP)
    assert Decimal(groq["max_cost_usd"]) == groq_bound
    oa = models["openai:gpt-4o-mini-transcribe"]
    oa_bound = (
        Decimal(oa["max_input_tokens"]) * _positive(oa["input_per_million"])
        + Decimal(oa["max_output_tokens"]) * _positive(oa["output_per_million"])
    ) / 1_000_000
    assert Decimal(oa["max_cost_usd"]) == oa_bound.quantize(_QUANTUM, ROUND_UP)
    assert (oa["max_input_tokens"], oa["max_output_tokens"]) == (16000, 2000)


def test_embedding_card_flags_the_secondary_source():
    model = _load(NEW_CARDS["embedding"])["models"]["jina:jina-embeddings-v3"]
    assert _positive(model["input_per_million"]) == Decimal("0.05")
    assert "secondary" in model["source"].lower()
    assert "usagepricing.com" in model["source"]


def test_readers_point_at_the_new_cards():
    from services import embedding_pricing, image_pricing, speech_pricing

    assert image_pricing._CARD["version"] == _load(NEW_CARDS["image"])["version"]
    assert speech_pricing._CARD["version"] == _load(NEW_CARDS["speech"])["version"]
    assert embedding_pricing._CARD["version"] == _load(NEW_CARDS["embedding"])["version"]


def test_llm_card_keeps_prices_and_cites_both_groq_pages():
    card, old = _load(NEW_CARDS["llm"]), _load("rate_card_2026-10-08.json")
    assert card["models"].keys() == old["models"].keys()
    for name, model in card["models"].items():
        for key in ("input_per_million", "cached_input_per_million", "output_per_million"):
            assert _positive(model[key]) == Decimal(old["models"][name][key])  # no price moved
        for key in ("max_input_units", "max_output_units", "pricing_mode"):
            assert model[key] == old["models"][name][key]
        if name.startswith("groq:"):
            assert "https://console.groq.com/docs/models " in model["source"] + " "
            assert "https://console.groq.com/docs/model/" in model["source"]


def test_both_llm_card_readers_resolve_the_same_file():
    from services import shard_pricing, usage_metering

    card = PRICING / NEW_CARDS["llm"]
    assert card == shard_pricing._INSTALLED_CARD_PATH
    assert _load(NEW_CARDS["llm"])["version"] == usage_metering.RATE_CARD_VERSION
    assert sha256(card.read_bytes()).hexdigest() == shard_pricing.INSTALLED_RATE_CARD_SHA256
    assert (
        shard_pricing.INSTALLED_RATE_CARD_OBSERVED_AT.date().isoformat()
        == (_load(NEW_CARDS["llm"])["observed_at"])
    )
