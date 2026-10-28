"""SPEC-353 etapa 1: Carta de objeto de cena jogavel e recusa sem id (R1-R3)."""

from __future__ import annotations

import re

import pytest

from services import card_piles, cards
from services import scene_cards as sc

ID_RE = re.compile(r"\b(cena|bas|dev|san|cor|arc|vig|bst|inf|mon|npc|enemy|fallback|sus)_[a-z0-9_]+\b")


def _obj_card() -> dict:
    obj = {"id": "sino_rachado", "name": "Sino Rachado"}
    it = {"label": "derrubar", "effect": {"kind": "damage", "params": {"amount": 4}}}
    card = sc._object_card(obj, it)
    assert card is not None
    cards.register_temp_card(card)
    return card


def _state(card_id: str | None, in_hand: bool) -> dict:
    mao = [card_id] if card_id and in_hand else []
    return {
        "player": {"prepared_cards": [], "card_usage": {}, "entropy": 5},
        "combat": {"pilhas": {"mao": mao, "compra": [], "descarte": [], "exaurida": []}},
    }


def test_object_card_in_hand_is_playable():
    card = _obj_card()
    st = _state(card["id"], True)
    res = cards.use_card(st, card["id"])
    assert res["ok"], res
    # frequencia de cena cobrada: segundo uso recusado
    again = cards.use_card(st, card["id"])
    assert not again["ok"]


def test_object_card_not_in_hand_refused_by_name():
    card = _obj_card()
    st = _state(card["id"], False)
    res = cards.use_card(st, card["id"])
    assert not res["ok"]
    assert "Derrubar (Sino Rachado)" in res["error"]
    assert not ID_RE.search(res["error"])


def test_unknown_card_error_has_no_id():
    res = cards.use_card(_state(None, False), "cena_fantasma_deadbeef")
    assert not res["ok"] and not ID_RE.search(res["error"])


@pytest.mark.parametrize("cid", ["muralha_viva", "golpe_devoto"])
def test_named_refusals_never_expose_id(cid):
    res = cards.use_card({"player": {"prepared_cards": []}}, cid)
    if not res["ok"]:
        assert not ID_RE.search(res["error"])


def test_hand_contract_playable_cards_accepted(monkeypatch):
    """R2: toda Carta jogavel da mao inicial (+ objeto de cena) e aceita por use_card."""
    monkeypatch.setenv("RPG_CARD_DECK", "on")
    card = _obj_card()
    for cid in ("bas_golpe", "bas_guarda"):
        if cards.get_card(cid) is None:
            continue
        st = {
            "player": {"prepared_cards": [], "deck": [cid], "card_usage": {}, "entropy": 5},
            "combat": {"pilhas": {"mao": [cid, card["id"]], "compra": [], "descarte": [], "exaurida": []}},
        }
        view = card_piles.public_view(st["combat"]["pilhas"])
        for row in view["mao"]:
            if row["jogavel"] and row["tipo"] == "ativa":
                fresh = {"player": dict(st["player"], card_usage={}), "combat": st["combat"]}
                assert cards.use_card(fresh, row["id"])["ok"], row["id"]
