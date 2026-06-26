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
        if not f.get("completed", False) and not f.get("defeated", False):
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


# --- Fase 2 / Etapa B: ascensão — concluir objetivo muda o MUNDO (determinístico) ---

def _raise_danger(world: dict, loc_id: str) -> None:
    """Sobe o perigo de um local em +1 (teto 4), via override de runtime."""
    overrides = dict(world.get("danger_overrides") or {})
    base = overrides.get(loc_id)
    if base is None:
        loc = gamedata.get_location(loc_id) or {}
        base = loc.get("danger", 1)
    overrides[loc_id] = min(4, int(base) + 1)
    world["danger_overrides"] = overrides
    if world.get("current_location_id") == loc_id:
        world["danger_level"] = overrides[loc_id]


def resolve_faction_completions(factions, world, events, intel) -> Tuple[list, dict, str]:
    """
    Aplica a ASCENSÃO de cada facção que concluiu o objetivo (`events` vem de `advance_factions`):
    o mundo muda de verdade (domina local, expande região, eleva perigo, invoca entidade, elimina
    rival). Determinístico — efeito autorado em `data/factions.json` (campo `ascension`).

    Não-onisciência: a nota de narração NOMEIA a facção só se o jogador a conhece (intel.known);
    senão descreve apenas a CONSEQUÊNCIA sentida (`perceived`), sem nome.

    Retorna (factions, world, nota).
    """
    factions = ensure_factions(factions)
    world = dict(world or {})
    intel = ensure_faction_intel(intel)
    if not events:
        return factions, world, ""

    by_id = {f.get("id"): f for f in factions}
    notes = []
    for ev in events:
        fid = ev.get("id")
        f = by_id.get(fid)
        if not f:
            continue
        asc = f.get("ascension") or {}
        atype = asc.get("type")
        perceived = asc.get("perceived", "")

        if atype == "expandir_regiao":
            f["region"] = asc.get("region", f.get("region"))
            if asc.get("next_goal"):
                f["goal"] = asc["next_goal"]
            f["progress"] = 0
            f["completed"] = False  # cadeia de escalada: continua evoluindo na nova frente
        elif atype == "dominar_local":
            tgt = asc.get("target")
            if tgt:
                ctrl = dict(world.get("controlled") or {})
                ctrl[tgt] = fid
                world["controlled"] = ctrl
        elif atype == "elevar_perigo":
            if asc.get("target"):
                _raise_danger(world, asc["target"])
        elif atype == "invocar_entidade":
            if asc.get("threat"):
                world["looming_threat"] = asc["threat"]
            if asc.get("target"):
                _raise_danger(world, asc["target"])
        elif atype == "eliminar_faccao":
            tgt = asc.get("target")
            if tgt and tgt in by_id:
                by_id[tgt]["defeated"] = True

        if intel.get(fid, {}).get("known"):
            notes.append(f"[MUNDO MUDA] {f.get('name')} concretizou seu intento: {perceived}")
        elif perceived:
            notes.append(f"[MUNDO MUDA] {perceived}")

    note = ""
    if notes:
        note = ("\n".join(notes) +
                "\nNarre estas consequências como algo que o jogador PERCEBE no mundo; "
                "NÃO revele nomes de facções que ele ainda não conhece.")
    return list(by_id.values()), world, note


# --- Fase 2: conhecimento do jogador sobre fações (não-onisciência) ---
# O jogador só sabe o que aprendeu (via NPC). Camadas: existência → objetivo → progresso (snapshot).

_REVEAL_LEVELS = ("existencia", "objetivo", "progresso")


def ensure_faction_intel(intel) -> dict:
    """Normaliza o mapa de inteligência (faction_id -> conhecimento). Default vazio."""
    if not isinstance(intel, dict):
        return {}
    out = {}
    for fid, rec in intel.items():
        rec = dict(rec or {})
        rec.setdefault("known", False)
        rec.setdefault("knows_goal", False)
        out[fid] = rec
    return out


def apply_faction_reveal(intel, factions, faction_id: str, level: str,
                         turn: int = 0) -> dict:
    """
    Aplica uma revelação de NPC ao conhecimento do jogador (determinístico, em camadas).
    level: 'existencia' | 'objetivo' | 'progresso'. id fora das fações = no-op.
    Retorna NOVO dict de intel.
    """
    intel = ensure_faction_intel(intel)
    lvl = (level or "").strip().lower()
    known_ids = {f.get("id") for f in ensure_factions(factions)}
    if not faction_id or faction_id not in known_ids or lvl not in _REVEAL_LEVELS:
        return intel

    rec = dict(intel.get(faction_id) or {})
    rec["known"] = True
    if lvl in ("objetivo", "progresso"):
        rec["knows_goal"] = True
    if lvl == "progresso":
        cur = next((f for f in ensure_factions(factions) if f.get("id") == faction_id), {})
        rec["progress_seen"] = int(cur.get("progress", 0))
        rec["intel_turn"] = int(turn)
    rec.setdefault("knows_goal", rec.get("knows_goal", False))
    intel = dict(intel)
    intel[faction_id] = rec
    return intel


# --- Fase 2: reputação muda por AÇÃO do jogador (determinístico) ---
# Convenção: a IA só identifica fação + direção; o VALOR do delta é fixo aqui.

REP_STEP = 12                       # delta fixo por ação (Python decide, não o LLM)
REP_MIN, REP_MAX = -100, 100
_ALIADO_AT, _HOSTIL_AT = 40, -40    # limiares de disposição derivada da reputação

_POS_CUES = ("ajud", "ajudo", "ajudou", "alia", "aliar", "favor", "apoi", "salv", "defend", "+")
_NEG_CUES = ("prejud", "trai", "traiu", "sabot", "atac", "rouba", "mata", "destr", "contra", "-")


def _disposition_for(rep: int) -> str:
    if rep >= _ALIADO_AT:
        return "aliado"
    if rep <= _HOSTIL_AT:
        return "hostil"
    return "neutro"


def _direction_sign(direction: str) -> int:
    """+1 para ajuda, -1 para prejuízo, 0 (no-op) se ambíguo/desconhecido."""
    d = (direction or "").strip().lower()
    if any(c in d for c in _POS_CUES):
        return 1
    if any(c in d for c in _NEG_CUES):
        return -1
    return 0


def apply_reputation(factions, faction_id: str, direction: str,
                     step: int = REP_STEP) -> Tuple[list, Optional[dict]]:
    """
    Aplica delta FIXO de reputação a uma fação identificada pelo id.
    direction: 'ajudou' (+) | 'prejudicou' (-). Clampa em [-100, 100] e
    re-deriva a disposition por limiar. id desconhecido ou direção ambígua → no-op.

    Retorna (novas_factions, evento|None). evento =
    {id, name, reputation, disposition, direction, delta} — para narração/crônica.
    """
    factions = ensure_factions(factions)
    sign = _direction_sign(direction)
    if not faction_id or sign == 0:
        return factions, None

    new_list, event = [], None
    for f in factions:
        f = dict(f)
        if f.get("id") == faction_id:
            old = int(f.get("reputation", 0))
            delta = sign * int(step)
            new_rep = max(REP_MIN, min(REP_MAX, old + delta))
            f["reputation"] = new_rep
            f["disposition"] = _disposition_for(new_rep)
            event = {
                "id": f.get("id"), "name": f.get("name"),
                "reputation": new_rep, "disposition": f["disposition"],
                "direction": "ajudou" if sign > 0 else "prejudicou",
                "delta": new_rep - old,
            }
        new_list.append(f)
    return new_list, event


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
