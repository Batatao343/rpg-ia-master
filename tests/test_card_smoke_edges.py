"""SPEC-397 R4/R5: arestas do smoke da SPEC-369 pela API real (MockLLM)."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from tests.fixtures.spec368_seed import _legacy, _load, _new_game

FARO = "cor1_tro_faro_do_abismo"


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
