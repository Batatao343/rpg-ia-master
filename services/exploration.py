"""services/exploration.py — recompensa de exploração (spec loot-exploracao).

Descoberta ambiental DETERMINÍSTICA ao entrar num local NOVO (fog of war) + baús
CURADOS por local. Reusa a engine de loot da Fase 6 (`services.economy.roll_loot`):
mesma escada de raridade por perigo, mesmo pool regional, mesmo claim de único.

Regras da spec:
- R1/R2: achado só na 1ª visita; chance modesta que ESCALA com o perigo (o perigo
  é onde mora a recompensa). Raridade vem das bandas do roll_loot (por perigo).
- R2b: exploração PASSIVA nunca cospe ÚNICO — único mora só nos baús curados.
- R3: baú curado (`treasure` no world_map) concede conteúdo 1x (world.looted_locations);
  pode conter único (via claim engine).
- R6: mecânica é Python — o narrador só descreve o que a função concedeu.
"""
from __future__ import annotations

import hashlib
import random
from typing import List, Optional, Tuple

from services import economy


def arrival_rng(game_id: str, location_id: str, turn: int) -> random.Random:
    """RNG estável entre processos para a descoberta de uma chegada."""
    raw = f"{game_id}|{location_id}|{int(turn)}".encode("utf-8")
    seed = int.from_bytes(hashlib.sha256(raw).digest()[:8], "big")
    return random.Random(seed)


def discovery_chance(danger: int) -> float:
    """Chance modesta do achado ambiental; escala com o perigo do local."""
    return min(0.5, 0.12 + 0.08 * max(1, int(danger or 1)))


def roll_discovery(world: dict, loc: dict, player_level: int,
                   rng: Optional[random.Random] = None) -> Optional[dict]:
    """Achado ambiental na PRIMEIRA visita (o caller garante o fog of war).
    Devolve {item_id, qty, gold, rarity} ou None. Passiva NUNCA concede único."""
    rng = rng or random.Random()
    world = world or {}
    loc = loc or {}
    danger = int(loc.get("danger", world.get("danger_level", 1)) or 1)
    if rng.random() >= discovery_chance(danger):
        return None
    region_id = loc.get("region_id", "default")
    roll = economy.roll_loot(region_id, danger, rng)
    item_id = roll.get("item_id")
    if item_id:
        from inventory import is_unique
        if is_unique(item_id):        # R2b: único só via baú curado, nunca passivo
            item_id = None
    gold = int(roll.get("gold", 0) or 0)
    if not item_id and gold <= 0:
        return None
    return {"item_id": item_id, "qty": 1, "gold": gold,
            "rarity": roll.get("rarity", "comum")}


def resolve_treasure(world: dict, loc: dict) -> Optional[dict]:
    """Baú CURADO de um local (`treasure` no world_map): {gold?, items?:[id...]}.
    One-shot (world.looted_locations). Devolve {items:[id...], gold, loc_id} ou
    None (sem baú ou já saqueado). Não muta — o apply_grant marca looted."""
    loc = loc or {}
    world = world or {}
    loc_id = loc.get("id") or world.get("current_location_id", "")
    treasure = loc.get("treasure")
    if not treasure or not loc_id:
        return None
    if loc_id in (world.get("looted_locations") or []):
        return None
    items = [str(i) for i in (treasure.get("items") or []) if i]
    gold = int(treasure.get("gold", 0) or 0)
    if not items and gold <= 0:
        return None
    return {"items": items, "gold": gold, "loc_id": loc_id}


def _grant_items(player: dict, item_ids: List[str],
                 projection: Optional[dict] = None) -> Tuple[List[str], list]:
    """Adiciona itens ao inventário; devolve (labels, eventos de claim de único)."""
    from inventory import add_item, is_unique, item_display, make_entry
    labels: List[str] = []
    unique_events: list = []
    for iid in item_ids:
        if not economy.is_unique_available(iid, projection):
            continue
        player["inventory"] = add_item(player.get("inventory", []), iid, 1)
        labels.append(item_display(make_entry(iid)))
        if is_unique(iid):
            unique_events.append(economy.claim_event(iid, "player"))
    return labels, unique_events


def discover_on_arrival(player: dict, world: dict, loc: dict, player_level: int,
                        rng: Optional[random.Random] = None,
                        projection: Optional[dict] = None,
                        ) -> Tuple[str, list]:
    """Entrypoint do storyteller ao CHEGAR num local novo. Resolve baú curado
    (prioridade) OU achado ambiental, MUTA player.inventory/gold + world (marca
    looted), e devolve (nota_para_o_narrador, eventos_de_claim). Nota "" = nada."""
    rng = rng or random.Random()
    # 1) baú curado tem prioridade (recompensa BOA que o design escolheu).
    tre = resolve_treasure(world, loc)
    if tre:
        labels, unique_events = _grant_items(player, tre["items"], projection)
        if tre["gold"]:
            player["gold"] = int(player.get("gold", 0) or 0) + int(tre["gold"])
        world["looted_locations"] = list(world.get("looted_locations") or []) + [tre["loc_id"]]
        partes = [p for p in ([", ".join(labels)] if labels else [])
                  + ([f"{tre['gold']} de ouro"] if tre["gold"] else [])]
        return (f"O jogador ENCONTROU um baú/esconderijo em {loc.get('name','o local')}: "
                f"{' e '.join(partes)}. Descreva o achado.", unique_events)
    # 2) achado ambiental (só 1ª visita — o caller já checou fog of war).
    disc = roll_discovery(world, loc, player_level, rng)
    if not disc:
        return ("", [])
    labels, unique_events = ([], [])
    if disc["item_id"]:
        labels, unique_events = _grant_items(player, [disc["item_id"]], projection)
    if disc["gold"]:
        player["gold"] = int(player.get("gold", 0) or 0) + int(disc["gold"])
    partes = ([", ".join(labels)] if labels else []) \
        + ([f"{disc['gold']} de ouro"] if disc["gold"] else [])
    return (f"Ao explorar {loc.get('name','o local')}, o jogador ENCONTROU: "
            f"{' e '.join(partes)}. Descreva o achado modesto.", unique_events)
