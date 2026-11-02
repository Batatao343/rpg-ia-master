"""SPEC-364 R22 (anti-deriva): a view da API tem a forma e os valores que a fixture do e2e usa."""

from __future__ import annotations

from copy import deepcopy
from pathlib import Path

from tests import spec364_board_helpers as hp

E2E = Path(__file__).resolve().parents[1] / "web" / "e2e" / "spec364-hidden-target.spec.ts"


def test_view_marks_hidden_enemy_and_filters_hand_targets(monkeypatch):
    client, saved, gid = hp.api_client(monkeypatch)
    st = hp.open_combat(client, saved, gid)
    visible = [e["id"] for e in st["enemies"] if not e.get("dead")][0]
    hidden = hp.add_second_enemy(st)
    hp.hide_enemy(st, hidden)
    saved[gid] = deepcopy(st)
    view = client.get("/game/state", params={"game_id": gid}).json()["combat"]
    positions = {p["participant_id"]: p for p in view["scene"]["positions"]}
    assert positions[hidden]["concealment"] == "escondido"
    assert positions[visible]["concealment"] == "visivel"
    hand = view["pilhas"]["mao"]
    attacks = [m for m in hand if m.get("alvo") == "inimigo"]
    assert attacks, "mao sem Carta de inimigo"
    for card in attacks:
        assert card["valid_targets"] == [visible]  # o escondido nao entra
        assert card["invalid_reason"] is None


def test_e2e_fixture_uses_the_same_literals():
    text = E2E.read_text(encoding="utf-8")
    assert (
        'concealment = "escondido"' in text
    )  # valor que o motor emite em `scene.positions[*].concealment`
    assert "valid_targets" in text and "invalid_reason" in text
    assert "bas_" in text  # Carta basica da mao
