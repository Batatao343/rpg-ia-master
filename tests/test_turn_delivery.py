"""SPEC-316 etapa 1 — entrega antecipada da narracao (funcoes puras)."""

from __future__ import annotations

import random

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
from langgraph.types import Overwrite

from services.turn_delivery import (
    early_mode,
    early_narrative,
    narrative_chunks,
)


def _state() -> dict:
    from playtest.runner import _build_initial_state

    random.seed(3)
    state = _build_initial_state("explorador", 3)
    state["messages"] = [HumanMessage(content="olho ao redor")]
    # o recibo do turno anterior ainda esta no estado: nao pode vazar na antecipada
    state["last_turn_outcome"] = {"player_message": "TEXTO DO TURNO ANTERIOR"}
    return state


def test_story_update_yields_guarded_text():
    state = _state()
    text = early_narrative(
        state, {"messages": [AIMessage(content="A estrada segue entre as colinas.")]}, "storyteller"
    )
    assert text == "A estrada segue entre as colinas."


def test_system_message_update_yields_none():
    state = _state()
    update = {"messages": [SystemMessage(content="COMBAT START")]}
    assert early_narrative(state, update, "storyteller") is None
    assert early_narrative(state, {"world": state["world"]}, "storyteller") is None


def test_update_routing_to_another_narrator_yields_none():
    state = _state()
    msgs = [AIMessage(content="Algo se move nas sombras.")]
    assert early_narrative(state, {"messages": msgs, "next": "combat_agent"}, "storyteller") is None
    assert early_narrative(state, {"messages": msgs, "next": "storyteller"}, "npc_actor") is None
    # vitoria: o router grafa `loot`, o no se chama `loot_agent`
    assert early_narrative(state, {"messages": msgs, "next": "loot"}, "combat_agent") is None
    # o proprio no no `next` nao o suprime
    assert early_narrative(state, {"messages": msgs, "next": "combat_agent"}, "combat_agent")


def test_guard_rejection_changes_text():
    state = _state()
    update = {"messages": [AIMessage(content="Você morreu. A estrada segue em frente.")]}
    text = early_narrative(state, update, "storyteller")
    assert text == "A estrada segue em frente."


def test_overwrite_messages_are_respected():
    state = _state()
    update = {
        "messages": Overwrite(
            [HumanMessage(content="x"), AIMessage(content="Texto reescrito pelo no.")]
        )
    }
    assert early_narrative(state, update, "storyteller") == "Texto reescrito pelo no."


def test_pure_does_not_mutate_inputs():
    state = _state()
    before = list(state["messages"])
    update = {"messages": [AIMessage(content="Vento frio.")]}
    early_narrative(state, update, "storyteller")
    assert state["messages"] == before and "last_turn_outcome" in state


def test_mode_default_is_shadow(monkeypatch):
    monkeypatch.delenv("RPG_EARLY_NARRATIVE", raising=False)
    assert early_mode() == "shadow"
    monkeypatch.setenv("RPG_EARLY_NARRATIVE", "ON")
    assert early_mode() == "on"
    monkeypatch.setenv("RPG_EARLY_NARRATIVE", "lixo")
    assert early_mode() == "off"


def test_narrative_chunks_roundtrip():
    text = "a" * 170
    parts = narrative_chunks(text, 80)
    assert [len(p) for p in parts] == [80, 80, 10] and "".join(parts) == text
    assert narrative_chunks("") == []
