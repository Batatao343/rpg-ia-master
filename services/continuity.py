"""Metatempo da sessão que não retrocede quando um checkpoint é restaurado."""
from __future__ import annotations

from copy import deepcopy
from typing import Any, Dict

MAX_DEATH_HISTORY = 32


def normalize(value: Dict[str, Any] | None, *, canonical_turn: int = 0) -> Dict[str, Any]:
    value = deepcopy(value or {})
    action_count = (
        max(0, int(value.get("session_action_count", 0) or 0))
        if "session_action_count" in value
        else max(0, int(canonical_turn or 0))
    )
    return {
        "session_action_count": action_count,
        "timeline_epoch": max(0, int(value.get("timeline_epoch", 0) or 0)),
        "last_checkpoint_turn": max(
            0, int(value.get("last_checkpoint_turn", canonical_turn) or 0)
        ),
        "death_history": [dict(row) for row in value.get("death_history", [])
                          if isinstance(row, dict)][-MAX_DEATH_HISTORY:],
    }


def advance_action(value: Dict[str, Any] | None, *, canonical_turn: int) -> Dict[str, Any]:
    out = normalize(value, canonical_turn=max(0, canonical_turn - 1))
    out["session_action_count"] += 1
    return out


def mark_checkpoint(value: Dict[str, Any] | None, *, canonical_turn: int) -> Dict[str, Any]:
    out = normalize(value, canonical_turn=canonical_turn)
    out["last_checkpoint_turn"] = int(canonical_turn)
    return out


def after_restore(dead_state: dict, restored_state: dict) -> Dict[str, Any]:
    dead_turn = int((dead_state.get("world") or {}).get("turn_count", 0) or 0)
    restored_turn = int((restored_state.get("world") or {}).get("turn_count", 0) or 0)
    meta = normalize(dead_state.get("continuity"), canonical_turn=dead_turn)
    combat = dead_state.get("combat") or {}
    death_context = combat.get("death_context") or {}
    location = str((dead_state.get("world") or {}).get("current_location") or "")
    cause = str(death_context.get("killer") or death_context.get("cause") or "queda letal")
    record = {
        "epoch": meta["timeline_epoch"],
        "session_action": meta["session_action_count"],
        "death_turn": dead_turn,
        "restored_turn": restored_turn,
        "lost_canonical_turns": max(0, dead_turn - restored_turn),
        "location": location,
        "cause": cause,
        "retained": ["histórico de mortes", "contagem de ações da sessão"],
        "reverted": ["estado do mundo", "inventário", "posição", "memória após o checkpoint"],
    }
    meta["timeline_epoch"] += 1
    meta["last_checkpoint_turn"] = restored_turn
    meta["death_history"] = [*meta["death_history"], record][-MAX_DEATH_HISTORY:]
    return meta
