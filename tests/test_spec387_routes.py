"""SPEC-387 R13-R16: rota Groq do CLASSIFY, nenhum modelo morto em rota/fixture, router esgotado."""

from __future__ import annotations

from pathlib import Path

import pytest
from langchain_core.messages import AIMessage, HumanMessage

import agents.router as router
import llm_setup
from llm_setup import FallbackLLM, ModelTier

ROOT = Path(__file__).resolve().parents[1]


def test_classify_groq_120b_antes_do_20b():
    groq = [m for p, m in llm_setup.ROUTES[ModelTier.CLASSIFY] if p == "groq"]
    assert groq == ["openai/gpt-oss-120b", "openai/gpt-oss-20b"]
    assert llm_setup.ROUTES[ModelTier.CLASSIFY][0][0] == "deepseek"
    assert llm_setup.ROUTES[ModelTier.CLASSIFY][-1][0] == "gemini"


def test_no_dead_groq_model_in_routes_or_fixtures():
    dead = "llama-3.3-70b-versatile"
    files = [ROOT / "llm_setup.py", *sorted((ROOT / "tests" / "fixtures").rglob("*.py"))]
    files.append(ROOT / "AGENTS.md")
    bad = [f.name for f in files if dead in f.read_text(encoding="utf-8")]
    assert not bad, bad
    assert "llama-3.3" not in (ROOT / "AGENTS.md").read_text(encoding="utf-8")


def _state(text, narration):
    msgs = ([AIMessage(content=narration)] if narration else []) + [HumanMessage(content=text)]
    return {"messages": msgs, "world": {}}


@pytest.fixture
def _exhausted(monkeypatch):
    monkeypatch.setattr(router, "get_llm", lambda **k: FallbackLLM("esgotado"))


def test_router_exhausted_opens_combat_with_cited_target(_exhausted):
    payload = router.dm_router_node(
        _state("Ataco o goblin", "Um goblin rosna entre as pedras e ergue a lâmina.")
    )
    assert payload["next"] == "combat_agent"
    assert router.last_decision()["route_source"] == "hostility_fallback"


def test_router_exhausted_without_citation_story(_exhausted):
    payload = router.dm_router_node(_state("Ataco o goblin", "A estrada está vazia e calma."))
    assert payload["next"] == "storyteller"
