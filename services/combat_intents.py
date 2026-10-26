"""services/combat_intents.py - intencoes de combate por regex fechada (SPEC-325).

Funcoes puras, sem LLM: a intencao vem de regex ou nome canonico. Fase A so
expoe o golpe nao-letal; as demais (fuga, objeto, ordem) entram nas fases B-D.
"""

from __future__ import annotations

from services.death_flow import NONLETHAL_RE, nonlethal_declared  # noqa: F401

__all__ = ["NONLETHAL_RE", "nonlethal_declared"]
