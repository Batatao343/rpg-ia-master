"""
encounter_budget.py — Orçamento determinístico de encontro (Fase 4.6).

O EncounterScanner (LLM) continua livre pra narrar "uma horda"; AQUI o motor
clampa o que entra de fato na mecânica: orçamento em PONTOS por tier
(1 boss ≠ 6 minions), escalando com danger, nível do player e party.
Também há PISO: encontro fraco em local perigoso é reforçado com criatura
regional (pick_encounter_enemy, 2.5b). LLM nunca decide a quantidade final.
"""
from typing import Dict, List, Optional, Tuple

TIER_COST = {"minion": 2, "elite": 5, "boss": 12}
BASE_BY_DANGER = {1: 2, 2: 4, 3: 7, 4: 10}


def tier_cost(enemy: Dict) -> int:
    return TIER_COST.get(str(enemy.get("type", "minion")).strip().lower(),
                         TIER_COST["minion"])


def encounter_budget(player_level: int, danger: int, allies_count: int = 0) -> int:
    d = max(1, min(4, int(danger or 1)))
    return BASE_BY_DANGER[d] + max(1, int(player_level or 1)) + 2 * max(0, int(allies_count or 0))


def clamp_encounter(enemies: List[Dict], budget: int) -> Tuple[List[Dict], List[str]]:
    """Corta o excedente do orçamento. Regras: boss NUNCA é cortado; prioriza
    VARIEDADE (1 de cada template antes de repetições); mantém >= 1 inimigo.
    Retorna (mantidos, logs de corte p/ o narrador)."""
    if not enemies:
        return [], []
    bosses = [e for e in enemies if tier_cost(e) == TIER_COST["boss"]]
    rest = [e for e in enemies if tier_cost(e) != TIER_COST["boss"]]

    def _template(e: Dict) -> str:
        import re
        return re.sub(r"_\d+$", "", str(e.get("id", e.get("name", "?"))))

    # variedade primeiro: 1ª instância de cada template, depois repetições
    seen: Dict[str, int] = {}
    firsts, repeats = [], []
    for e in sorted(rest, key=tier_cost, reverse=True):  # elites antes de minions
        t = _template(e)
        (firsts if t not in seen else repeats).append(e)
        seen[t] = seen.get(t, 0) + 1

    kept = list(bosses)
    spent = sum(tier_cost(e) for e in kept)
    for e in firsts + repeats:
        c = tier_cost(e)
        if spent + c <= budget or not kept:
            kept.append(e)
            spent += c
    cut = [e for e in enemies if e not in kept]
    logs = ([f"Apenas {len(kept)} inimigo(s) alcançam você — o resto se perde na confusão."]
            if cut else [])
    return kept, logs


def fill_encounter(enemies: List[Dict], budget: int, loc: Dict, danger: int,
                   turn: int = 0, make_instance=None) -> Tuple[List[Dict], List[str]]:
    """PISO (budget/2): local perigoso reforça encontro fraco com criatura regional.
    `make_instance(entry, i)` transforma a entrada do bestiário em instância de
    combate (injetado pelo chamador para reusar o pipeline do spawn)."""
    import world_utils as wu

    kept = list(enemies)
    logs: List[str] = []
    floor = max(TIER_COST["minion"], budget // 2)
    spent = sum(tier_cost(e) for e in kept)
    i = 0
    while spent < floor and i < 4:
        i += 1
        entry = wu.pick_encounter_enemy(loc, danger, turn)
        if not entry or make_instance is None:
            break
        inst = make_instance(entry, len(kept) + i)
        if not inst:
            break
        kept.append(inst)
        spent += tier_cost(inst)
        logs.append(f"{inst.get('name', 'Algo')} surge atraído pelo tumulto.")
    return kept, logs
