"""SPEC-409 R1.5: staging publication of the renewed LLM card (offline; no DB, no network)."""

from __future__ import annotations

import pytest

from scripts.staging import publish_rate_card, synthetic_data, vercel_env
from services import shard_pricing, usage_metering

REF = "abcdefghijklmnopqrst"


def test_profile_ids_follow_the_pricing_version():
    ids = publish_rate_card.profile_ids("spec409-staging-2026-11-13")
    assert ids == {
        "portrait": "spec409-staging-2026-11-13-portrait",
        "scene": "spec409-staging-2026-11-13-scene",
    }


def test_profile_statements_copy_model_and_ceiling_from_the_old_profiles():
    stmts = publish_rate_card.profile_statements("spec409-staging-2026-11-13")
    assert len(stmts) == 2
    for sql, params in stmts:
        assert "insert into app.image_price_profiles" in sql
        assert "from app.image_price_profiles" in sql  # copies model/size/ceiling, never invents
        assert "on conflict (profile_id) do nothing" in sql
        assert params[1] == "spec409-staging-2026-11-13"
    assert [p[0] for _, p in stmts] == [
        "spec409-staging-2026-11-13-portrait",
        "spec409-staging-2026-11-13-scene",
    ]
    assert [p[3] for _, p in stmts] == ["staging-326-portrait", "staging-326-scene"]


def test_dry_run_prints_the_plan_without_touching_anything(capsys, monkeypatch):
    monkeypatch.delenv("RPG_STAGING_DB_URL", raising=False)
    assert publish_rate_card.main(["--dry-run"]) == 0
    out = capsys.readouterr().out
    assert shard_pricing.INSTALLED_RATE_CARD_SHA256 in out
    assert usage_metering.RATE_CARD_VERSION in out
    assert "spec409-staging-2026-11-13-portrait" in out


def test_live_run_requires_matching_staging_confirmation(monkeypatch):
    monkeypatch.setenv("SUPABASE_PROJECT_REF", REF)
    monkeypatch.setenv("RPG_STAGING_DB_URL", "postgresql://postgres.zzzzzzzzzzzzzzzzzzzz:x@h/db")
    monkeypatch.setattr(publish_rate_card.common, "load_dotenv_quietly", lambda: None)
    with pytest.raises(SystemExit):
        publish_rate_card.main([])  # no --confirm-staging
    with pytest.raises(SystemExit):
        publish_rate_card.main(["--confirm-staging", REF])  # DSN of another project


PRICING_ID = "spec409-staging-2026-11-13"


def _installed_row() -> tuple:
    return (
        usage_metering.RATE_CARD_VERSION,
        shard_pricing.INSTALLED_RATE_CARD_SHA256,
        shard_pricing.INSTALLED_RATE_CARD_OBSERVED_AT,
    )


def _profile_rows() -> list[tuple]:
    return [(pid,) for pid in publish_rate_card.profile_ids(PRICING_ID).values()]


def test_published_rows_matching_the_installed_card_have_no_problems():
    assert publish_rate_card.published_problems(PRICING_ID, _installed_row(), _profile_rows()) == []


def test_preexisting_row_with_another_hash_is_reported():
    version, _, observed_at = _installed_row()
    stale = (version, "0" * 64, observed_at)
    problems = publish_rate_card.published_problems(PRICING_ID, stale, _profile_rows())
    assert problems == ["rate_card_sha256 differs from the installed card"]


def test_missing_version_row_or_profile_is_reported():
    assert publish_rate_card.published_problems(PRICING_ID, None, []) == [
        f"pricing_versions row {PRICING_ID} is missing"
    ]
    problems = publish_rate_card.published_problems(
        PRICING_ID, _installed_row(), _profile_rows()[:1]
    )
    assert problems == [f"image_price_profiles missing: {PRICING_ID}-scene"]


def test_seed_prereqs_keep_the_wallet_ids_and_vercel_env_agrees():
    assert synthetic_data.WALLET_PRICING == publish_rate_card.DEFAULT_PRICING_ID
    assert vercel_env.NON_SECRET_LITERALS["RPG_SPEECH_PRICING_VERSION"] == (
        synthetic_data.WALLET_PRICING
    )
    ids = publish_rate_card.profile_ids(synthetic_data.WALLET_PRICING)
    assert {
        "RPG_IMAGE_PRICE_PROFILE_PORTRAIT": ids["portrait"],
        "RPG_IMAGE_PRICE_PROFILE_SCENE": ids["scene"],
    } == vercel_env.DYNAMIC_ART_PRICE_PROFILES
