"""SPEC-387 R10: nome genérico do scanner ("Criatura hostil") vira criatura da REGIÃO atual.

Sem LLM e sem RPG_FAUNA: o catálogo é o mesmo de `services/fauna._region_candidates`. A escolha é
determinística por `crc32(game_id|turn|dica)`, então recarregar/repetir o turno dá a mesma criatura.
"""

from __future__ import annotations

import zlib

from observability.telemetry import log_event
from services import encounter_manifest as em


def is_contentless_name(name: str) -> bool:
    """True quando o nome não tem token de conteúdo ("Criatura hostil", "Inimigo")."""
    return not em.name_tokens(name)


def _bestiary_candidates(region: str, danger: int) -> list[str]:
    """Bestiário com `regions` ∋ região, sem chefe e com perigo compatível; prefere as
    criaturas físicas de Valoria (`familia_valoria`) quando a região as tem."""
    import gamedata
    from encounter_budget import is_boss
    from services import fauna

    rows = [
        (bid, e)
        for bid, e in sorted((gamedata.BESTIARY or {}).items())
        if region in (e.get("regions") or []) and not is_boss(e) and fauna._fits_danger(bid, danger)
    ]
    physical = [bid for bid, e in rows if e.get("familia_valoria")]
    return physical or [bid for bid, _e in rows]


def regional_pick(state: dict | None, hint: str) -> str | None:
    """Id do bestiário de uma criatura da região atual (sem chefe, perigo compatível) ou None."""
    from services import fauna
    from services.shared_pool import _region_of

    world = (state or {}).get("world") or {}
    region = _region_of(str(world.get("current_location_id") or ""))
    if not region:
        return None
    danger = fauna._region_danger(region, world)
    ids = sorted(str(e.get("id")) for e in fauna._region_candidates(region, danger) if e.get("id"))
    if not ids:  # o catálogo de fauna ainda não cobre a região: mesmo filtro sobre o bestiário
        ids = _bestiary_candidates(region, danger)
    if not ids:
        return None
    seed = f"{(state or {}).get('game_id') or 'game'}|{world.get('turn_count', 0)}|{hint}"
    return ids[zlib.crc32(seed.encode()) % len(ids)]


def regional_template(
    name: str, state: dict | None, hint: str, encounter_level: int
) -> dict | None:
    """Ficha da criatura regional que substitui `name` genérico; None mantém o caminho de hoje."""
    if not is_contentless_name(name):
        return None
    bid = regional_pick(state, hint)
    if not bid:
        return None
    from agents.bestiary import template_by_id

    template = template_by_id(bid, encounter_level=encounter_level)
    if template:
        log_event("combat", "spawn_generic_regional", level="info")
    return template
