"""SPEC-357 R8/R9/R17 - API da loja de Cartas: bloco publico, compra idempotente, flag off."""

from __future__ import annotations

import uuid

import pytest
from fastapi.testclient import TestClient

import persistence
from services import card_shop


@pytest.fixture(autouse=True)
def _on(monkeypatch):
    monkeypatch.setenv("RPG_CARD_REWARDS", "on")


@pytest.fixture()
def client(tmp_path, monkeypatch):
    import api

    monkeypatch.setattr(persistence, "SAVES_DIR", str(tmp_path))
    monkeypatch.setenv("RPG_RATE_LIMIT", "0")
    api._rate_hits.clear()
    return TestClient(api.app)


def _new(client):
    r = client.post(
        "/game/new",
        json={
            "name": "Loja",
            "race": "Humano",
            "class_name": "Sangromante",
            "region": "Brekmar",
            "level": 4,
            "backstory": "",
        },
    )
    assert r.status_code == 200, r.text
    gid = r.json()["game_id"]
    st = persistence.load_game_state(persistence.save_path(gid))
    st["world"]["current_location_id"] = "brekmar"
    st["player"]["gold"] = 500
    assert persistence.save_game_state(st)
    return gid


def _load(gid):
    return persistence.load_game_state(persistence.save_path(gid))


def _stats(client, gid):
    r = client.get("/game/state", params={"game_id": gid})
    assert r.status_code == 200, r.text
    return r.json()["player_stats"]


def _post(client, gid, card_id, action_id=None):
    return client.post(
        "/game/loja-cartas",
        json={"game_id": gid, "action_id": action_id or str(uuid.uuid4()), "card_id": card_id},
    )


def test_state_has_loja_when_on(client):
    gid = _new(client)
    shop = _stats(client, gid)["loja_cartas"]
    assert shop["merchant_id"] == "quinquilharias_brekmar" and len(shop["ofertas"]) == 3
    assert all(not o["id"].startswith("neu1_ka_") for o in shop["ofertas"])


def test_api_state_has_no_loja_when_off(client, monkeypatch):
    gid = _new(client)
    monkeypatch.setenv("RPG_CARD_REWARDS", "off")
    assert "loja_cartas" not in _stats(client, gid)


def test_api_loja_cartas_ok_and_idempotent(client):
    gid = _new(client)
    shop = _stats(client, gid)["loja_cartas"]
    pick = shop["ofertas"][0]
    action = str(uuid.uuid4())
    r = _post(client, gid, pick["id"], action)
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["player_stats"]["gold"] == 500 - pick["preco"]
    assert body["player_stats"]["loja_cartas"]["ofertas"][0]["conhecida"] is True
    again = _post(client, gid, pick["id"], action)  # mesmo action_id: recibo, sem nova cobranca
    assert again.status_code in (200, 400)  # legacy rejeita a repeticao; DB devolve o recibo
    st = _load(gid)
    assert st["player"]["gold"] == 500 - pick["preco"]
    assert st["player"]["known_cards"].count(pick["id"]) == 1


def test_api_rejections(client):
    gid = _new(client)
    r = _post(client, gid, "neu1_ka_xadrez_com_lyss")
    assert r.status_code == 400 and r.json()["code"] == "loja_cartas_rejected"
    pick = _stats(client, gid)["loja_cartas"]["ofertas"][0]["id"]
    assert _post(client, gid, pick).status_code == 200
    r = _post(client, gid, pick)  # ja conhecida
    assert r.status_code == 400 and r.json()["code"] == "loja_cartas_rejected"
    st = _load(gid)
    st["combat"] = {"active": True}
    assert persistence.save_game_state(st)
    other = card_shop.shelf(st)[1][1]
    r = _post(client, gid, other)
    assert r.status_code == 409


def test_api_loja_cartas_off_409(client, monkeypatch):
    gid = _new(client)
    pick = _stats(client, gid)["loja_cartas"]["ofertas"][0]["id"]
    monkeypatch.setenv("RPG_CARD_REWARDS", "off")
    r = _post(client, gid, pick)
    assert r.status_code == 409 and r.json()["code"] == "card_rewards_off"
    assert _load(gid)["player"]["gold"] == 500
