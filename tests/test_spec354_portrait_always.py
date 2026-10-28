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


def test_enemy_portrait_never_passes_registry_or_price(monkeypatch):
    """R6.3: sem a flag a view só lê o catálogo curado — nenhum registro (pago/DB) nem preço é entregue."""
    monkeypatch.setenv("RPG_CREATURE_ART", "off")
    seen: dict = {}
    real = ca.portrait_for

    class Boom:  # registro falso: falha se for consultado
        def get(self, *a, **k):
            raise AssertionError("registro consultado com a flag off")

    def spy(enemy, manifest, **kw):
        seen.update(kw)
        assert kw.get("registry") is None or not isinstance(kw["registry"], Boom)
        return real(enemy, manifest, **kw)

    monkeypatch.setattr(ca, "portrait_for", spy)
    out = api._enemy_portrait({"game_id": "g"}, {}, {"id": "enemy_x_1", "name": "X", "arquetipo": "bruto"})
    assert out["gerar"] is None
    assert seen.get("registry") is None and seen.get("quote_price") is None
