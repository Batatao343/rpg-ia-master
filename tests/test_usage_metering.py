"""SPEC-182: each billable attempt has provenance and a stable identity."""

from __future__ import annotations

from decimal import Decimal
from uuid import UUID

from services.usage_metering import (
    decision_attempt,
    exact_billable_cost,
    normalize_attempts,
    operation_cost,
    reserve_next_attempt,
    safe_provider_usage,
)


OPERATION = UUID("11111111-1111-4111-8111-111111111111")


def attempt(model: str, outcome: str, *, usage: dict | None = None) -> dict:
    return {
        "provider": "groq", "model": model, "tier": "fast",
        "outcome": outcome, "usage": usage, "network_attempted": True,
    }


def test_fallback_and_structured_retry_count_each_network_attempt() -> None:
    attempts = [
        attempt("openai/gpt-oss-20b", "invalid_structured", usage={
            "input_tokens": 1000, "output_tokens": 100, "cached_tokens": 200,
        }),
        attempt("openai/gpt-oss-20b", "success", usage={
            "input_tokens": 1100, "output_tokens": 200, "cached_tokens": 0,
        }),
        attempt("openai/gpt-oss-120b", "success", usage={
            "input_tokens": 1200, "output_tokens": 300, "cached_tokens": 100,
        }),
    ]
    first = normalize_attempts(attempts, operation_id=OPERATION)
    replay = normalize_attempts(attempts, operation_id=OPERATION)
    assert len(first) == 3
    assert [item.event_id for item in first] == [item.event_id for item in replay]
    assert len(set(item.event_id for item in first)) == 3
    assert all(item.cost_basis == "token_priced" for item in first)
    assert all(item.cost_usd > 0 for item in first)
    assert operation_cost(first) == sum((item.cost_usd for item in first), Decimal("0"))


def test_pre_response_timeout_is_reserved_and_skipped_candidates_are_not_billed() -> None:
    attempts = [
        {**attempt("openai/gpt-oss-20b", "build_error"), "network_attempted": False},
        attempt("openai/gpt-oss-20b", "invoke_error"),
    ]
    events = normalize_attempts(attempts, operation_id=OPERATION)
    assert len(events) == 1
    assert events[0].cost_basis == "estimated"
    assert events[0].billing_exact is False
    assert events[0].cost_usd > 0


def test_billable_error_uses_reported_units_and_provider_cost_takes_precedence() -> None:
    events = normalize_attempts([
        attempt("openai/gpt-oss-20b", "invoke_error", usage={
            "input_tokens": 500, "output_tokens": 80,
            "provider_cost_usd": "0.000123",
        }),
    ], operation_id=OPERATION)
    assert events[0].cost_basis == "provider_reported"
    assert events[0].cost_usd == Decimal("0.000123")
    assert events[0].input_units == 500


def test_unknown_model_is_conservative_and_cannot_authorize_exact_spend() -> None:
    events = normalize_attempts([
        attempt("unknown-future-model", "success", usage={
            "input_tokens": 40, "output_tokens": 10,
        }),
    ], operation_id=OPERATION)
    assert events[0].cost_basis == "estimated"
    assert events[0].cost_usd > 0
    assert events[0].billing_exact is False
    assert reserve_next_attempt("groq", "unknown-future-model") is None
    assert exact_billable_cost(events) is None


def test_versioned_rate_card_and_cached_units_are_retained() -> None:
    events = normalize_attempts([
        attempt("openai/gpt-oss-20b", "success", usage={
            "input_tokens": 1000, "output_tokens": 100, "cached_tokens": 800,
        }),
    ], operation_id=OPERATION)
    assert events[0].cached_units == 800
    assert events[0].pricing_version.startswith("2026-10-08")
    assert events[0].cost_usd == Decimal("0.00007460")


def test_operation_id_and_ordinal_change_event_identity() -> None:
    values = [attempt("openai/gpt-oss-20b", "success", usage={
        "input_tokens": 5, "output_tokens": 2,
    })]
    left = normalize_attempts(values, operation_id=OPERATION)
    right = normalize_attempts(values, operation_id=UUID("22222222-2222-4222-8222-222222222222"))
    assert left[0].event_id != right[0].event_id


def test_decision_image_and_audio_units_share_content_free_normalizer() -> None:
    from types import SimpleNamespace

    decision = SimpleNamespace(model="jev-test", usage=SimpleNamespace(
        input_tokens=12, output_tokens=3), cost_usd=None)
    decision_events = normalize_attempts(
        [decision_attempt(decision)], operation_id=OPERATION,
        component="decision", category="decision",
    )
    image_safe = safe_provider_usage({
        "input_tokens": 40, "output_tokens": 100, "images": 1,
        "prompt": "SECRET_PROMPT", "image_b64": "SECRET_IMAGE",
    }, image_generated=True)
    image_events = normalize_attempts([{
        "provider": "openai", "model": "gpt-image-2", "outcome": "success",
        "network_attempted": True, "usage": image_safe,
    }], operation_id=OPERATION, component="image", category="image")
    audio_events = normalize_attempts([{
        "provider": "future-stt", "model": "unknown", "outcome": "success",
        "network_attempted": True, "usage": {"audio_units": 30},
    }], operation_id=OPERATION, component="speech", category="speech_to_text")
    embedding_events = normalize_attempts([{
        "provider": "jina", "model": "jina-embeddings-v3", "outcome": "success",
        "network_attempted": True, "usage": {"input_tokens": 35},
    }], operation_id=OPERATION, component="embedding", category="embedding")
    assert decision_events[0].input_units == 12
    assert decision_events[0].category == "decision"
    assert image_events[0].image_units == 1
    assert image_events[0].category == "image"
    assert "SECRET" not in repr(image_safe)
    assert audio_events[0].audio_units == 30
    assert embedding_events[0].input_units == 35
    assert all(event.cost_basis == "estimated" for event in
               [*decision_events, *image_events, *audio_events, *embedding_events])
