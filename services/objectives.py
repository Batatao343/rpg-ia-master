"""Representação pública de objetivos, separada dos beats privados do diretor."""
from __future__ import annotations

from typing import Any, Dict, Iterable


def public_objective(plan: Dict[str, Any] | None, quests: Iterable[dict] | None,
                     world: Dict[str, Any] | None) -> Dict[str, Any]:
    """Deriva uma direção segura sem copiar beat/clímax do ``CampaignPlan``."""
    active = next(
        (q for q in (quests or []) if isinstance(q, dict) and q.get("status") == "active"),
        None,
    )
    if active:
        text = str(active.get("description") or active.get("title") or "").strip()
        return {
            "objective": text or "Avance na missão registrada.",
            "source": "side_quest",
            "quest_id": str(active.get("id") or ""),
            "location_id": str(active.get("location_id") or ""),
        }

    plan = plan or {}
    world = world or {}
    location = str(world.get("current_location") or plan.get("location") or "esta região").strip()
    arc = str(plan.get("arc_title") or "").strip()
    objective = f"Investigue os acontecimentos em {location}."
    if arc:
        objective += f" Arco atual: {arc}."
    return {
        "objective": objective,
        "source": "campaign",
        "quest_id": "",
        "location_id": str(world.get("current_location_id") or ""),
    }
