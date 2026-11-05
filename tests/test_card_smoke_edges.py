"""SPEC-397 R4/R5: arestas do smoke da SPEC-369 pela API real (MockLLM)."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from tests.fixtures.spec368_seed import _legacy, _load, _new_game

FARO = "cor1_tro_faro_do_abismo"
LAST_LOG: list[str] = [""]  # log da última chamada de `_reward_faro`


@pytest.fixture
def client(tmp_path):
    import api

    with _legacy(str(tmp_path)):
        yield TestClient(api.app)


def test_medico_starts_with_the_surgical_saw_equipped(client):
    """R4: a "Serra Cirúrgica" da prosa do smoke é a arma equipada de saída do Médico de Campo."""
    import inventory

    gid = _new_game(client, "Médico de Campo", "Smoke397")
    assert "serra_cirurgica" in inventory.equipped_items(_load(gid)["player"])


def test_faro_do_abismo_by_reward_is_listed_and_negates_ambush(client):
    """R5: a passiva que chega pelo espólio entra em `player_stats.cards` e anula a emboscada."""
    import persistence
    from agents.combat import _has_vigilia, _opening_initiator
    from api_presenters import _cards_block

    gid = _new_game(client, "Corruptor", "Smoke397")
    state = _load(gid)
    assert FARO not in (state["player"].get("known_cards") or [])
    state["player"]["espolio_pendente"] = {
        "id": "c1",
        "ofertas": [FARO],
        "origem": "vitoria",
        "turno": 1,
        "recusa_ouro": 15,
    }
    assert persistence.save_game_state(state)
    r = client.post("/game/espolio", json={"game_id": gid, "card_id": FARO})
    assert r.status_code == 200, r.text
    player = _load(gid)["player"]
    assert FARO in player["known_cards"]
    assert any(c["id"] == FARO for c in _cards_block(player))
    assert _has_vigilia(player)
    assert _opening_initiator({"encounter_surprise": "enemy"}, "", player)[0] is None


def _reward_faro(client, gid, mutate=None):
    import persistence

    state = _load(gid)
    if mutate:
        mutate(state["player"])
    state["player"]["espolio_pendente"] = {
        "id": "c1",
        "ofertas": [FARO],
        "origem": "vitoria",
        "turno": 1,
        "recusa_ouro": 15,
    }
    assert persistence.save_game_state(state)
    r = client.post("/game/espolio", json={"game_id": gid, "card_id": FARO})
    assert r.status_code == 200, r.text
    LAST_LOG[:] = [r.json().get("log", "")]
    return _load(gid)["player"]


def test_passive_reward_keeps_four_of_four_and_prepare_still_works(client):
    """P1-1: nível 1 com 4 Preparadas: a passiva não toma slot; reenviar a lista atual passa."""
    from agents.combat import _has_vigilia
    from services import cards

    gid = _new_game(client, "Corruptor", "Smoke397")
    player = _reward_faro(client, gid)
    assert "sempre ativa" in LAST_LOG[0] and "não ocupa Preparação" in LAST_LOG[0]
    assert len(player["prepared_cards"]) == 4 and FARO not in player["prepared_cards"]
    assert FARO not in (player.get("deck") or [])
    assert _has_vigilia(player)
    state = _load(gid)
    assert cards.set_prepared(state, list(player["prepared_cards"]))["ok"]


def test_passive_reward_with_deck_on_before_first_conflict(client):
    """Baralho on sem `deck` ainda (compra antes do 1º conflito): a passiva vale mesmo assim."""
    from agents.combat import _has_vigilia

    gid = _new_game(client, "Corruptor", "Smoke397")
    player = _reward_faro(client, gid, lambda p: p.pop("deck", None))
    assert not player.get("deck") and _has_vigilia(player)


def test_deactivate_deck_keeps_the_passive_effect(client):
    from agents.combat import _has_vigilia
    from services import card_piles

    gid = _new_game(client, "Corruptor", "Smoke397")
    player = _reward_faro(client, gid)
    player["prepared_cards_pre_deck"] = list(player["prepared_cards"])
    card_piles.deactivate_deck(player)
    assert _has_vigilia(player)


def test_passive_reason_is_permanent_and_vigilia_id_has_one_source():
    from agents import combat
    from services import card_rewards, initiative_cards

    assert card_rewards.acervo_reason({"deck": ["x"]}, FARO) == "passiva_permanente"
    assert combat.VIGILIA_CARD_ID is initiative_cards.VIGILIA_CARD_ID
