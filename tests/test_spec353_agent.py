"""SPEC-353 R22/R54 no agente: aliado de cena na abertura e limpeza do registro ao abrir conflito."""

from __future__ import annotations

import random

import pytest

import agents.combat as combat
import party as party_mod
from tests.test_encounter_identity_repro import _install_llm, _scan, _start_state


@pytest.fixture(autouse=True)
def _on(monkeypatch):
    monkeypatch.setenv("RPG_CARD_DECK", "on")
    random.seed(7)


def _ally():
    return {"id": "npc_ketil", "name": "Ketil", "is_ally": True, "transient": True,
            "vitalidade": 8, "max_vitalidade": 8, "virtudes": {"corpo": 2}}


def test_opening_sets_scene_allies(monkeypatch):
    _install_llm(monkeypatch, scan=_scan(("Goblin", 1)))
    monkeypatch.setattr(party_mod, "scene_allies", lambda state, excluded=None: [_ally()])
    res = combat._combat_node(_start_state(hint="Goblin"))
    names = [a.get("name") for a in res["combat"].get("scene_allies") or []]
    assert names == ["Ketil"]


def test_new_conflict_clears_last_round_board(monkeypatch):
    _install_llm(monkeypatch, scan=_scan(("Goblin", 1)))
    state = _start_state(hint="Goblin")
    state["combat"] = {
        **(state.get("combat") or {}),
        "last_round_board": [{"tipo": "jogada"}],
        "last_mech_log": ["velho"],
        "fontes_condicao": {"x": {"Sangramento": "player"}},
    }
    res = combat._combat_node(state)
    meta = res["combat"]
    assert not meta.get("last_round_board") and not meta.get("fontes_condicao")
    assert "velho" not in (meta.get("last_mech_log") or [])
