"""SPEC-364 R23a: 409 de alvo invalido tira so a jogada certa (play_index), em JSON e em SSE; estado intacto."""

from __future__ import annotations

import json
from copy import deepcopy

import pytest

from tests import spec364_board_helpers as hp


@pytest.fixture
def seeded(monkeypatch):
    client, saved, gid = hp.api_client(monkeypatch)
    st = hp.open_combat(client, saved, gid)
    visible = [e["id"] for e in st["enemies"] if not e.get("dead")][0]
    other = hp.add_second_enemy(st)
    hp.hide_enemy(st, other)
    saved[gid] = deepcopy(st)
    cards = hp.hand_attack_cards(client, gid)
    assert len(cards) >= 1, "mao sem Carta de ataque jogavel"
    cid = cards[0]["id"]
    plays = [
        {"card_id": cid, "target_id": visible},
        {"card_id": cid, "target_id": other},  # o escondido: indice 1
        {"card_id": cid, "target_id": visible},
    ]
    return client, saved, gid, plays, cid


def _body(gid, plays):
    return {"game_id": gid, "input_text": "Jogo", "jogadas": plays}


def test_json_409_names_the_exact_play(seeded):
    client, saved, gid, plays, cid = seeded
    before = deepcopy(saved[gid])
    r = client.post("/game/action", json=_body(gid, plays))
    assert r.status_code == 409, r.text
    detail = r.json()["detail"]
    assert detail["code"] == "invalid_target"
    assert detail["play_index"] == 1 and detail["card_id"] == cid
    assert saved[gid] == before  # Folego, pilhas, rodada, mech_log e save intactos


def test_sse_409_names_the_exact_play(seeded):
    client, saved, gid, plays, cid = seeded
    before = deepcopy(saved[gid])
    r = client.post("/game/action/stream", json=_body(gid, plays))
    text = r.text
    assert "event: error" in text, text[:400]
    data = next(
        json.loads(line[len("data:"):].strip())
        for block in text.split("\n\n")
        if block.startswith("event: error")
        for line in block.splitlines()
        if line.startswith("data:")
    )
    assert data["detail"]["code"] == "invalid_target"
    assert data["detail"]["play_index"] == 1 and data["detail"]["card_id"] == cid
    assert saved[gid] == before


def test_first_invalid_play_index_zero(seeded):
    client, saved, gid, plays, cid = seeded
    hidden = plays[1]["target_id"]
    r = client.post("/game/action", json=_body(gid, [{"card_id": cid, "target_id": hidden}, plays[0]]))
    assert r.status_code == 409 and r.json()["detail"]["play_index"] == 0
