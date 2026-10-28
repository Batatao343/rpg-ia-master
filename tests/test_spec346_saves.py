"""SPEC-346 R32: saves antigos continuam retomando no tabuleiro."""

from __future__ import annotations

import random

import pytest
from langchain_core.messages import HumanMessage

import agents.combat as combat
from tests.test_spec346_board_no_llm import _after_open, _attack_decl, _open


@pytest.fixture(autouse=True)
def _on(monkeypatch):
    monkeypatch.setenv("RPG_CARD_DECK", "on")
    random.seed(9)


def test_mid_combat_old_save_resumes_on(monkeypatch):
    """Save `on` do meio do combate (round >= 1, sem os campos novos) retoma por jogadas."""
    state, res = _open(monkeypatch)
    nxt = _after_open(state, res)
    for key in ("initiator", "initiator_reason"):  # save de antes da SPEC-346
        nxt["combat"].pop(key, None)
    nxt["combat"]["round"] = 2
    nxt["messages"] = [*nxt["messages"], HumanMessage(content="Jogo as cartas")]
    nxt["combat_declaration"] = _attack_decl(nxt)
    out = combat._combat_node(nxt)
    assert out["combat"]["round"] == 3
    assert out["messages"][0].content.strip()


def test_save_at_opening_resumes_asking_for_cards(monkeypatch):
    state, res = _open(monkeypatch)
    nxt = _after_open(state, res)
    assert nxt["combat"]["round"] == 0
    nxt["messages"] = [*nxt["messages"], HumanMessage(content="Jogo as cartas")]
    nxt["combat_declaration"] = _attack_decl(nxt)
    out = combat._combat_node(nxt)
    assert out["combat"]["round"] == 1


def test_old_combat_result_without_new_fields_loads(monkeypatch):
    import agents.loot as loot

    monkeypatch.setattr(loot, "_narrate", lambda *a, **k: "ok")
    state = {
        "player": {"name": "T", "gold": 1, "inventory": [], "level": 1},
        "world": {"current_location_id": "pantano_melancolia", "turn_count": 2},
        "messages": [HumanMessage(content="Vasculho o corpo")],
        "loot_source": "TREASURE",
        "combat": {"phase": "ended", "result": {"outcome": "victory"}},
        "conflict_summary": {},
    }
    assert "[SISTEMA]" in loot.loot_node(state)["messages"][0].content
