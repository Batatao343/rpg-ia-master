"""SPEC-346 D4: "Vigília Ciumenta" no baralho/preparadas anula a emboscada (regra atual vale)."""

import random

import pytest

import agents.combat as combat
from tests.test_encounter_identity_repro import _install_llm, _scan, _start_state


@pytest.fixture(autouse=True)
def _on(monkeypatch):
    monkeypatch.setenv("RPG_CARD_DECK", "on")
    random.seed(4)


def _open(monkeypatch, *, vigilia):
    _install_llm(monkeypatch, scan=_scan(("Goblin", 1)))
    state = _start_state(hint="Goblin")
    state["world"]["encounter_surprise"] = "enemy"
    if vigilia:
        state["player"]["prepared_cards"] = [
            *state["player"].get("prepared_cards", []),
            combat.VIGILIA_CARD_ID,
        ]
    return combat._combat_node(state)


def test_ambush_with_vigilia_falls_back_to_current_rule(monkeypatch):
    res = _open(monkeypatch, vigilia=True)
    assert res["combat"]["initiator"] is None
    assert res["combat"]["initiator_reason"] == "ambush_negated_vigilia"


def test_ambush_without_vigilia_enemies_first(monkeypatch):
    res = _open(monkeypatch, vigilia=False)
    assert res["combat"]["initiator"] == "enemy"
