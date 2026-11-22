"""Documented direct Images API counter arithmetic and unsupported-format gates."""

from datetime import timedelta
from decimal import Decimal
from uuid import uuid4

import pytest

from services.image_pricing import IMAGE_PRICING_VERSION, price_image_event, require_image_prices
from services.shard_pricing import PricingUnavailable
from services.usage_metering import normalize_attempts, safe_provider_usage
from tests.fakes.local_pricing import card_observed_at

MODEL = "gpt-image-2-2026-04-21"
USAGE = {
    "input_tokens": 150,
    "output_tokens": 100,
    "input_tokens_details": {"text_tokens": 100, "image_tokens": 50},
}


def reading(usage, model=MODEL):
    safe = safe_provider_usage(usage, image_generated=True)
    event = normalize_attempts(
        [
            {
                "provider": "openai",
                "model": model,
                "outcome": "success",
                "network_attempted": True,
                "usage": safe,
            }
        ],
        operation_id=uuid4(),
        component="image",
        category="image",
    )[0]
    return price_image_event(event, safe)


def test_standard_direct_image_tokens_are_priced_without_provider_cost_or_batch_discount():
    event = reading(USAGE)
    # 100 text at $5/M + 50 input image at $8/M + 100 image output at $30/M.
    assert event.billing_exact and event.cost_usd == Decimal("0.003900000")
    assert event.cost_basis == "rate_card" and event.pricing_version == IMAGE_PRICING_VERSION
    safe = safe_provider_usage(USAGE, image_generated=True)
    assert safe_provider_usage(safe, image_generated=True) == safe
    assert "provider_cost_usd" not in safe


@pytest.mark.parametrize(
    "usage",
    [
        {"input_tokens": 150, "output_tokens": 100},
        {**USAGE, "input_tokens_details": {"text_tokens": 100, "image_tokens": 51}},
        {**USAGE, "input_tokens_details": {"text_tokens": True, "image_tokens": 50}},
        {**USAGE, "output_tokens_details": {"text_tokens": 1, "image_tokens": 99}},
        {**USAGE, "output_tokens_details": {"image_tokens": 100}},
        {**USAGE, "input_tokens_details": "invalid"},
        {**USAGE, "output_tokens": -1},
    ],
)
def test_incomplete_or_inconsistent_counter_breakdown_is_not_exact(usage):
    assert not reading(usage).billing_exact


def test_unpublished_model_and_stale_card_cannot_authorize_dispatch(monkeypatch):
    monkeypatch.delenv("RPG_RATE_CARD_MAX_AGE_DAYS", raising=False)
    observed = card_observed_at()["image"]
    with pytest.raises(PricingUnavailable):
        require_image_prices("unpublished", observed)
    with pytest.raises(PricingUnavailable):
        # SPEC-236 R7: default window is 30 d (RPG_RATE_CARD_MAX_AGE_DAYS), was a fixed 7 d.
        require_image_prices(MODEL, observed + timedelta(days=31))
    assert not reading(USAGE, "unpublished").billing_exact


@pytest.mark.parametrize("references", [(), (b"synthetic input",)])
def test_gpt_image_json_and_form_omit_unsupported_response_format(monkeypatch, references):
    import httpx

    from infrastructure.openai_images import OpenAIImageGenerator
    from infrastructure.ports import ImageGenerationInput

    calls = []

    def post(url, **kwargs):
        body = kwargs["data"] if references else kwargs["json"]
        assert "response_format" not in body
        assert url.endswith("/images/edits" if references else "/images/generations")
        calls.append(body)
        return httpx.Response(200, json={"data": [{"b64_json": "eA=="}], "usage": USAGE})

    monkeypatch.setattr(httpx, "post", post)
    result = OpenAIImageGenerator("synthetic-key").generate(
        ImageGenerationInput("private", MODEL, "1024x1536", references)
    )
    assert calls and result.payload == b"x" and result.usage == USAGE


# --- SPEC-425 R1: extra_models ------------------------------------------------- #
def _with_extra(monkeypatch, extra):
    from services import image_pricing

    monkeypatch.setattr(image_pricing, "_CARD", {**image_pricing._CARD, "extra_models": extra})


def test_card_sem_extra_models_so_cobre_o_modelo_do_card():
    from services.image_pricing import priced_models

    assert priced_models() == frozenset({MODEL})


def test_card_prices_extra_models(monkeypatch):
    from services.image_pricing import priced_models

    new = "gpt-image-2.6-sunburst"
    _with_extra(monkeypatch, [new, "gpt-image-2.6-flare"])
    assert priced_models() == frozenset({MODEL, new, "gpt-image-2.6-flare"})
    require_image_prices(new, card_observed_at()["image"] + timedelta(hours=1))
    event = reading(USAGE, model=new)
    # same standard rates as the pinned model: 100*5 + 50*8 + 100*30 per million
    assert event.billing_exact and event.cost_usd == Decimal("0.003900000")
    assert event.cost_basis == "rate_card"


def test_modelo_desconhecido_segue_indisponivel(monkeypatch):
    _with_extra(monkeypatch, ["gpt-image-2.6-sunburst"])
    at = card_observed_at()["image"] + timedelta(hours=1)
    with pytest.raises(PricingUnavailable):
        require_image_prices("gpt-image-2.6-flare", at)
    assert not reading(USAGE, model="gpt-image-2.6-flare").billing_exact
