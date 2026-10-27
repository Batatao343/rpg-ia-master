"""SPEC-335 R6 - variedade minima do Acervo de cada Postura, por faixa de nivel.

Em cada faixa de nivel, o Acervo que o jogador de uma Postura (com UMA subclasse escolhida)
tem a seu dispor oferece:

* >= 10 Cartas;
* >= 4 ``kind``s de efeito distintos;
* >= 3 palavras-chave distintas (Vigilia, Rachadura, Eco, Guardar...).

Definicao (a mais estrita das razoaveis, sem afrouxar):

* faixa = nivel de entrada de cada tier (1, 4, 7, 9, 12, 15, 18, 20) mais o nivel 3, em que a
  subclasse e escolhida. O que a Postura oferece e CUMULATIVO (``level_req`` <= nivel): um nivel
  alto nunca tem menos opcoes que um baixo;
* nos niveis 1-2 so o TRONCO (Cartas sem subclasse) esta no Acervo; a partir do 3, tronco + a
  subclasse do jogador. A conta e POR SUBCLASSE (15 combinacoes), nunca a uniao das tres;
* Cartas de Virtude, basicas, Ápice (``apex``), status/maldicao e as neutras (``classe: Neutra``,
  so por espolio) nao entram.

Se uma Postura ou faixa falhar, o conserto e AUTORIA (mais Cartas), nunca afrouxar o numero.
"""

from __future__ import annotations

import pytest

from services import card_effects as fx
from services import cards

POSTURAS = {
    "Devoto do Abismo": ("consagrado", "zeloso", "enlutado"),
    "Sangromante": ("exposto", "avaro", "silencioso"),
    "Corruptor": ("biologia", "alma", "inorganica"),
    "Arcanista Cinzento": ("calibrado", "descoberto", "improvisador"),
    "Médico de Campo": ("cirurgiao_trincheira", "boticario", "cirurgiao_ferro"),
}
FAIXAS = (1, 3, 4, 7, 9, 12, 15, 18, 20)
MIN_CARTAS, MIN_KINDS, MIN_PALAVRAS = 10, 4, 3
NIVEL_DA_SUBCLASSE = 3


def acervo(postura: str, subclasse: str, nivel: int) -> list[dict]:
    """Cartas de jogador da Postura ao alcance de quem tem ``nivel`` e ``subclasse``."""
    return [
        c
        for c in cards.all_cards().values()
        if c.get("classe") == postura
        and c.get("tipo") in cards._DECK_TIPOS
        and not c.get("basica")
        and not c.get("apex")
        and c.get("tipo") not in cards.STATUS_TIPOS
        and int(c.get("level_req", 1) or 1) <= nivel
        and (
            not c.get("subclasse") or (nivel >= NIVEL_DA_SUBCLASSE and c["subclasse"] == subclasse)
        )
    ]


def medidas(cs: list[dict]) -> tuple[int, int, int]:
    kinds = {e.get("kind") for c in cs for e in fx.normalize(c)}
    palavras = {k for c in cs for k in fx.card_keyword_ids(c)}
    return len(cs), len(kinds), len(palavras)


CASOS = [
    (postura, sub, nivel) for postura, subs in POSTURAS.items() for sub in subs for nivel in FAIXAS
]


@pytest.mark.parametrize(("postura", "subclasse", "nivel"), CASOS)
def test_variedade_minima_por_postura_subclasse_e_faixa(postura, subclasse, nivel):
    n, kinds, palavras = medidas(acervo(postura, subclasse, nivel))
    assert n >= MIN_CARTAS, f"{postura}/{subclasse} nivel {nivel}: {n} Cartas (< {MIN_CARTAS})"
    assert kinds >= MIN_KINDS, f"{postura}/{subclasse} nivel {nivel}: {kinds} kinds"
    assert palavras >= MIN_PALAVRAS, f"{postura}/{subclasse} nivel {nivel}: {palavras} palavras"


def test_faixas_cobrem_todos_os_level_req_do_acervo():
    """Uma Carta num nivel fora das faixas nao seria medida: a lista de faixas tem de acompanhar."""
    niveis = {
        int(c.get("level_req", 1) or 1)
        for c in cards.all_cards().values()
        if c.get("classe") in POSTURAS and not c.get("basica")
    }
    assert niveis <= set(FAIXAS), sorted(niveis - set(FAIXAS))


def test_oferta_e_cumulativa_e_neutras_ficam_de_fora():
    for postura, subs in POSTURAS.items():
        for sub in subs:
            antes = 0
            for nivel in FAIXAS:
                ids = {c["id"] for c in acervo(postura, sub, nivel)}
                assert len(ids) >= antes, (postura, sub, nivel)
                assert not any(i.startswith("neu1_") for i in ids)
                antes = len(ids)
