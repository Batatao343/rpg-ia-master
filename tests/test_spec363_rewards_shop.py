"""SPEC-363 R31/R32: espólio sem utilitária; destino da loja com o motivo certo."""

from __future__ import annotations

import pytest

from services import card_rewards as cr
from services import cards
from tests.test_card_rewards import _player, _state


@pytest.fixture(autouse=True)
def _on(monkeypatch):
    monkeypatch.setenv("RPG_CARD_REWARDS", "on")


@pytest.mark.parametrize(
    "klass", ["Sangromante", "Arcanista", "Corvo", "Devoto", "Médico de Campo"]
)
def test_rewards_never_offer_utility(klass):
    offered = 0
    for seed in range(200):
        for cid in cr.roll_rewards(_state(class_name=klass), None, seed):
            offered += 1
            assert (cards.get_card(cid) or {}).get("tipo") != "utilitaria", (klass, seed, cid)
    assert offered > 0


def _full_deck_player(n):
    ids = [c for c, v in cards.all_cards().items() if v.get("tipo") == "ativa"][:n]
    player = _player()
    player["deck"] = list(ids)
    return player


def test_shop_destination_reason_deck_full_vs_room():
    full = _full_deck_player(cards.DECK_MAX)
    extra = next(
        c
        for c, v in cards.all_cards().items()
        if c not in full["deck"] and v.get("tipo") == "ativa"
    )
    assert cr.acervo_reason(dict(full), extra) == "baralho_cheio"
    room = _full_deck_player(cards.DECK_MIN)
    assert cr.acervo_reason(dict(room), extra) is None  # há vaga: nunca "Baralho cheio"


def test_shop_destination_reason_copy_limit():
    player = _full_deck_player(cards.DECK_MIN)
    common = next(
        c
        for c, v in cards.all_cards().items()
        if v.get("tipo") == "ativa" and v.get("patamar") not in cards._COMMON_PATAMARES
    )
    player["deck"] = [*player["deck"][:-1], common]
    assert cr.acervo_reason(dict(player), common) == "limite_de_copias"


def test_shop_destination_reason_without_deck(monkeypatch):
    player = _player(level=1)
    player["deck"] = []
    player["prepared_cards"] = list(range(60))  # sem vaga nas Preparadas
    some = next(iter(cards.all_cards()))
    player["prepared_cards"] = [f"x{i}" for i in range(60)]
    monkeypatch.setenv("RPG_CARD_DECK", "on")
    assert cr.acervo_reason(dict(player), some) == "sem_baralho"
    monkeypatch.setenv("RPG_CARD_DECK", "off")
    assert cr.acervo_reason(dict(player), some) == "preparadas_cheias"


def test_public_shop_exposes_reason_only_for_acervo():
    from services import card_shop

    state = {
        "game_id": "g363",
        "player": {**_full_deck_player(cards.DECK_MAX), "gold": 999, "level": 5},
        "world": {
            "current_location_id": "brekmar",
            "visited": ["brekmar"],
            "turn_count": 3,
            "world_clock": {"day": 1, "period": "manha"},
            "merchant_stocks": {},
            "merchant_restock_day": {},
            "danger_level": 1,
        },
        "world_projection": {},
        "factions": [],
    }
    shop = card_shop.public_shop(state)
    if shop:
        for offer in shop["ofertas"]:
            if offer["destino"] == "acervo":
                assert offer.get("destino_motivo") == "baralho_cheio"
            else:
                assert "destino_motivo" not in offer
