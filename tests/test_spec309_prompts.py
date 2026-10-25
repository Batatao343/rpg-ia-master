"""SPEC-309 Etapa 5 (R12, R18, R19, R22) + F2 da SPEC-308: costura nos prompts."""

from __future__ import annotations

import random

import pytest
from langchain_core.messages import HumanMessage

import agents.combat as combat
import agents.npc as npc
import agents.storyteller as stt
import gamedata
from agents import world_simulator as wsim
from services import world_director as wd
from tests.test_ambient_consumers import _Spy, _story_state
from tests.test_combat_lifecycle import _enemy, _player


@pytest.fixture(autouse=True)
def _mode_on(monkeypatch):
    monkeypatch.setenv("RPG_WORLD_ENGINE", "on")
    monkeypatch.setenv("RPG_NPC_KNOWLEDGE", "off")


def _with_siege(st):
    st["world_projection"] = {
        "location_states": {
            "skallgard": {"state": "cerco", "severity": 2, "since_day": 1, "crisis_id": "c"}
        }
    }
    return st


def test_storyteller_prompt_has_block_after_ambiente(monkeypatch):
    spy = _Spy()
    monkeypatch.setattr(stt, "get_llm", lambda *a, **k: spy)
    stt.storyteller_node(_with_siege(_story_state()))
    prompt = spy.prompts[0]
    assert "<MUNDO_PERCEBIDO>" in prompt and "Skallgard está sitiada." in prompt
    assert prompt.index("<AMBIENTE>") < prompt.index("<MUNDO_PERCEBIDO>")
    assert "não invente causa, duração nem gravidade" in prompt


def test_storyteller_prompt_no_block_when_empty(monkeypatch):
    spy = _Spy()
    monkeypatch.setattr(stt, "get_llm", lambda *a, **k: spy)
    stt.storyteller_node(_story_state())
    assert "MUNDO_PERCEBIDO" not in spy.prompts[0]


def test_golden_rule_full_prompt(monkeypatch):
    """§3.6: cerco nao percebido em outra regiao nao aparece no prompt inteiro."""
    from tests.spec309_helpers import world_state_two_regions

    spy = _Spy()
    monkeypatch.setattr(stt, "get_llm", lambda *a, **k: spy)
    st = _story_state()
    two = world_state_two_regions()
    st.update(
        event_log=two["event_log"],
        world_projection=two["world_projection"],
        world_sim=two["world_sim"],
    )
    stt.storyteller_node(st)
    prompt = spy.prompts[0]
    assert "sitiada" not in prompt and "Brekmar agora" not in prompt
    assert "Zedrik" not in prompt


def test_combat_narration_has_block(monkeypatch):
    spy = _Spy()
    monkeypatch.setattr(combat, "get_llm", lambda *a, **k: spy)
    random.seed(1)
    state = {
        "game_id": "p309-combat",
        "messages": [HumanMessage(content="ataco o goblin")],
        "player": _player(),
        "enemies": [_enemy(hp=200)],
        "combat": {"active": True},
        "world": {
            "current_location": "Skallgard",
            "current_location_id": "skallgard",
            "turn_count": 3,
            "danger_level": 2,
            "world_clock": {"day": 1, "period": "Manhã"},
        },
        "party": [],
    }
    _with_siege(state)
    combat.combat_node(state)
    assert "<MUNDO_PERCEBIDO>" in "\n".join(spy.prompts)


def test_npc_prompt_has_local_state_only(monkeypatch):
    seen = {}

    class _NPCLLM(_Spy):
        def invoke(self, msgs, *a, **k):
            seen["p"] = str(msgs[0].content)
            raise RuntimeError("so o prompt interessa")

    monkeypatch.setattr(npc, "get_llm", lambda *a, **k: _NPCLLM())
    st = _with_siege(_story_state())
    st.update(
        active_npc_name="Guarda",
        npcs={
            "Guarda": {
                "name": "Guarda",
                "role": "guarda",
                "persona": "rude",
                "location": "skallgard",
                "memory": [],
                "relationship": 5,
            }
        },
        messages=[HumanMessage(content="quem manda aqui?")],
    )
    try:
        npc.npc_actor_node(st)
    except Exception:  # noqa: BLE001
        pass
    assert "Skallgard está sitiada." in seen["p"]


class _DayLLM:
    def __init__(self):
        self.msgs = None
        self.calls = 0

    def with_structured_output(self, model):
        outer = self

        class _Inv:
            def invoke(self, msgs):
                outer.calls += 1
                outer.msgs = msgs
                return model(text="Os ventos mudaram sobre Skallgard.")

        return _Inv()


def test_narrate_day_human_message_has_context(monkeypatch):
    """R12: bloco CONTEXTO so na mensagem humana; os fatos continuam sendo as linhas FATO."""
    from tests.test_spec302_perception import _item

    llm = _DayLLM()
    monkeypatch.setattr(wsim, "get_llm", lambda **kw: llm)
    st = _with_siege(_story_state())
    st["factions"] = gamedata.seed_factions()
    out = wsim.narrate_day(st, [_item("fome.sinal.preco", region="skallgard", loc="skallgard")])
    assert out
    human = str(llm.msgs[-1].content)
    assert "FATO:" in human and "CONTEXTO (não é fato novo):" in human
    assert "Skallgard está sitiada." in human
    assert "CONTEXTO" in str(llm.msgs[0].content)
    assert llm.calls == 1  # R22


def test_narrate_day_name_guard_unchanged(monkeypatch):
    from tests.test_spec302_perception import _item

    class _Leaky(_DayLLM):
        def with_structured_output(self, model):
            class _Inv:
                def invoke(self, msgs):
                    return model(text="O Marechal Vorr marchou.")

            return _Inv()

    monkeypatch.setattr(wsim, "get_llm", lambda **kw: _Leaky())
    st = _story_state()
    st["factions"] = gamedata.seed_factions()
    item = _item("fome.sinal.preco", region="skallgard", loc="skallgard")
    out = wsim.narrate_day(st, [item])
    assert out  # cai no template ou aceita o texto; nunca levanta


def test_invoke_count_unchanged(monkeypatch):
    """R22: o storyteller faz o mesmo numero de invokes com ou sem o bloco."""
    counts = []
    for siege in (False, True):
        spy = _Spy()
        monkeypatch.setattr(stt, "get_llm", lambda *a, _s=spy, **k: _s)
        st = _story_state()
        stt.storyteller_node(_with_siege(st) if siege else st)
        counts.append(len(spy.prompts))
    assert counts[0] == counts[1]


def test_f2_blocked_route_unperceived_is_discovered_on_travel(monkeypatch):
    """F2 (SPEC-308): ao tentar viajar por rota bloqueada que o heroi nao sabia, ele descobre."""
    spy = _Spy()
    monkeypatch.setattr(stt, "get_llm", lambda *a, **k: spy)
    st = _story_state(text="Vou para Fortaleza de Vorr")
    dest = next(c for c in gamedata.get_connections("skallgard") if c.get("kind") != "interior")
    ev = wd._ev(
        "g",
        1,
        "route_blocked",
        "skallgard",
        {"other_location_id": dest["id"], "crisis_id": "c", "day": 1},
    )
    ev["turn"] = 1
    st["event_log"] = [ev]
    st["world_projection"] = {
        "blocked_routes": [{"a": "skallgard", "b": dest["id"], "blocked_by_event": ev["event_id"]}]
    }
    st["world_sim"] = {"perceived_ids": []}
    st["messages"] = [HumanMessage(content=f"Viajo para {dest['name']}")]
    out = stt.storyteller_node(st)
    assert "BLOQUEADA" in spy.prompts[0]
    assert ev["event_id"] in (out.get("world_sim") or {}).get("perceived_ids", [])
