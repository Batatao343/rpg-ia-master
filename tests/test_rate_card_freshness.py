"""SPEC-409 R3: CI guard against rate cards close to expiry.

``test_installed_rate_cards_not_near_expiry`` is the ONLY test in the suite that reads the real
wall clock against a card date (declared exception). It fails when any installed card is stale
or expires within ``GUARD_DAYS``; the simulated siblings prove the detection with an explicit
``now``. A leaf test (``test_real_clock_only_in_freshness_guard``) keeps it the only one.
"""

from __future__ import annotations

import re
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from services import finops_alerts
from services.finops_alerts import (
    Freshness,
    expiring_rate_cards,
    installed_freshness,
    stale_rate_cards,
)

GUARD_DAYS = 10  # SPEC-409 D2: warn this many days before the 30-day window ends
_RENEW = "renove: docs/spec197/runbooks/budget.md § Renovação de rate cards (SPEC-409)"
_WINDOW_ENV = (
    "RPG_RATE_CARD_MAX_AGE_DAYS",
    "RPG_FINOPS_LLM_CARD_MAX_AGE_DAYS",
    "RPG_RATE_CARD_WARN_DAYS",
)


_CLOCK_NEXT_TO_CARD = re.compile(
    r"installed_freshness\([^)]*\)[^\n]*datetime\.now|datetime\.now[^\n]*installed_freshness"
)


def _assert_cards_not_near_expiry(items: list[Freshness], now: datetime) -> None:
    items = list(items)
    problems = stale_rate_cards(items, now) + expiring_rate_cards(
        items, now, warn=timedelta(days=GUARD_DAYS)
    )
    if not problems:
        return
    by_name = {f.name: f for f in items}
    lines = []
    for alert in problems:
        card = by_name[alert.provider]
        remaining = (card.max_age - (now - card.observed_at)).total_seconds() / 86400
        lines.append(f"{alert.provider}: {remaining:.1f} dias restantes ({alert.kind})")
    raise AssertionError(
        "rate card vencido ou perto de vencer; " + "; ".join(lines) + f". {_RENEW}"
    )


@pytest.fixture(autouse=True)
def _clean_window_env(monkeypatch):
    for name in _WINDOW_ENV:
        monkeypatch.delenv(name, raising=False)


def _expiry(name: str) -> datetime:
    card = next(f for f in installed_freshness() if f.name == name)
    return card.observed_at + card.max_age


def test_guard_fails_nine_days_before_expiry():
    now = _expiry("image") - timedelta(days=9)
    with pytest.raises(AssertionError, match="budget.md"):
        _assert_cards_not_near_expiry(installed_freshness(), now)


def test_guard_fails_when_already_stale():
    now = _expiry("llm") + timedelta(days=1)
    with pytest.raises(AssertionError, match="budget.md"):
        _assert_cards_not_near_expiry(installed_freshness(), now)


def test_guard_passes_eleven_days_before_expiry():
    items = installed_freshness()
    soonest = min(f.observed_at + f.max_age for f in items)
    now = soonest - timedelta(days=11)
    assert now >= max(f.observed_at for f in items), "fixture: all cards observed before now"
    _assert_cards_not_near_expiry(items, now)


def test_guard_names_the_card_and_days_left():
    now = _expiry("embedding") - timedelta(days=9)
    with pytest.raises(AssertionError) as caught:
        _assert_cards_not_near_expiry(installed_freshness(), now)
    assert "embedding" in str(caught.value)
    assert "dias restantes" in str(caught.value)


def test_embedding_card_is_tracked():
    assert "embedding" in {f.name for f in installed_freshness()}
    assert "embedding" in finops_alerts.EXPIRING_CARD_NAMES


def test_installed_rate_cards_not_near_expiry():
    """The single real-clock test: renew the cards before this goes red."""
    _assert_cards_not_near_expiry(installed_freshness(), datetime.now(UTC))


def test_real_clock_only_in_freshness_guard():
    """Source-reading test (inventory case (c)): the wall clock is never handed to the installed
    card freshness outside this file (``datetime.now`` next to ``installed_freshness`` in the
    same statement). Unrelated ``datetime.now`` uses (e.g. the daily cap) are not flagged."""
    tests = Path(__file__).parent
    offenders = []
    for path in sorted(tests.glob("test_*.py")):
        if path.name == Path(__file__).name:
            continue
        text = path.read_text(encoding="utf-8")
        if _CLOCK_NEXT_TO_CARD.search(text):
            offenders.append(path.name)
    assert offenders == []
