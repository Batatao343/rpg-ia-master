"""SPEC-357 R8/R9/R17 - API da loja de Cartas: bloco publico, compra idempotente, flag off."""

from __future__ import annotations

import uuid

import pytest
from fastapi.testclient import TestClient

import persistence
from services import card_shop
from tests.fakes.two_principals import two_principals  # noqa: F401  (fixture)


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
    # legacy nao tem recibo: a repeticao cai em "ja conhece" (400) e nunca cobra de novo
    assert again.status_code == 400 and again.json()["code"] == "loja_cartas_rejected"
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


# ---------------------------------------------------------------- P2-6: perfil DB offline
def test_db_profile_replay_returns_receipt_single_debit(monkeypatch, tmp_path, two_principals):
    """R9: no perfil DB o mesmo `action_id` devolve o recibo e cobra uma vez so (rodar sem -n)."""
    tp = two_principals
    monkeypatch.setenv("RPG_CARD_REWARDS", "on")
    stored = tp.store.get(tp.a, tp.game_a)
    state = dict(stored.state)
    state.pop("_storage_version", None)
    state["world"] = {**state["world"], "current_location_id": "brekmar"}
    state["player"] = {**state["player"], "gold": 500, "level": 4}
    tp.store.save(tp.a, tp.game_a, stored.version, state)
    gid = str(tp.game_a)
    shop = tp.client_a.get("/game/state", params={"game_id": gid}).json()["player_stats"][
        "loja_cartas"
    ]
    pick = shop["ofertas"][0]
    body = {"game_id": gid, "action_id": str(uuid.uuid4()), "card_id": pick["id"]}
    first = tp.client_a.post("/game/loja-cartas", json=body)
    assert first.status_code == 200, first.text
    again = tp.client_a.post("/game/loja-cartas", json=body)
    assert again.status_code == 200 and again.json() == first.json()
    final = tp.store.get(tp.a, tp.game_a).state["player"]
    assert final["gold"] == 500 - pick["preco"]
    assert final["known_cards"].count(pick["id"]) == 1


# ---------------------------------------------------------------- P2-5: round-trip e save pre-357
def test_quest_card_fields_round_trip_and_pre357_quest_loads(client):
    from services import quest_log

    gid = _new(client)
    st = _load(gid)
    planned = {
        "id": "q357",
        "title": "Caça",
        "status": "completed",
        "location_id": "brekmar",
        "region_id": "brekmar",
        "reward_hint": "justa · uma técnica",
        "reward_card_planned": True,
        "reward_card_label": "justa",
        "reward_card": "neu1_ge_lanterna_de_aranha",
    }
    old = {"id": "q_old", "title": "Antiga", "status": "active", "reward_hint": "modesta"}
    st["quests"] = [planned, old]
    assert persistence.save_game_state(st)
    back = _load(gid)["quests"]
    assert back[0] == planned and back[1] == old
    view = quest_log.public_quest_view(back[0], 5)
    assert view["reward_card_name"] == "Lanterna de Aranha" and "reward_card_planned" not in view
    assert "reward_card_name" not in quest_log.public_quest_view(back[1], 5)
    assert client.get("/game/state", params={"game_id": gid}).status_code == 200
