"""services/combat_flags.py - kill switches por capacidade de conflito (SPEC-325 R1).

Cada capacidade dormente do motor de conflito tem a sua variavel `RPG_*`:
`off` = comportamento anterior byte a byte; `shadow` = calcula e registra, sem
mudar estado, cena, ficha ou prosa; `on` = efeito real. Default do codigo e
`shadow`; valor invalido tambem vira `shadow` (mesmo padrao de `law.mode()`).
"""

from __future__ import annotations

import os
from typing import Literal

Mode = Literal["off", "shadow", "on"]
MODES: tuple[str, ...] = ("off", "shadow", "on")

# capacidade -> variavel de ambiente
ENV_VARS: dict[str, str] = {
    "reveal_resist": "RPG_COMBAT_REVEAL_RESIST",
    "nonlethal": "RPG_COMBAT_NONLETHAL",
    "chase_approach": "RPG_CHASE_APPROACH",
    "chase_attack": "RPG_CHASE_ATTACK",
    "chase_abandon": "RPG_CHASE_ABANDON",
    "objects": "RPG_COMBAT_OBJECTS",
    "companion_orders": "RPG_COMPANION_ORDERS",
    "reinforcements": "RPG_COMBAT_REINFORCEMENTS",
}
CAPS: tuple[str, ...] = tuple(ENV_VARS)

_DTYPE_LABEL = {
    "cortante": "Cortante",
    "perfurante": "Perfurante",
    "impactante": "Impactante",
    "igneo": "Ígneo",
    "gelido": "Gélido",
    "eletrico": "Elétrico",
    "arcano": "Arcano",
    "corrosivo": "Corrosivo",
    "abissal": "Abissal",
}
_EFFECT_LABEL = {"imune": "imune", "resiste": "resiste", "vulneravel": "vulnerável"}
RESIST_EFFECTS: tuple[str, ...] = tuple(_EFFECT_LABEL)


def mode(cap: str) -> Mode:
    """Modo da capacidade; capacidade desconhecida ou valor invalido -> `shadow`."""
    var = ENV_VARS.get(cap)
    raw = str(os.getenv(var, "shadow") if var else "shadow").strip().lower()
    return raw if raw in MODES else "shadow"  # type: ignore[return-value]


def active(cap: str) -> bool:
    return mode(cap) == "on"


def shadow(cap: str) -> bool:
    return mode(cap) == "shadow"


def resistance_label(entry: str) -> str:
    """`igneo:imune` -> `Ígneo (imune)`. Entrada sem `:` (formato legado do overlay
    do bestiario) volta como esta."""
    dtype, sep, effect = str(entry).partition(":")
    if not sep:
        return str(entry)
    return f"{_DTYPE_LABEL.get(dtype, dtype.capitalize())} ({_EFFECT_LABEL.get(effect, effect)})"


def is_resistance_entry(entry: object) -> bool:
    """Formato `<dtype>:<imune|resiste|vulneravel>` (invariante do playtest)."""
    if not isinstance(entry, str):
        return False
    dtype, sep, effect = entry.partition(":")
    return bool(sep and dtype and effect in RESIST_EFFECTS)


def abandon_mode() -> Mode:
    """`chase_abandon` efetivo: sem a alma dos companheiros (`RPG_COMPANION_SOUL=off`) ninguém
    consome o destino selado, então abandono/sacrificio ficam `off` (SPEC-325 B-P2-1)."""
    from services import companion_soul

    return "off" if companion_soul.mode() == "off" else mode("chase_abandon")
