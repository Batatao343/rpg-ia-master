"""SPEC-377 item 2: uma unica implementacao de custo_folego."""

import pytest

from services import card_effects as fx
from services import cards


def _jogo_antigo(card: dict) -> int:
    """Regra do jogo congelada (cópia literal de `cards.custo_folego` antes da SPEC-377)."""
    if "custo_folego" in card:
        try:
            return max(0, min(3, int(card["custo_folego"])))
        except (TypeError, ValueError):
            pass
    effect = card.get("efeito") or {}
    freq = str(card.get("frequencia", "livre"))
    if card.get("apex") or freq == "descanso_longo":
        return 3
    try:
        dano_base = int(effect.get("dano_base", 0) or 0)
        tier = int(card.get("tier", 1) or 1)
    except (TypeError, ValueError):
        dano_base, tier = 0, 1
    if tier >= 3 or dano_base >= 8:
        return 2
    if freq == "livre" and str(effect.get("kind") or "") not in {"dano", "dot", "contra_ataque"}:
        return 0
    return 1


def test_uma_implementacao(monkeypatch):
    """O nome do lint é alias: um patch na implementação única chega a `fx.custo_folego`."""
    monkeypatch.setattr(cards, "custo_folego", lambda card: 42)
    assert fx.custo_folego({}) == 42


def test_paridade_catalogo_com_jogo():
    """Catálogo inteiro e `effective_card` (Ruptura, evolução A/B) iguais à regra antiga do jogo."""
    for cid, card in cards.all_cards().items():
        assert fx.custo_folego(card) == _jogo_antigo(card), cid
        assert cards.custo_folego(card) == _jogo_antigo(card), cid
        if not (card.get("ruptura") or card.get("evolucao")):
            continue
        for player in ({}, {"evolved_cards": {cid: "A"}}, {"evolved_cards": {cid: "B"}}):
            for rup in (False, True):
                eff = cards.effective_card(player, cid, ruptura=rup)
                assert fx.custo_folego(eff) == _jogo_antigo(eff), (cid, player, rup)


@pytest.mark.parametrize("cid", ["cor_toque", "toque_corrosivo"])
def test_dot_livre_custa_1_no_lint(cid):
    card = cards.all_cards()[cid]
    assert card.get("custo_folego") is None
    assert fx.custo_folego(card) == 1


@pytest.mark.parametrize(
    "card",
    [
        {"custo_folego": "x", "frequencia": "livre"},
        {"efeito": {"kind": "dano", "dano_base": "alto"}, "tier": "?"},
        {"efeito": {"kind": "dano", "dano_base": None}},
    ],
)
def test_valor_invalido_nao_quebra(card):
    assert fx.custo_folego(card) in (0, 1, 2)
