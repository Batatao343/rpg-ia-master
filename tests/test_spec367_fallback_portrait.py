"""SPEC-367 R10-R12: inimigo de fallback não tem oferta paga nem reutiliza `tipo:fallback_*`."""

from __future__ import annotations

import json

import pytest
from fastapi import HTTPException

import api
from scripts import retire_creature_portrait as rcp
from services import creature_art as art
from services.creature_portraits import SnapshotRegistry


def test_is_fallback_enemy_variants():
    assert art.is_fallback_enemy({"id": "fallback_criatura_hostil", "name": "Criatura hostil"})
    assert art.is_fallback_enemy({"id": "fallback_criatura_hostil_1"})
    assert art.is_fallback_enemy({"id": "fallback_criatura_hostil_r2"})
    assert art.is_fallback_enemy({"id": "x1", "bestiary_id": "fallback_criatura_hostil"})
    assert not art.is_fallback_enemy({"id": "enemy_goblin_1", "name": "Goblin"})
    assert not art.is_fallback_enemy({})


def _reg_with_fallback_ready():
    reg = SnapshotRegistry(
        {
            "tipo:fallback_criatura_hostil": {
                "status": "ready",
                "visibility": "shared",
                "store": "shared",
                "variants": [{"variant": "thumb", "url": "https://x/y.png"}],
            }
        }
    )
    return reg


def test_portrait_for_fallback_no_offer_no_registry(monkeypatch):
    monkeypatch.setenv("RPG_CREATURE_ART", "on")
    enemy = {"id": "fallback_criatura_hostil_1", "name": "Criatura hostil"}
    out = art.portrait_for(
        enemy,
        None,
        game_id="g",
        registry=_reg_with_fallback_ready(),
        quote_price=15,
        quote_milli=15,
    )
    assert out["gerar"] is None
    assert out["src"] is None or "x/y.png" not in out["src"]
    assert out["estado"] in ("marcador", "pronto")
    assert not out["proprio"]


def test_portrait_for_regular_enemy_still_offers(monkeypatch):
    monkeypatch.setenv("RPG_CREATURE_ART", "on")
    enemy = {"id": "enemy_goblin_1", "name": "Goblin-Mineiro"}
    out = art.portrait_for(enemy, None, game_id="g", registry=None, quote_price=15)
    assert out["gerar"] is not None or art.curated_covers_key(
        enemy, art.portrait_key(enemy, None, game_id="g")
    )


class _Reg:
    def __init__(self):
        self.calls = []

    def retire(self, **kw):
        self.calls.append(("retire", kw))
        return ["k1"]


class _Shared:
    def __init__(self):
        self.deleted = []

    def delete(self, key):
        self.deleted.append(key)
        return True


def test_retire_env_file_and_dry_run(monkeypatch, tmp_path, capsys):
    env = tmp_path / "e.env"
    env.write_text("SPEC367_ONLY_HERE=zzz-secret\n", encoding="utf-8")
    monkeypatch.delenv("SPEC367_ONLY_HERE", raising=False)
    seen = {}
    shared = _Shared()
    reg = _Reg()

    class _Rt:
        game_store = type("S", (), {"pool": object()})()
        shared_blob_store = shared

    def fake_build():
        import os

        seen["env"] = os.environ.get("SPEC367_ONLY_HERE")
        return _Rt()

    monkeypatch.setattr(rcp, "build_runtime", fake_build)
    monkeypatch.setattr(rcp, "PostgresPortraitRegistry", lambda pool: reg)
    monkeypatch.setattr(
        rcp,
        "_dry_report",
        lambda runtime, key: {"portrait_key": key, "status_atual": "ready", "objetos": ["a"]},
    )
    monkeypatch.setattr(
        "sys.argv",
        ["r", "tipo:x", "--reason", "m", "--env-file", str(env), "--dry-run"],
    )
    assert rcp.main() == 0
    out = capsys.readouterr().out
    assert seen["env"] == "zzz-secret"
    assert "zzz-secret" not in out
    assert json.loads(out)["status_atual"] == "ready"
    assert reg.calls == [] and shared.deleted == []
    monkeypatch.delenv("SPEC367_ONLY_HERE", raising=False)


class _Store:
    def __init__(self):
        self.keys = []

    def get_many(self, keys, *, game_id, npc_known=()):
        self.keys.extend(keys)
        return {}


def test_quote_refuses_fallback_409(monkeypatch):
    store = _Store()
    monkeypatch.setattr(api, "_portrait_store", lambda runtime=None: store)
    state = {
        "game_id": "0a1b2c3d-0000-4000-8000-000000000001",
        "enemies": [{"id": "fallback_criatura_hostil_1", "name": "Criatura hostil"}],
        "combat": {"active": True},
        "npcs": {},
    }
    req = api.ArtQuoteRequest(image_type="monster", enemy_id="fallback_criatura_hostil_1")
    with pytest.raises(HTTPException) as exc:
        api._monster_quote_inputs(state, req, None)
    assert exc.value.status_code == 409
    assert exc.value.detail == "creature_portrait_not_offered"
    assert store.keys == []
