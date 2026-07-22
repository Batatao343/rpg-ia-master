"""Suíte da spec checkpoints-morte — vertical de morte na API (POST /game/death).

Offline. Cobre: ação barrada com queda pendente (409), Continuar (restaura do
checkpoint), Aceitar (memorial), e sem-pendência (409).
"""
import uuid

import pytest
from fastapi.testclient import TestClient
from langchain_core.messages import AIMessage, HumanMessage

import api
import persistence


@pytest.fixture()
def client():
    api._rate_hits.clear()
    return TestClient(api.app)


@pytest.fixture()
def saves_dir(tmp_path, monkeypatch):
    monkeypatch.setattr(persistence, "SAVES_DIR", str(tmp_path))
    return tmp_path


def _state(gid, *, hp, gold, death_pending=False, game_over=False, turn=8):
    return {
        "game_id": gid,
        "player": {"name": "Kael", "class_name": "Sangromante", "race": "Humano",
                   "level": 2, "hp": hp, "max_hp": 30, "gold": gold, "defense": 12,
                   "inventory": [], "known_abilities": ["ataque_basico"],
                   "equipment": {"weapon": None, "armor": None, "accessory": None}},
        "world": {"current_location": "Cripta", "current_location_id": "pm_cripta_afogada",
                  "turn_count": turn, "danger_level": 4, "world_clock": {"day": 3}},
        "messages": [HumanMessage(content="luto"), AIMessage(content="☠️ Você tomba.")],
        "campaign_plan": {"beats": []},
        "death_pending": death_pending, "game_over": game_over,
    }


def test_acao_com_queda_pendente_e_409(client, saves_dir):
    gid = str(uuid.uuid4())
    persistence.save_game_state(_state(gid, hp=0, gold=0, death_pending=True))
    r = client.post("/game/action", json={"input_text": "Ataco", "game_id": gid})
    assert r.status_code == 409


def test_death_continue_restaura_do_checkpoint(client, saves_dir):
    gid = str(uuid.uuid4())
    # checkpoint são (hp cheio, ouro 200); save vivo morto (hp 0, ouro 0)
    persistence.save_checkpoint(_state(gid, hp=30, gold=200, turn=5))
    persistence.save_game_state(_state(gid, hp=0, gold=0, death_pending=True, turn=9))
    r = client.post("/game/death", json={"game_id": gid, "choice": "continue"})
    assert r.status_code == 200
    body = r.json()
    assert body["player_stats"]["hp"] == 30       # restaurou o checkpoint
    assert body["player_stats"]["gold"] == 200
    assert body["death_pending"] is False
    # save vivo agora reflete o restaurado, sem game_over
    reloaded = persistence.load_game_state(persistence.save_path(gid))
    assert reloaded["player"]["gold"] == 200 and not reloaded.get("game_over")


def test_death_accept_vira_memorial(client, saves_dir):
    gid = str(uuid.uuid4())
    persistence.save_checkpoint(_state(gid, hp=30, gold=200))
    persistence.save_game_state(_state(gid, hp=0, gold=0, death_pending=True))
    r = client.post("/game/death", json={"game_id": gid, "choice": "accept"})
    assert r.status_code == 200
    reloaded = persistence.load_game_state(persistence.save_path(gid))
    assert reloaded.get("game_over") is True and not reloaded.get("death_pending")
    # memorial: ação seguinte é barrada (409)
    assert client.post("/game/action", json={"input_text": "x", "game_id": gid}).status_code == 409


def test_death_sem_pendencia_e_409(client, saves_dir):
    gid = str(uuid.uuid4())
    persistence.save_game_state(_state(gid, hp=20, gold=50, death_pending=False))
    r = client.post("/game/death", json={"game_id": gid, "choice": "continue"})
    assert r.status_code == 409


def test_death_choice_invalida_e_422(client, saves_dir):
    gid = str(uuid.uuid4())
    persistence.save_game_state(_state(gid, hp=0, gold=0, death_pending=True))
    r = client.post("/game/death", json={"game_id": gid, "choice": "revive"})
    assert r.status_code == 422
