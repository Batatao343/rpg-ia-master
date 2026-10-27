"""SPEC-328 R3/R4 - migração idempotente de save para o Baralho de Conflito."""

import copy

import pytest

from services import card_piles as cp
from services import cards

CLASSES = ["Devoto do Abismo", "Sangromante", "Corruptor", "Arcanista Cinzento", "Médico de Campo"]


def _old_player(class_name="Sangromante"):
    pool = [
        c["id"]
        for c in cards.cards_for_class(class_name)
        if not c.get("subclasse") and c.get("level_req", 1) == 1
    ]
    return {
        "class_name": class_name,
        "level": 1,
        "known_cards": pool[:6],
        "prepared_cards": pool[:4],
        "virtue_cards": [{"card_id": "vir_x"}],
    }


@pytest.mark.parametrize("cls", CLASSES)
def test_save_antigo_ganha_baralho_valido(cls):
    p = _old_player(cls)
    original = list(p["prepared_cards"])
    assert cp.migrate_deck(p) is True
    deck = p["deck"]
    basics = cards.basicas_for_class(cls)
    assert cards.DECK_MIN <= len(deck) <= cards.DECK_MAX
    assert deck.count(basics["golpe"][0]) == 4 and deck.count(basics["guarda"][0]) == 4
    assert deck.count(basics["assinatura"][0]) == 1
    for cid in original:
        tipo = cards.get_card(cid)["tipo"]
        assert (cid in deck) == (tipo in ("ativa", "reacao", "utilitaria"))
    assert set(deck) <= set(p["prepared_cards"])  # R4: prepared deriva do baralho


def test_idempotente():
    p = _old_player()
    cp.migrate_deck(p)
    first = copy.deepcopy(p)
    assert cp.migrate_deck(p) is False
    assert p == first


def test_passivas_e_virtude_ficam_fora_do_baralho():
    p = _old_player()
    passiva = next(
        c["id"]
        for c in cards.cards_for_class(p["class_name"])
        if c.get("tipo") == "passiva" and not c.get("subclasse")
    )
    p["known_cards"].append(passiva)
    p["prepared_cards"].append(passiva)
    cp.migrate_deck(p)
    assert passiva not in p["deck"]
    assert passiva in p["prepared_cards"]  # segue como talento permanente
    assert "vir_x" not in p["deck"]


def test_baralho_existente_nao_e_sobrescrito():
    p = _old_player()
    p["deck"] = ["bas_san_golpe"] * 12
    assert cp.migrate_deck(p) is False
    assert p["deck"] == ["bas_san_golpe"] * 12


def test_basica_usavel_mesmo_fora_das_preparadas_antigas():
    """`use_card` aceita carta do baralho (as basicas nao estao no Acervo)."""
    p = _old_player()
    cp.migrate_deck(p)
    res = cards.use_card({"player": p}, "bas_san_golpe")
    assert res["ok"], res
