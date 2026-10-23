"""npc_seed.py — Semente estruturada de NPC (SPEC-297 R4/R5/R6).

O MOTOR sorteia os ingredientes (raça, origem, facção, profissão, desejo, medo,
segredo pessoal, contradição, maneirismo) com `random.Random` determinístico;
a LLM só costura o texto depois. Puro: zero LLM/rede, mesmo input -> mesma semente.

Dados: `data/npc_seed_tables.json` (curado) + `origins.json`, `factions.json`,
`world_map.json`. Cada linha de tabela declara `regions`/`races`/`factions`
permitidas (ausente/vazia = qualquer).
"""

from __future__ import annotations

import hashlib
import json
import os
import random
from collections.abc import Callable
from functools import lru_cache

from pydantic import BaseModel

from gamedata import DATA_DIR

SEED_TABLES_PATH = os.path.join(DATA_DIR, "npc_seed_tables.json")
TABLE_KEYS = ("professions", "desires", "fears", "secrets", "contradictions", "mannerisms")
MIN_TABLE_ENTRIES = 15
MIN_COMBINATIONS_PER_ORIGIN = 1000
MAX_REROLLS = 5
FACTION_CHANCE = 0.5


class NpcSeed(BaseModel):
    race_id: str
    origin_region_id: str
    home_location_id: str
    faction_id: str | None = None
    profession_id: str
    desire_id: str
    fear_id: str
    secret_id: str
    contradiction_id: str
    mannerism_id: str


def _read_json(path: str) -> dict:
    with open(path, encoding="utf-8") as handle:
        return json.load(handle)


@lru_cache(maxsize=4)
def load_seed_tables(path: str = SEED_TABLES_PATH) -> dict:
    return _read_json(path)


@lru_cache(maxsize=1)
def _lore() -> dict:
    origins = _read_json(os.path.join(DATA_DIR, "origins.json"))
    factions = _read_json(os.path.join(DATA_DIR, "factions.json"))
    world = _read_json(os.path.join(DATA_DIR, "world_map.json"))
    region_by_name = {r["name"]: r["id"] for r in origins.get("regions", [])}
    faction_region = {
        fid: region_by_name.get(f.get("region", ""), "") for fid, f in factions.items()
    }
    locations = {loc["id"]: loc for loc in world.get("locations", [])}
    by_region: dict[str, list[str]] = {}
    for loc in world.get("locations", []):
        by_region.setdefault(loc.get("region_id", ""), []).append(loc["id"])
    return {
        "races": [r["id"] for r in origins.get("races", [])],
        "regions": [r["id"] for r in origins.get("regions", [])],
        "factions": sorted(factions),
        "faction_region": faction_region,
        "locations": locations,
        "locations_by_region": by_region,
    }


def lore_ids() -> dict[str, set[str]]:
    lore = _lore()
    return {
        "races": set(lore["races"]),
        "regions": set(lore["regions"]),
        "factions": set(lore["factions"]),
        "locations": set(lore["locations"]),
    }


def _allowed(row: dict, key: str, value: str | None) -> bool:
    allowed = row.get(key) or []
    if not allowed:
        return True
    return value is not None and value in allowed


def compatible_rows(
    table: str, *, region: str, race: str, faction: str | None, tables: dict | None = None
) -> list[dict]:
    rows = (tables or load_seed_tables()).get(table, [])
    return [
        row
        for row in rows
        if _allowed(row, "regions", region)
        and _allowed(row, "races", race)
        and _allowed(row, "factions", faction)
    ]


def compatible_factions(region: str) -> list[str]:
    lore = _lore()
    return [fid for fid in lore["factions"] if lore["faction_region"].get(fid) == region]


def seed_rng(game_id: str, turn: int, location_id: str, slot: int = 0) -> random.Random:
    key = f"{game_id}|{turn}|{location_id}|{slot}"
    return random.Random(int.from_bytes(hashlib.sha256(key.encode("utf-8")).digest()[:8], "big"))


def roll_npc_seed(*, game_id: str, turn: int, location_id: str, slot: int = 0) -> NpcSeed:
    """Sorteio determinístico da semente (R4). Mesma entrada -> mesma semente."""
    lore = _lore()
    tables = load_seed_tables()
    rng = seed_rng(game_id, int(turn), location_id, slot)
    loc = lore["locations"].get(location_id)
    region = (loc or {}).get("region_id") or rng.choice(lore["regions"])
    pool_locs = lore["locations_by_region"].get(region) or [location_id or region]
    home = location_id if loc else rng.choice(pool_locs)
    race = rng.choice(lore["races"])
    factions = compatible_factions(region)
    faction = rng.choice(factions) if factions and rng.random() < FACTION_CHANCE else None
    picked: dict[str, str] = {}
    for key in TABLE_KEYS:
        rows = compatible_rows(key, region=region, race=race, faction=faction, tables=tables)
        if not rows:  # lint garante >=1; defensivo contra tabela editada
            rows = tables.get(key, [])
        picked[key] = rng.choice(rows)["id"]
    return NpcSeed(
        race_id=race,
        origin_region_id=region,
        home_location_id=home,
        faction_id=faction,
        profession_id=picked["professions"],
        desire_id=picked["desires"],
        fear_id=picked["fears"],
        secret_id=picked["secrets"],
        contradiction_id=picked["contradictions"],
        mannerism_id=picked["mannerisms"],
    )


def seed_signature(seed: NpcSeed) -> str:
    """sha256 da tupla ordenada dos ids (R6); `home_location_id` não conta."""
    parts = sorted(
        [
            seed.race_id,
            seed.origin_region_id,
            seed.faction_id or "-",
            seed.profession_id,
            seed.desire_id,
            seed.fear_id,
            seed.secret_id,
            seed.contradiction_id,
            seed.mannerism_id,
        ]
    )
    return hashlib.sha256("|".join(parts).encode("utf-8")).hexdigest()


def roll_unique_seed(
    *,
    game_id: str,
    turn: int,
    location_id: str,
    signature_taken: Callable[[str], bool],
    max_rerolls: int = MAX_REROLLS,
) -> NpcSeed | None:
    """R6: re-sorteia (`slot+1`) até `max_rerolls` vezes se a assinatura já existe.

    Devolve None quando esgota — o chamador gera a entidade só-local."""
    for slot in range(max_rerolls + 1):
        seed = roll_npc_seed(game_id=game_id, turn=turn, location_id=location_id, slot=slot)
        if not signature_taken(seed_signature(seed)):
            return seed
    return None


def seed_labels(seed: NpcSeed) -> dict[str, str]:
    """Rótulos legíveis (para o prompt de geração, R7)."""
    tables = load_seed_tables()
    lore = _lore()

    def label(table: str, ident: str) -> str:
        for row in tables.get(table, []):
            if row["id"] == ident:
                return str(row.get("label", ident))
        return ident

    loc = lore["locations"].get(seed.home_location_id) or {}
    return {
        "raca": seed.race_id,
        "regiao": seed.origin_region_id,
        "local_de_origem": str(loc.get("name", seed.home_location_id)),
        "faccao": seed.faction_id or "",
        "profissao": label("professions", seed.profession_id),
        "desejo": label("desires", seed.desire_id),
        "medo": label("fears", seed.fear_id),
        "segredo_pessoal": label("secrets", seed.secret_id),
        "contradicao": label("contradictions", seed.contradiction_id),
        "maneirismo": label("mannerisms", seed.mannerism_id),
    }


def seed_ids(seed: NpcSeed) -> dict[str, list[str] | str | None]:
    return seed.model_dump()


def combinations_for_region(region: str, *, tables: dict | None = None) -> int:
    """Combinações possíveis (sem facção, conservador) para uma origem (R5)."""
    lore = _lore()
    tables = tables or load_seed_tables()
    total = 0
    for race in lore["races"]:
        product = 1
        for key in TABLE_KEYS:
            product *= len(
                compatible_rows(key, region=region, race=race, faction=None, tables=tables)
            )
        total += product
    return total
