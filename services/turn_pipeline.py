"""Pure preparation and disjoint branch adapters for a game turn."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable


@dataclass(frozen=True)
class TurnPreparation:
    game_id: str
    turn: int
    timeline_epoch: int
    in_active_combat: bool


@dataclass(frozen=True)
class StageInterval:
    name: str
    started_ms: float
    finished_ms: float


def summarize_stage_intervals(intervals: Iterable[StageInterval]) -> dict[str, int]:
    """Distinguish elapsed critical path from total work and real overlap."""
    rows = [row for row in intervals if row.finished_ms >= row.started_ms]
    if not rows:
        return {"critical_path_ms": 0, "work_ms": 0, "overlap_ms": 0}
    critical = max(row.finished_ms for row in rows) - min(row.started_ms for row in rows)
    work = sum(row.finished_ms - row.started_ms for row in rows)
    return {
        "critical_path_ms": max(0, int(round(critical))),
        "work_ms": max(0, int(round(work))),
        "overlap_ms": max(0, int(round(work - critical))),
    }


def prepare_turn(state: dict) -> tuple[dict, TurnPreparation]:
    """Advance canonical turn/continuity exactly once before parallel reads."""
    world = dict(state.get("world") or {})
    world["turn_count"] = int(world.get("turn_count", 0) or 0) + 1
    from services.continuity import advance_action

    continuity = advance_action(
        state.get("continuity"), canonical_turn=world["turn_count"],
    )
    prepared = TurnPreparation(
        game_id=str(state.get("game_id") or ""),
        turn=world["turn_count"],
        timeline_epoch=int(continuity.get("timeline_epoch", 0) or 0),
        in_active_combat=bool((state.get("combat") or {}).get("active")),
    )
    return {
        "world": world,
        "continuity": continuity,
        "turn_prepared": True,
    }, prepared


def turn_prepare_node(state: dict) -> dict:
    from observability.telemetry import span

    with span("turn.prepare"):
        update, _prepared = prepare_turn(state)
        return update


def route_intent_node(state: dict) -> dict:
    """Router branch adapter: it never owns the canonical world channel."""
    from agents.router import dm_router_node

    from observability.telemetry import span

    with span("turn.route"):
        update = dict(dm_router_node(state) or {})
    update.pop("world", None)
    return update


def dispatch_node(_state: dict) -> dict:
    from observability.telemetry import span

    with span("turn.dispatch"):
        return {"turn_prepared": False}
