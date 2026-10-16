"""SPEC-222 R2: um turno não vaza texto do jogador/nome do herói para stdout, stderr ou logs."""
from __future__ import annotations

import logging
import uuid

import pytest
from fastapi.testclient import TestClient

ACTION_SENTINEL = "SENTINELA-9f3c"
NAME_SENTINEL = "Sentinela-7b2a"


@pytest.fixture()
def client(monkeypatch):
    import api
    monkeypatch.setenv("RPG_RATE_LIMIT", "0")
    api._rate_hits.clear()
    return TestClient(api.app)


def _assert_clean(text: str) -> None:
    lowered = text.casefold()
    assert ACTION_SENTINEL.casefold() not in lowered
    assert NAME_SENTINEL.casefold() not in lowered


def test_turn_does_not_log_player_text_or_character_name(client, capfd, caplog):
    caplog.set_level(logging.DEBUG)
    response = client.post("/game/new", json={
        "name": NAME_SENTINEL, "race": "Humano", "class_name": "Sangromante",
        "region": "Nova Arcádia", "level": 1, "backstory": ""})
    assert response.status_code == 200, response.text
    game_id = response.json()["game_id"]
    for text in (f"Olho ao redor e digo {ACTION_SENTINEL}.",
                 f"Falo com o taverneiro sobre {ACTION_SENTINEL}.",
                 f"Ataco o inimigo gritando {ACTION_SENTINEL}!"):
        r = client.post("/game/action", json={"input_text": text, "game_id": game_id,
                                              "action_id": str(uuid.uuid4())})
        assert r.status_code == 200, r.text
    out, err = capfd.readouterr()
    _assert_clean(out)
    _assert_clean(err)
    _assert_clean("\n".join(record.getMessage() for record in caplog.records))


def test_prose_repetition_log_omits_narration(caplog):
    from services import prose_guard
    narration = f"{NAME_SENTINEL} caminha pela praça sob a chuva fina."
    with caplog.at_level(logging.WARNING, logger="rpg.prose"):
        prose_guard.log_if_repeats(narration, narration, where="storyteller")
    assert caplog.records, "a repetição continua observável"
    logged = "\n".join(record.getMessage() for record in caplog.records).casefold()
    assert "sentinela" not in logged and "caminha" not in logged  # nem trecho normalizado
