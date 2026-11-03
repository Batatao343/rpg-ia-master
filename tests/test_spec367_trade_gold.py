"""SPEC-367 R15-R17: ouro na narração de compra/venda (contexto antes/preço/depois + validação V-G)."""

from __future__ import annotations

import pytest

from agents import loot
from services import prose_guard
from tests.fixtures import spec367_smoke as fx
from tests.test_card_shop_loot_text import _offer, _state


def test_vg_rejects_smoke_text():
    assert not prose_guard.gold_claims_ok(fx.SMOKE_TEXT, allowed=fx.ALLOWED, gold_after=fx.DEPOIS)


def test_vg_accepts_correct_text():
    assert prose_guard.gold_claims_ok(fx.CORRECT_TEXT, allowed=fx.ALLOWED, gold_after=fx.DEPOIS)


@pytest.mark.parametrize("text", fx.BENIGN)
def test_vg_benign_corpus(text):
    assert prose_guard.gold_claims_ok(text, allowed=fx.ALLOWED, gold_after=fx.DEPOIS), text


def test_vg_all_coins_ok_when_zero():
    t = "Você entrega todas as moedas da bolsa ao mercador."
    assert prose_guard.gold_claims_ok(t, allowed={50}, gold_after=0)
    assert not prose_guard.gold_claims_ok(t, allowed={50}, gold_after=5)


@pytest.mark.parametrize(
    "text",
    [
        "Ele recebe 30 moedas.",
        "Você paga vinte e cinco peças de ouro.",
        "Duas coroas tilintam no balcão.",
        "Você entrega quarenta moedas ao ferreiro.",
        "A bolsa fica vazia depois do trato.",
        "Você não deixa nenhuma moeda para trás... sem moeda alguma.",
        "Você gasta todo o seu ouro na Carta.",
    ],
)
def test_vg_number_words(text):
    assert not prose_guard.gold_claims_ok(text, allowed=fx.ALLOWED, gold_after=fx.DEPOIS), text


def test_vg_number_words_allowed():
    assert prose_guard.gold_claims_ok(
        "Cinco moedas sobram.", allowed=fx.ALLOWED, gold_after=fx.DEPOIS
    )
    assert prose_guard.gold_claims_ok(
        "Quarenta e cinco moedas ficam na mão dele.", allowed=fx.ALLOWED, gold_after=fx.DEPOIS
    )


class _Capture:
    """LLM simulado: guarda o contexto da narração e devolve um texto fixo."""

    def __init__(self, reply):
        self.reply = reply
        self.contexts: list[str] = []

    def invoke(self, msgs, *a, **k):
        from langchain_core.messages import AIMessage

        self.contexts.append(str(msgs[-1].content))
        return AIMessage(content=self.reply)

    def with_structured_output(self, _m):
        return self


def _install(monkeypatch, reply):
    cap = _Capture(reply)
    monkeypatch.setattr(loot, "get_llm", lambda *a, **k: cap)
    monkeypatch.setattr(
        "services.narrative_sink.narrate_text",
        lambda llm, msgs, **k: llm.invoke(msgs),
    )
    return cap


@pytest.fixture(autouse=True)
def _on(monkeypatch):
    monkeypatch.setenv("RPG_CARD_REWARDS", "on")


def test_narrate_gold_check_rejects_to_fallback(monkeypatch):
    cap = _install(monkeypatch, fx.SMOKE_TEXT)
    out = loot._narrate("ctx", "A forja fecha o negócio.", gold_check=(fx.ALLOWED, fx.DEPOIS))
    assert out == "A forja fecha o negócio."
    assert cap.contexts


def test_narrate_gold_check_accepts_correct(monkeypatch):
    _install(monkeypatch, fx.CORRECT_TEXT)
    out = loot._narrate("ctx", "fb", gold_check=(fx.ALLOWED, fx.DEPOIS))
    assert out == fx.CORRECT_TEXT


def test_gold_context_line():
    line = loot._gold_context(50, 45, 5)
    assert "Ouro antes: 50. Preço: 45. Ouro depois: 5." in line
    assert "últimas moedas" in line and "não cite outro número" in line
    assert "últimas moedas" not in loot._gold_context(50, 50, 0)


def _card_buy(monkeypatch, reply):
    cap = _install(monkeypatch, reply)
    st = _state("")
    _, name = _offer(st)
    out = loot.loot_node(_state(f"Compro o {name}, por favor."))
    return cap, out["messages"][0].content, name


def test_context_has_before_price_after(monkeypatch):
    cap, body, _ = _card_buy(monkeypatch, fx.CORRECT_TEXT)
    ctx = " ".join(cap.contexts)
    assert "Ouro antes: 500. Preço: " in ctx and "Ouro depois: " in ctx
    assert "[SISTEMA] +1 Carta" in body


def test_vg_rejection_uses_merchant_fallback(monkeypatch):
    _, body, _ = _card_buy(monkeypatch, "Você entrega as últimas 45 moedas ao mercador.")
    assert "últimas" not in body
    assert "fecha o negócio sem cerimônia" in body
    assert "[SISTEMA] +1 Carta" in body


def test_sell_path_validated(monkeypatch):
    _install(monkeypatch, "Você entrega as últimas 4000 moedas.")
    monkeypatch.setattr(
        loot,
        "_parse_trade_intent",
        lambda *a, **k: loot.TradeIntent(mode="sell", item_ref="corda", qty=1),
    )
    st = _state("Vendo a corda", location="na_anel_dourado")
    body = loot.loot_node(st)["messages"][0].content
    assert "4000" not in body and "últimas" not in body
    assert "[SISTEMA]" in body
