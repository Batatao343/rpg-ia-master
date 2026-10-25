"""SPEC-311 Etapa 5 — integração: nenhuma chamada LLM nova (R27) e saves antigos (R26)."""

from __future__ import annotations

import re

import pytest
from langchain_core.messages import HumanMessage

import agents.campaign_manager as cm
import agents.loot as loot
import agents.npc as npc
import agents.storyteller as stt
import gamedata
from services import economy
from services import planner_context as pc
from services import reputation as rep
from tests.test_ambient_consumers import _Spy, _story_state
from tests.test_spec311_price_reasons import _keeper, _shop_state


@pytest.fixture(autouse=True)
def _env(monkeypatch):
    monkeypatch.setenv("RPG_WORLD_ENGINE", "on")
    monkeypatch.setenv("RPG_CALENDAR", "on")
    monkeypatch.setenv("RPG_NPC_KNOWLEDGE", "off")


def _skall_cerco(st: dict) -> dict:
    st["world_projection"] = {"location_states": {"skallgard": {"state": "cerco", "severity": 2}}}
    return st


def test_invoke_count_unchanged_storyteller(monkeypatch):
    """R27: o gatilho do mundo só liga uma flag; o turno faz as mesmas chamadas."""
    counts = []
    for cause in (None, "crise_regiao"):
        spy = _Spy()
        monkeypatch.setattr(pc, "world_replan_cause", lambda *a, _c=cause, **k: _c)
        monkeypatch.setattr(stt, "get_llm", lambda *a, _s=spy, **k: _s)
        stt.storyteller_node(_story_state())
        counts.append(len(spy.prompts))
    assert counts[0] == counts[1] >= 1


def test_invoke_count_unchanged_loot(monkeypatch):
    """R27: com e sem motivos de preço o loot narra com a MESMA 1 chamada."""
    import gamedata as gd

    counts = []
    for scenario in ("plain", "cerco1"):
        spy = _Spy()
        monkeypatch.setattr(loot, "get_llm", lambda *a, _s=spy, **k: _s)
        st = _shop_state("quinquilharias_brekmar", scenario, "compro algo")
        item = next(iter(economy.merchant_stock(st, "brekmar")[1]))
        st["messages"][0].content = f"compro {gd.ARTIFACTS_DB[item]['name']}"
        out = loot.loot_node(st)
        assert "[SISTEMA]" in out["messages"][0].content
        counts.append(len(spy.prompts))
    assert counts[0] == counts[1]
    # com cerco, o contexto levou a linha de motivos; sem, não
    assert "MOTIVOS DO PREÇO" in spy.prompts[-1]


def _keeper_state() -> dict:
    st = _keeper(_shop_state("ferreiro_skallgard", "cerco2", "oi"), "ferreiro_skallgard", 5)
    key, row = rep.find_keeper(st, "ferreiro_skallgard")
    base = _story_state({"current_location_id": "skallgard", "current_location": "Skallgard"})
    base.update(
        factions=gamedata.seed_factions(),
        active_npc_name=key,
        npcs=st["npcs"],
        messages=[HumanMessage(content="Como andam os preços?")],
        world_projection=st["world_projection"],
    )
    return base


def _npc_prompts(monkeypatch, state: dict) -> list[str]:
    spy = _Spy()
    monkeypatch.setattr(npc, "get_llm", lambda *a, **k: spy)
    monkeypatch.setattr(npc, "RAG_AVAILABLE", False)
    npc.npc_actor_node(state)
    return spy.prompts


def test_invoke_count_unchanged_npc_keeper(monkeypatch):
    with_block = _npc_prompts(monkeypatch, _keeper_state())
    monkeypatch.setattr(npc, "_commerce_block", lambda *a, **k: "")
    without = _npc_prompts(monkeypatch, _keeper_state())
    assert len(with_block) == len(without) >= 1
    p = with_block[0]
    assert "<SEU_COMERCIO>" in p and "<SEU_COMERCIO>" not in without[0]
    assert p.index("<ATITUDE>") < p.index("<SEU_COMERCIO>") < p.index("<MEMORIA>")
    block = p[p.index("<SEU_COMERCIO>") : p.index("</SEU_COMERCIO>")]
    assert not re.search(r"\d|%", block)


def test_old_save_loads_and_plans(monkeypatch):
    """R26: estado pré-302 (sem world_sim, quests sem world_kind) planeja sem erro."""
    old = {
        "world": {"current_location": "Skallgard", "current_location_id": "skallgard"},
        "messages": [HumanMessage(content="olho em volta")],
        "campaign_plan": {},
        "quests": [{"id": "q1", "title": "Velha missão", "status": "active"}],
    }

    class _LLM:
        def with_structured_output(self, _m):
            return self

        def invoke(self, msgs, *_a, **_k):
            self.text = "\n".join(str(m.content) for m in msgs)
            return cm.CampaignPlanModel(
                location="Skallgard", beats=["a", "b", "c"], climax="x", arc_title="Arco"
            )

    llm = _LLM()
    monkeypatch.setattr(cm, "get_llm", lambda *a, **k: llm)
    monkeypatch.setattr(
        cm,
        "build_context_pack",
        lambda *a, **k: type("Pack", (), {"lore_block": "", "world_state_block": ""})(),
    )
    plan = cm._build_plan(old)
    assert plan["location"] == "Skallgard"
    assert "Velha missão" in llm.text and "tipo: mundo" not in llm.text
    assert pc.world_replan_cause(old, [], []) is None
