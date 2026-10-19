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
# SPEC-226 R7: custo por categoria canônica.
CATEGORIA_COST = {"lacaio": 2, "padrao": 3, "elite": 5, "chefe": 12, "nomeado": 12}
BASE_BY_DANGER = {1: 2, 2: 4, 3: 7, 4: 10}


def tier_cost(enemy: dict) -> int:
    from combat_mechanics import normalize_categoria

    return CATEGORIA_COST[normalize_categoria(enemy)]


# SPEC-287: economia de ações no PISO do encontro. O custo por categoria é
# linear, mas no motor v4 cada corpo age uma vez por rodada contra uma
# Vitalidade do herói que não cresce com o nível (só Corpo a altera). A arena
# da SPEC-285 mediu a ameaça superlinear: 1→2→3 Lacaios = 0,05→0,32→0,56 de
# morte no nível 5, com custo 2→4→6. Sem isso, o piso (budget//2) crescia com
# o nível e o perigo e era completado com mais corpos: grupos de Lacaio nos
# níveis 5–8 matavam mais que um Chefe.
# [BALANCEAR] 1,25 é o menor passo que mantém os pisos dos níveis 5–8 da arena
# em até 2 corpos; pisos ≤ 4 (níveis 1–4) não mudam para nenhum passo ≥ 0,
# porque 1 corpo custa o mesmo e 2 corpos já alcançam qualquer piso ≤ 4.
ACTION_ECONOMY_STEP = 1.25


def action_economy_multiplier(bodies: int) -> float:
    """Multiplicador do custo por número de corpos (1 corpo = ×1)."""
    return 1.0 + ACTION_ECONOMY_STEP * max(0, int(bodies or 0) - 1)


def floor_cost(enemies: list[dict]) -> float:
    """SPEC-287: custo efetivo usado pelo piso (`fill_encounter`).

    Chefe/Nomeado entram pelo custo linear (já ignoram o orçamento); os demais
    somam o custo por categoria × `action_economy_multiplier(n)`, com n = número
    de corpos não-chefe."""
    bosses = [e for e in enemies if tier_cost(e) == TIER_COST["boss"]]
    rest = [e for e in enemies if tier_cost(e) != TIER_COST["boss"]]
    return sum(tier_cost(e) for e in bosses) + sum(
        tier_cost(e) for e in rest
    ) * action_economy_multiplier(len(rest))


def encounter_budget(player_level: int, danger: int, allies_count: int = 0) -> int:
    d = max(1, min(4, int(danger or 1)))
    lvl = max(1, int(player_level or 1))
    allies = 2 * max(0, int(allies_count or 0))
    raw = BASE_BY_DANGER[d] + lvl + allies
    # Teto de sobrevivência (achado do playtest da Fase 5): a base de perigo era
    # um piso duro que IGNORAVA o sub-nível — nível-1 em danger-4 pegava budget 11
    # (≈2 elites) = sentença de morte por burst, contra 1 minion no perigo
    # apropriado. Viajar sub-nivelado ficava mais letal que atacar tudo no seu
    # nível. O teto amarra a dificuldade MÁXIMA de um encontro aleatório/forçado
    # ao nível do herói: perigo alto continua o mais duro que ele enfrenta, mas
    # deixa de ser one-shot. Bosses IGNORAM o budget (clamp_encounter nunca corta
    # boss), então chefes de história/encontros roteirizados não são afetados.
    cap = 5 + 3 * lvl + allies
    return min(raw, cap)


def clamp_encounter(
    enemies: list[dict], budget: int, player_level: int = 0, *, protected: set | None = None
) -> tuple[list[dict], list[str]]:
    """Corta o excedente do orçamento. Regras: boss NUNCA é cortado; prioriza
    VARIEDADE (1 de cada template antes de repetições); mantém >= 1 inimigo.
    Nível 1 (spec balanceamento-early-game R2.1): no máximo 1 elite — burst de
    2+ elites é sentença de morte pro herói recém-criado. Bosses seguem intactos.
    SPEC-203 (D-B): templates `protected` (alvo canônico resolvido) entram ANTES
    da variedade — fauna nunca toma a vaga do alvo; a regra numérica não muda.
    Retorna (mantidos, logs de corte p/ o narrador)."""
    if not enemies:
        return [], []
    bosses = [e for e in enemies if tier_cost(e) == TIER_COST["boss"]]
    rest = [e for e in enemies if tier_cost(e) != TIER_COST["boss"]]
    if int(player_level or 0) == 1:
        elites = [e for e in rest if tier_cost(e) == TIER_COST["elite"]]
        for extra in elites[1:]:
            rest.remove(extra)

    def _template(e: dict) -> str:
        import re

        return re.sub(r"_\d+$", "", str(e.get("id", e.get("name", "?"))))

    # variedade primeiro: 1ª instância de cada template, depois repetições
    seen: dict[str, int] = {}
    canonical, firsts, repeats = [], [], []
    protected = set(protected or ())
    for e in sorted(rest, key=tier_cost, reverse=True):  # elites antes de minions
        t = _template(e)
        if t in protected:
            canonical.append(e)
            continue
        (firsts if t not in seen else repeats).append(e)
        seen[t] = seen.get(t, 0) + 1

    kept = list(bosses)
    spent = sum(tier_cost(e) for e in kept)
    for e in canonical + firsts + repeats:
        c = tier_cost(e)
        if spent + c <= budget or not kept:
            kept.append(e)
            spent += c
    cut = [e for e in enemies if e not in kept]
    logs = (
        [f"Apenas {len(kept)} inimigo(s) alcançam você — o resto se perde na confusão."]
        if cut
        else []
    )
    return kept, logs


def fill_encounter(
    enemies: list[dict], budget: int, loc: dict, danger: int, turn: int = 0, make_instance=None
) -> tuple[list[dict], list[str]]:
    """PISO (budget/2): local perigoso reforça encontro fraco com criatura regional.
    `make_instance(entry, i)` transforma a entrada do bestiário em instância de
    combate (injetado pelo chamador para reusar o pipeline do spawn).
    SPEC-287: o piso é medido por `floor_cost` (economia de ações), não pela
    soma linear — cada corpo extra pesa mais, então o piso fecha com menos corpos."""
    import world_utils as wu

    kept = list(enemies)
    logs: list[str] = []
    floor = max(TIER_COST["minion"], budget // 2)
    spent = floor_cost(kept)
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
        spent = floor_cost(kept)
        logs.append(f"{inst.get('name', 'Algo')} surge atraído pelo tumulto.")
    return kept, logs
