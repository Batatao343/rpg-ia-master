"""SPEC-346 R29/R30: o narrador de entrada sabe exatamente quantos inimigos lutam."""

from __future__ import annotations

import random

import pytest
from langchain_core.messages import AIMessage

import agents.combat as combat
from tests.test_encounter_identity_repro import _scan, _start_state


@pytest.fixture(autouse=True)
def _on(monkeypatch):
    monkeypatch.setenv("RPG_CARD_DECK", "on")
    random.seed(3)


class _CaptureLLM:
    is_fallback = False

    def __init__(self, scan, prompts):
        self.scan, self.prompts = scan, prompts

    def with_structured_output(self, schema, **_kw):
        owner = self

        class _S:
            def invoke(self, _m):
                if schema is combat.EncounterScanner:
                    return owner.scan
                raise RuntimeError("sem structured output")

        return _S()

    def invoke(self, messages):
        self.prompts.append(messages[0].content)
        return AIMessage(content="Os saqueadores cercam você na estrada.")


def _template(name, **_kw):
    return {
        "id": "enemy_saqueador",
        "name": name,
        "virtudes": {"forca": 2, "agilidade": 2, "corpo": 2, "mente": 1, "carisma": 1},
    }


def test_entrance_prompt_states_exact_count(monkeypatch):
    prompts: list[str] = []
    scan = _scan(("Saqueador", 6))
    monkeypatch.setattr(combat, "get_llm", lambda **k: _CaptureLLM(scan, prompts))
    monkeypatch.setattr(combat, "generate_new_enemy", _template)
    state = _start_state(hint="saqueadores")
    state["player"]["level"] = 1
    state["world"]["danger_level"] = 1
    result = combat._combat_node(state)
    spawned = len(result["enemies"])
    assert 1 <= spawned < 6, "o orçamento do encontro precisa cortar o excedente do scanner"
    entrance = prompts[-1]
    assert f"exatamente: {spawned} " in entrance
    assert "Os demais recuam e não entram na luta" in entrance
    assert result["combat"]["round"] == 0


def test_entrance_prompt_without_cut_has_no_retreat_clause(monkeypatch):
    prompts: list[str] = []
    scan = _scan(("Saqueador", 1))
    monkeypatch.setattr(combat, "get_llm", lambda **k: _CaptureLLM(scan, prompts))
    monkeypatch.setattr(combat, "generate_new_enemy", _template)
    state = _start_state(hint="o saqueador")
    result = combat._combat_node(state)
    # o orçamento pode PREENCHER a luta (reforço regional): o prompt diz o total real
    import re

    clause = re.search(r"exatamente: (.*?)\.", prompts[-1]).group(1)
    assert sum(int(n) for n in re.findall(r"(\d+) ", clause + " ")) == len(result["enemies"])
    assert "Os demais recuam" not in prompts[-1]
