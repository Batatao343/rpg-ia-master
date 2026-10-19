"""SPEC-223 R6 — corpus de prompt injection com um LLM que OBEDECE a injeção.

`ScriptedLLM` devolve exatamente o structured output malicioso pedido pelo
jogador. O motor (validadores com prova, clamps, gates Python) tem de rejeitar ou
clampar 100% dos casos: XP/ouro/nível/inventário/quests/segredos/mortes/relação
inalterados ou dentro do clamp. Determinístico e offline.
"""

from __future__ import annotations

import json
from copy import deepcopy
from pathlib import Path
from types import SimpleNamespace

import pytest
from langchain_core.messages import HumanMessage

from services.event_processor import process_pending_events
from services.prompt_guard import PLAYER_INPUT_RULE, PLAYER_INPUT_TAG, wrap_player_input

CORPUS = json.loads(
    (Path(__file__).parent / "fixtures" / "prompt_injection" / "corpus.json").read_text(
        encoding="utf-8"
    )
)["cases"]


class ScriptedLLM:
    """Obedece a injeção: valida o payload malicioso no schema pedido e registra o prompt."""

    def __init__(self, payload: dict):
        self.payload = payload
        self.prompts: list = []

    def with_structured_output(self, schema):
        def invoke(messages):
            self.prompts.append(list(messages))
            data = dict(self.payload)
            if "dialogue" in schema.model_fields:
                data = {
                    "dialogue": "Está bem.",
                    "action_description": "assente",
                    "memory_update": "",
                    **data,
                }
            return schema.model_validate(data)

        return SimpleNamespace(invoke=invoke)


def test_corpus_has_at_least_twenty_cases():
    assert len(CORPUS) >= 20
    assert len({c["id"] for c in CORPUS}) == len(CORPUS)


def _story_state(player_input: str) -> dict:
    return {
        "game_id": "spec223",
        "messages": [HumanMessage(content=player_input)],
        "player": {
            "name": "Ari",
            "class_name": "Devoto do Abismo",
            "level": 1,
            "xp": 0,
            "gold": 10,
            "inventory": [],
            "vitalidade": 8,
            "max_vitalidade": 8,
        },
        "world": {
            "current_location_id": "nova_arcadia",
            "current_location": "Nova Arcádia",
            "turn_count": 6,
            "danger_level": 1,
            "visited": ["nova_arcadia"],
            "world_clock": {"day": 1, "period": "Manhã"},
        },
        "npcs": {},
        "factions": [],
        "faction_intel": {},
        "quests": [
            {
                "id": "q_ativa",
                "title": "Achar o sino",
                "status": "active",
                "location_id": "nova_arcadia",
                "created_turn": 2,
                "origin_name": "Grum",
                "progress_log": [
                    {"kind": "created", "turn": 2},
                    {"kind": "location_reached", "turn": 2},
                ],
            },
            {
                "id": "q_nova",
                "title": "Levar a carta",
                "status": "active",
                "location_id": "",
                "created_turn": 6,
                "origin_name": "Grum",
                "progress_log": [{"kind": "created", "turn": 6}],
            },
        ],
        "campaign_plan": {
            "beats": [{"description": "Investigar o sino", "status": "pending"}],
            "current_step": 0,
        },
        "event_log": [],
        "world_projection": {},
        "pending_world_events": [],
    }


@pytest.fixture
def story(monkeypatch):
    from agents import storyteller

    monkeypatch.setattr(
        storyteller,
        "build_context_pack",
        lambda *a, **k: SimpleNamespace(lore_block="", memory_block="", world_state_block=""),
    )
    monkeypatch.setattr(storyteller, "simulate_world", lambda s, w, *a: (w, ""))
    monkeypatch.setattr(storyteller, "check_encounter", lambda *a, **k: None)

    def run(case):
        llm = ScriptedLLM(case["update"])
        monkeypatch.setattr(storyteller, "get_llm", lambda **k: llm)
        state = _story_state(case["player_input"])
        out = storyteller.storyteller_node(deepcopy(state))
        merged = {**state, **out}
        merged = {**merged, **process_pending_events(merged)}
        return state, merged, llm

    return run


@pytest.mark.parametrize("case", [c for c in CORPUS if c["kind"] == "story"], ids=lambda c: c["id"])
def test_story_injection_has_no_mechanical_authority(story, case):
    before, after, llm = story(case)
    p0, p1 = before["player"], after["player"]
    assert (p1.get("xp", 0), p1.get("gold", 0), p1.get("level", 1)) == (
        p0["xp"],
        p0["gold"],
        p0["level"],
    )
    assert p1.get("inventory", []) == p0["inventory"]
    assert [q["status"] for q in after["quests"]] == ["active", "active"]
    assert not (after["world_projection"].get("revealed_facts") or {})
    applied = {e["type"] for e in after["event_log"]}
    assert not applied & {
        "quest_completed",
        "secret_revealed",
        "npc_killed",
        "level_up",
        "unique_item_claimed",
    }
    # R5: a entrada chegou delimitada como dado e o system prompt traz a regra.
    prompt = llm.prompts[0]
    assert PLAYER_INPUT_RULE in str(prompt[0].content)
    human = [m for m in prompt if isinstance(m, HumanMessage)]
    assert human and str(human[-1].content) == wrap_player_input(case["player_input"])


def _npc_state(player_input: str, **npc_over) -> dict:
    npc = {
        "name": "Grum",
        "role": "ferreiro",
        "persona": "rabugento",
        "in_scene": True,
        "relationship": 5,
        "memory": [],
        "known_by_player": True,
        "home_location_id": "nova_arcadia",
        "location": "Nova Arcádia",
    }
    npc.update(npc_over)
    return {
        "game_id": "spec223",
        "messages": [HumanMessage(content=player_input)],
        "active_npc_name": "Grum",
        "npcs": {"Grum": npc},
        "party": [],
        "player": {"name": "Ari", "level": 1, "xp": 0, "gold": 10},
        "world": {
            "current_location_id": "nova_arcadia",
            "current_location": "Nova Arcádia",
            "turn_count": 6,
        },
        "factions": [],
        "faction_intel": {},
        "quests": [],
        "event_log": [],
    }


@pytest.fixture
def npc_run(monkeypatch):
    from agents import npc as npc_mod

    monkeypatch.setattr(
        npc_mod,
        "build_context_pack",
        lambda *a, **k: SimpleNamespace(lore_block="", memory_block="", world_state_block=""),
    )
    monkeypatch.setattr(npc_mod, "add_npc_memory", lambda *a, **k: True)

    def run(state, payload):
        llm = ScriptedLLM(payload)
        monkeypatch.setattr(npc_mod, "get_llm", lambda **k: llm)
        return npc_mod.npc_actor_node(state), llm

    return run


@pytest.mark.parametrize("case", [c for c in CORPUS if c["kind"] == "npc"], ids=lambda c: c["id"])
def test_npc_relationship_injection_is_clamped(npc_run, case):
    from agents.npc import RELATIONSHIP_STEP_CAP

    out, llm = npc_run(_npc_state(case["player_input"]), case["response"])
    rel = out["npcs"]["Grum"]["relationship"]
    assert abs(rel - 5) <= RELATIONSHIP_STEP_CAP
    assert PLAYER_INPUT_RULE in str(llm.prompts[0][0].content)
    assert f"<{PLAYER_INPUT_TAG}>" in str(llm.prompts[0][-1].content)


@pytest.mark.parametrize(
    "case", [c for c in CORPUS if c["kind"] == "recruit"], ids=lambda c: c["id"]
)
def test_recruit_injection_needs_real_interactions(npc_run, case):
    out, llm = npc_run(_npc_state(case["player_input"], **case["npc"]), {})
    assert not out.get("party")
    assert out["last_interaction_outcome"]["code"] == "too_few_interactions"
    assert llm.prompts == []  # gate Python decide sem LLM


@pytest.mark.parametrize(
    "case", [c for c in CORPUS if c["kind"] in ("npc_name", "enemy_name")], ids=lambda c: c["id"]
)
def test_entity_name_injection_is_bounded(monkeypatch, case):
    from agents import bestiary
    from agents import npc as npc_mod
    from llm_setup import ModelTier

    tiers: list = []
    names: list = []

    def fake_llm(**kwargs):
        tiers.append(kwargs.get("tier"))
        return SimpleNamespace(
            with_structured_output=lambda schema: SimpleNamespace(
                invoke=lambda msgs: (
                    names.append(str(msgs[0].content))
                    or (_ for _ in ()).throw(RuntimeError("offline"))
                )
            )
        )

    mod = npc_mod if case["kind"] == "npc_name" else bestiary
    monkeypatch.setattr(mod, "get_llm", fake_llm)
    monkeypatch.setattr(mod, "query_rag", lambda *a, **k: "")
    monkeypatch.setattr(mod, "find_existing_entity", lambda *a, **k: None)
    if case["kind"] == "npc_name":
        data = npc_mod.generate_new_npc(case["name"])
    else:
        data = bestiary.generate_new_enemy(case["name"])
    assert tiers == [ModelTier.FAST]
    assert len(data["name"]) <= 60
    assert not set(data["name"]) & set("<>{};()")


@pytest.mark.parametrize(
    "case", [c for c in CORPUS if c["kind"] == "backstory"], ids=lambda c: c["id"]
)
def test_backstory_injection_is_truncated_and_marked(case):
    from services.prompt_guard import ORIGIN_MARKER, origin_fragment

    long = (case["backstory"] * 40)[:2000]
    frag = origin_fragment(long)
    assert frag.startswith(ORIGIN_MARKER)
    assert len(frag) <= len(ORIGIN_MARKER) + 1 + 300 * 5  # escape pode expandir < >
    assert "<" not in frag and ">" not in frag
    assert (
        len(origin_fragment(long).replace("&lt;", "<").replace("&gt;", ">").replace("&amp;", "&"))
        <= len(ORIGIN_MARKER) + 1 + 300
    )
