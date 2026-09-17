"""Canonical actor lifecycle and action eligibility (pure Python)."""
from __future__ import annotations

import re
import copy
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


class TransitionReadiness(TypedDict):
    ready: bool
    code: str
    phase: str


_ORPHAN_PHASES = {
    ActorPhase.LAST_STAND,
    ActorPhase.TERMINAL,
    ActorPhase.DEAD,
}


_RECOVERY = re.compile(
    r"\b(?:descans|repous|recuper|trat|socorr|ajud|aguard[^.]{0,20}(?:acord|socorr))",
    re.IGNORECASE,
)


def classify_actor(state: dict) -> ActorPhase:
    player = state.get("player") or {}
    if state.get("game_over"):
        return ActorPhase.DEAD
    if state.get("death_pending"):
        return ActorPhase.DEATH_PENDING
    if player.get("dead"):
        return ActorPhase.DEAD
    if player.get("estado_terminal"):
        return ActorPhase.TERMINAL
    if player.get("last_stand_pending"):
        return ActorPhase.LAST_STAND
    if player.get("incapacitated"):
        return ActorPhase.INCAPACITATED
    if not player.get("conscious", True):
        return ActorPhase.UNCONSCIOUS
    return ActorPhase.ACTIVE


def transition_readiness(state: dict) -> TransitionReadiness:
    """Classify whether a state is safe to resume as a new playable turn.

    Critical transitions have an explicit owner (combat or the death-choice
    flow). They may be returned to a client, but they must never become a
    playable checkpoint with that owner absent.
    """
    if (state.get("combat") or {}).get("active"):
        return {"ready": False, "code": "combat_active", "phase": "combat"}
    phase = classify_actor(state)
    if phase in {
        ActorPhase.LAST_STAND,
        ActorPhase.TERMINAL,
        ActorPhase.DEATH_PENDING,
        ActorPhase.DEAD,
    }:
        return {
            "ready": False,
            "code": f"transition_{phase.value}",
            "phase": phase.value,
        }
    return {"ready": True, "code": "ready", "phase": phase.value}


def sanitize_interturn_state(state: dict) -> dict:
    """Repair only legacy/restored snapshots that lost their transition owner.

    This is deliberately not used inside a live combat. It closes ephemeral
    death-flow flags while preserving wounds; a critically wounded protagonist
    therefore returns unconscious and must use the normal recovery path.
    """
    clean = copy.deepcopy(state)
    player = dict(clean.get("player") or {})
    player["last_stand_pending"] = False
    player["last_stand_resolved"] = False
    player["estado_terminal"] = False
    player["dead"] = False
    player["incapacitated"] = False
    wounds = player.get("ferimentos") or {}
    has_critical_wound = bool(wounds.get("critico"))
    player["conscious"] = not has_critical_wound
    # Old checkpoints sometimes encoded the transient combat marker ``dead``
    # with zero vitality but no wound explaining an unconscious recovery. A
    # restored, conscious actor must have a minimally playable pool; genuine
    # critical wounds remain at zero and follow the recovery action contract.
    if not has_critical_wound and int(player.get("vitalidade", 0) or 0) <= 0:
        player["vitalidade"] = 1
        if "hp" in player:
            player["hp"] = 1
    clean["player"] = player
    clean["death_pending"] = False
    clean["game_over"] = False
    return clean


def orphan_transition(state: dict) -> TransitionReadiness | None:
    """Return an ownerless critical transition that the guard may repair.

    Live combat, the death-choice screen and memorial mode are explicit owners;
    repairing any of those here would skip gameplay. Only legacy/corrupt state
    that reached a request boundary without an owner is eligible.
    """
    if (
        (state.get("combat") or {}).get("active")
        or state.get("death_pending")
        or state.get("game_over")
    ):
        return None
    phase = classify_actor(state)
    if phase not in _ORPHAN_PHASES:
        return None
    return {"ready": False, "code": f"transition_{phase.value}", "phase": phase.value}


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
