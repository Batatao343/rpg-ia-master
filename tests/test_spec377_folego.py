"""SPEC-377 item 2: uma unica implementacao de custo_folego."""

import json
from pathlib import Path

import pytest

from services import card_effects as fx
from services import cards

_EVID = Path(__file__).resolve().parents[1] / "docs" / "spec377" / "folego_divergencias.json"


def test_uma_implementacao():
    assert fx.custo_folego.__doc__.startswith("Alias")
    assert fx.custo_folego({"custo_folego": 2}) == cards.custo_folego({"custo_folego": 2})


def test_paridade_catalogo_com_jogo():
    """Oraculo: a coluna `jogo` da Etapa 0 (so as divergentes) vale para o catalogo todo."""
    oraculo = {
        d["id"]: d["jogo"] for d in json.loads(_EVID.read_text("utf-8"))["catalogo"]["divergentes"]
    }
    for cid, card in cards.all_cards().items():
        esperado = oraculo.get(cid)
        if esperado is not None:
            assert fx.custo_folego(card) == esperado, cid
        assert 0 <= fx.custo_folego(card) <= 3, cid


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
