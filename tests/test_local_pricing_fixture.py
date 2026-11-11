"""Local pricing fixtures must not expire with the wall clock (CI 39089618980).

The synthetic pricing versions seeded by the Postgres/audit tests pin the
installed LLM rate card's ``observed_at`` (required by ``require_fresh``). A
fixed 10-day window therefore expired on 2026-10-18 00:00 UTC, ten days after
the card was observed, and every local paid-effect test started returning
``image_pricing_unavailable``. Production fail-closed behaviour is unchanged.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone, UTC
from decimal import Decimal

import pytest

from services.shard_pricing import (
    INSTALLED_RATE_CARD_OBSERVED_AT,
    INSTALLED_RATE_CARD_SHA256,
    ChannelFee,
    PricingUnavailable,
    PricingVersion,
)
from services.usage_metering import RATE_CARD_VERSION
from tests.fakes.local_pricing import installed_card_max_age_seconds


def _version(max_age_seconds: int, now: datetime) -> PricingVersion:
    return PricingVersion(
        version_id="fixture",
        shard_budget_unit_brl=Decimal("0.03"),
        fx_usd_brl=Decimal("5"),
        fx_source="test",
        fx_observed_at=now,
        fx_max_age=timedelta(seconds=864000),
        fx_buffer_rate=Decimal("0.1"),
        rate_card_version=RATE_CARD_VERSION,
        rate_card_sha256=INSTALLED_RATE_CARD_SHA256,
        rate_card_source="test",
        rate_card_observed_at=INSTALLED_RATE_CARD_OBSERVED_AT,
        rate_card_max_age=timedelta(seconds=max_age_seconds),
        channel_fees=(ChannelFee("web", Decimal("0.04"), Decimal("0.20")),),
    )


@pytest.mark.parametrize("days_after", [0, 9, 10, 11, 60, 400])
def test_fixture_window_stays_fresh_regardless_of_wall_clock(days_after):
    now = INSTALLED_RATE_CARD_OBSERVED_AT + timedelta(days=days_after, hours=2)
    _version(installed_card_max_age_seconds(now), now).require_fresh(now)


def test_old_fixed_window_was_a_time_bomb():
    now = datetime(2026, 10, 18, 2, 21, tzinfo=UTC)
    with pytest.raises(PricingUnavailable):
        _version(864000, now).require_fresh(now)


def test_production_guard_still_rejects_a_card_older_than_its_window():
    now = INSTALLED_RATE_CARD_OBSERVED_AT + timedelta(days=40)
    with pytest.raises(PricingUnavailable):
        _version(30 * 86400, now).require_fresh(now)


def test_card_epoch_is_inside_every_installed_window():
    from services.shard_pricing import DEFAULT_RATE_CARD_MAX_AGE_DAYS
    from tests.fakes.local_pricing import card_epoch, card_observed_at

    seen = card_observed_at()
    assert set(seen) == {"llm", "image", "speech", "embedding"}
    for name, observed in seen.items():
        age = card_epoch() - observed
        assert timedelta(0) <= age <= timedelta(days=DEFAULT_RATE_CARD_MAX_AGE_DAYS), name


def test_pinned_card_clock_passes_with_real_window_logic(monkeypatch):
    from services import finops_alerts
    from tests.fakes.local_pricing import card_epoch, pin_card_clock

    monkeypatch.delenv("RPG_RATE_CARD_MAX_AGE_DAYS", raising=False)
    assert pin_card_clock(monkeypatch) == card_epoch()
    finops_alerts.require_paid_effect("image")  # patched: "now" is the card epoch
    finops_alerts.require_paid_effect("stt")


def test_pinned_card_clock_does_not_disable_the_window(monkeypatch):
    from services.finops_alerts import require_paid_effect
    from tests.fakes.local_pricing import card_epoch

    monkeypatch.delenv("RPG_RATE_CARD_MAX_AGE_DAYS", raising=False)
    late = card_epoch() + timedelta(days=31)
    for category in ("image", "stt"):
        with pytest.raises(PricingUnavailable):
            require_paid_effect(category, now=late)
