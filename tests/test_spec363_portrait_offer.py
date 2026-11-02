"""SPEC-363 R2/R4: a oferta `retrato.gerar` usa o mesmo portão da cotação."""

from __future__ import annotations

import itertools

import pytest
from fastapi import HTTPException

import api
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
    monkeypatch.setattr(api, "_portrait_price_estilhas", lambda: 3)


def test_offer_requires_image_switch(monkeypatch):
    _wire(monkeypatch, switch=False, pricing=True)
    assert api._portrait_offer_price() is None


def test_offer_requires_fresh_pricing(monkeypatch):
    _wire(monkeypatch, switch=True, pricing=False)
    assert api._portrait_offer_price() is None


def test_offer_requires_price(monkeypatch):
    _wire(monkeypatch, switch=True, pricing=True)
    monkeypatch.setattr(api, "_portrait_price_estilhas", lambda: None)
    assert api._portrait_offer_price() is None


def test_offer_open_when_gate_open(monkeypatch):
    _wire(monkeypatch, switch=True, pricing=True)
    assert api._portrait_offer_price() == 3


def test_offer_requires_dynamic_art_env(monkeypatch):
    monkeypatch.setattr(api, "_database_profile", lambda: True)
    monkeypatch.delenv("RPG_DYNAMIC_ART_ENABLED", raising=False)
    monkeypatch.setenv("RPG_CREATURE_ART", "on")
    assert api._creature_art_live() is False


def test_offer_store_error_is_closed(monkeypatch):
    class _Boom:
        def is_enabled(self, key):
            raise RuntimeError("store down")

    monkeypatch.setattr(kill_switches, "get_switches", lambda: _Boom())
    assert api._image_effect_open() is False


@pytest.mark.parametrize("live,db,env,gate", list(itertools.product([False, True], repeat=4)))
def test_offer_implies_quote_ok(monkeypatch, live, db, env, gate):
    """Propriedade sobre os 2^4 estados: se a oferta existe, o guard da cotação não levanta."""
    _wire(monkeypatch, switch=gate, pricing=gate)
    monkeypatch.setattr(api, "_database_profile", lambda: db)
    monkeypatch.setenv("RPG_DYNAMIC_ART_ENABLED", "1" if env else "0")
    from services import creature_art

    monkeypatch.setattr(creature_art, "mode", lambda: "on" if live else "off")
    offered = api._creature_art_live() and api._portrait_offer_price() is not None
    if offered:
        api._guard_image_effect()  # não pode levantar
    else:
        # quando o portão está fechado a cotação recusaria — a oferta não pode existir
        if not gate:
            with pytest.raises(HTTPException):
                api._guard_image_effect()


def test_art_preflight_causes():
    from scripts.staging.art_preflight import evaluate

    base = dict(pricing_fresh=True, env={"RPG_DYNAMIC_ART_ENABLED": "1", "RPG_CREATURE_ART": "on"}, price_estilhas=2)
    cap = [{"key": "image_generation", "enabled": False, "actor_id": "system:finops"}]
    r = evaluate(switches={"image_generation": False}, audit=cap, **base)
    assert r["ok"] is False and r["causa"] == "daily_cap" and r["switch_actor"] == "system:finops"
    assert evaluate(switches={}, audit=[], **base)["ok"] is True
    assert evaluate(switches={}, audit=[], **{**base, "pricing_fresh": False})["causa"] == "pricing_stale"
    assert evaluate(switches={}, audit=[], **{**base, "price_estilhas": None})["causa"] == "no_price"
    off_env = {**base["env"], "RPG_KILL_SWITCHES_OFF": "image_generation"}
    assert evaluate(switches={}, audit=[], **{**base, "env": off_env})["causa"] == "env_kill_switches_off"
