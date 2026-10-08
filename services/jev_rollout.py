"""Opt-in Jev routing observation and guarded rollout (SPEC-180).

Jev is a decision backend, not a chat model. The default is ``off`` because
the SPEC-178 paired run contains uncovered regressions. This module sends only
the narrow DecisionState DTO and never mutates GameState.
"""

from __future__ import annotations

import hashlib
import os
import time
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from typing import Literal, cast

from services.jev_decision import (
    ChoiceAnswer, ChoiceQuestion, DecisionBackend, DecisionRequest,
    DecisionState, JevDecisionBackend, JevError,
)


RolloutMode = Literal["off", "shadow", "primary"]
_ROUTES = frozenset({"storyteller", "combat_agent", "npc_actor", "loot", "none"})
_QUESTION = ChoiceQuestion(
    instructions=(
        "Classifique a intenção da última ação do jogador de RPG. Escolha uma rota. "
        "COMBAT para atacar, sacar arma ou reagir a ameaça; NPC para conversa social; "
        "LOOT para vasculhar, pegar, comprar, vender ou criar; STORY para movimento, "
        "exploração e observação. Escolha none se não houver intenção clara."
    ),
    criteria={
        "storyteller": "Movimentação, exploração ou observar o cenário",
        "combat_agent": "Atacar, sacar arma ou reagir a ameaça",
        "npc_actor": "Conversa social ou diplomacia",
        "loot": "Vasculhar, pegar item, comprar, vender ou criar",
        "none": "Nenhuma intenção clara",
    },
)
# SPEC-178/179 produced NO_GO. A later, separate eval-authoring/promotion task
# must set a reviewed (evidence id, threshold) pair before primary can decide.
PRIMARY_CALIBRATION: tuple[str, float] | None = None


@dataclass(frozen=True)
class JevRolloutEvent:
    """Safe metadata for the SPEC-182 usage metering hook; no prompt or key."""

    mode: RolloutMode
    outcome: str
    model: str | None
    latency_ms: int
    input_tokens: int | None
    output_tokens: int | None
    cost_usd: float | None
    choice: str | None = None
    confidence: float | None = None


_telemetry_hook: Callable[[JevRolloutEvent], None] | None = None


def set_jev_rollout_telemetry_hook(
    hook: Callable[[JevRolloutEvent], None] | None,
) -> None:
    global _telemetry_hook
    _telemetry_hook = hook


def _emit(event: JevRolloutEvent) -> None:
    if _telemetry_hook is not None:
        try:
            _telemetry_hook(event)
        except Exception:
            pass


def rollout_mode() -> RolloutMode:
    value = os.getenv("RPG_JEV_ROUTER_MODE", "off").strip().lower()
    return cast(RolloutMode, value) if value in {"off", "shadow", "primary"} else "off"


def _threshold() -> float | None:
    if PRIMARY_CALIBRATION is None:
        return None
    evidence_id, value = PRIMARY_CALIBRATION
    return value if evidence_id and 0 <= value <= 1 else None


def _request(state: Mapping[str, object], action: str) -> DecisionRequest:
    world = state.get("world") or {}
    if not isinstance(world, Mapping):
        world = {}
    combat = state.get("combat") or {}
    if not isinstance(combat, Mapping):
        combat = {}
    return DecisionRequest(
        state=DecisionState(
            action=action,
            location_id=str(world.get("current_location") or "Aethelgard"),
            in_combat=bool(combat.get("active")),
            active_npc=(str(state["active_npc_name"])
                        if state.get("active_npc_name") else None),
        ),
        questions={"route": _QUESTION},
    )


def _idempotency_key(state: Mapping[str, object], action: str) -> str:
    # Stable across a retry of the same turn; no player text appears in headers.
    world = state.get("world") or {}
    turn = world.get("turn_count", "") if isinstance(world, Mapping) else ""
    basis = f"{state.get('game_id', '')}|{turn}|{action}"
    return "rpg-router-" + hashlib.sha256(basis.encode("utf-8")).hexdigest()[:40]


def decide_route(
    state: Mapping[str, object],
    action: str,
    *,
    backend: DecisionBackend | None = None,
) -> str | None:
    """Return a primary Jev route or ``None`` to use the current CLASSIFY.

    Shadow observes only. Primary is inert until an operator explicitly sets
    both the approval flag and a code-frozen, reviewed confidence threshold. The current
    production RouterDecision also needs free-form target/loot fields, so only
    STORY/NONE can be represented without changing that contract.
    """
    mode = rollout_mode()
    if mode == "off":
        return None
    if mode == "primary" and os.getenv("RPG_JEV_ROUTER_PRIMARY_APPROVED") != "1":
        _emit(JevRolloutEvent(mode, "approval_required", None, 0, None, None, None))
        return None
    threshold = _threshold() if mode == "primary" else None
    if mode == "primary" and threshold is None:
        _emit(JevRolloutEvent(mode, "uncalibrated_threshold", None, 0, None, None, None))
        return None

    start = time.monotonic()
    owned = backend is None
    model: str | None = None
    input_tokens: int | None = None
    output_tokens: int | None = None
    cost_usd: float | None = None
    choice: str | None = None
    confidence: float | None = None
    outcome = "error"
    route: str | None = None
    try:
        request = _request(state, action)
        if backend is None:
            # Shadow is synchronous in this graph: bound its latency impact.
            limit = 2.0 if mode == "shadow" else 8.0
            backend = JevDecisionBackend(
                timeout_seconds=limit, total_timeout_seconds=limit,
                max_retries=0,
            )
        result = backend.decide(request, idempotency_key=_idempotency_key(state, action))
        model = result.model
        if result.usage is not None:
            input_tokens = result.usage.input_tokens
            output_tokens = result.usage.output_tokens
        cost_usd = result.cost_usd
        answer = result.answers.get("route")
        if not isinstance(answer, ChoiceAnswer) or answer.choice not in _ROUTES:
            outcome = "invalid_answer"
        else:
            choice = answer.choice
            confidence = answer.confidence
            if mode == "shadow":
                outcome = "observed"
            elif threshold is not None and answer.confidence < threshold:
                outcome = "low_confidence"
            elif answer.choice not in {"storyteller", "none"}:
                outcome = "payload_unrepresentable"
            else:
                route = "storyteller"
                outcome = "primary"
    except Exception as exc:
        # Error/timeout/configuration all fall back. Do not log provider text,
        # which could contain request details or a credential.
        outcome = exc.code if isinstance(exc, JevError) else "error"
    finally:
        if owned and backend is not None:
            try:
                close = getattr(backend, "close", None)
                if callable(close):
                    close()
            except Exception:
                pass
        _emit(JevRolloutEvent(
            mode, outcome, model, round((time.monotonic() - start) * 1000),
            input_tokens, output_tokens, cost_usd, choice, confidence,
        ))
    return route
