"""SPEC-318 R4: replan do arco depois da entrega (nó `enrich`), 1º turno inline."""

from __future__ import annotations

import random

import pytest
from langchain_core.messages import HumanMessage

import persistence
from agents import campaign_manager as cm
from agents import enrich


def _plan(**kw):
    base = {
        "location": "Nova Arcádia",
        "beats": [{"description": "Explore a praça.", "status": "pending"}] * 3,
        "climax": "Resolva.",
        "current_step": 0,
        "last_planned_turn": 1,
        "arc_title": "A Praça",
    }
    return {**base, **kw}


def _state(**kw):
    st = {
        "game_id": "g318",
        "messages": [HumanMessage(content="olho ao redor")],
        "world": {
            "turn_count": 20,
            "current_location": "Nova Arcádia",
            "current_location_id": "nova_arcadia",
        },
        "campaign_plan": _plan(),
        "needs_replan": False,
    }
    st.update(kw)
    return st


def _stream_nodes(graph, state):
    nodes = []
    for mode, data in graph.stream(state, stream_mode=["updates"]):
        if mode == "updates":
            nodes.extend(data.keys())
    return nodes


def test_needs_inline_plan_only_without_plan():
    assert cm.needs_inline_plan({"campaign_plan": None}) is True
    assert cm.needs_inline_plan({}) is True
    assert cm.needs_inline_plan({"campaign_plan": _plan()}) is False


def test_first_turn_plans_inline(tmp_path, monkeypatch):
    monkeypatch.setattr(persistence, "SAVES_DIR", str(tmp_path))
    from main import app
    from playtest.runner import _build_initial_state

    random.seed(1)
    st = _build_initial_state("explorador", 1)
    st["campaign_plan"] = None
    nodes = _stream_nodes(app, st)
    assert nodes.index("campaign_manager") < nodes.index("dm_router")


def test_existing_plan_skips_campaign_manager_in_front_of_router(tmp_path, monkeypatch):
    monkeypatch.setattr(persistence, "SAVES_DIR", str(tmp_path))
    from main import app
    from playtest.runner import _build_initial_state

    random.seed(2)
    st = _build_initial_state("explorador", 2)
    st["campaign_plan"] = _plan(last_planned_turn=0)
    st["world"] = {**st["world"], "turn_count": 40}  # periódico vencido
    nodes = _stream_nodes(app, st)
    assert "campaign_manager" not in nodes
    assert nodes.index("dm_router") < nodes.index("enrich") < nodes.index("archivist")


def test_flag_off_keeps_legacy_topology(tmp_path, monkeypatch):
    monkeypatch.setattr(persistence, "SAVES_DIR", str(tmp_path))
    monkeypatch.setenv("RPG_REPLAN_AFTER", "off")
    from main import app
    from playtest.runner import _build_initial_state

    random.seed(2)
    st = _build_initial_state("explorador", 2)
    nodes = _stream_nodes(app, st)
    assert nodes.index("campaign_manager") < nodes.index("dm_router")


def test_interval_replan_runs_in_enrich(monkeypatch):
    calls = []

    def fake_build(state, info=None):
        calls.append(state["world"]["turn_count"])
        return _plan(arc_title="Novo Arco", last_planned_turn=state["world"]["turn_count"])

    monkeypatch.setattr(cm, "_build_plan", fake_build)
    out = enrich.enrich_node(_state(campaign_plan=_plan(last_planned_turn=1)))  # 20 - 1 >= 15
    assert calls == [20]
    assert out["campaign_plan"]["arc_title"] == "Novo Arco" and out["needs_replan"] is False
    assert out["chronicle"][-1]["title"] == "Novo Arco"  # arco novo = capítulo novo
    assert "messages" not in out


def test_router_update_arrives_before_any_replan(tmp_path, monkeypatch):
    """O replan SMART só roda depois da update do narrador (entregue pela SPEC-316)."""
    monkeypatch.setattr(persistence, "SAVES_DIR", str(tmp_path))
    order = []

    def fake_build(state, info=None):
        order.append("replan")
        return _plan(last_planned_turn=state["world"]["turn_count"])

    monkeypatch.setattr(cm, "_build_plan", fake_build)
    from main import app
    from playtest.runner import _build_initial_state

    random.seed(3)
    st = _build_initial_state("explorador", 3)
    st["campaign_plan"] = _plan(last_planned_turn=0)
    st["world"] = {**st["world"], "turn_count": 40}
    for mode, data in app.stream(st, stream_mode=["updates"]):
        if mode == "updates":
            order.extend(f"node:{n}" for n in data)
    narrator = next(
        i
        for i, n in enumerate(order)
        if n in ("node:storyteller", "node:npc_actor", "node:loot_agent")
    )
    assert order.index("node:dm_router") < narrator < order.index("replan")
    assert order.index("replan") < order.index("node:archivist")


def test_next_turn_uses_new_plan(monkeypatch):
    monkeypatch.setattr(
        cm, "_build_plan", lambda s, i=None: _plan(arc_title="Arco 2", last_planned_turn=20)
    )
    st = _state(campaign_plan=_plan(last_planned_turn=1))
    st = {**st, **enrich.enrich_node(st)}
    assert st["campaign_plan"]["arc_title"] == "Arco 2"
    assert cm._should_replan({**st, "world": {**st["world"], "turn_count": 21}}) is False


def test_failed_replan_keeps_old_plan_and_flags_retry(monkeypatch):
    monkeypatch.setattr(cm, "_build_plan", lambda s, i=None: None)
    out = enrich.enrich_node(_state(campaign_plan=_plan(last_planned_turn=1)))
    assert out == {"needs_replan": True}


def test_no_replan_during_combat_or_when_not_due(monkeypatch):
    monkeypatch.setattr(cm, "_build_plan", lambda *a, **k: pytest.fail("não devia replanejar"))
    assert enrich.enrich_node(_state(campaign_plan=_plan(last_planned_turn=18))) == {}
    due = _state(campaign_plan=_plan(last_planned_turn=1), combat={"active": True})
    assert enrich.enrich_node(due) == {}


def test_flag_off_disables_enrich_replan(monkeypatch):
    monkeypatch.setenv("RPG_REPLAN_AFTER", "off")
    monkeypatch.setattr(cm, "_build_plan", lambda *a, **k: pytest.fail("não devia replanejar"))
    assert enrich.enrich_node(_state(campaign_plan=_plan(last_planned_turn=1))) == {}


def test_english_beat_retry_is_fast_tier(monkeypatch):
    from llm_setup import ModelTier

    tiers = []

    class _LLM:
        def __init__(self, english):
            self.english = english

        def with_structured_output(self, model):
            beats = (
                ["Investigate the old well", "Meet the stranger", "Face the shadow"]
                if self.english
                else ["Investigue o poço", "Encontre o estranho", "Enfrente a sombra"]
            )
            plan = model(
                location="Nova Arcádia",
                beats=beats,
                climax="Confronto final no poço.",
                arc_title="O Poço",
            )
            return type("I", (), {"invoke": lambda _s, _m: plan})()

    def fake_get_llm(*, temperature=0.4, tier=ModelTier.SMART):
        tiers.append(tier)
        return _LLM(english=len(tiers) == 1)

    monkeypatch.setattr(cm, "get_llm", fake_get_llm)
    monkeypatch.setattr(
        cm,
        "build_context_pack",
        lambda *a, **k: type("P", (), {"lore_block": "", "world_state_block": ""})(),
    )
    plan = cm._build_plan(_state())
    assert plan is not None
    assert tiers == [ModelTier.SMART, ModelTier.FAST]
