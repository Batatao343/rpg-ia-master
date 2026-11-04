"""SPEC-377 R1-R6: hook diario `post` que poda `wanted` totalmente decaido.

Modulo proprio: `services/law.py` e god-file e nao cresce.
"""

from __future__ import annotations

from typing import Any


def day_hook(ctx: Any) -> Any:
    """Poda entradas `wanted` sem calor, capital nem recompensa (via `law.daily_tick`).

    Vazio fora do motor `on`: o `storyteller` mescla `state_patch` sem olhar o modo,
    entao o guard mora aqui (o de `npc_world` nao serve de modelo, R6)."""
    from services import law, world_engine

    res = world_engine.DayHookResult()
    if world_engine.mode() != "on" or law.mode() == "off" or ctx.state is None:
        return res
    patch = law.daily_tick(ctx.state, int(ctx.day))
    if patch:
        res.state_patch = patch
    return res
