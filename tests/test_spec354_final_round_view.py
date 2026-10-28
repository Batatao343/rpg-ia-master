"""SPEC-354 R4.1: o registro da rodada final sobrevive ao fim do conflito na view (só Baralho on)."""

from __future__ import annotations

import api
from tests.test_api_jogadas import _state

BOARD = [{"ator_id": "player", "ator_nome": "Ayla", "lado": "heroi", "resultado": "acerto", "dano": 5}]


def _ended(monkeypatch, mode="on"):
    state = _state(monkeypatch, mode)
    meta = state["combat"]
    meta.pop("pilhas", None)  # o motor apaga as pilhas no fim do conflito (agents/combat.py)
    meta["active"] = False
    meta["phase"] = "ended"
    meta["last_round_board"] = list(BOARD)
    return state


def test_final_round_board_survives_end_with_deck_on(monkeypatch):
    block = api._combat_block(_ended(monkeypatch))
    assert block["registro_rodada"] == BOARD


def test_no_final_round_board_with_deck_off(monkeypatch):
    block = api._combat_block(_ended(monkeypatch, "off"))
    assert "registro_rodada" not in block


def test_active_combat_without_piles_has_no_board(monkeypatch):
    state = _ended(monkeypatch)
    state["combat"]["active"] = True
    state["combat"]["phase"] = "player"
    assert "registro_rodada" not in api._combat_block(state)
