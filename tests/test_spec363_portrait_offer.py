"""SPEC-363 R2/R4: a oferta `retrato.gerar` usa o mesmo portão da cotação."""

from __future__ import annotations

import pytest

import api
import api_core
import api_presenters
import routes.art
from services import kill_switches
from services.shard_pricing import PricingUnavailable


class _Switches:
    def __init__(self, on: bool):
        self.on = on

    def is_enabled(self, key):
        return self.on

    def require(self, key):
        if not self.on:
            raise kill_switches.SwitchOff(key)


def _wire(monkeypatch, *, switch: bool, pricing: bool):
    monkeypatch.setattr(kill_switches, "get_switches", lambda: _Switches(switch))

    def _require(category, **kw):
        if not pricing:
            raise PricingUnavailable("stale")

    import services.finops_alerts as fa

    monkeypatch.setattr(fa, "require_paid_effect", _require)
    monkeypatch.setattr(api_presenters, "_portrait_price_estilhas", lambda: 3)


def test_offer_requires_image_switch(monkeypatch):
    _wire(monkeypatch, switch=False, pricing=True)
    assert api._portrait_offer_price() is None


def test_offer_requires_fresh_pricing(monkeypatch):
    _wire(monkeypatch, switch=True, pricing=False)
    assert api._portrait_offer_price() is None


def test_offer_requires_price(monkeypatch):
    _wire(monkeypatch, switch=True, pricing=True)
    monkeypatch.setattr(api_presenters, "_portrait_price_estilhas", lambda: None)
    assert api._portrait_offer_price() is None


def test_offer_open_when_gate_open(monkeypatch):
    _wire(monkeypatch, switch=True, pricing=True)
    assert api._portrait_offer_price() == 3


def test_offer_requires_dynamic_art_env(monkeypatch):
    monkeypatch.setattr(api_core, "_database_profile", lambda: True)
    monkeypatch.delenv("RPG_DYNAMIC_ART_ENABLED", raising=False)
    monkeypatch.setenv("RPG_CREATURE_ART", "on")
    assert api_presenters._creature_art_live() is False


def test_offer_store_error_is_closed(monkeypatch):
    class _Boom:
        def is_enabled(self, key):
            raise RuntimeError("store down")

    monkeypatch.setattr(kill_switches, "get_switches", lambda: _Boom())
    assert api._image_effect_open() is False


class _Registry:
    def get(self, key):
        return None


@pytest.mark.parametrize("price", [None, 3])
@pytest.mark.parametrize("fresh", [False, True])
@pytest.mark.parametrize("switch", [False, True])
@pytest.mark.parametrize("env", [False, True])
@pytest.mark.parametrize("db", [False, True])
@pytest.mark.parametrize("live", [False, True])
def test_offer_implies_quote_ok(monkeypatch, live, db, env, switch, fresh, price):
    """Propriedade (2^5 x preço): switch, rate card e preço variam de forma INDEPENDENTE e a afirmação é
    sobre a view que monta a oferta (`_enemy_portrait`): `gerar` presente => a cotação não recusa."""
    _wire(monkeypatch, switch=switch, pricing=fresh)
    monkeypatch.setattr(api_presenters, "_portrait_price_estilhas", lambda: price)
    monkeypatch.setattr(api_core, "_database_profile", lambda: db)
    monkeypatch.setenv("RPG_DYNAMIC_ART_ENABLED", "1" if env else "0")
    from services import creature_art

    monkeypatch.setattr(creature_art, "mode", lambda: "on" if live else "off")
    state = {"game_id": "g363", "combat": {}}
    enemy = {"id": "enemy_goblin_1", "name": "Goblin", "categoria": "padrao"}
    view = api._enemy_portrait(
        state, {}, enemy, registry=_Registry() if api_presenters._creature_art_live() else None
    )
    gerar = (view or {}).get("gerar")
    if gerar:
        routes.art._guard_image_effect()  # não pode levantar (switch on + preço fresco)
        assert db and env and live and switch and fresh and price
    if not (switch and fresh):
        assert not gerar, "oferta com o portão da imagem fechado"
    if price is None:
        assert not gerar


def test_art_preflight_causes():
    from scripts.staging.art_preflight import evaluate

    base = dict(
        pricing_fresh=True,
        env={"RPG_DYNAMIC_ART_ENABLED": "1", "RPG_CREATURE_ART": "on"},
        price_estilhas=2,
    )
    cap = [{"key": "image_generation", "enabled": False, "actor_id": "system:finops"}]
    r = evaluate(switches={"image_generation": False}, audit=cap, **base)
    assert r["ok"] is False and r["causa"] == "daily_cap" and r["switch_actor"] == "system:finops"
    assert evaluate(switches={}, audit=[], **base)["ok"] is True
    assert (
        evaluate(switches={}, audit=[], **{**base, "pricing_fresh": False})["causa"]
        == "pricing_stale"
    )
    assert (
        evaluate(switches={}, audit=[], **{**base, "price_estilhas": None})["causa"] == "no_price"
    )
    off_env = {**base["env"], "RPG_KILL_SWITCHES_OFF": "image_generation"}
    assert (
        evaluate(switches={}, audit=[], **{**base, "env": off_env})["causa"]
        == "env_kill_switches_off"
    )


def test_offer_present_when_everything_open(monkeypatch):
    _wire(monkeypatch, switch=True, pricing=True)
    monkeypatch.setattr(api_core, "_database_profile", lambda: True)
    monkeypatch.setenv("RPG_DYNAMIC_ART_ENABLED", "1")
    from services import creature_art

    monkeypatch.setattr(creature_art, "mode", lambda: "on")
    enemy = {"id": "enemy_goblin_1", "name": "Goblin", "categoria": "padrao"}
    view = api._enemy_portrait({"game_id": "g363", "combat": {}}, {}, enemy, registry=_Registry())
    assert view["gerar"] and view["gerar"]["preco_estilhas"] == 3
