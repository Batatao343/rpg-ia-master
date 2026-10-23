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


def test_round_trip_favors_shelter_knows_player_e_recent_changes():
    st = persistence._raw_to_state(_old_state())
    st["game_id"] = "44444444-4444-4444-8444-444444444444"
    st["npcs"]["Brenna"].update(
        {
            "favors": {
                "last_day": 2,
                "debt": {"amount": 50, "due_day": 9, "overdue_applied": False},
                "intercession": {"faction_id": "legiao_ferro"},
            },
            "heard_deeds": ["d1"],
            "relationship_basis": {"race": -1, "origin": 1, "fame": 0, "faction": 0},
            "recent_changes": [{"turn": 3, "text": "Brenna não gostou disso."}],
        }
    )
    st["world"]["shelter"] = {"npc_id": "npc_brenna", "location_id": "skallgard", "until_clock": 14}
    st["factions"] = [
        {
            "id": "legiao_ferro",
            "name": "Legião",
            "reputation": 4,
            "disposition": "neutro",
            "knows_player": True,
            "recent_changes": [{"turn": 3, "text": "Legião vai lembrar disso."}],
        }
    ]
    assert persistence.save_game_state(st)
    back = persistence.load_game_state(persistence.save_path(st["game_id"]))
    npc, orig = back["npcs"]["Brenna"], st["npcs"]["Brenna"]
    for key in ("favors", "heard_deeds", "relationship_basis", "recent_changes"):
        assert npc[key] == orig[key], key
    assert back["world"]["shelter"] == st["world"]["shelter"]
    fac = back["factions"][0]
    assert (
        fac["knows_player"] is True and fac["recent_changes"] == st["factions"][0]["recent_changes"]
    )
