"""SPEC-357 R10 - compra de Carta por texto no no `loot` (sem LLM de classificacao)."""

from __future__ import annotations

import pytest
from langchain_core.messages import HumanMessage

from agents import loot
from services import card_shop, cards


@pytest.fixture(autouse=True)
def _on(monkeypatch):
    monkeypatch.setenv("RPG_CARD_REWARDS", "on")


def _state(text, gold=500, location="brekmar"):
    return {
        "game_id": "g357",
        "messages": [HumanMessage(content=text)],
        "loot_source": "SHOP",
        "player": {
            "name": "Iria",
            "class_name": "Sangromante",
            "level": 4,
            "gold": gold,
            "vitalidade": 18,
            "max_vitalidade": 18,
            "inventory": [{"id": "corda", "qty": 2}],
            "equipment": {},
            "known_cards": [],
            "deck": [],
        },
        "world": {
            "current_location_id": location,
            "visited": [location],
            "turn_count": 3,
            "world_clock": {"day": 1, "period": "manha"},
            "merchant_stocks": {},
            "merchant_restock_day": {},
            "danger_level": 1,
        },
        "world_projection": {},
        "factions": [],
    }


def _offer(state):
    _, ids = card_shop.shelf(state)
    return ids[0], cards.get_card(ids[0])["name"]


def test_text_buy_exact_card_name():
    cid, name = _offer(_state(""))
    out = loot.loot_node(_state(f"Compro o {name}, por favor."))
    assert cid in out["player"]["known_cards"]
    assert out["player"]["gold"] < 500
    assert "[SISTEMA] +1 Carta" in out["messages"][0].content and name in out["messages"][0].content


def test_text_buy_item_unchanged(monkeypatch):
    st = _state("Compro uma corda.", location="na_anel_dourado")
    out = loot.loot_node(st)
    assert "Carta" not in out["messages"][0].content
    assert out["player"].get("known_cards") == []  # nenhuma Carta entrou


def test_text_ambiguous_falls_back(monkeypatch):
    _, ids = card_shop.shelf(_state(""))
    names = [cards.get_card(i)["name"] for i in ids[:2]]
    st = _state(f"Compro {names[0]} e {names[1]}.")
    assert card_shop.match_offer(st, loot.economy._fold_key(st["messages"][0].content)) is None
    seen = []
    monkeypatch.setattr(
        loot,
        "_parse_trade_intent",
        lambda *a: seen.append(1) or loot.TradeIntent(mode="observe", item_ref=""),
    )
    loot.loot_node(st)
    assert seen  # caiu no fluxo de itens


def test_observe_lists_techniques():
    out = loot.loot_node(_state("Examino o estoque e anoto os preços."))
    assert "Técnica: " in out["messages"][0].content
    assert out["messages"][0].content.count("Técnica: ") <= 3


def test_loot_off_identical(monkeypatch):
    _cid, name = _offer(_state(""))
    monkeypatch.setenv("RPG_CARD_REWARDS", "off")
    out = loot.loot_node(_state("Examino o estoque e anoto os preços."))
    assert "Técnica" not in out["messages"][0].content
    bought = loot.loot_node(_state(f"Compro o {name}."))
    assert "+1 Carta" not in bought["messages"][0].content
    assert (bought.get("player") or {}).get("known_cards", []) == []
