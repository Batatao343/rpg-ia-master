"""SPEC-301 — construtores de estado compartilhados pelos testes de membership."""

from __future__ import annotations

import copy

import gamedata
from services import faction_membership as fm


def make_state(**over) -> dict:
    state = {
        "game_id": "g301",
        "player": {
            "name": "Heroi",
            "class_name": "Médico de Campo",
            "race": "Humano",
            "race_id": "race_humanos",
            "origin_region_id": "nova_arcadia",
            "level": 3,
            "gold": 200,
            "vitalidade": 20,
            "max_vitalidade": 20,
            "virtudes": {"corpo": 2, "mente": 2, "agilidade": 2, "forca": 2, "carisma": 2},
            "inventory": [],
        },
        "world": {
            "current_location_id": "na_anel_ferro",
            "current_location": "Anel de Ferro",
            "turn_count": 5,
            "world_clock": {"day": 3, "period": "Manhã"},
            "visited": ["na_anel_ferro"],
        },
        "factions": gamedata.seed_factions(),
        "faction_intel": {},
        "faction_membership": {},
        "quests": [],
        "npcs": {},
        "event_log": [],
        "world_projection": {},
    }
    for key, value in over.items():
        state[key] = value
    return state


def at(state: dict, location_id: str) -> dict:
    out = copy.deepcopy(state)
    out["world"]["current_location_id"] = location_id
    return out


def merge(state: dict, updates: dict) -> dict:
    out = dict(state)
    out.update(copy.deepcopy(updates))
    return out


def set_day(state: dict, day: int) -> dict:
    out = copy.deepcopy(state)
    out["world"]["world_clock"]["day"] = day
    return out


def set_rep(state: dict, fid: str, value: int) -> dict:
    out = copy.deepcopy(state)
    for f in out["factions"]:
        if f["id"] == fid:
            f["reputation"] = value
    return out


def faction(state: dict, fid: str) -> dict:
    return next(f for f in state["factions"] if f["id"] == fid)


def joined(state: dict, fid: str = "legiao_ferro", **record) -> dict:
    """Estado com vínculo ativo direto (sem passar pelo rito)."""
    out = copy.deepcopy(state)
    rec = {
        "faction_id": fid,
        "status": "ativo",
        "rank_index": 0,
        "merit": 0,
        "joined_day": 1,
        "left_day": 0,
        "cooldown_until_day": 0,
        "offenses": [],
        "exposed": False,
        "rival_awareness": {},
        "last_info_day": 0,
        "rite_quest_id": "",
        "marks": [],
    }
    rec.update(record)
    out["faction_membership"][fid] = rec
    out["faction_intel"][fid] = {"known": True, "knows_goal": True}
    return out


def add_npc(state: dict, npc_id: str, name: str = "", in_scene: bool = True) -> dict:
    out = copy.deepcopy(state)
    out["npcs"][name or npc_id] = {
        "id": npc_id,
        "name": name or npc_id,
        "in_scene": in_scene,
        "relationship": 5,
    }
    return out


def mission_quest(
    fid: str,
    *,
    kind: str = "apoio",
    tier: int = 1,
    target: str = "",
    created_turn: int = 1,
    qid: str = "q1",
    location_id: str = "",
) -> dict:
    q = {
        "id": qid,
        "title": "Missao de teste",
        "description": "desc",
        "status": "active",
        "origin_name": "",
        "origin_entity_id": "",
        "location_id": location_id,
        "created_turn": created_turn,
        "resolved_turn": 0,
        "reward_hint": "",
        "progress_log": [{"kind": "created", "turn": created_turn, "detail": ""}],
        "reward_gold": 0,
        "reward_delivered": False,
        "faction_id": fid,
        "mission_kind": kind,
        "mission_tier": tier,
    }
    if target:
        q["target_faction_id"] = target
    return q


def accepting_ids() -> list[str]:
    return [fid for fid, row in fm.load_catalog().items() if row.get("accepts") != "nao"]
