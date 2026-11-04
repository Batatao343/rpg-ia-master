"""SPEC-384 D8: alias de rota removido; a rota canônica de logout continua."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

import api

GID = "11111111-1111-4111-8111-111111111111"
BODY = {
    "action_id": "33333333-3333-4333-8333-333333333333",
    "quote_id": "22222222-2222-4222-8222-222222222222",
    "confirmed": True,
}


@pytest.fixture()
def client(monkeypatch):
    monkeypatch.setenv("RPG_RATE_LIMIT", "0")
    return TestClient(api.app)


def test_alias_art_player_confirm_removido(client):
    assert client.post(f"/game/{GID}/art/player/confirm", json=BODY).status_code in (404, 405)
    paths = {getattr(r, "path", "") for r in api.app.routes}
    assert "/game/{game_id}/art/player/confirm" not in paths
    assert "/game/{game_id}/art/confirm" in paths


def test_auth_logout_canonico_mantido():
    paths = {getattr(r, "path", "") for r in api.app.routes}
    assert "/auth/logout" in paths
