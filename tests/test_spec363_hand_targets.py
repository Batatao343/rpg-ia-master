"""SPEC-363 R19/R21: toda Carta da mão tem alvos válidos, iguais aos que o motor aceita."""

from __future__ import annotations

import pytest

from services import cards
from services import combat_targeting as ct
from tests.test_combat_targeting import _enemy_ids, _state

BASIC_ACTIVE = sorted(
    cid for cid, c in cards.all_cards().items() if cid.startswith("bas_") and c.get("tipo") == "ativa"
)


def _hidden_state():
    state = _state(2)
    ids = _enemy_ids(state)
    state["combat"]["scene"]["positions"][ids[0]]["hidden_from"] = ["player"]
    return state, ids


def test_basic_cards_exist():
    assert BASIC_ACTIVE, "catálogo sem cartas básicas ativas"


@pytest.mark.parametrize("card_id", BASIC_ACTIVE[:60])
def test_hand_cards_have_valid_targets(card_id):
    state, ids = _hidden_state()
    res = ct.hand_card_targeting(state, card_id)
    kind = str((cards.get_card(card_id).get("efeito") or {}).get("kind") or "")
    if kind in ct._SUPPORT_EFFECTS:
        assert "player" in res["valid_targets"]
    else:
        assert ids[0] not in res["valid_targets"]
        assert res["valid_targets"] == [ids[1]]


@pytest.mark.parametrize("card_id", BASIC_ACTIVE[:60])
def test_view_target_implies_engine_accepts(card_id):
    state, ids = _hidden_state()
    state["combat"]["pilhas"] = {"mao": [card_id]}
    res = ct.hand_card_targeting(state, card_id)
    for tid in res["valid_targets"]:
        assert ct.check_declared_target(state, card_id=card_id, action_kind=None, maneuver=None, target_id=tid) is None
    kind = str((cards.get_card(card_id).get("efeito") or {}).get("kind") or "")
    if kind not in ct._SUPPORT_EFFECTS:
        bad = ct.check_declared_target(state, card_id=card_id, action_kind=None, maneuver=None, target_id=ids[0])
        assert bad == "target_hidden" or bad is not None


def test_utility_card_has_no_targets():
    util = next((c for c, v in cards.all_cards().items() if v.get("tipo") == "utilitaria"), None)
    if util:
        state, _ = _hidden_state()
        assert ct.hand_card_targeting(state, util)["invalid_reason"] == "fora_de_combate"
