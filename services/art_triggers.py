"""Gatilhos fechados e orçamento raro por instância de arco."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from typing import Any, Mapping
from uuid import NAMESPACE_URL, uuid5

from services.visual_catalog import visual_for


NPC_LIMIT_PER_ARC = 4
NPC_COOLDOWN_TURNS = 15


@dataclass(frozen=True)
class ArtGenerationRequest:
    trigger_kind: str
    trigger_instance_id: str
    subject_type: str
    subject_id: str
    arc_instance_id: str | None
    action_key: str


def arc_instance_id(state: Mapping[str, Any]) -> str:
    plan = state.get("campaign_plan") or {}
    existing = str(plan.get("arc_instance_id") or "")
    if existing:
        return existing
    seed = ":".join([
        str(state.get("game_id") or ""), str(plan.get("arc_title") or "sem-arco"),
        str(plan.get("last_planned_turn") or (state.get("world") or {}).get("turn_count", 0)),
    ])
    return uuid5(NAMESPACE_URL, seed).hex


def _budget(state: Mapping[str, Any], arc_id: str) -> dict[str, Any]:
    existing = (state.get("art_arc_budgets") or {}).get(arc_id) or {}
    return {
        "arc_instance_id": arc_id,
        "npc_generations_used": int(existing.get("npc_generations_used", 0) or 0),
        "epic_generation_used": bool(existing.get("epic_generation_used")),
        "last_npc_generation_turn": existing.get("last_npc_generation_turn"),
    }


def reserve_request(state: Mapping[str, Any], request: ArtGenerationRequest) -> dict[str, Any] | None:
    if request.trigger_kind == "subclass_chosen":
        return None
    ledger = list(state.get("art_generation_ledger") or [])
    dedupe = (request.trigger_kind, request.trigger_instance_id, request.arc_instance_id)
    if any((row.get("trigger_kind"), row.get("trigger_instance_id"), row.get("arc_instance_id")) == dedupe
           for row in ledger):
        return None
    budgets = {key: dict(value) for key, value in (state.get("art_arc_budgets") or {}).items()}
    if request.trigger_kind in {"npc_first_appearance", "arc_epic_moment"}:
        if not request.arc_instance_id:
            return None
        budget = _budget(state, request.arc_instance_id)
        if request.trigger_kind == "npc_first_appearance":
            turn = int((state.get("world") or {}).get("turn_count", 0) or 0)
            last = budget["last_npc_generation_turn"]
            if budget["npc_generations_used"] >= NPC_LIMIT_PER_ARC:
                return None
            if last is not None and turn - int(last) < NPC_COOLDOWN_TURNS:
                return None
            budget["npc_generations_used"] += 1
            budget["last_npc_generation_turn"] = turn
        elif budget["epic_generation_used"]:
            return None
        else:
            budget["epic_generation_used"] = True
        budgets[request.arc_instance_id] = budget
    generation_id = uuid5(
        NAMESPACE_URL,
        f"{state.get('game_id')}:{request.trigger_kind}:{request.trigger_instance_id}:"
        f"{request.arc_instance_id}:{request.action_key}",
    ).hex
    ledger.append({
        "generation_id": generation_id, "trigger_kind": request.trigger_kind,
        "trigger_instance_id": request.trigger_instance_id,
        "arc_instance_id": request.arc_instance_id, "subject_type": request.subject_type,
        "subject_id": request.subject_id, "status": "pending",
    })
    return {"art_arc_budgets": budgets, "art_generation_ledger": ledger[-128:],
            "request": request, "generation_id": generation_id}


def resolve_art_triggers(previous: Mapping[str, Any], current: Mapping[str, Any], *,
                         action_key: str) -> list[ArtGenerationRequest]:
    if not current.get("dynamic_art_enabled", True):
        return []
    result: list[ArtGenerationRequest] = []
    arc_id = arc_instance_id(current)
    cue = next((row.get("cue") for row in reversed(current.get("visual_cue_ledger") or [])
                if row.get("action_key") == action_key), None)
    if cue and cue.get("kind") == "npc_first_appearance" and cue.get("fallback"):
        subject_id = str(cue.get("subject_id") or "")
        npc = next((value for key, value in (current.get("npcs") or {}).items()
                    if str(key) == subject_id or str(value.get("name")) == cue.get("subject_name")), None)
        if npc and npc.get("name") and npc.get("known_by_player", True) and npc.get("in_scene", True):
            canonical = str(npc.get("entity_id") or "")
            if not canonical or visual_for("npc", canonical) is None:
                result.append(ArtGenerationRequest(
                    "npc_first_appearance", subject_id, "npc", subject_id, arc_id, action_key))
    before_combat = previous.get("combat") or {}
    combat = current.get("combat") or {}
    new_conflict = combat.get("active") and combat.get("conflict_id") != before_combat.get("conflict_id")
    enemies = current.get("enemies") or []
    boss = next((enemy for enemy in enemies
                 if str(enemy.get("type") or enemy.get("categoria", "")).lower() in {"boss", "chefe"}), None)
    if new_conflict and boss:
        instance = str(combat.get("conflict_id") or hashlib.sha256(action_key.encode()).hexdigest())
        result.append(ArtGenerationRequest(
            "arc_epic_moment", instance, "scene", instance, arc_id, action_key))
    return result
