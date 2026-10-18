"""Opt-in Jev routing: shadow observation and guarded primary (SPEC-180, SPEC-217 R14).

Jev is a decision backend, not a chat model. ``RPG_JEV_ROUTER_MODE`` defaults to
``off``: nothing here runs, no thread, no network, no telemetry.

The decision policy is the one frozen and measured by SPEC-217 J2 (run
``SPEC-217-J2-20261018T134801Z``, GO by R9, Astra APPROVED):
``plain+target+guard@0.50+lootsrc+lguard@0.50`` with location features OFF and
the verb lexicon unchanged. The policy code is *imported* from the frozen
experiment modules (``evals/experiments/jev_router_hybrid.py`` and
``spec238_loot.py``) instead of copied, so production sends exactly the request
the J2 measured and decides with exactly its code; their structure digests are
pinned in ``tests/test_jev_rollout.py``.

* ``shadow``: CLASSIFY decides. The Jev runs in parallel with it, bounded by a
  short deadline, and only its agreement with the router's effective payload is
  logged (labels, booleans and latencies; never player text or names).
* ``primary``: requires, besides this code-frozen calibration, the owner-only
  approval flag ``RPG_JEV_ROUTER_PRIMARY_APPROVED=1`` (setting it in any
  environment needs a separate, explicit owner approval; see SPEC-217 R15).
  A covered decision skips CLASSIFY; any fallback (abstain, low confidence,
  guard, unrepresentable target, error, timeout, kill switch) uses CLASSIFY in
  the same turn. Python gates in ``agents/router.py`` always run first.
"""

from __future__ import annotations

from concurrent.futures import Future, ThreadPoolExecutor
from concurrent.futures import TimeoutError as FutureTimeout
from dataclasses import dataclass
import hashlib
import os
import threading
import time
from collections.abc import Callable, Mapping
from typing import Any, Literal, cast

from services.jev_decision import (
    ChoiceAnswer, DecisionBackend, JevDecisionBackend, JevError,
)


RolloutMode = Literal["off", "shadow", "primary"]

# SPEC-217 R14: frozen by the J2 confirmatory run (GO by the pre-registered R9,
# Astra J2 review APPROVED). τ applies to route, target and loot source alike;
# the frozen policy objects carry the same 0.50 (asserted in tests).
PRIMARY_CALIBRATION: tuple[str, float] | None = ("SPEC-217-J2-20261018T134801Z", 0.50)
POLICY_VARIANT = "plain+target+guard@0.50+lootsrc+lguard@0.50"
# Astra J2 risk 3: the J2 used a 10 s timeout; production stays short so a
# degraded Jev costs at most this much before CLASSIFY (observed max 352 ms).
JEV_DEADLINE_SECONDS = 1.0
# Owner-only: setting this in any environment needs a separate approval.
APPROVAL_ENV = "RPG_JEV_ROUTER_PRIMARY_APPROVED"


@dataclass(frozen=True)
class JevRouting:
    """A covered Jev decision in the router's own vocabulary."""

    route: str  # storyteller | combat_agent | npc_actor | loot
    target_id: str | None
    loot_source: str | None  # TREASURE | SHOP | CRAFT (route loot only)
    confidence: float


@dataclass(frozen=True)
class JevRolloutEvent:
    """Safe metadata only: labels, booleans, latencies. No prompt, text or key."""

    mode: RolloutMode
    outcome: str
    model: str | None
    latency_ms: int
    input_tokens: int | None
    output_tokens: int | None
    cost_usd: float | None
    choice: str | None = None
    confidence: float | None = None
    reason: str | None = None          # fallback reason of the frozen policy
    covered: bool | None = None        # the Jev would decide this turn
    jev_route: str | None = None       # effective route if the Jev decided
    classify_route: str | None = None  # effective route the router returned
    agree_route: bool | None = None
    agree_target: bool | None = None
    agree_loot: bool | None = None
    wait_ms: int | None = None         # wall time the turn waited for the Jev


_telemetry_hook: Callable[[JevRolloutEvent], None] | None = None


def set_jev_rollout_telemetry_hook(
    hook: Callable[[JevRolloutEvent], None] | None,
) -> None:
    global _telemetry_hook
    _telemetry_hook = hook


def _emit(event: JevRolloutEvent) -> None:
    try:
        from observability.telemetry import log_event
        log_event("jev", event.mode, level="info", **{
            key: value for key, value in event.__dict__.items()
            if key != "mode" and value is not None
        })
    except Exception:
        pass
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


def _idempotency_key(state: Mapping[str, object], action: str) -> str:
    # Stable across a retry of the same turn; no player text appears in headers.
    world = state.get("world") or {}
    turn = world.get("turn_count", "") if isinstance(world, Mapping) else ""
    basis = f"{state.get('game_id', '')}|{turn}|{action}"
    return "rpg-router-" + hashlib.sha256(basis.encode("utf-8")).hexdigest()[:40]


def _jev_switched_off() -> bool:
    try:
        from services.kill_switches import JEV, get_switches
        return not get_switches().is_enabled(JEV)
    except Exception:
        return False


# ---------------------------------------------------------------------------
# Frozen policy (imported, never copied)
# ---------------------------------------------------------------------------

def _frozen() -> tuple[Any, Any]:
    """Lazy import: keeps ``off`` free of the experiment modules."""
    from evals.experiments import jev_router_hybrid as hybrid
    from evals.experiments import spec238_loot as loot
    return hybrid, loot


def frozen_request(state: Mapping[str, Any], action: str) -> Any:
    """The exact J2 arm-B request (route + target + loot_source, location off)."""
    _hybrid, loot = _frozen()
    return loot.frozen_j1b_request({"action": action, "state": state})


def frozen_decision(state: Mapping[str, Any], action: str,
                    answers: Mapping[str, Mapping[str, Any]]) -> dict[str, Any]:
    """The J2 arm-B decision for these answers (route/target/loot_source)."""
    hybrid, loot = _frozen()
    view = hybrid.scene_view(state)
    return loot.frozen_loot_decision(
        route=answers.get("route"), target=answers.get("target"),
        loot_source=answers.get("loot_source"), verbs=hybrid.extract_verbs(action),
        in_combat=bool((state.get("combat") or {}).get("active")),
        target_status=view.target_status,
    )


def target_name_for_id(state: Mapping[str, Any], actor_id: str | None) -> str | None:
    """Jev scene-actor ID -> the name ``dm_router_node`` writes as a target.

    NPC: its ``state["npcs"]`` key (what ``active_npc_name`` holds), else the
    party member name; enemy: its display name. Inverse of the J2
    ``map_target_to_id`` on every visible actor (parity-tested).
    """
    if not actor_id:
        return None
    from services.entity_identity import resolve_npc_entity_id
    for key, row in (state.get("npcs") or {}).items():
        if isinstance(row, dict) and (
                resolve_npc_entity_id(row, key) or str(row.get("id") or "")) == actor_id:
            return str(key)
    for member in state.get("party") or []:
        if isinstance(member, dict) and member.get("name") and (
                resolve_npc_entity_id(member, member["name"])
                or str(member.get("id") or "")) == actor_id:
            return str(member["name"])
    for enemy in state.get("enemies") or []:
        if isinstance(enemy, dict) and str(enemy.get("id") or "") == actor_id:
            return str(enemy.get("name") or actor_id)
    return None


def target_id_for_name(state: Mapping[str, Any], name: str | None) -> str | None:
    """Router target name -> scene actor ID (the J2 ``map_target_to_id``)."""
    from evals.experiments.spec217_j2 import map_target_to_id
    return map_target_to_id(state, name)


# ---------------------------------------------------------------------------
# Execution
# ---------------------------------------------------------------------------

_executor: ThreadPoolExecutor | None = None
_client: Any = None
_lock = threading.Lock()


def _pool() -> ThreadPoolExecutor:
    global _executor
    with _lock:
        if _executor is None:
            _executor = ThreadPoolExecutor(max_workers=4, thread_name_prefix="jev-router")
        return _executor


def _default_backend() -> DecisionBackend:
    """Shared HTTP client (connection reuse); a cheap adapter per call."""
    global _client
    import httpx
    with _lock:
        if _client is None:
            _client = httpx.Client()
    return JevDecisionBackend(
        client=_client, timeout_seconds=JEV_DEADLINE_SECONDS,
        total_timeout_seconds=JEV_DEADLINE_SECONDS, max_retries=0,
    )


@dataclass
class _Evaluation:
    outcome: str
    decision: dict[str, Any] | None = None
    model: str | None = None
    input_tokens: int | None = None
    output_tokens: int | None = None
    cost_usd: float | None = None
    choice: str | None = None
    confidence: float | None = None
    latency_ms: int = 0


def _evaluate(state: Mapping[str, Any], action: str, backend: DecisionBackend | None,
              key: str) -> _Evaluation:
    start = time.monotonic()
    result = _Evaluation(outcome="error")
    try:
        request = frozen_request(state, action)
        decided = (backend or _default_backend()).decide(request, idempotency_key=key)
        result.model = decided.model
        if decided.usage is not None:
            result.input_tokens = decided.usage.input_tokens
            result.output_tokens = decided.usage.output_tokens
        result.cost_usd = decided.cost_usd
        answers: dict[str, dict[str, Any]] = {}
        for name, answer in decided.answers.items():
            if isinstance(answer, ChoiceAnswer):
                answers[name] = {"choice": answer.choice, "confidence": answer.confidence}
        route = answers.get("route")
        if route is not None:
            result.choice, result.confidence = route["choice"], route["confidence"]
        if set(request.questions) - set(answers):
            result.outcome = "invalid_answer"
        else:
            result.decision = frozen_decision(state, action, answers)
            result.outcome = "covered" if result.decision["source"] == "jev" else "fallback"
    except Exception as exc:
        # Error/timeout/configuration all fall back. Never log provider text.
        result.outcome = exc.code if isinstance(exc, JevError) else "error"
    result.latency_ms = round((time.monotonic() - start) * 1000)
    return result


class JevPending:
    """One turn's Jev evaluation, started before (primary) or alongside (shadow) CLASSIFY."""

    def __init__(self, mode: RolloutMode, future: Future, started: float) -> None:
        self.mode = mode
        self._future = future
        self._started = started
        self._waited_ms = 0

    def _result(self) -> _Evaluation:
        remaining = max(0.0, self._started + JEV_DEADLINE_SECONDS - time.monotonic())
        before = time.monotonic()
        try:
            evaluation = self._future.result(timeout=remaining)
        except FutureTimeout:
            evaluation = _Evaluation(outcome="timeout",
                                     latency_ms=round(JEV_DEADLINE_SECONDS * 1000))
        except Exception:
            evaluation = _Evaluation(outcome="error")
        self._waited_ms = round((time.monotonic() - before) * 1000)
        return evaluation

    def _event(self, evaluation: _Evaluation, **extra: Any) -> JevRolloutEvent:
        decision = evaluation.decision or {}
        outcome = extra.pop("outcome", evaluation.outcome)
        return JevRolloutEvent(
            self.mode, outcome, evaluation.model, evaluation.latency_ms,
            evaluation.input_tokens, evaluation.output_tokens, evaluation.cost_usd,
            evaluation.choice, evaluation.confidence,
            reason=decision.get("reason"), covered=decision.get("source") == "jev",
            wait_ms=self._waited_ms, **extra,
        )

    def primary_routing(self) -> JevRouting | None:
        """Primary: the covered decision, or ``None`` to use CLASSIFY now."""
        evaluation = self._result()
        decision = evaluation.decision
        if evaluation.outcome != "covered" or not decision:
            _emit(self._event(evaluation))
            return None
        routing = JevRouting(decision["route"], decision["target"], decision["loot_source"],
                             float(evaluation.confidence or 0.0))
        _emit(self._event(evaluation, outcome="primary", jev_route=routing.route))
        return routing

    def observe(self, effective: Mapping[str, Any],
                as_payload: Callable[[JevRouting], Mapping[str, Any]],
                state: Mapping[str, Any]) -> None:
        """Shadow: compare what primary would return with the effective payload."""
        try:
            evaluation = self._result()
            decision = evaluation.decision
            extra: dict[str, Any] = {"classify_route": str(effective.get("next") or "")}
            if evaluation.outcome == "covered" and decision:
                routing = JevRouting(decision["route"], decision["target"],
                                     decision["loot_source"], float(evaluation.confidence or 0.0))
                try:
                    extra.update(_agreement(state, effective, as_payload(routing)))
                except Exception:
                    extra["jev_route"] = routing.route  # agreement unavailable, keep the observation
            _emit(self._event(evaluation, **extra))
        except Exception:
            pass  # shadow never affects the turn


def _agreement(state: Mapping[str, Any], effective: Mapping[str, Any],
               jev: Mapping[str, Any]) -> dict[str, Any]:
    route_a, route_b = effective.get("next"), jev.get("next")
    same_route = route_a == route_b
    if route_b == "npc_actor":
        agree_target: bool | None = same_route and (
            effective.get("active_npc_name") == jev.get("active_npc_name"))
    elif route_b == "combat_agent":
        try:
            agree_target = same_route and (
                target_id_for_name(state, effective.get("combat_target"))
                == target_id_for_name(state, jev.get("combat_target")))
        except Exception:
            agree_target = None
    else:
        agree_target = None
    agree_loot = (same_route and effective.get("loot_source") == jev.get("loot_source")
                  if route_b == "loot" else None)
    return {"jev_route": str(route_b or ""), "agree_route": same_route,
            "agree_target": agree_target, "agree_loot": agree_loot}


def begin(state: Mapping[str, Any], action: str, *,
          backend: DecisionBackend | None = None) -> JevPending | None:
    """Start this turn's Jev evaluation, or ``None`` (off/kill switch/not approved).

    ``off`` returns before touching anything else (byte-identical router).
    """
    mode = rollout_mode()
    if mode == "off":
        return None
    if _jev_switched_off():  # SPEC-196: operator kill switch decision_backend:jev
        _emit(JevRolloutEvent(mode, "kill_switch", None, 0, None, None, None))
        return None
    if mode == "primary" and os.getenv(APPROVAL_ENV) != "1":
        _emit(JevRolloutEvent(mode, "approval_required", None, 0, None, None, None))
        return None
    if mode == "primary" and _threshold() is None:
        _emit(JevRolloutEvent(mode, "uncalibrated_threshold", None, 0, None, None, None))
        return None
    key = _idempotency_key(state, action)
    started = time.monotonic()
    future = _pool().submit(_evaluate, dict(state), action, backend, key)
    return JevPending(mode, future, started)
