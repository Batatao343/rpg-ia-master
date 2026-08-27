"""Canonical actor lifecycle and action eligibility (pure Python)."""
from __future__ import annotations

import re
from enum import StrEnum
from typing import Literal, TypedDict


class ActorPhase(StrEnum):
    ACTIVE = "active"
    UNCONSCIOUS = "unconscious"
    INCAPACITATED = "incapacitated"
    LAST_STAND = "last_stand"
    TERMINAL = "terminal"
    DEATH_PENDING = "death_pending"
    DEAD = "dead"


class ActionEligibility(TypedDict):
    phase: str
    allowed: bool
    code: str
    action_kind: Literal["normal", "recovery", "none"]
    message: str


_RECOVERY = re.compile(
    r"\b(?:descans|repous|recuper|trat|socorr|ajud|aguard[^.]{0,20}(?:acord|socorr))",
    re.IGNORECASE,
)


def classify_actor(state: dict) -> ActorPhase:
    player = state.get("player") or {}
    if state.get("game_over") or player.get("dead"):
        return ActorPhase.DEAD
    if state.get("death_pending"):
        return ActorPhase.DEATH_PENDING
    if player.get("estado_terminal"):
        return ActorPhase.TERMINAL
    if player.get("last_stand_pending"):
        return ActorPhase.LAST_STAND
    if player.get("incapacitated"):
        return ActorPhase.INCAPACITATED
    if not player.get("conscious", True):
        return ActorPhase.UNCONSCIOUS
    return ActorPhase.ACTIVE


def evaluate_action(state: dict, action: str) -> ActionEligibility:
    phase = classify_actor(state)
    if (state.get("combat") or {}).get("active"):
        return {"phase": phase.value, "allowed": True, "code": "combat_resolution",
                "action_kind": "normal", "message": ""}
    if phase == ActorPhase.ACTIVE:
        return {"phase": phase.value, "allowed": True, "code": "ok",
                "action_kind": "normal", "message": ""}
    if phase == ActorPhase.UNCONSCIOUS and _RECOVERY.search(str(action or "")):
        return {"phase": phase.value, "allowed": True, "code": "recovery_requested",
                "action_kind": "recovery", "message": ""}
    messages = {
        ActorPhase.UNCONSCIOUS: (
            "Você está inconsciente. Declare descanso, tratamento ou aguarde socorro; "
            "ações de viagem, conversa, saque e combate não são possíveis agora."
        ),
        ActorPhase.INCAPACITATED: "Você está incapacitado e precisa de ajuda ou recuperação.",
        ActorPhase.LAST_STAND: "A Última Ação precisa ser resolvida antes de qualquer outra ação.",
        ActorPhase.TERMINAL: "O Estado Terminal precisa ser resolvido antes de qualquer outra ação.",
        ActorPhase.DEATH_PENDING: "Escolha continuar do checkpoint ou aceitar o fim.",
        ActorPhase.DEAD: "Esta campanha terminou e permanece como memorial.",
    }
    return {"phase": phase.value, "allowed": False, "code": f"blocked_{phase.value}",
            "action_kind": "none", "message": messages[phase]}
