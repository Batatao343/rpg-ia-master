"""Direção social canônica quando não existe interlocutor em cena."""
from __future__ import annotations

from typing import Any, Dict

import gamedata
from services.objectives import public_objective


def build_social_direction(state: Dict[str, Any]) -> str:
    world = state.get("world") or {}
    current_id = str(world.get("current_location_id") or "")
    connections = list(gamedata.get_connections(current_id)) if current_id else []
    destination = min(
        (loc for loc in connections if isinstance(loc, dict) and loc.get("name")),
        key=lambda loc: (int(loc.get("danger", loc.get("danger_level", 9)) or 9),
                         str(loc.get("name"))),
        default=None,
    )
    objective = public_objective(
        state.get("campaign_plan"), state.get("quests"), world,
    )["objective"]
    if destination:
        return (
            f"Não há interlocutor aqui. O destino conectado {destination['name']} "
            f"é uma direção concreta para procurar gente ou informação. {objective}"
        )
    return f"Não há interlocutor aqui. Dê uma pista ambiental útil. {objective}"
