"""SPEC-237: Jina embeddings are priced by tokens from a versioned embedding rate card."""
from __future__ import annotations

from decimal import Decimal
from hashlib import sha256
from pathlib import Path
from uuid import UUID, uuid4

import httpx

import rag
from services import embedding_pricing
from services.usage_metering import normalize_attempts, operation_cost

OP = UUID("00000000-0000-0000-0000-000000000237")


def _attempt(provider="jina", model="jina-embeddings-v3", usage=None, outcome="response"):
    return {"provider": provider, "model": model, "outcome": outcome,
            "network_attempted": True, "usage": usage if usage is not None else {}}


def _events(attempts, category="embedding"):
    return normalize_attempts(attempts, operation_id=OP, component="embedding:x",
                              category=category)


def test_jina_embedding_is_priced_by_tokens_not_the_one_dollar_floor():
    [event] = _events([_attempt(usage={"input_tokens": 1_000_000})])
    assert event.cost_usd == Decimal("0.050000000")
    assert event.cost_basis == "token_priced" and event.billing_exact is True
    assert event.pricing_version == embedding_pricing.EMBEDDING_PRICING_VERSION
    assert event.counts_as_spend is True


def test_small_embedding_is_fractions_of_a_cent():
    [event] = _events([_attempt(usage={"input_tokens": 500})])
    assert event.cost_usd == Decimal("0.000025000")


def test_estimated_tokens_are_marked_estimated_but_still_priced_by_card():
    [event] = _events([_attempt(usage={"input_tokens": 400, "units_estimated": 1})])
    assert event.cost_basis == "estimated" and event.billing_exact is False
    assert event.cost_usd == Decimal("0.000020000")


def test_unknown_embedding_model_still_fails_safe():
    [event] = _events([_attempt(provider="gemini", model="models/gemini-embedding-001",
                                usage={"input_tokens": 10})])
    assert event.cost_usd == Decimal("1.000000000")
    assert event.pricing_version == "unknown-conservative-v1"


def test_embedding_card_does_not_price_llm_category():
    [event] = _events([_attempt(usage={"input_tokens": 10})], category="llm")
    assert event.cost_usd == Decimal("1.000000000")


def test_failed_embedding_without_usage_is_still_no_spend():
    [event] = _events([_attempt(usage={}, outcome="http_error")])
    assert event.cost_basis == "failed_no_usage" and event.cost_usd == 0


def test_main_rate_card_is_untouched_and_pinned():
    from services.shard_pricing import INSTALLED_RATE_CARD_SHA256
    path = Path(__file__).resolve().parents[1] / "data/pricing/rate_card_2026-10-08.json"
    assert sha256(path.read_bytes()).hexdigest() == INSTALLED_RATE_CARD_SHA256
    assert "jina" not in path.read_text(encoding="utf-8")


def _jina(handler):
    return rag._JinaEmbeddingsHTTPX(
        api_key="k", model_name="jina-embeddings-v3",
        client=httpx.Client(transport=httpx.MockTransport(handler)))


def test_jina_response_without_usage_estimates_tokens_from_text_length():
    emb = _jina(lambda r: httpx.Response(
        200, request=r, json={"data": [{"index": 0, "embedding": [0.1]}]}))
    captured: list[dict] = []
    with rag.embedding_usage_scope(captured.append):
        emb.embed_query("a" * 100)
    assert captured[0]["usage"] == {"input_tokens": 50, "units_estimated": 1}
    assert "aaaa" not in repr(captured)


def test_jina_response_with_usage_is_not_marked_estimated():
    emb = _jina(lambda r: httpx.Response(200, request=r, json={
        "data": [{"index": 0, "embedding": [0.1]}], "usage": {"total_tokens": 17}}))
    captured: list[dict] = []
    with rag.embedding_usage_scope(captured.append):
        emb.embed_query("hello")
    assert captured[0]["usage"] == {"input_tokens": 17}


def test_forty_turns_of_offline_embedding_usage_stay_far_below_a_text_cap():
    """Staging tripped a 5 BRL cap after ~17 turns at US$ 1 per embedding."""
    total = Decimal("0")
    for turn in range(40):
        events = normalize_attempts(
            [_attempt(usage={"input_tokens": 3000}) for _ in range(3)],
            operation_id=uuid4(), component=f"embedding:{turn}", category="embedding")
        total += operation_cost(events)
    assert total < Decimal("0.05")  # ~US$ 0.018; a 5 BRL cap is ~US$ 0.9


# --- Sol review (SPEC-237) ----------------------------------------------------------------
def _version():
    from datetime import timedelta

    from services.shard_pricing import (
        INSTALLED_RATE_CARD_OBSERVED_AT as at,
    )
    from services.shard_pricing import (
        INSTALLED_RATE_CARD_SHA256,
        ChannelFee,
        PricingVersion,
    )
    from services.usage_metering import RATE_CARD_VERSION

    return at, PricingVersion(
        version_id="sim-237", shard_budget_unit_brl=Decimal("0.03"), fx_usd_brl=Decimal("5"),
        fx_source="sim", fx_observed_at=at, fx_max_age=timedelta(days=1),
        fx_buffer_rate=Decimal("0.10"), rate_card_version=RATE_CARD_VERSION,
        rate_card_sha256=INSTALLED_RATE_CARD_SHA256, rate_card_source="installed",
        rate_card_observed_at=at, rate_card_max_age=timedelta(days=1),
        channel_fees=(ChannelFee("web", Decimal("0.04"), Decimal("0.20")),))


def test_wallet_quote_accepts_exact_embedding_priced_by_the_embedding_card():
    """quote_usage must honor the embedding card, not reject it as a foreign text-card version."""
    from services.shard_pricing import quote_usage

    at, version = _version()
    [llm] = normalize_attempts(
        [{"provider": "groq", "model": "openai/gpt-oss-20b", "outcome": "success",
          "network_attempted": True, "usage": {"input_tokens": 100, "output_tokens": 10}}],
        operation_id=OP, component="llm")
    [emb] = _events([_attempt(usage={"input_tokens": 1000})])
    quote = quote_usage([llm, emb], version, at=at)
    assert quote.provider_cost_usd == llm.cost_usd + emb.cost_usd
    assert embedding_pricing.EMBEDDING_PRICING_VERSION in quote.usage_rate_versions


def test_wallet_quote_rejects_embedding_card_outside_embedding_category():
    from dataclasses import replace

    import pytest

    from services.shard_pricing import PricingUnavailable, quote_usage

    at, version = _version()
    [emb] = _events([_attempt(usage={"input_tokens": 1000})])
    with pytest.raises(PricingUnavailable):
        quote_usage([replace(emb, category="llm")], version, at=at)


def test_jina_unparseable_body_is_estimated_not_the_one_dollar_floor():
    emb = _jina(lambda r: httpx.Response(200, request=r, content=b"not json"))
    captured: list[dict] = []
    with rag.embedding_usage_scope(captured.append):
        try:
            emb.embed_query("b" * 40)
        except ValueError:
            pass
    assert captured[0]["outcome"] == "invalid_response"
    assert captured[0]["usage"] == {"input_tokens": 20, "units_estimated": 1}
    [event] = _events(captured)
    assert event.cost_basis == "estimated" and event.cost_usd < Decimal("0.01")
