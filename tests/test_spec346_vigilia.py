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


def test_vigilia_holds_in_round_one_at_level_3(monkeypatch):
    """P1-1: a surpresa crua do mundo não reabre a emboscada na rodada 1."""
    from langchain_core.messages import HumanMessage

    from services import conflict_orchestrator as orch
    from tests.test_spec346_board_no_llm import _after_open, _attack_decl

    _install_llm(monkeypatch, scan=_scan(("Goblin", 1)))
    state = _start_state(hint="Goblin")
    state["player"]["level"] = 3
    state["world"]["encounter_surprise"] = "enemy"
    state["player"]["prepared_cards"] = [
        *state["player"].get("prepared_cards", []),
        combat.VIGILIA_CARD_ID,
    ]
    nxt = _after_open(state, combat._combat_node(state))
    nxt["messages"] = [*nxt["messages"], HumanMessage(content="joga")]
    nxt["combat_declaration"] = _attack_decl(nxt)
    seen = {}
    real = orch.run_round

    def spy(*a, **k):
        seen["initiator"] = k.get("initiator")
        return real(*a, **k)

    monkeypatch.setattr(orch, "run_round", spy)
    combat._combat_node(nxt)
    assert seen["initiator"] is None


def _opening_text(monkeypatch, *, vigilia):
    res = _open(monkeypatch, vigilia=vigilia)
    return res["messages"][-1].content


def test_opening_narration_says_enemy_struck_first(monkeypatch):
    """SPEC-397 R3: emboscada inimiga aparece na abertura narrada."""
    assert "ataca primeiro" in _opening_text(monkeypatch, vigilia=False)


def test_opening_narration_says_ambush_was_sensed(monkeypatch):
    """SPEC-397 R3: emboscada negada pela Carta de Iniciativa: o herói percebeu a tempo."""
    text = _opening_text(monkeypatch, vigilia=True)
    assert "percebe a emboscada a tempo" in text and "ataca primeiro" not in text


def test_opening_without_ambush_has_no_line(monkeypatch):
    _install_llm(monkeypatch, scan=_scan(("Goblin", 1)))
    state = _start_state(hint="Goblin")
    text = combat._combat_node(state)["messages"][-1].content
    assert "ataca primeiro" not in text and "emboscada" not in text
