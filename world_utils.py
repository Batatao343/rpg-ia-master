"""
world_utils.py
Mecânica de mundo da Fase 0: relógio, viagem entre locais (fog of war) e descanso.
Tudo determinístico (sem LLM) — funciona igual no modo simulado.
"""
from typing import Optional, Tuple

import gamedata

PERIODS = ["Amanhecer", "Manhã", "Tarde", "Anoitecer", "Noite"]

# Pistas de intenção
_REST_WORDS = ["descans", "dormir", "durmo", "acamp", "repous", "pernoit", "descabel"]
_TRAVEL_CUES = ["vou", "viaj", "ir para", "ir até", "ir a", "sigo para", "sigo até",
                "caminho para", "rumo a", "parto", "vamos para", "seguir para",
                "me dirijo", "atravesso para", "voltar para", "volto para", "viajo"]


def ensure_world(world: dict) -> dict:
    """Backfill dos campos novos (compat com saves antigos). Retorna cópia."""
    world = dict(world or {})
    if not world.get("world_clock"):
        world["world_clock"] = {"day": 1, "period": PERIODS[0]}
    world.setdefault("visited", [])

    if not world.get("current_location_id"):
        loc = gamedata.find_location_by_name(world.get("current_location", ""))
        world["current_location_id"] = loc.get("id") if loc else gamedata.START_LOCATION_ID

    cid = world.get("current_location_id")
    if cid and cid not in world["visited"]:
        world["visited"] = world["visited"] + [cid]

    # mantém o nome em sincronia, se possível
    loc = gamedata.get_location(cid) if cid else {}
    if loc:
        world.setdefault("current_location", loc["name"])
        world.setdefault("danger_level", loc.get("danger", 1))
    return world


def advance_clock(world: dict, steps: int = 1) -> dict:
    """Avança o relógio em N períodos, virando o dia quando passa da Noite."""
    clock = dict(world.get("world_clock") or {"day": 1, "period": PERIODS[0]})
    idx = PERIODS.index(clock["period"]) if clock.get("period") in PERIODS else 0
    idx += max(0, steps)
    clock["day"] = clock.get("day", 1) + idx // len(PERIODS)
    clock["period"] = PERIODS[idx % len(PERIODS)]
    world["world_clock"] = clock
    world["time_of_day"] = clock["period"]
    return world


def is_rest(text: str) -> bool:
    t = (text or "").lower()
    return any(w in t for w in _REST_WORDS)


def find_travel_destination(world: dict, text: str) -> Optional[dict]:
    """
    Se o texto cita um local CONECTADO ao atual (com ou sem verbo de movimento),
    retorna o nó de destino; senão None.
    """
    t = (text or "").lower()
    cur_id = world.get("current_location_id")
    for dest in gamedata.get_connections(cur_id):
        if dest["name"].lower() in t or dest["id"] in t:
            return dest
    return None


def apply_travel(world: dict, dest: dict) -> dict:
    """Move o jogador para um destino: revela, sincroniza nome/perigo, gasta tempo."""
    world = dict(world)
    world["current_location_id"] = dest["id"]
    world["current_location"] = dest["name"]
    visited = list(world.get("visited", []))
    if dest["id"] not in visited:
        visited.append(dest["id"])
    world["visited"] = visited
    world["danger_level"] = dest.get("danger", world.get("danger_level", 1))
    advance_clock(world, 1)
    return world


def apply_rest(player: dict, world: dict) -> Tuple[dict, dict]:
    """Descanso: recupera ~metade dos recursos e avança 2 períodos."""
    player = dict(player)
    for res, mx in (("hp", "max_hp"), ("mana", "max_mana"), ("stamina", "max_stamina")):
        if mx in player:
            ceiling = player.get(mx, 0)
            healed = player.get(res, 0) + max(1, ceiling // 2)
            player[res] = min(ceiling, healed)
    world = dict(world)
    advance_clock(world, 2)
    # Fações avançam no tempo off-screen: o storyteller chama advance_factions(2)
    # após o descanso (2 períodos). world_simulator narrado virá no próximo slice.
    return player, world


# --- Fase 2: fações com objetivos próprios (mundo vivo, determinístico) ---

def ensure_factions(factions) -> list:
    """Backfill/normaliza a lista de fações (compat com saves sem o campo)."""
    if not factions:
        return gamedata.seed_factions()
    out = []
    for f in factions:
        f = dict(f or {})
        f.setdefault("progress", 0)
        f.setdefault("pace", 3)
        f.setdefault("disposition", "neutro")
        f.setdefault("reputation", 0)
        f.setdefault("completed", False)
        out.append(f)
    return out


def advance_factions(factions, periods: int = 1) -> Tuple[list, list]:
    """
    Avança o progresso de cada facção em `pace * periods` (determinístico, sem RNG).
    Marca como concluída ao cruzar 100 e devolve eventos das que ACABARAM de concluir.

    Retorna (novas_factions, eventos) — eventos é lista de dicts
    {id, name, goal, disposition} prontos para virar evento de mundo/narração.
    """
    factions = ensure_factions(factions)
    periods = max(0, int(periods))
    if periods == 0:
        return factions, []

    new_list, events = [], []
    for f in factions:
        f = dict(f)
        if not f.get("completed", False):
            f["progress"] = min(100, f.get("progress", 0) + f.get("pace", 3) * periods)
            if f["progress"] >= 100 and not f.get("completed", False):
                f["completed"] = True
                events.append({
                    "id": f.get("id"),
                    "name": f.get("name"),
                    "goal": f.get("goal", ""),
                    "disposition": f.get("disposition", "neutro"),
                })
        new_list.append(f)
    return new_list, events


def clock_label(world: dict) -> str:
    c = world.get("world_clock") or {}
    return f"Dia {c.get('day', 1)} · {c.get('period', PERIODS[0])}"


def starting_world(region_name: str, level: int) -> dict:
    """Monta o WorldState inicial a partir do local de início da região escolhida."""
    loc = gamedata.start_location_for_region(region_name) or {}
    loc_id = loc.get("id") or gamedata.START_LOCATION_ID
    return {
        "current_location": loc.get("name") or region_name,
        "current_location_id": loc_id,
        "visited": [loc_id] if loc_id else [],
        "world_clock": {"day": 1, "period": PERIODS[0]},
        "time_of_day": PERIODS[0],
        "turn_count": 0,
        "danger_level": loc.get("danger", level),
        "weather": "Nublado",
        "quest_plan": [],
        "quest_plan_origin": None,
    }
