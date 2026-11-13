"""SPEC-409 R4: a stale installed rate card makes the finops cron fail (HTTP 500), nothing else does.

Only ``stale_rate_card`` counts (D4): ``rate_card_expiring`` and other blocking alerts such as
``wallet_mismatch`` keep the old contract (``failed`` only for the daily-cap evaluation).
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from fastapi.testclient import TestClient

import api
from infrastructure.finops_reader import FakeFinopsReader
from services import cron_internal, finops_job
from services import finops_alerts as fa
from services.finops_job import run_finops
from services.kill_switches import MemorySwitchStore
from tests.fakes.local_pricing import card_epoch, pin_fresh_installed_cards
from tests.test_spec196_finops import PRICING, group

NOW = card_epoch()
WINDOW = timedelta(days=30)


def _freshness(**ages_days: float) -> list[fa.Freshness]:
    return [
        fa.Freshness(name, NOW - timedelta(days=age), WINDOW) for name, age in ages_days.items()
    ]


def _run(monkeypatch, cards: list[fa.Freshness], **reader_kw) -> dict:
    monkeypatch.setattr(finops_job, "installed_freshness", lambda: cards)
    reader = FakeFinopsReader(pricing_refs=PRICING, **reader_kw)
    return run_finops(reader, now=NOW, switch_store=MemorySwitchStore())


def test_run_finops_fails_when_rate_card_stale(monkeypatch):
    out = _run(monkeypatch, _freshness(llm=31, image=1, speech=1, embedding=1))
    assert out["failed"] == 1
    assert "stale_rate_card" in out["alert_kinds"].split(",")
    assert out["stale_rate_cards"] == "llm"


def test_run_finops_names_every_stale_card(monkeypatch):
    out = _run(monkeypatch, _freshness(llm=1, image=40, speech=1, embedding=35))
    assert out["failed"] == 1 and out["stale_rate_cards"] == "embedding,image"


def test_run_finops_expiring_card_does_not_fail(monkeypatch):
    out = _run(monkeypatch, _freshness(llm=28, image=1, speech=1, embedding=1))
    kinds = out["alert_kinds"].split(",")
    assert "rate_card_expiring" in kinds and "stale_rate_card" not in kinds
    assert out["failed"] == 0 and out["stale_rate_cards"] == ""


def test_run_finops_other_blocking_alert_does_not_fail(monkeypatch):
    cards = _freshness(llm=1, image=1, speech=1, embedding=1)
    out = _run(monkeypatch, cards, groups=[group(ver="unknown-conservative-v1", model="m")])
    assert "unknown_pricing" in out["alert_kinds"].split(",") and out["blocking_alerts"] >= 1
    assert out["failed"] == 0


def test_stale_card_failures_counts_once_per_run():
    alerts = [
        fa.Alert("stale_rate_card", "x", provider="image", blocking=True),
        fa.Alert("stale_rate_card", "y", provider="image", blocking=True),
        fa.Alert("wallet_mismatch", "z", blocking=True),
    ]
    assert fa.stale_card_failures(alerts) == (1, "image")
    assert fa.stale_card_failures([alerts[2]]) == (0, "")


def test_cron_finops_returns_500_on_stale_card(monkeypatch):
    secret = "s" * 40
    monkeypatch.setenv("RPG_CRON_SECRET", secret)
    stale = datetime.now(UTC) - timedelta(days=90)
    monkeypatch.setattr(
        finops_job, "installed_freshness", lambda: [fa.Freshness("image", stale, WINDOW)]
    )
    monkeypatch.setattr(
        cron_internal, "_finops_reader", lambda: FakeFinopsReader(pricing_refs=PRICING)
    )
    monkeypatch.setattr(cron_internal, "_finops_recorder", lambda: None)
    res = TestClient(api.app).post(
        "/internal/cron/finops", headers={"Authorization": f"Bearer {secret}"}
    )
    body = res.json()
    assert res.status_code == 500 and body["ok"] is False and body["failed"] == 1
    assert body["stale_rate_cards"] == "image"


def test_cron_finops_ok_with_fresh_cards(monkeypatch):
    secret = "s" * 40
    monkeypatch.setenv("RPG_CRON_SECRET", secret)
    pin_fresh_installed_cards(monkeypatch, datetime.now(UTC))
    monkeypatch.setattr(
        cron_internal, "_finops_reader", lambda: FakeFinopsReader(pricing_refs=PRICING)
    )
    monkeypatch.setattr(cron_internal, "_finops_recorder", lambda: None)
    res = TestClient(api.app).post(
        "/internal/cron/finops", headers={"Authorization": f"Bearer {secret}"}
    )
    assert res.status_code == 200 and res.json()["ok"] is True
