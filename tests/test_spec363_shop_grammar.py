"""SPEC-363 R28: "Quero comprar <Carta> da <mercador>" compra; ressalva/pergunta/negação não."""

from __future__ import annotations

import pytest

from agents import loot
from services import card_shop, cards, economy
from tests.test_card_shop_loot_text import _offer, _state


@pytest.fixture(autouse=True)
def _on(monkeypatch):
    monkeypatch.setenv("RPG_CARD_REWARDS", "on")


def _merchant_name(state) -> str:
    return economy.MERCHANTS[card_shop.shelf(state)[0]]["name"]


def _buys(text, **extra) -> bool:
    out = loot.loot_node({**_state(text), **extra})
    return bool(out["player"]["known_cards"]) if out.get("player") else False


def test_buy_with_merchant_complement():
    st = _state("")
    _, name = _offer(st)
    merchant = _merchant_name(st)
    assert _buys(f"Quero comprar a {name} da {merchant}")
    assert _buys(f"Quero comprar {name} do {merchant}, por favor")


def test_complement_negatives_do_not_buy():
    st = _state("")
    cid, name = _offer(st)
    merchant = _merchant_name(st)
    assert not _buys(f"Quero comprar a {name} da {merchant}?")
    assert not _buys(f"Quero comprar a {name} da {merchant} depois")
    assert not _buys(f"Quero comprar a {name} da Okka desconhecida")
    assert not _buys(f"Não quero comprar a {name} da {merchant}")


def test_complement_accepts_present_npc(monkeypatch):
    st = _state("")
    _, name = _offer(st)
    monkeypatch.setattr(
        "services.npc_layers.npcs_for_context", lambda state: ["Okka"], raising=True
    )
    assert _buys(f"Quero comprar a {name} da Okka")


def test_complement_accepts_current_location_name():
    st = _state("")
    _, name = _offer(st)
    loc = {**st["world"], "current_location": "Forja dos Clãs"}
    out = loot.loot_node({**_state(f"Quero comprar a {name} da Forja dos Clãs"), "world": loc})
    assert out["player"]["known_cards"]
    assert cards.get_card(out["player"]["known_cards"][0])
