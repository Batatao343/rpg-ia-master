"""Vocabulário e classificação determinística da causa de um conflito."""
from __future__ import annotations

from typing import Any, Dict

ORIGINS = {
    "player_provoked", "travel_encounter", "regional_danger", "arc_pressure",
    "pursuit_recurrence", "unknown",
}


def normalize(value: object) -> str:
    value = str(value or "")
    return value if value in ORIGINS else "unknown"


def from_encounter(encounter: Dict[str, Any] | None, world: Dict[str, Any] | None,
                   *, trigger: str = "travel") -> str:
    encounter, world = encounter or {}, world or {}
    if (world.get("chase") or {}).get("active") or encounter.get("reason") == "recurrence":
        return "pursuit_recurrence"
    if encounter.get("reason") in {"reinforcements", "controlled", "faction_pressure"}:
        return "regional_danger"
    if encounter.get("reason") in {"arc", "beat", "scripted"}:
        return "arc_pressure"
    if trigger == "rest":
        return "regional_danger"
    return "travel_encounter"


def materialize(combat: Dict[str, Any] | None, hint: object) -> str:
    current = normalize(hint)
    if current != "unknown":
        return current
    return normalize((combat or {}).get("origin"))
