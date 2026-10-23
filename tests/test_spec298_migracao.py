"""SPEC-298 R28 — migração suave, sem bump de schema."""

import copy

import persistence
from services import reputation as rep


def _old_state():
    return {
        "game_id": "11111111-1111-4111-8111-111111111111",
        "player": {"name": "T", "race": "Elfo"},
        "world": {"current_location_id": "skallgard"},
        "npcs": {"Brenna": {"id": "npc_brenna", "name": "Brenna", "relationship": 7}},
        "messages": [],
    }


def test_save_antigo_carrega_com_defaults_neutros():
    state = persistence._raw_to_state(_old_state())
    assert state["location_fame"] == {} and state["reputation_pending"] == []
    assert state["reputation_notices"] == []
    assert state["player"]["race_id"] == "race_elfos"
    assert state["player"]["origin_region_id"] == ""
    assert state["world"]["shelter"] is None
    npc = state["npcs"]["Brenna"]
    assert npc["race_id"] == "" and npc["heard_deeds"] == [] and npc["favors"] == {}


def test_ensure_idempotente():
    once = rep.ensure_reputation_fields(_old_state())
    twice = rep.ensure_reputation_fields(copy.deepcopy(once))
    assert once == twice


def test_npc_existente_nao_recalcula_relacao():
    state = persistence._raw_to_state(_old_state())
    assert state["npcs"]["Brenna"]["relationship"] == 7
    assert "relationship_basis" in state["npcs"]["Brenna"]
    assert state["npcs"]["Brenna"]["relationship_basis"] == {}


def test_round_trip_save_load_preserva_fama():
    st = persistence._raw_to_state(_old_state())
    st["location_fame"] = {"skallgard": {"renown": 12, "infamy": 0, "deeds": ["e1"]}}
    st["reputation_pending"] = [
        {"subject_id": "e1", "faction_id": "legiao_ferro", "delta": -6, "created_day": 1}
    ]
    assert persistence.SCHEMA_VERSION == 8
    assert persistence.save_game_state(st)
    back = persistence.load_game_state(persistence.save_path(st["game_id"]))
    assert back["location_fame"] == st["location_fame"]
    assert back["reputation_pending"] == st["reputation_pending"]
