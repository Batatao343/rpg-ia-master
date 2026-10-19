"""SPEC-211 — endpoint GET /game/codex/dossiers."""

from __future__ import annotations

import json
import os
import uuid

import pytest
from fastapi.testclient import TestClient

import api
import persistence
from services import player_knowledge as pk
from services.dossier_visibility import assert_no_private_fields, leak_view

HIDDEN_LOC = "mon_verme_primordial_das_raizes_do_mundo"
RATO = "enemy_rato_peste_anel_lama"


def _save(**extra):
    game_id = str(uuid.uuid4())
    state = {
        "game_id": game_id,
        "narrative_summary": "",
        "messages": [],
        "player": {"name": "T", "class_name": "Devoto do Abismo", "race": "Humano"},
        "world": {
            "current_location": "Nova Arcádia",
            "current_location_id": "nova_arcadia",
            "turn_count": 8,
            "visited": ["nova_arcadia", HIDDEN_LOC],
        },
        "npcs": {
            "Grum": {
                "name": "Grum",
                "role": "Ferreiro",
                "knowledge_source": "met",
                "created_turn": 1,
                "last_seen_turn": 5,
                "hidden_traits": ["x_oculto"],
                "memory": ["PRIVADO"],
            }
        },
        "factions": [],
        "faction_intel": {},
        "event_log": [],
        "world_projection": {},
        "bestiary_knowledge": {RATO: {"seen": 1, "fought": 1, "last_update_turn": 6}},
    }
    state.update(extra)
    assert persistence.save_game_state(state)
    return game_id


@pytest.fixture
def client():
    return TestClient(api.app)


def _path(gid):
    return os.path.join(persistence.SAVES_DIR, f"{gid}.json")


def test_get_dossiers_404_sem_save(client):
    assert (
        client.get("/game/codex/dossiers", params={"game_id": str(uuid.uuid4())}).status_code == 404
    )


def test_get_dossiers_ok_e_oraculos(client):
    gid = _save()
    resp = client.get("/game/codex/dossiers", params={"game_id": gid})
    assert resp.status_code == 200
    body = resp.json()
    assert body["generated_at_turn"] == 8 and body["version"] >= 6
    assert {"npcs", "locations", "factions", "secrets", "chronicle_index"} == set(body["sections"])
    assert assert_no_private_fields(body) == []
    loaded = persistence.load_game_state(_path(gid))
    assert pk.assert_no_player_leak(leak_view(body), loaded) == []
    assert HIDDEN_LOC not in resp.text and "x_oculto" not in resp.text


def test_codex_antigo_inalterado(client):
    gid = _save()
    body = client.get("/game/codex", params={"game_id": gid}).json()
    assert {"locations", "factions", "characters", "creatures", "secrets", "meta"} <= set(body)
    assert "sections" not in body


def test_arte_so_se_publica(client, monkeypatch):
    gid = _save()
    body = client.get("/game/codex/dossiers", params={"game_id": gid}).json()
    assert body["sections"]["npcs"][0]["art"]["asset_id"]
    from services import visual_catalog as vc

    monkeypatch.setattr(vc, "visual_for", lambda *a, **k: None)
    body = client.get("/game/codex/dossiers", params={"game_id": gid}).json()
    assert body["sections"]["npcs"][0]["art"] is None
    assert body["sections"]["locations"][0]["art"] is None


def test_oculto_e_inexistente_indistinguiveis(client):
    com = _save()
    sem = _save(
        world={
            "current_location": "Nova Arcádia",
            "current_location_id": "nova_arcadia",
            "turn_count": 8,
            "visited": ["nova_arcadia"],
        }
    )
    a = client.get("/game/codex/dossiers", params={"game_id": com}).json()
    b = client.get("/game/codex/dossiers", params={"game_id": sem}).json()
    assert json.dumps(a, sort_keys=True) == json.dumps(b, sort_keys=True)


def test_sem_cache_publico(client):
    gid = _save()
    cc = client.get("/game/codex/dossiers", params={"game_id": gid}).headers.get(
        "cache-control", ""
    )
    assert "no-store" in cc and "public" not in cc


def test_roundtrip_save_load_dossie_identico(client):
    gid = _save()
    first = client.get("/game/codex/dossiers", params={"game_id": gid}).json()
    persistence.save_game_state(persistence.load_game_state(_path(gid)))
    assert client.get("/game/codex/dossiers", params={"game_id": gid}).json() == first


def test_save_legado_sem_campos_novos_carrega(client):
    gid = _save()
    with open(_path(gid), encoding="utf-8") as fh:
        raw = json.load(fh)
    for key in ("bestiary_knowledge", "faction_intel", "chronicle", "memory_facts"):
        raw.pop(key, None)
    with open(_path(gid), "w", encoding="utf-8") as fh:
        json.dump(raw, fh)
    assert client.get("/game/codex/dossiers", params={"game_id": gid}).status_code == 200


def test_npcs_block_do_hud_omite_npc_oculto(monkeypatch):
    """SPEC-211: o fallback legado (HUD) não reabre NPC oculto que o dossiê esconde."""
    real = pk._entity_visibility
    monkeypatch.setattr(
        pk, "_entity_visibility", lambda eid: "hidden" if eid == "npc_grum" else real(eid)
    )
    state = {"world": {"turn_count": 1}, "event_log": []}
    npcs = {
        "Grum": {"name": "Grum", "knowledge_source": "met"},
        "Zé": {"name": "Zé", "knowledge_source": "met"},
    }
    assert [n["name"] for n in api._npcs_block(npcs, state)] == ["Zé"]
    assert [n["name"] for n in api._npcs_block(npcs)] == [
        "Grum",
        "Zé",
    ]  # sem state: comportamento antigo


# --- Revisão Sol independente (SPEC-211) -----------------------------------


def test_api_json_criatura_tier1_sem_chaves_acima_do_tier(client):
    """R6: chave acima do tier AUSENTE do JSON da API (não `null`)."""
    gid = _save(bestiary_knowledge={RATO: {"seen": 1, "last_update_turn": 6}})
    body = client.get("/game/codex/dossiers", params={"game_id": gid}).json()
    creature = body["bestiary"][0]
    assert creature["tier"] == 1
    for key in (
        "description",
        "type",
        "max_hp",
        "defense",
        "attacks",
        "behavior",
        "loot",
        "revealed_cards",
        "revealed_resistances",
    ):
        assert key not in creature, key


def test_api_json_criatura_tier2_sem_chaves_de_tier3(client):
    gid = _save()
    creature = client.get("/game/codex/dossiers", params={"game_id": gid}).json()["bestiary"][0]
    assert creature["tier"] == 2
    for key in ("max_hp", "defense", "attacks", "behavior", "loot"):
        assert key not in creature, key
