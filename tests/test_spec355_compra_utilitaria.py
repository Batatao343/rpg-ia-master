"""SPEC-355 R11: utilitaria fica no baralho, mas nunca entra na mao do conflito."""

from __future__ import annotations

import json
import random

import pytest

from services import card_piles as cp
from services import cards

POSTURAS = [
    "Devoto do Abismo",
    "Sangromante",
    "Corruptor",
    "Arcanista Cinzento",
    "Médico de Campo",
]


def _deck_with_utility(cls: str) -> tuple[list[str], str]:
    from scripts.cards import sim

    deck = sim.full_deck(cls, 5, "")
    util = next(
        (cid for cid in deck if (cards.get_card(cid) or {}).get("tipo") == "utilitaria"),
        None,
    )
    if util is None:
        pool = [c["id"] for c in cards.cards_for_class(cls) if c.get("tipo") == "utilitaria"]
        assert pool, f"{cls} sem utilitaria no acervo"
        util = pool[0]
        deck = [*deck[:-1], util]
    return deck, util


def _player(cls: str, deck: list[str]) -> dict:
    return {"class_name": cls, "deck": deck, "level": 5}


@pytest.mark.parametrize("cls", POSTURAS)
def test_no_utility_in_combat_hand(cls):
    deck, util = _deck_with_utility(cls)
    for seed in range(40):
        piles = cp.start_piles(_player(cls, deck), seed)
        assert util in piles["fora_do_conflito"]
        seen = piles["mao"] + piles["compra"] + piles["descarte"] + piles["exaurida"]
        assert not any((cards.get_card(c) or {}).get("tipo") == "utilitaria" for c in seen)
        for _ in range(30):  # compra o monte inteiro e embaralha varias vezes
            cp.draw(piles, 3, random.Random(seed))
            piles["descarte"].extend(piles["mao"])
            piles["mao"] = []
        assert not any(
            (cards.get_card(c) or {}).get("tipo") == "utilitaria" for c in piles["compra"]
        )


def test_utility_kept_in_deck_and_acervo():
    deck, util = _deck_with_utility("Médico de Campo")
    player = _player("Médico de Campo", deck)
    cp.start_piles(player, 1)
    assert util in player["deck"]  # o baralho da ficha não muda
    assert any(c["id"] == util for c in cards.cards_for_class("Médico de Campo"))


def test_old_save_with_utility_in_compra_loads():
    deck, util = _deck_with_utility("Médico de Campo")
    piles = cp.start_piles(_player("Médico de Campo", deck), 3)
    piles.pop("fora_do_conflito")
    piles["compra"].append(util)  # conflito em voo, salvo antes da 355
    restored = json.loads(json.dumps(piles))
    assert util in restored["compra"]  # continua comprável até o próximo conflito
    cp.draw(restored, len(restored["compra"]) + 1)
