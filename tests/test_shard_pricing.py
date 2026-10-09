"""SPEC-183 financial vectors and conservation properties (offline)."""

from __future__ import annotations

from dataclasses import replace
from datetime import datetime, timedelta, timezone
from decimal import Decimal, ROUND_CEILING, ROUND_FLOOR
import json
from random import Random
from uuid import uuid4

import pytest

from services.shard_pricing import (
    INSTALLED_RATE_CARD_OBSERVED_AT, INSTALLED_RATE_CARD_SHA256, ChannelFee,
    PricingUnavailable, PricingVersion, PurchaseSku,
    contribution_report, quote_purchase, quote_usage, version_from_record,
)
from services.usage_metering import RATE_CARD_VERSION, UsageEvent, normalize_attempts


NOW = datetime(2026, 10, 8, 12, tzinfo=timezone.utc)


def version(**changes) -> PricingVersion:
    base = PricingVersion(
        version_id="simulation-183", shard_budget_unit_brl=Decimal("0.03"),
        fx_usd_brl=Decimal("5"), fx_source="simulated FX",
        fx_observed_at=NOW, fx_max_age=timedelta(days=1),
        fx_buffer_rate=Decimal("0.10"), rate_card_version=RATE_CARD_VERSION,
        rate_card_sha256=INSTALLED_RATE_CARD_SHA256,
        rate_card_source="installed rate card",
        rate_card_observed_at=INSTALLED_RATE_CARD_OBSERVED_AT,
        rate_card_max_age=timedelta(days=1),
        channel_fees=(ChannelFee("web", Decimal("0.04"), Decimal("0.20")),
                      ChannelFee("play", Decimal("0.10"), Decimal("0"))),
    )
    return replace(base, **changes)


def sku(channel: str, gross: str, units: int) -> PurchaseSku:
    return PurchaseSku("example-" + channel, channel, Decimal(gross), units, "simulation-183")


def test_golden_channel_vectors_include_fixed_fee_and_different_gross() -> None:
    web = quote_purchase(sku("web", "10.50", 311), version(), at=NOW)
    play = quote_purchase(sku("play", "11.00", 311), version(), at=NOW)
    assert (web.channel_fee_brl, web.target_margin_brl, web.variable_budget_brl) == (
        Decimal("0.62"), Decimal("0.53"), Decimal("9.35"),
    )
    assert (play.channel_fee_brl, play.target_margin_brl, play.variable_budget_brl) == (
        Decimal("1.10"), Decimal("0.55"), Decimal("9.35"),
    )
    assert web.shard_milli_granted == play.shard_milli_granted == 311
    assert web.rounding_reserve_brl == play.rounding_reserve_brl == Decimal("0.02")
    assert web.contribution_margin_brl == Decimal("0.55")
    assert play.contribution_margin_brl == Decimal("0.57")
    assert web.tax_brl == play.tax_brl == 0
    summary = contribution_report([web, play], fixed_infra_brl=Decimal("37.25"))
    assert summary["contribution_margin_brl"] == Decimal("1.12")
    assert summary["fixed_infra_brl"] == Decimal("37.25")


def test_golden_usage_ceil_buffer_and_pricing_provenance() -> None:
    event = UsageEvent(
        event_id=uuid4(), operation_id=uuid4(), component="llm", attempt_ordinal=0,
        category="llm", provider="groq", model="20b", outcome="success",
        input_units=1, output_units=1, cached_units=0, audio_units=None,
        image_units=None, cost_usd=Decimal("0.019"),
        cost_basis="provider_reported", pricing_version="provider-reported-v1",
        billing_exact=True,
    )
    quote = quote_usage([event], version(), at=NOW)
    assert quote.fx_with_buffer == Decimal("5.50")
    assert quote.variable_cost_brl == Decimal("0.10450")
    assert quote.shard_milli_debited == 4
    assert quote.debit_budget_brl == Decimal("0.12")
    assert quote.rounding_reserve_brl == Decimal("0.01550")
    assert quote.usage_event_ids == (str(event.event_id),)
    assert quote.usage_rate_versions == ("provider-reported-v1",)


def test_quote_rejects_impossible_or_mismatched_sku() -> None:
    with pytest.raises(PricingUnavailable):
        quote_purchase(sku("web", "0.10", 1), version(), at=NOW)
    with pytest.raises(PricingUnavailable):
        quote_purchase(sku("web", "10.50", 312), version(), at=NOW)
    with pytest.raises(PricingUnavailable):
        quote_purchase(sku("web", "10.50", 311), version(version_id="another"), at=NOW)
    with pytest.raises(PricingUnavailable):
        quote_purchase(sku("ios", "10.50", 311), version(), at=NOW)


@pytest.mark.parametrize("changes", [
    {"fx_source": ""}, {"rate_card_source": ""},
    {"fx_observed_at": NOW - timedelta(days=2)},
    {"rate_card_observed_at": NOW - timedelta(days=2)},
    {"rate_card_observed_at": NOW.replace(hour=23, minute=59)},
    {"rate_card_version": "missing-card"},
    {"rate_card_sha256": "0" * 64},
])
def test_missing_or_stale_fx_rate_card_fails_closed(changes: dict) -> None:
    try:
        selected = version(**changes)
    except PricingUnavailable:
        return
    with pytest.raises(PricingUnavailable):
        quote_purchase(sku("web", "10.50", 311), selected, at=NOW)


def test_estimated_or_wrong_card_usage_cannot_be_debited() -> None:
    unknown = normalize_attempts([{
        "provider": "unknown", "model": "x", "outcome": "success",
        "network_attempted": True, "usage": {"input_tokens": 10},
    }], operation_id=uuid4())[0]
    with pytest.raises(PricingUnavailable):
        quote_usage([unknown], version(), at=NOW)
    exact = normalize_attempts([{
        "provider": "groq", "model": "openai/gpt-oss-20b", "outcome": "success",
        "network_attempted": True,
        "usage": {"input_tokens": 1000, "output_tokens": 100},
    }], operation_id=uuid4())[0]
    assert quote_usage([exact], version(), at=NOW).shard_milli_debited > 0
    with pytest.raises(PricingUnavailable):
        quote_usage([replace(exact, pricing_version="other")], version(), at=NOW)
    with pytest.raises(PricingUnavailable):
        quote_usage([exact, replace(exact, event_id=uuid4(), operation_id=uuid4())],
                    version(), at=NOW)


def test_financial_property_conservation_and_margin_1000_cases() -> None:
    random = Random(183)
    for _ in range(1000):
        gross = Decimal(random.randint(200, 20000)) / 100
        fee_pct = Decimal(random.randint(0, 30)) / 100
        fee_fixed = Decimal(random.randint(0, 300)) / 100
        unit = Decimal(random.randint(1, 100)) / 10000
        selected = version(
            shard_budget_unit_brl=unit,
            channel_fees=(ChannelFee("web", fee_pct, fee_fixed),),
        )
        fee = (gross * fee_pct + fee_fixed).quantize(Decimal("0.01"), rounding=ROUND_CEILING)
        target = (gross * Decimal("0.05")).quantize(Decimal("0.01"), rounding=ROUND_CEILING)
        budget = gross - fee - target
        if budget <= 0:
            continue
        units = int((budget / unit).to_integral_value(rounding=ROUND_FLOOR))
        if units <= 0:
            continue
        receipt = quote_purchase(sku("web", str(gross), units), selected, at=NOW)
        assert receipt.allocated_budget_brl <= receipt.variable_budget_brl
        assert receipt.variable_budget_brl < receipt.allocated_budget_brl + unit
        assert Decimal("0") <= receipt.rounding_reserve_brl < unit
        assert receipt.contribution_margin_brl >= gross * Decimal("0.05")
        assert receipt.gross_brl == (
            receipt.channel_fee_brl + receipt.tax_brl + receipt.allocated_budget_brl
            + receipt.contribution_margin_brl
        )


def test_usage_property_ceil_never_underfunds_1000_cases() -> None:
    random = Random(184)
    for _ in range(1000):
        unit = Decimal(random.randint(1, 100)) / 10000
        cost = Decimal(random.randint(0, 10_000_000)) / 1_000_000_000
        selected = version(shard_budget_unit_brl=unit)
        event = UsageEvent(
            uuid4(), uuid4(), "llm", 0, "llm", "groq", "20b", "success",
            None, None, None, None, None, cost, "provider_reported",
            "provider-reported-v1", True,
        )
        quote = quote_usage([event], selected, at=NOW)
        assert quote.debit_budget_brl >= quote.variable_cost_brl
        assert Decimal("0") <= quote.rounding_reserve_brl < unit


def test_extreme_numeric_bounds_use_exact_ratio_or_fail_closed() -> None:
    selected = version(
        shard_budget_unit_brl=Decimal("0.0000000001"),
        fx_usd_brl=Decimal("9999999999.9999999999"),
        fx_buffer_rate=Decimal("0"),
    )
    event = UsageEvent(
        uuid4(), uuid4(), "llm", 0, "llm", "groq", "20b", "success",
        None, None, None, None, None, Decimal("0.09"), "provider_reported",
        "provider-reported-v1", True,
    )
    assert quote_usage([event], selected, at=NOW).shard_milli_debited == 9_000_000_000_000_000_000
    with pytest.raises(PricingUnavailable, match="bigint"):
        quote_usage([replace(event, cost_usd=Decimal("999999999.999999999"))],
                    selected, at=NOW)
    with pytest.raises(PricingUnavailable, match="bigint"):
        quote_purchase(sku("web", "9999999999999999.99", 1), selected, at=NOW)
    with pytest.raises(PricingUnavailable, match="escala"):
        version(shard_budget_unit_brl=Decimal("0.00000000001"))


def test_version_loader_rejects_floats_and_roundtrips_text_config() -> None:
    value = version()
    record = {
        "version_id": value.version_id, "shard_budget_unit_brl": "0.03",
        "fx_usd_brl": "5", "fx_source": "simulated FX",
        "fx_observed_at": NOW.isoformat(), "fx_max_age_seconds": 86400,
        "fx_buffer_rate": "0.10", "rate_card_version": RATE_CARD_VERSION,
        "rate_card_sha256": INSTALLED_RATE_CARD_SHA256,
        "rate_card_source": "installed rate card",
        "rate_card_observed_at": INSTALLED_RATE_CARD_OBSERVED_AT.isoformat(),
        "rate_card_max_age_seconds": 86400,
        "channel_fees": {"web": {"percentage": "0.04", "fixed_brl": "0.20"},
                         "play": {"percentage": "0.10", "fixed_brl": "0"}},
    }
    assert version_from_record(json.loads(json.dumps(record))) == value
    record["fx_usd_brl"] = 5.0
    with pytest.raises(PricingUnavailable):
        version_from_record(record)


def test_cli_reports_only_simulation_and_keeps_fixed_infra_separate(tmp_path, capsys) -> None:
    from scripts.pricing_report import main

    version_file = tmp_path / "version.json"
    sku_file = tmp_path / "sku.json"
    version_file.write_text(json.dumps({
        "version_id": "simulation-183", "shard_budget_unit_brl": "0.03",
        "fx_usd_brl": "5", "fx_source": "simulated FX",
        "fx_observed_at": NOW.isoformat(), "fx_max_age_seconds": 86400,
        "fx_buffer_rate": "0.10", "rate_card_version": RATE_CARD_VERSION,
        "rate_card_sha256": INSTALLED_RATE_CARD_SHA256,
        "rate_card_source": "installed rate card",
        "rate_card_observed_at": INSTALLED_RATE_CARD_OBSERVED_AT.isoformat(),
        "rate_card_max_age_seconds": 86400,
        "channel_fees": {"web": {"percentage": "0.04", "fixed_brl": "0.20"}},
    }), encoding="utf-8")
    sku_file.write_text(json.dumps({
        "sku_id": "example-web", "channel": "web", "gross_brl": "10.50",
        "shard_milli": 311, "pricing_version": "simulation-183",
    }), encoding="utf-8")
    assert main(["--version-json", str(version_file), "--sku-json", str(sku_file),
                 "--usage-usd", "0.019", "--fixed-infra-brl", "37.25",
                 "--at", NOW.isoformat()]) == 0
    result = json.loads(capsys.readouterr().out)
    assert result["simulation_only"] is True
    assert result["purchase"]["shard_milli_granted"] == 311
    assert result["usage"]["shard_milli_debited"] == 4
    assert result["report"]["fixed_infra_brl"] == "37.25"
    assert result["report"]["contribution_margin_brl"] == "0.55"
