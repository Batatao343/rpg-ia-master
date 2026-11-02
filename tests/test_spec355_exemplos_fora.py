"""SPEC-355 R12: as 4 Cartas 2d6 de `exemplos.json` saem do pool jogavel, mas seguem no catalogo."""

from __future__ import annotations

from scripts.cards import sim
from services import cards

IDS = ("golpe_devoto", "corte_sangrento", "praga_lenta", "raio_cinza")


def test_exemplo_2d6_out_of_pool():
    assert cards.EXEMPLO_FORA_DO_POOL == frozenset(IDS)
    for cid in IDS:
        assert cards.get_card(cid) is not None  # golden, testes do motor e saves antigos
        assert cid in cards.all_cards()
    classes = {cards.get_card(c)["classe"] for c in IDS}
    for cls in classes | {""}:
        assert not {c["id"] for c in cards.cards_for_class(cls)} & set(IDS), cls
        assert not set(IDS) & set(sim.full_deck(cls, 5, "")) if cls else True


def test_creation_pool_skips_exemplos():
    import character_creator

    classes = {cards.get_card(c)["classe"] for c in IDS}
    assert classes
    for cls in sorted(classes):
        cards_out = character_creator._resolve_starting_cards({"level": 1}, cls, {})
        got = {
            cid
            for value in cards_out.values()
            if isinstance(value, list)
            for cid in value
            if isinstance(cid, str)
        }
        assert got, cls  # a criação monta algum Acervo
        assert not set(IDS) & got, cls
