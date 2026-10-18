"""services/conflict_resolution.py — motor de RESOLUÇÃO do conflito v2 (spec conflito-04).

Núcleo determinístico da mecânica nova: iniciativa por lado, ataque
`2d10 + Virtude vs Esquiva`, Crítico/Supercrítico por DUPLA nos dados mantidos,
Vantagem/Desvantagem (3d10 mantendo 2), testes gerais `Ímpeto + Presságio +
Virtude vs dificuldade`, e integração de Ruptura.

Este é o núcleo em produção desde o cutover conflito-13; o antigo pipeline
d20+AC foi removido.
"""
import random
from typing import Dict, List, Optional

# R4: Virtude adequada por tipo de arma/carta.
VIRTUDE_POR_TIPO = {
    "pesada": "forca", "arco": "agilidade", "adaga": "agilidade", "rapieira": "agilidade",
    "magia": "mente", "arcana": "mente", "precisa": "mente",
    "comando": "carisma", "fe": "carisma", "medo": "carisma", "presenca": "carisma",
    "sangue": "corpo", "carne": "corpo", "transformacao": "corpo",
}

# R7: dificuldades-base dos testes gerais.
DIFICULDADES = {"facil": 9, "comum": 12, "dificil": 15, "extremo": 18, "quase_impossivel": 21}

_LEGACY_VIRTUDE = {"forca": "str", "agilidade": "dex", "corpo": "con",
                   "mente": "int", "carisma": "cha"}


def virtude_para_tipo(tipo: str) -> str:
    """Mapeia um tipo de arma/carta (R4) para a Virtude adequada. Default: forca."""
    return VIRTUDE_POR_TIPO.get(str(tipo or "").strip().lower(), "forca")


def virtude_value(actor: dict, key: str) -> int:
    """Valor de Virtude (0-5) do ator. Player/criatura nova usa `virtudes`; inimigo
    legado (pré-conflito-15) cai numa derivação do `attributes` D&D (clampado 0-5)."""
    v = actor.get("virtudes")
    if isinstance(v, dict) and key in v:
        try:
            return max(0, min(5, int(v.get(key, 0) or 0)))
        except (TypeError, ValueError):
            return 0
    from combat_mechanics import actor_mods
    return max(0, min(5, actor_mods(actor).get(_LEGACY_VIRTUDE.get(key, "str"), 0)))


def compute_esquiva(actor: dict, *, include_modifiers: bool = True) -> int:
    """Esquiva = 10 + Agilidade − penalidade (armadura pesada é conflito-05).

    SPEC-232 R1: soma o stat `ac` de condições ativas e passivas estáticas
    (`combat_modifiers`). Fichas persistidas guardam só a base
    (`include_modifiers=False`) — buff transitório nunca vira dado salvo."""
    base = 10 + virtude_value(actor, "agilidade") - int(actor.get("esquiva_penalidade", 0) or 0)
    if include_modifiers:
        from combat_mechanics import combat_modifiers
        base += int(combat_modifiers(actor).get("ac", 0) or 0)
    return base


# --------------------------------------------------------------------------
# Rolagem (2d10 / 3d10 mantendo 2)
# --------------------------------------------------------------------------
def _d10(rng) -> int:
    return rng.randint(1, 10)


def roll_kept(advantage: int, rng) -> Dict:
    """R6: advantage>0 = Vantagem (3d10, mantém 2 maiores); <0 = Desvantagem (3d10,
    mantém 2 menores); 0 = normal (2d10). Sinal só — não acumula dados extras."""
    net = 1 if advantage > 0 else (-1 if advantage < 0 else 0)
    if net == 0:
        rolled = [_d10(rng), _d10(rng)]
        return {"rolled": rolled, "kept": list(rolled)}
    rolled = [_d10(rng) for _ in range(3)]
    ordenado = sorted(rolled)
    kept = ordenado[-2:] if net > 0 else ordenado[:2]
    return {"rolled": rolled, "kept": kept}


def _crit_from_kept(kept: List[int]) -> Optional[str]:
    """R5: dupla 1-9 nos dados MANTIDOS = Crítico; dupla 10 = Supercrítico."""
    a, b = kept[0], kept[1]
    if a == b:
        if a == 10:
            return "supercritico"
        if 1 <= a <= 9:
            return "critico"
    return None


# --------------------------------------------------------------------------
# Iniciativa por lado (R2/R3)
# --------------------------------------------------------------------------
def _initiative_value(actor: dict) -> int:
    """Agilidade + `initiative` de condições/passivas (SPEC-232 R2)."""
    from combat_mechanics import combat_modifiers
    return virtude_value(actor, "agilidade") + int(
        combat_modifiers(actor).get("initiative", 0) or 0)


def _side_roll(participants: List[dict], rng) -> Dict:
    ag = max((_initiative_value(p) for p in participants
              if p.get("conscious", True)), default=0)
    dados = [_d10(rng), _d10(rng)]
    return {"dice": dados, "agilidade": ag, "total": sum(dados) + ag}


def roll_initiative_by_side(sides: Dict[str, List[dict]], *,
                            initiator: Optional[str] = None, rng=None) -> Dict:
    """R2: se `initiator` iniciou claramente, age primeiro sem disputa; senão cada
    lado rola 2d10 + maior Agilidade consciente e o maior total age primeiro.
    Retorna {"order": [side...], "auto": bool, "rolls": {side: roll|None}}."""
    rng = rng or random
    if initiator and initiator in sides:
        outros = [s for s in sides if s != initiator]
        rolls = {s: _side_roll(sides[s], rng) for s in outros}
        ordem = [initiator] + sorted(outros, key=lambda s: rolls[s]["total"], reverse=True)
        return {"order": ordem, "auto": True, "rolls": {initiator: None, **rolls}}
    rolls = {s: _side_roll(sides[s], rng) for s in sides}
    ordem = sorted(sides, key=lambda s: rolls[s]["total"], reverse=True)
    return {"order": ordem, "auto": False, "rolls": rolls}


# --------------------------------------------------------------------------
# Ataque: 2d10 + Virtude vs Esquiva (R4/R5/R6/R8)
# --------------------------------------------------------------------------
def resolve_attack(attacker: dict, target: dict, *,
                   virtude_key: Optional[str] = None,
                   virtude_value_override: Optional[int] = None,
                   advantage: int = 0, ruptura: bool = False,
                   esquiva: Optional[int] = None, rng=None) -> Dict:
    """Resolve um ataque. Retorna a matemática COMPLETA (R9): dados rolados/mantidos,
    Virtude, total, Esquiva, resultado (erro/acerto/critico/supercritico) e o
    multiplicador do efeito PRINCIPAL. Ruptura concede Vantagem (R8)."""
    rng = rng or random
    from combat_mechanics import combat_modifiers
    if ruptura:
        advantage += 1
    if virtude_value_override is not None:
        vval = int(virtude_value_override)
    else:
        vval = virtude_value(attacker, virtude_key or "forca")
    # SPEC-232 R1/R2: buffs/debuffs (condições) e passivas estáticas do atacante
    # entram no total; `advantage` tipado conta só pelo sinal (Vantagem não acumula).
    mods = combat_modifiers(attacker)
    modificador = int(mods.get("attack", 0) or 0)
    cond_adv = int(mods.get("advantage", 0) or 0)
    advantage += (1 if cond_adv > 0 else -1 if cond_adv < 0 else 0)
    esq = int(esquiva) if esquiva is not None else compute_esquiva(target)

    roll = roll_kept(advantage, rng)
    kept = roll["kept"]
    total = sum(kept) + vval + modificador
    crit = _crit_from_kept(kept)
    if crit == "supercritico":
        resultado, mult, acerto = "supercritico", 3, True
    elif crit == "critico":
        resultado, mult, acerto = "critico", 2, True
    else:
        acerto = total >= esq
        resultado, mult = ("acerto" if acerto else "erro"), 1

    return {
        "dice_rolled": roll["rolled"], "dice_kept": kept, "virtude": vval,
        "modificador": modificador, "total": total, "esquiva_alvo": esq, "resultado": resultado,
        "acerto": acerto, "efeito_principal_multiplicador": mult,
        "ruptura": bool(ruptura), "advantage": advantage,
    }


# --------------------------------------------------------------------------
# Testes gerais: Ímpeto + Presságio + Virtude vs dificuldade (R7/R8)
# --------------------------------------------------------------------------
def general_test(actor: dict, virtude_key: str, dificuldade, *,
                 ruptura: bool = False, rng=None) -> Dict:
    """Teste FORA de ataque. Ímpeto maior = consequência favorável; Presságio maior
    = desfavorável; empate = puro. Ruptura: 2 dados de Ímpeto, mantém o maior (R8).
    Ataques NÃO usam esta matriz."""
    rng = rng or random
    dc = DIFICULDADES.get(dificuldade, dificuldade) if isinstance(dificuldade, str) else int(dificuldade)
    vval = virtude_value(actor, virtude_key)
    if ruptura:
        impetos = [_d10(rng), _d10(rng)]
        impeto = max(impetos)
    else:
        impetos = [_d10(rng)]
        impeto = impetos[0]
    pressagio = _d10(rng)
    total = impeto + pressagio + vval
    if impeto > pressagio:
        consequencia = "favoravel"
    elif pressagio > impeto:
        consequencia = "desfavoravel"
    else:
        consequencia = "puro"
    return {
        "impeto": impeto, "impetos_rolados": impetos, "pressagio": pressagio,
        "virtude": vval, "total": total, "dificuldade": dc,
        "sucesso": total >= dc, "consequencia": consequencia, "ruptura": bool(ruptura),
    }
