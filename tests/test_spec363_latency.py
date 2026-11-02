"""SPEC-363 R34/R35: CLASSIFY desiste cedo do DeepSeek; o enrich fica em série quando o plano lê as fichas."""

from __future__ import annotations

import langchain_openai
import pytest

import llm_setup
from llm_setup import ModelTier


@pytest.fixture()
def captured(monkeypatch):
    got: list[dict] = []
    monkeypatch.setattr(langchain_openai, "ChatOpenAI", lambda **kw: got.append(kw) or object())
    monkeypatch.setenv("DEEPSEEK_API_KEY", "test-key")
    monkeypatch.delenv("LLM_TIMEOUT_SECONDS", raising=False)
    monkeypatch.delenv("DEEPSEEK_TIMEOUT_SECONDS", raising=False)
    llm_setup._CLIENT_CACHE.clear()
    yield got
    llm_setup._CLIENT_CACHE.clear()


def test_deepseek_classify_timeout_constant(captured):
    llm_setup._cached_for_tier("deepseek", "deepseek-v4-flash", 0.0, ModelTier.CLASSIFY)
    assert captured[-1]["timeout"] == llm_setup.DEEPSEEK_CLASSIFY_TIMEOUT_S
    assert llm_setup.DEEPSEEK_CLASSIFY_TIMEOUT_S >= 4.0


@pytest.mark.parametrize("tier", [ModelTier.FAST, ModelTier.SMART])
def test_deepseek_fast_smart_keep_12s(captured, tier):
    llm_setup._cached_for_tier("deepseek", "deepseek-v4-flash", 0.0, tier)
    assert captured[-1]["timeout"] == 12.0


def test_classify_and_fast_do_not_share_a_client(captured):
    llm_setup._cached_for_tier("deepseek", "deepseek-v4-flash", 0.0, ModelTier.FAST)
    llm_setup._cached_for_tier("deepseek", "deepseek-v4-flash", 0.0, ModelTier.CLASSIFY)
    assert [c["timeout"] for c in captured] == [12.0, llm_setup.DEEPSEEK_CLASSIFY_TIMEOUT_S]


def test_global_timeout_still_wins(captured, monkeypatch):
    monkeypatch.setenv("LLM_TIMEOUT_SECONDS", "33")
    llm_setup._cached_for_tier("deepseek", "deepseek-v4-flash", 0.0, ModelTier.CLASSIFY)
    assert captured[-1]["timeout"] == 33.0


def test_explicit_deepseek_env_wins_over_tier_constant(captured, monkeypatch):
    monkeypatch.setenv("DEEPSEEK_TIMEOUT_SECONDS", "40")
    llm_setup._cached_for_tier("deepseek", "deepseek-v4-flash", 0.0, ModelTier.CLASSIFY)
    assert captured[-1]["timeout"] == 40.0


def test_other_providers_unaffected(captured, monkeypatch):
    monkeypatch.setenv("GROQ_API_KEY", "k")
    llm_setup._cached_for_tier("groq", "openai/gpt-oss-20b", 0.0, ModelTier.CLASSIFY)
    assert captured[-1]["timeout"] == 90.0


def test_enrich_stays_serial_when_plan_reads_sheets(monkeypatch):
    """R35: `_build_plan` monta o contexto com os NPCs da cena (`npcs_for_context`), e a ficha pode
    renomear/fundir o stub (dedupe) — então o replan precisa ver as fichas já completas."""
    from agents import enrich

    order: list[str] = []
    seen: dict = {}

    def npcs(state):
        order.append("npcs")
        return {"npcs": {"Okka": {"name": "Okka", "completed": True}}}

    def plan(state):
        order.append("plan")
        seen["npcs"] = state.get("npcs")
        return {"needs_replan": False}

    monkeypatch.setattr(enrich, "_enrich_npcs", npcs)
    monkeypatch.setattr(enrich, "_enrich_plan", plan)
    monkeypatch.setattr(enrich.latency_flags, "two_phase_on", lambda: True)
    monkeypatch.setattr(enrich.latency_flags, "replan_after_on", lambda: True)
    out = enrich.enrich_node({"npcs": {"Okka": {"name": "Okka"}}})
    assert order == ["npcs", "plan"]
    assert seen["npcs"]["Okka"].get("completed") is True
    assert out["npcs"]["Okka"]["completed"] is True
