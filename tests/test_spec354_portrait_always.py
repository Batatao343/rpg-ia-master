"""SPEC-354 R6: todo inimigo da view tem retrato (arte curada ou ícone da família), com a flag off."""

from __future__ import annotations

import api
from services import creature_art as ca
from tests.test_api_jogadas import _state


def test_marker_for_every_enemy_with_flag_off(monkeypatch):
    monkeypatch.setenv("RPG_CARD_DECK", "on")
    monkeypatch.setenv("RPG_CREATURE_ART", "off")
    monkeypatch.setattr(ca, "_curated", lambda *a, **k: None)
    block = api._combat_block(_state(monkeypatch))
    assert block["enemies"]
    for e in block["enemies"]:
        r = e["retrato"]
        assert r["estado"] == "marcador" and r["src"] is None and r["gerar"] is None
        assert r["icone"] == ca.FAMILY_ICON.get(r["familia"], "dark")


def test_portrait_for_has_no_offer_with_flag_off(monkeypatch):
    monkeypatch.setenv("RPG_CREATURE_ART", "off")

    out = ca.portrait_for({"id": "enemy_x_1", "name": "X", "arquetipo": "bruto"}, None, game_id="g")
    assert out["estado"] in ("marcador", "pronto") and out["gerar"] is None


def test_curated_family_art_is_ready(monkeypatch):
    monkeypatch.setenv("RPG_CREATURE_ART", "off")
    monkeypatch.setattr(ca, "_curated", lambda kind, key: "/fam.webp" if kind == "creature_family" else None)
    out = ca.portrait_for({"id": "enemy_x_1", "name": "X", "arquetipo": "bruto"}, None, game_id="g")
    assert out["estado"] == "pronto" and out["src"] == "/fam.webp"
