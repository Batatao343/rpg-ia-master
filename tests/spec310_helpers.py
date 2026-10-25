"""SPEC-310 — construtores de estado compartilhados pelos testes do NPC que sabe de si."""

from __future__ import annotations

import gamedata
from services import faction_relations as fr
from services import world_director as wd

GAME = "g310"
HOME = "na_anel_lama"
HERE = "na_anel_ferro"
WAR_KEY = fr.pair_key("legiao_ferro", "filhos_chama_azul")


def make_state(**over) -> dict:
    state = {
        "game_id": GAME,
        "world": {
            "current_location_id": HERE,
            "current_location": "Anel de Ferro",
            "turn_count": 8,
            "world_clock": {"day": 5, "period": "Manhã"},
            "visited": [HERE],
        },
        "factions": gamedata.seed_factions(),
        "faction_intel": {},
        "npcs": {},
        "party": [],
        "event_log": [],
        "world_projection": {},
        "world_sim": {},
        "messages": [],
    }
    state.update(over)
    return state


def sergeant(**over) -> dict:
    row = {
        "id": "npc_sargento_ruiva",
        "name": "Ruiva",
        "role": "Sargento da Legião",
        "persona": "Seca.",
        "location": "Anel de Ferro",
        "faction_id": "legiao_ferro",
        "home_location_id": HOME,
        "relationship": 5,
        "memory": [],
        "in_scene": True,
    }
    row.update(over)
    return row


def war_state(**over) -> dict:
    st = make_state(**over)
    st["faction_intel"] = {"filhos_chama_azul": {"known": True}}  # fação secreta no catálogo
    st["world_sim"] = {"relation_bands": {WAR_KEY: "guerra"}}
    return st


def changed_today_event(day: int = 5) -> dict:
    a, b = fr.split_key(WAR_KEY)
    return {
        "event_id": wd.event_id(GAME, "faction_relation_changed", day, a, b),
        "type": "faction_relation_changed",
        "turn": 8,
        "actor_id": "engine",
        "target_id": a,
        "payload": {"other_faction_id": b, "relation": "enemy_of"},
        "source": "engine",
    }


def sim_entry(home: str = HOME, **pos) -> dict:
    return {"version": 1, "npcs": {"npc_sargento_ruiva": {"home": home, "pos": pos, "status": ""}}}
