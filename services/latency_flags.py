"""SPEC-318: flags do trabalho pos-narracao (lidas a cada chamada; nunca levantam).

  RPG_NPC_TWO_PHASE=off|on        ficha de NPC em duas fases + memoria de NPC pelo arquivista (default on)
  RPG_REPLAN_AFTER=off|on         replan do arco depois da entrega (default on)
  RPG_DAY_DIGEST=llm|inline       digest do dia: chamada `narrate_day` ou bloco factual (default inline)
  RPG_ARCHIVE_POLICY=legacy|lean  gate do arquivista (default legacy)
  RPG_ARCHIVE_POLICY_SHADOW=0|1   mede o que `lean` pularia sem mudar nada (default 0)

Valor invalido cai no default do codigo.
"""

from __future__ import annotations

import os


def _choice(name: str, allowed: tuple[str, ...], default: str) -> str:
    raw = os.getenv(name, "").strip().lower()
    return raw if raw in allowed else default


def two_phase_on() -> bool:
    return _choice("RPG_NPC_TWO_PHASE", ("off", "on"), "on") == "on"


def replan_after_on() -> bool:
    return _choice("RPG_REPLAN_AFTER", ("off", "on"), "on") == "on"


def day_digest_inline() -> bool:
    return _choice("RPG_DAY_DIGEST", ("llm", "inline"), "inline") == "inline"


def archive_policy() -> str:
    return _choice("RPG_ARCHIVE_POLICY", ("legacy", "lean"), "legacy")


def archive_low_wanted() -> bool:
    """Os emissores so marcam `archive_low` quando a politica `lean` (ou o shadow) vai le-la:
    com as flags legadas o estado fica identico ao de antes da SPEC-318."""
    return archive_policy() == "lean" or archive_policy_shadow()


def archive_policy_shadow() -> bool:
    return os.getenv("RPG_ARCHIVE_POLICY_SHADOW", "").strip().lower() in ("1", "true", "on")
