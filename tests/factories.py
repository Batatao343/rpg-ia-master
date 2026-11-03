"""SPEC-379 R2: fabricas de estado a partir das pecas canonicas do produto.

Nao existe um `build_initial_state()` unico no produto: `api._create_game` monta o
dict inline. `make_state` compoe as mesmas pecas, na mesma ordem, sem inventar
defaults. `tests/test_factories.py::test_make_state_matches_api_new_game` e o guard
contra deriva (compara com o `initial_state` real de `POST /game/new`).

Unica excecao declarada: `game_id` (constante `"factory-game"`; o produto usa uuid4).
"""

from __future__ import annotations

import copy
import functools
from typing import Any

from langchain_core.messages import HumanMessage, SystemMessage

import gamedata
import progression
from character_creator import create_player_character
from gamedata import seed_factions
from playtest.runner import _DEFAULT_CHAR  # defaults de personagem do produto
from services import world_calendar
from services.chronicle import default_chapter_title
from services.prompt_guard import origin_fragment
from services.reputation import resolve_race_id, resolve_region_id
from world_utils import starting_world

DEFAULT_NAME = "Herói"  # default do criador (character_creator.py)
_PLAYER_CARRY = ("subclass", "progression_events", "progression_grants")


@functools.lru_cache(maxsize=64)
def _sheet(class_name: str, race: str, region: str, level: int) -> dict[str, Any]:
    """Ficha do criador: nao depende do game_id, e o unico cache."""
    char = create_player_character(
        {
            "name": DEFAULT_NAME,
            "class_name": class_name,
            "race": race,
            "region": region,
            "backstory": "",
            "level": level,
            "appearance": "",
            "visual_exclusions": "",
        },
        use_llm_flavor=False,
    )
    gamedata.sync_vitality(char)
    return char


def _resolve(class_name, race, region, level) -> dict[str, Any]:
    return copy.deepcopy(
        _sheet(
            class_name or _DEFAULT_CHAR["class_name"],
            race or _DEFAULT_CHAR["race"],
            region or _DEFAULT_CHAR["region"],
            int(level),
        )
    )


def _player_block(char: dict[str, Any], level: int) -> dict[str, Any]:
    """Espelha o bloco `player` de `api._create_game`."""
    return {
        "name": char["name"],
        "class_name": char["class_name"],
        "race": char["race"],
        "race_id": resolve_race_id(char.get("race")),
        "origin_region_id": resolve_region_id(char.get("region")),
        "level": char["level"],
        "xp": char.get("xp", 0),
        "hp": char["hp"],
        "max_hp": char["max_hp"],
        "entropy": char.get("entropy", 0),
        "max_entropy": char.get("max_entropy", 0),
        "abyss_charge": char.get("abyss_charge", 0),
        "gold": 50 * level,
        "alignment": "Neutro",
        "virtudes": char["virtudes"],
        "vitalidade": char.get("vitalidade", char.get("max_vitalidade", char["max_hp"])),
        "max_vitalidade": char.get("max_vitalidade", char["max_hp"]),
        "vitalidade_max_penalty": char.get("vitalidade_max_penalty", 0),
        "ferimento_espacos": char.get("ferimento_espacos", {}),
        "ferimentos": char.get("ferimentos", {"leve": [], "grave": [], "critico": []}),
        "inventory": char["inventory"],
        "equipment": char.get("equipment", {"weapon": None, "armor": None, "accessory": None}),
        "known_cards": char.get("known_cards", []),
        "prepared_cards": char.get("prepared_cards", []),
        "card_usage": char.get("card_usage", {}),
        "virtue_cards": char.get("virtue_cards", []),
        "evolved_cards": char.get("evolved_cards", {}),
        "pending_choices": char.get("pending_choices", []),
        **{k: char[k] for k in _PLAYER_CARRY if k in char},
        "defense": char["defense"],
        "attack_bonus": char.get("attack_bonus", 0),
        "active_conditions": [],
        "racial_traits": char.get("racial_traits", []),
        "condition_resists": char.get("condition_resists", []),
        "racial_save_bonus": char.get("racial_save_bonus", {}),
        "appearance": "",
        "visual_exclusions": "",
    }


def _base_state(game_id: str, char: dict[str, Any], level: int) -> dict[str, Any]:
    name, region = char["name"], char["region"]
    return {
        "game_id": game_id,
        "processed_action_ids": [],
        "visual_seen_entity_ids": [],
        "visual_cue_ledger": [],
        "narrative_summary": f"A jornada de {name} começa em {region}. {origin_fragment('')}".rstrip(),
        "archivist_last_run": 0,
        "chronicle": [
            {
                "title": default_chapter_title(region),
                "started_turn": 0,
                "location": region,
                "entries": [],
            }
        ],
        "combat_target": None,
        "loot_source": None,
        "player": _player_block(char, level),
        "world": starting_world(region, level),
        "messages": [
            SystemMessage(content=f"A jornada de {name} começa em {region}."),
            HumanMessage(
                content=f"Descreva o cenário ao meu redor. Sou um {char['class_name']} de nível {level}."
            ),
        ],
        "party": [],
        "enemies": [],
        "factions": seed_factions(),
        "faction_intel": {},
        "bestiary_knowledge": {},
        "quests": [],
        "archive_due": False,
        "game_over": False,
        "death_pending": False,
        "continuity": {
            "session_action_count": 0,
            "timeline_epoch": 0,
            "last_checkpoint_turn": 0,
            "death_history": [],
        },
        "npcs": {},
        "campaign_plan": {},
        "needs_replan": False,
        "next": "storyteller",
        "event_log": [],
        "world_projection": {},
        "pending_world_events": [],
        "event_rejections": [],
        "art_arc_budgets": {},
        "art_generation_ledger": [],
    }


def make_player(
    *, class_name=None, race=None, region=None, level=1, **overrides: Any
) -> dict[str, Any]:
    """Bloco `player` canonico (ja normalizado pela progressao)."""
    char = _resolve(class_name, race, region, level)
    player = progression.normalize_player_progression(_player_block(char, int(level)))
    player.update(overrides)
    return player


def make_world(*, region=None, level=1, **overrides: Any) -> dict[str, Any]:
    """Bloco `world` canonico de `starting_world` (sem calendario: depende do game_id)."""
    world = starting_world(region or _DEFAULT_CHAR["region"], int(level))
    world.update(overrides)
    return world


def make_state(
    *,
    game_id: str = "factory-game",
    class_name=None,
    race=None,
    region=None,
    level=1,
    player: dict | None = None,
    world: dict | None = None,
    **overrides: Any,
) -> dict[str, Any]:
    """Estado inicial igual ao de `POST /game/new`, com o `game_id` final desde o inicio."""
    char = _resolve(class_name, race, region, level)
    state = _base_state(game_id, char, int(level))
    state["player"] = progression.normalize_player_progression(state["player"])
    world_calendar.init_new_game(state)  # calendario seedado pelo game_id final
    state["player"].update(player or {})
    state["world"].update(world or {})
    state.update(overrides)
    return state
