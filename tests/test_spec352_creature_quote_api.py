"""SPEC-352 (offline): contrato da API de cotação `monster` (validação, chave só no servidor, 409/422)."""

from __future__ import annotations

import pytest
from fastapi import HTTPException
from pydantic import ValidationError

import api
from services import visual_catalog


def _state(**extra):
    state = {
        "game_id": "0a1b2c3d-0000-4000-8000-000000000001",
        "enemies": [
            {"id": "enemy_goblin_1", "name": "Goblin", "categoria": "padrao"},
            {"id": "enemy_goblin_2", "name": "Goblin 2", "categoria": "padrao", "dead": True},
        ],
        "combat": {"active": True},
        "npcs": {},
    }
    state.update(extra)
    return state


class _Store:
    def __init__(self, rows=None):
        self.rows, self.keys = rows or {}, []

    def get_many(self, keys, *, game_id, npc_known=()):
        self.keys.extend(keys)
        return {k: v for k, v in self.rows.items() if k in keys}


def _req(**kw):
    return api.ArtQuoteRequest(image_type="monster", **kw)


def test_quote_body_cannot_carry_portrait_key():
    with pytest.raises(ValidationError):
        api.ArtQuoteRequest(image_type="monster", enemy_id="enemy_goblin_1", portrait_key="tipo:x")


def test_quote_flag_off_404(monkeypatch):
    monkeypatch.delenv("RPG_CREATURE_ART", raising=False)
    with pytest.raises(HTTPException) as exc:
        api.create_image_quote("g", _req(enemy_id="enemy_goblin_1"))
    assert exc.value.status_code == 404 and exc.value.detail == "creature_art_disabled"


@pytest.mark.parametrize(
    "kw", [{}, {"enemy_id": "x", "reformulation": True}, {"enemy_id": "x", "offer_id": None}]
)
def test_quote_monster_requires_enemy_and_rejects_offer_or_reformulation(monkeypatch, kw):
    monkeypatch.setenv("RPG_CREATURE_ART", "on")
    if kw.get("offer_id", 1) is None:
        kw = {"enemy_id": "x", "offer_id": "5d4c6f43-0c40-4e38-97a5-0a8f2b2a1a10"}
    with pytest.raises(HTTPException) as exc:
        api.create_image_quote("g", _req(**kw))
    assert exc.value.status_code == 422


def test_enemy_id_is_only_for_monster(monkeypatch):
    with pytest.raises(HTTPException) as exc:
        api.create_image_quote("g", api.ArtQuoteRequest(image_type="player", enemy_id="x"))
    assert exc.value.status_code == 422


def test_quote_kill_switch_503_before_any_row(monkeypatch):
    monkeypatch.setenv("RPG_CREATURE_ART", "on")
    monkeypatch.setenv("RPG_RUNTIME_PROFILE", "local")
    monkeypatch.setenv("RPG_DYNAMIC_ART_ENABLED", "1")

    def off():
        raise HTTPException(503, "image_generation_disabled")

    monkeypatch.setattr(api, "_guard_image_effect", off)
    with pytest.raises(HTTPException) as exc:
        api.create_image_quote("g", _req(enemy_id="enemy_goblin_1"))
    assert exc.value.status_code == 503


@pytest.mark.parametrize("enemy_id", ["enemy_goblin_2", "inexistente", "enemy_goblin_1"])
def test_quote_enemy_not_in_conflict_422(monkeypatch, enemy_id):
    state = _state()
    if enemy_id == "enemy_goblin_1":
        state["combat"] = {"active": False}
    monkeypatch.setattr(api, "_portrait_store", lambda runtime=None: _Store())
    with pytest.raises(HTTPException) as exc:
        api._monster_quote_inputs(state, _req(enemy_id=enemy_id), None)
    assert exc.value.status_code == 422 and exc.value.detail == "enemy_not_in_conflict"


def test_quote_recomputes_key_server_side(monkeypatch):
    store = _Store()
    monkeypatch.setattr(api, "_portrait_store", lambda runtime=None: store)
    trigger, brief = api._monster_quote_inputs(_state(), _req(enemy_id="enemy_goblin_1"), None)
    assert trigger.trigger_kind == "creature_portrait" and trigger.subject_type == "monster"
    assert trigger.subject_id == "tipo:enemy_goblin" == store.keys[0]
    assert trigger.trigger_instance_id.startswith("tipo:enemy_goblin|")
    assert brief["reference_asset_ids"] == [] and brief["size"] == "1024x1536"


def test_quote_curated_409(monkeypatch):
    monkeypatch.setattr(api, "_portrait_store", lambda runtime=None: _Store())
    monkeypatch.setattr(
        visual_catalog,
        "visual_for",
        lambda kind, sid: (
            {"variants": {"thumbnail": {"url": "/c.webp"}}}
            if (kind, sid) == ("creature", "enemy_goblin")
            else None
        ),
    )
    with pytest.raises(HTTPException) as exc:
        api._monster_quote_inputs(_state(), _req(enemy_id="enemy_goblin_1"), None)
    assert exc.value.status_code == 409 and exc.value.detail == "creature_portrait_curated"


@pytest.mark.parametrize("status", ["pending", "ready"])
def test_quote_existing_409_without_issuing(monkeypatch, status):
    store = _Store({"tipo:enemy_goblin": {"status": status}})
    monkeypatch.setattr(api, "_portrait_store", lambda runtime=None: store)
    with pytest.raises(HTTPException) as exc:
        api._monster_quote_inputs(_state(), _req(enemy_id="enemy_goblin_1"), None)
    assert exc.value.status_code == 409 and exc.value.detail == "creature_portrait_exists"


def test_important_enemy_gets_own_key(monkeypatch):
    state = _state()
    state["enemies"].append({"id": "enemy_goblin_3", "name": "Grishnak", "categoria": "padrao"})
    monkeypatch.setattr(api, "_portrait_store", lambda runtime=None: _Store())
    trigger, brief = api._monster_quote_inputs(state, _req(enemy_id="enemy_goblin_3"), None)
    assert trigger.subject_id == f"unico:{state['game_id']}:goblin:grishnak"
    assert "Grishnak" in brief["subject"]


def test_quality_monster_422(monkeypatch):
    from types import SimpleNamespace

    import infrastructure.request_context as rc
    import infrastructure.runtime as rt
    import services.dynamic_art as da

    monkeypatch.setattr(api, "_database_profile", lambda: True)
    monkeypatch.setattr(
        api, "load_game_state", lambda _p: {"game_id": "0a1b2c3d-0000-4000-8000-000000000001"}
    )
    monkeypatch.setattr(api, "_resolve_save_file", lambda g: g)
    monkeypatch.setattr(rt, "get_runtime", lambda: SimpleNamespace(resources=(object(),)))
    monkeypatch.setattr(rc, "current_principal", lambda: SimpleNamespace(user_id="u"))

    class Repo:
        def __init__(self, *_a, **_k):
            pass

        def set_quality(self, *_a, **_k):
            from infrastructure.contracts import Conflict

            raise Conflict("quality_not_applicable")

    monkeypatch.setattr(da, "DynamicArtRepository", Repo)
    with pytest.raises(HTTPException) as exc:
        api.dynamic_art_quality(
            "g", "5d4c6f43-0c40-4e38-97a5-0a8f2b2a1a10", api.ArtQualityRequest(approved=False)
        )
    assert exc.value.status_code == 422 and exc.value.detail == "quality_not_applicable"
