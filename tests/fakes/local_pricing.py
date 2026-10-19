"""Rate-card freshness window for synthetic pricing versions in local tests only.

``PricingVersion.require_fresh`` pins ``rate_card_observed_at`` to the installed
card, so a fixed window makes every local fixture expire N days after that card
was observed. Fixtures instead cover the card's current age plus a margin. The
production guard (installed card + its own published window) is untouched.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone, UTC
from math import ceil

from services.shard_pricing import INSTALLED_RATE_CARD_OBSERVED_AT

FIXTURE_MARGIN = timedelta(days=10)


def installed_card_max_age_seconds(now: datetime | None = None) -> int:
    moment = now or datetime.now(UTC)
    age = max(moment - INSTALLED_RATE_CARD_OBSERVED_AT, timedelta(0))
    return ceil((age + FIXTURE_MARGIN).total_seconds())
