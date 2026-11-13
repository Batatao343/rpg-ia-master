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
