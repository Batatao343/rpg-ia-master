"""Rate-card freshness window for synthetic pricing versions in local tests only.

``PricingVersion.require_fresh`` pins ``rate_card_observed_at`` to the installed
card, so a fixed window makes every local fixture expire N days after that card
was observed. Fixtures instead cover the card's current age plus a margin. The
production guard (installed card + its own published window) is untouched.
"""

from __future__ import annotations

from datetime import datetime, timedelta, UTC
from math import ceil

from services.shard_pricing import INSTALLED_RATE_CARD_OBSERVED_AT

FIXTURE_MARGIN = timedelta(days=10)


def installed_card_max_age_seconds(now: datetime | None = None) -> int:
    moment = now or datetime.now(UTC)
    age = max(moment - INSTALLED_RATE_CARD_OBSERVED_AT, timedelta(0))
    return ceil((age + FIXTURE_MARGIN).total_seconds())


def card_observed_at() -> dict[str, datetime]:
    """``observed_at`` (UTC) of the four installed rate cards, read from the loaded JSON."""
    from services.embedding_pricing import _CARD as embedding_card
    from services.image_pricing import _CARD as image_card
    from services.speech_pricing import _CARD as speech_card

    def seen(raw: str) -> datetime:
        moment = datetime.fromisoformat(raw)
        return moment if moment.tzinfo else moment.replace(tzinfo=UTC)

    return {
        "llm": INSTALLED_RATE_CARD_OBSERVED_AT,
        "image": seen(image_card["observed_at"]),
        "speech": seen(speech_card["observed_at"]),
        "embedding": seen(embedding_card["observed_at"]),
    }


def card_epoch() -> datetime:
    """A fixed 'now' just after the newest installed card: every card is fresh, forever."""
    return max(card_observed_at().values()) + timedelta(hours=12)


def pin_card_clock(monkeypatch) -> datetime:
    """Run the real freshness-window logic against ``card_epoch()`` instead of the wall clock.

    Only ``require_paid_effect`` loses its wall clock; the window itself (the 30-day default,
    env overrides cleared so the result never depends on the shell) still decides.
    """
    import functools

    from services import finops_alerts

    for name in (
        "RPG_RATE_CARD_MAX_AGE_DAYS",
        "RPG_FINOPS_LLM_CARD_MAX_AGE_DAYS",
        "RPG_FINOPS_BLOCK_STALE",  # =0 no shell tornaria o gate no-op
    ):
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setattr(
        finops_alerts,
        "require_paid_effect",
        functools.partial(finops_alerts.require_paid_effect, now=card_epoch()),
    )
    return card_epoch()
