"""
services/ecology.py — População de criaturas reage à caça e ao poder (Fase 6.3).

100% view derivada de dados que JÁ existem:
- `bestiary_knowledge` (Fase 3.2) é o censo: `defeated` + `last_update_turn`
  dão a pressão de caça (com decay por inatividade — parar de caçar devolve
  a população; o mundo fica raro, nunca vazio);
- `world_projection` dá o controlador do local (criatura da fação no poder
  domina os encontros);
- `blocked_routes` (Fase 6.1) barram migração — bicho também não atravessa
  rota fechada.

Zero estado novo, zero LLM, pesos determinísticos auditáveis.
"""
from typing import Dict, List, Optional

import random

# Constantes de calibração (chute declarado — playtest ajusta)
HUNT_WINDOW_FULL = 10    # kills "quentes" até N turnos atrás contam cheio
HUNT_WINDOW_HALF = 20    # até aqui contam metade; depois, zero (população volta)
FACTION_BOOST = 2.0
MIGRANT_WEIGHT = 0.5
MIGRANT_THRESHOLD = 0.3  # pressão média local abaixo disto abre vaga p/ migrante

_PRESSURE_STEPS = ((6, 0.1), (3, 0.3), (1, 0.6))


def hunt_pressure(enemy_id: str, bestiary_knowledge: Optional[Dict],
                  turn: int) -> float:
    """Peso [0.1..1.0] da criatura no sorteio da região. 1.0 = população intacta."""
    bk = (bestiary_knowledge or {}).get(enemy_id) or {}
    kills = int(bk.get("defeated", 0) or 0)
    if kills <= 0:
        return 1.0
    inactive = int(turn) - int(bk.get("last_update_turn", turn) or turn)
    if inactive > HUNT_WINDOW_HALF:
        return 1.0  # decay total: pararam de caçar, a população voltou
    effective = kills if inactive <= HUNT_WINDOW_FULL else kills * 0.5
    for threshold, weight in _PRESSURE_STEPS:
        if effective >= threshold:
            return weight
    return 1.0


def faction_boost(enemy: Dict, location_id: str,
                  projection: Optional[Dict]) -> float:
    """Criatura da fação que CONTROLA o local pesa mais (o poder traz os seus)."""
    fac = enemy.get("faction")
    if not fac or not location_id:
        return 1.0
    from services import graph_resolver as gr
    controller = gr.get_current_controller(location_id, projection)
    return FACTION_BOOST if controller and controller == fac else 1.0


def weighted_pick(candidates: List[Dict], weights: List[float],
                  rng: Optional[random.Random] = None) -> Optional[Dict]:
    rng = rng or random.Random()
    pool = [(c, w) for c, w in zip(candidates, weights) if w > 0]
    if not pool:
        return None
    cs, ws = zip(*pool)
    return rng.choices(list(cs), weights=list(ws), k=1)[0]


def suppressed_creatures(region_id: str, bestiary: Dict,
                         bestiary_knowledge: Optional[Dict], turn: int) -> List[str]:
    """Criaturas da região quase-extintas localmente (pressão <= 0.3)."""
    out = []
    for eid, e in (bestiary or {}).items():
        if region_id in (e.get("regions") or []):
            if hunt_pressure(eid, bestiary_knowledge, turn) <= MIGRANT_THRESHOLD:
                out.append(eid)
    return out


def suppressed_loot(region_id: str, bestiary: Dict,
                    bestiary_knowledge: Optional[Dict], turn: int) -> set:
    """Fase 6.3 (R4): drops das criaturas suprimidas somem do loot regional
    (as peles somem quando os bichos somem). Volta com o decay."""
    items: set = set()
    for eid in suppressed_creatures(region_id, bestiary, bestiary_knowledge, turn):
        for iid in (bestiary.get(eid) or {}).get("loot") or []:
            items.add(iid)
    return items


def migrant_candidates(loc: Dict, bestiary: Dict,
                       projection: Optional[Dict]) -> List[Dict]:
    """Criaturas de regiões CONECTADAS e alcançáveis (rotas 6.1 respeitadas) —
    entram no sorteio com peso reduzido quando a fauna local rareou."""
    from gamedata import get_location
    from services.economy import _blocked_pairs

    loc_id = (loc or {}).get("id", "")
    region_id = (loc or {}).get("region_id", "")
    blocked = _blocked_pairs(projection)
    neighbor_regions = set()
    for conn in (loc or {}).get("connections") or []:
        if frozenset((loc_id, conn)) in blocked:
            continue  # bicho também não atravessa rota bloqueada
        nregion = (get_location(conn) or {}).get("region_id", "")
        if nregion and nregion != region_id:
            neighbor_regions.add(nregion)
    out = []
    for e in (bestiary or {}).values():
        if "BOSS" in str(e.get("type", "")).upper():
            continue  # boss não migra (fica onde o Codex o pôs)
        if neighbor_regions & set(e.get("regions") or []):
            if region_id not in (e.get("regions") or []):
                out.append(e)
    return out


def regional_rarity_label(enemy_id: str, bestiary_knowledge: Optional[Dict],
                          turn: int) -> str:
    """Rótulo p/ o Codex do jogador (3.2): reflete a pressão de caça atual."""
    p = hunt_pressure(enemy_id, bestiary_knowledge, turn)
    if p <= 0.1:
        return "quase não se vê mais por aqui"
    if p <= 0.3:
        return "cada vez mais rara na região"
    if p <= 0.6:
        return "menos comum do que já foi"
    return ""
