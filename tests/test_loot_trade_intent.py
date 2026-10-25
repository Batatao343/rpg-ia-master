"""SPEC-317 R3 — TradeIntent não chama o CLASSIFY quando o regex + catálogo já decidem."""

from __future__ import annotations

from agents import loot
from tests.test_remediacao_comerciante_real import _market_state


class _Boom:
    calls = 0

    def with_structured_output(self, _schema):
        _Boom.calls += 1
        return self

    def invoke(self, _messages):
        return loot.TradeIntent(mode="buy", item_ref="via-classify", qty=1)


def _install(monkeypatch):
    _Boom.calls = 0
    monkeypatch.setattr(loot, "get_llm", lambda **_k: _Boom())


def test_regex_shop_with_unique_catalog_item_skips_classify(monkeypatch):
    _install(monkeypatch)
    intent = loot._parse_trade_intent(_market_state(), "SHOP", "Compro a poção de cura menor.")
    assert _Boom.calls == 0
    assert intent.mode == "buy" and intent.item_ref == "pocao_cura" and intent.qty == 1


def test_ambiguous_item_calls_classify(monkeypatch):
    _install(monkeypatch)
    intent = loot._parse_trade_intent(
        _market_state(), "SHOP", "Compro a corda e a poção de cura menor."
    )
    assert _Boom.calls == 1
    assert intent.item_ref == "via-classify"


def test_explicit_quantity_calls_classify(monkeypatch):
    _install(monkeypatch)
    loot._parse_trade_intent(_market_state(), "SHOP", "Compro 2 cordas.")
    assert _Boom.calls == 1


def test_unknown_item_calls_classify(monkeypatch):
    _install(monkeypatch)
    loot._parse_trade_intent(_market_state(), "SHOP", "Compro um dragão de estimação.")
    assert _Boom.calls == 1


def test_craft_with_unique_recipe_skips_classify(monkeypatch):
    _install(monkeypatch)
    state = _market_state()
    intent = loot._parse_trade_intent(state, "CRAFT", "Forjo uma espada de aço temperado.")
    assert _Boom.calls == 0
    assert intent.mode == "craft"
    from services import economy

    assert economy.find_recipe(intent.item_ref) is not None


def test_number_words_call_classify(monkeypatch):
    _install(monkeypatch)
    loot._parse_trade_intent(_market_state(), "SHOP", "Compro doze cordas.")
    assert _Boom.calls == 1
    loot._parse_trade_intent(_market_state(), "SHOP", "Compro um par de cordas.")
    assert _Boom.calls == 2


def test_resolve_item_ref_does_not_mutate_state(monkeypatch):
    import copy

    state = _market_state()
    before = copy.deepcopy(state["world"])
    loot._resolve_item_ref(state, "buy", "compro a corda")
    assert state["world"] == before
