"""SPEC-367 R1-R3: cotacao por prefixo significativo do nome de item livre."""

from __future__ import annotations

import pytest

from agents import loot
from tests.test_spec364_market import CATALOG, _snap, _st

FACA = "Faca de pedra-sabão usada em sacrifícios de sangue ao mar"
FACA2 = "Faca de pedra-sabão lascada"


@pytest.fixture(autouse=True)
def _on(monkeypatch):
    monkeypatch.setenv("RPG_CARD_REWARDS", "on")


@pytest.fixture
def no_llm(monkeypatch):
    def boom(*a, **k):
        raise AssertionError("get_llm nao deveria ser chamado")

    monkeypatch.setattr(loot, "get_llm", boom)


def _faca(text, extra=()):
    inv = [{"id": "item_desconhecido", "qty": 1, "display_name": FACA}]
    for n in extra:
        inv.append({"id": "item_desconhecido_2", "qty": 1, "display_name": n})
    return _st(text, inventory_extra=inv)


def test_partial_name_question_quotes(no_llm):
    st = _faca("Posso vender a Faca de pedra-sabão?")
    before = _snap(st)
    body = loot.loot_node(st)["messages"][0].content
    snap = loot.economy.public_market_snapshot(st)
    n = next(q["sell_price"] for q in snap["quotes"] if q["item_name"] == FACA)
    assert body == (
        f"[SISTEMA] Faca de pedra-sabão usada em sacrifícios…: o mercador paga {int(n)} moedas. "
        "Diga claramente que vende para confirmar; nada mudou."
    )
    assert _snap(st) == before


@pytest.mark.parametrize("text", ["Posso vender a faca?", "Posso vender a Faca de?"])
def test_prefix_needs_two_significant_tokens(text):
    assert loot._cites_inventory(_faca(text), loot.economy._fold_key(text)) is None


def test_ambiguous_prefix_falls_to_observe(no_llm):
    text = "Posso vender a Faca de pedra-sabão?"
    st = _faca(text, extra=[FACA2])
    assert loot._cites_inventory(st, loot.economy._fold_key(text)) is None
    body = loot.loot_node(st)["messages"][0].content
    assert "consulta sem transação" in body


def test_longest_prefix_wins_between_entries():
    text = "posso vender a faca de pedra-sabao usada?"
    st = _faca(text, extra=[FACA2])
    e = loot._cites_inventory(st, text)
    assert e is not None and e["display_name"] == FACA


def test_affirmative_sell_unchanged(monkeypatch):
    class _Stub:
        def with_structured_output(self, _model):
            return self

        def invoke(self, _msgs):
            return loot.TradeIntent(mode="sell", item_ref="Faca de pedra-sabão", qty=1)

    monkeypatch.setattr(loot, "get_llm", lambda *a, **k: _Stub())
    st = _faca("Vendo a Faca de pedra-sabão")
    intent = loot._parse_trade_intent(st, "SHOP", "Vendo a Faca de pedra-sabão")
    assert intent.mode == "sell"


@pytest.mark.parametrize("text", CATALOG)
def test_catalog_questions_still_observe(text, no_llm):
    body = loot.loot_node(_faca(text))["messages"][0].content
    assert "consulta sem transação" in body
