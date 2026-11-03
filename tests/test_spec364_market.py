"""SPEC-364 R4-R9: pergunta de catalogo vira consulta; mercado em duas secoes; nome curto; mercador citado."""

from __future__ import annotations

import copy

import pytest

import inventory
from agents import loot
from services import card_shop, economy
from tests.test_card_shop_loot_text import _state

LONG = (
    "Faca de esfolar de osso de baleia, cabo envolto em couro cru — a lâmina que Haldor usa "
    "para os couros mais grossos de Valoria"
)
LOC = "na_anel_dourado"


@pytest.fixture(autouse=True)
def _on(monkeypatch):
    monkeypatch.setenv("RPG_CARD_REWARDS", "on")


@pytest.fixture
def no_llm(monkeypatch):
    calls = []

    def boom(*a, **k):
        calls.append(1)
        raise AssertionError("get_llm nao deveria ser chamado")

    monkeypatch.setattr(loot, "get_llm", boom)
    return calls


def _st(text, inventory_extra=None, location=LOC):
    st = _state(text, location=location)
    st["player"]["inventory"] = [{"id": "tocha", "qty": 1}] + list(inventory_extra or [])
    return st


def _snap(st):
    return copy.deepcopy((st["player"]["gold"], st["player"]["inventory"]))


CATALOG = [
    "O que a Forja dos Clãs tem à venda?",
    "O que vocês vendem?",
    "Tem algo à venda aqui?",
    "O que tem pra vender?",
    "Quais mercadorias você tem?",
]


@pytest.mark.parametrize("text", CATALOG)
def test_catalog_questions_observe(text, no_llm):
    st = _st(text)
    before = _snap(st)
    intent = loot._parse_trade_intent(st, "SHOP", text)
    assert intent.mode == "observe"
    out = loot.loot_node(st)
    body = out["messages"][0].content
    assert "para vender" not in body and "Você não tem" not in body
    assert "consulta sem transação" in body
    assert _snap(st) == before
    assert not no_llm


def test_explicit_sell_still_sells(monkeypatch):
    class _Stub:
        def with_structured_output(self, _model):
            return self

        def invoke(self, _msgs):
            return loot.TradeIntent(mode="sell", item_ref="tocha", qty=1)

    monkeypatch.setattr(loot, "get_llm", lambda *a, **k: _Stub())
    for text in ("Vendo a Tocha", "Quero vender a Tocha", "Vender a tocha por favor"):
        intent = loot._parse_trade_intent(_st(text), "SHOP", text)
        assert intent.mode == "sell", text
        out = loot.loot_node(_st(text))
        assert out["player"]["gold"] > 500, text
        assert not any(e["id"] == "tocha" for e in out["player"]["inventory"]), text


@pytest.mark.parametrize(
    "text",
    [
        "Posso vender a Tocha?",
        "Quanto vale a Tocha?",
        "Me vende a Corda?",
        "Quanto custa a Corda?",
        "Me vende uma tocha?",
    ],
)
def test_question_never_trades_item(text, no_llm):
    st = _st(text)
    before = _snap(st)
    out = loot.loot_node(st)
    body = out["messages"][0].content
    assert "nada mudou" in body or "consulta sem transação" in body
    assert _snap(st) == before
    assert (
        "player" not in out
        or out["player"] is None
        or _snap({**st, "player": out["player"]}) == before
    )
    assert not no_llm


def test_question_quote_text():
    out = loot.loot_node(_st("Posso vender a Tocha?"))
    body = out["messages"][0].content
    assert body.lower().startswith("[sistema] tocha: o mercador paga ")
    assert "Diga claramente que vende para confirmar; nada mudou." in body


def test_market_two_sections():
    st = _st(
        "Examino o estoque.",
        inventory_extra=[{"id": "item_desconhecido", "qty": 1, "display_name": LONG}],
    )
    body = loot.loot_node(st)["messages"][0].content
    assert "À venda:" in body and "Pelo que você carrega:" in body
    sell_part = body.split("Pelo que você carrega:")[1]
    sale_part = body.split("Pelo que você carrega:")[0]
    assert "Faca de esfolar de osso de baleia" in sell_part and "paga" in sell_part
    assert "a lâmina que Haldor" not in body
    assert "Faca de esfolar" not in sale_part
    assert "estoque 0" not in body
    assert "(estoque " in sale_part


def test_snapshot_source_field():
    st = _st("x", inventory_extra=[{"id": "item_desconhecido", "qty": 1, "display_name": LONG}])
    snap = economy.public_market_snapshot(st)
    sources = {q["item_name"]: q["source"] for q in snap["quotes"]}
    assert sources[LONG] == "player"
    assert any(v == "merchant" for v in sources.values())
    assert all(q["source"] == "merchant" for q in snap["quotes"] if q["stock"] > 0)


def test_short_display():
    assert inventory.short_name(LONG) == "Faca de esfolar de osso de baleia"
    assert inventory.short_name("Tocha") == "Tocha"
    cut = inventory.short_name("Adaga de lamina longa e muito fina para cortar cordas de seda fina")
    assert cut.endswith("…") and len(cut) <= 41 and " " not in cut[-2:]
    entry = {"id": "item_desconhecido", "qty": 1, "display_name": LONG}
    assert inventory.short_display(entry) == "Faca de esfolar de osso de baleia"
    assert entry["display_name"] == LONG  # save intacto


def _capture(monkeypatch):
    seen = []

    def fake(context, fallback, canonical_summary=None, gold_check=None):
        seen.append((context, fallback))
        return fallback

    monkeypatch.setattr(loot, "_narrate", fake)
    return seen


def test_buy_narration_names_merchant_card(monkeypatch):
    seen = _capture(monkeypatch)
    st = _st("", location="brekmar")
    mid = card_shop.shelf(st)[0]
    name = economy.MERCHANTS[mid]["name"]
    cid = card_shop.shelf(st)[1][0]
    from services import cards

    cname = cards.get_card(cid)["name"]
    out = loot.loot_node(_st(f"Compro o {cname}, por favor.", location="brekmar"))
    assert out["player"]["known_cards"]
    ctx, fb = seen[-1]
    assert f"Mercador: {name}" in ctx and "não invente outro" in ctx
    assert fb == f"{name} fecha o negócio sem cerimônia."


def test_buy_narration_names_merchant_item(monkeypatch):
    seen = _capture(monkeypatch)
    st = _st("Compro uma corda.")
    snap = economy.public_market_snapshot(st)
    out = loot.loot_node(st)
    assert out["messages"]
    ctx, fb = seen[-1]
    assert f"Mercador: {snap['merchant_name']}" in ctx
    assert fb == f"{snap['merchant_name']} fecha o negócio sem cerimônia."


def test_buy_ask_quotes_buy_price_even_with_item_in_pack():
    """P3-3: 'Me vende uma corda?' (Corda também na mochila) cota o preço de COMPRA, não o que o mercador paga."""
    st = _st("Me vende uma corda?", inventory_extra=[{"id": "corda", "qty": 1}])
    body = loot.loot_node(st)["messages"][0].content
    assert " custa " in body and "paga" not in body


def test_buy_ask_for_unstocked_item_says_not_for_sale():
    body = loot.loot_node(_st("Me vende uma tocha?"))["messages"][0].content
    assert "não está à venda" in body and "paga" not in body
