"""SPEC-180: reversible routing, fail-closed fallback and shadow isolation."""

from __future__ import annotations

from copy import deepcopy

from langchain_core.messages import HumanMessage
import pytest

from agents import router
from services import jev_rollout
from services.jev_decision import ChoiceAnswer, DecisionResult, Usage


class Backend:
    def __init__(self, choice: str = "storyteller", confidence: float = 0.95,
                 error: Exception | None = None) -> None:
        self.choice = choice
        self.confidence = confidence
        self.error = error
        self.calls = []
        self.closed = False

    def decide(self, request, **kwargs):
        self.calls.append((request, kwargs))
        if self.error:
            raise self.error
        probabilities = {key: (1.0 if key == self.choice else 0.0)
                         for key in jev_rollout._QUESTION.criteria}
        return DecisionResult(
            model="fixture-jev", answers={"route": ChoiceAnswer(
                type="choice", choice=self.choice, probabilities=probabilities,
                confidence=self.confidence,
            )},
            usage=Usage(input_tokens=10, output_tokens=2),
            correlation_id="fixture", latency_ms=4,
        )

    def close(self):
        self.closed = True


def state():
    return {
        "game_id": "game-1", "world": {"turn_count": 3, "current_location": "Vila"},
        "messages": [HumanMessage(content="Olho o altar")],
        "combat": {"active": False},
    }


def test_off_and_invalid_config_never_call_backend(monkeypatch: pytest.MonkeyPatch) -> None:
    backend = Backend()
    for mode in ("off", "typo"):
        monkeypatch.setenv("RPG_JEV_ROUTER_MODE", mode)
        assert jev_rollout.decide_route(state(), "Olho o altar", backend=backend) is None
    assert not backend.calls


def test_shadow_observes_but_keeps_baseline_route_and_state(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("RPG_JEV_ROUTER_MODE", "shadow")
    backend = Backend(choice="combat_agent")
    backend_settings = []

    def build_backend(**kwargs):
        backend_settings.append(kwargs)
        return backend

    monkeypatch.setattr(jev_rollout, "JevDecisionBackend", build_backend)
    baseline = router.RouterDecision(
        route=router.RouteType.NPC, loot_context=None, target=None,
        reasoning="fixture", confidence=0.9,
    )

    class LLM:
        def with_structured_output(self, _schema):
            return self

        def invoke(self, _messages):
            return baseline.model_copy(deep=True)

    monkeypatch.setattr(router, "get_llm", lambda **_kwargs: LLM())
    before = state()
    original = deepcopy(before)
    observed = []
    jev_rollout.set_jev_rollout_telemetry_hook(observed.append)
    try:
        result = router.dm_router_node(before)
    finally:
        jev_rollout.set_jev_rollout_telemetry_hook(None)
    assert result["next"] == "npc_actor"
    assert before == original
    assert len(backend.calls) == 1
    assert backend.closed
    assert backend_settings[0]["total_timeout_seconds"] == 2.0
    assert backend_settings[0]["max_retries"] == 0
    assert observed[0].outcome == "observed"
    assert observed[0].choice == "combat_agent"
    assert observed[0].confidence == 0.95
    assert observed[0].input_tokens == 10
    assert not hasattr(observed[0], "action")


def test_primary_requires_approval_and_threshold(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("RPG_JEV_ROUTER_MODE", "primary")
    monkeypatch.setenv("RPG_JEV_ROUTER_MIN_CONFIDENCE", "0.0")
    backend = Backend()
    assert jev_rollout.decide_route(state(), "Olho o altar", backend=backend) is None
    monkeypatch.setenv("RPG_JEV_ROUTER_PRIMARY_APPROVED", "1")
    assert jev_rollout.decide_route(state(), "Olho o altar", backend=backend) is None
    assert not backend.calls


def test_primary_threshold_unrepresentable_error_and_idempotency(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("RPG_JEV_ROUTER_MODE", "primary")
    monkeypatch.setenv("RPG_JEV_ROUTER_PRIMARY_APPROVED", "1")
    monkeypatch.setattr(jev_rollout, "PRIMARY_CALIBRATION", ("future-reviewed-evidence", 0.9))
    s = state()
    original = deepcopy(s)
    events = []
    jev_rollout.set_jev_rollout_telemetry_hook(events.append)
    try:
        low = Backend(confidence=0.8)
        assert jev_rollout.decide_route(s, "Olho o altar", backend=low) is None
        dynamic = Backend(choice="loot")
        assert jev_rollout.decide_route(s, "Olho o altar", backend=dynamic) is None
        broken = Backend(error=TimeoutError("timeout with secret content"))
        assert jev_rollout.decide_route(s, "Olho o altar", backend=broken) is None
        good = Backend()
        assert jev_rollout.decide_route(s, "Olho o altar", backend=good) == "storyteller"
        assert jev_rollout.decide_route(s, "Olho o altar", backend=good) == "storyteller"
    finally:
        jev_rollout.set_jev_rollout_telemetry_hook(None)
    assert [e.outcome for e in events] == [
        "low_confidence", "payload_unrepresentable", "error", "primary", "primary",
    ]
    assert good.calls[0][1]["idempotency_key"] == good.calls[1][1]["idempotency_key"]
    assert good.calls[0][0].state.model_dump() == {
        "action": "Olho o altar", "location_id": "Vila",
        "in_combat": False, "active_npc": None,
    }
    assert s == original


def test_python_gate_precedes_jev_and_rollback_uses_baseline(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("RPG_JEV_ROUTER_MODE", "primary")
    monkeypatch.setenv("RPG_JEV_ROUTER_PRIMARY_APPROVED", "1")
    monkeypatch.setattr(jev_rollout, "PRIMARY_CALIBRATION", ("future-reviewed-evidence", 0.9))
    backend = Backend()
    monkeypatch.setattr(jev_rollout, "JevDecisionBackend", lambda **_kwargs: backend)
    travel = state()
    travel["messages"] = [HumanMessage(content="Viajo para o norte")]
    assert router.dm_router_node(travel)["next"] == "storyteller"
    assert not backend.calls

    monkeypatch.setenv("RPG_JEV_ROUTER_MODE", "off")
    assert jev_rollout.decide_route(state(), "Olho o altar", backend=backend) is None
    assert not backend.calls


def test_router_primary_candidate_and_error_fallback(monkeypatch: pytest.MonkeyPatch) -> None:
    """Exercise integration under a simulated future approved calibration."""
    monkeypatch.setenv("RPG_JEV_ROUTER_MODE", "primary")
    monkeypatch.setenv("RPG_JEV_ROUTER_PRIMARY_APPROVED", "1")
    monkeypatch.setattr(jev_rollout, "PRIMARY_CALIBRATION", ("future-reviewed-evidence", 0.9))
    backend = Backend()
    monkeypatch.setattr(jev_rollout, "JevDecisionBackend", lambda **_kwargs: backend)

    def forbidden_llm(**_kwargs):
        raise AssertionError("CLASSIFY called on accepted primary STORY")

    monkeypatch.setattr(router, "get_llm", forbidden_llm)
    assert router.dm_router_node(state())["next"] == "storyteller"
    assert len(backend.calls) == 1

    backend.error = TimeoutError("provider timeout")
    baseline = router.RouterDecision(
        route=router.RouteType.COMBAT, loot_context=None, target="Guarda",
        reasoning="fixture", confidence=0.9,
    )

    class LLM:
        def with_structured_output(self, _schema):
            return self

        def invoke(self, _messages):
            return baseline.model_copy(deep=True)

    monkeypatch.setattr(router, "get_llm", lambda **_kwargs: LLM())
    assert router.dm_router_node(state())["next"] == "combat_agent"
    assert len(backend.calls) == 2


def test_question_contract_matches_frozen_ab() -> None:
    from evals.experiments.jev_router_ab import QUESTION

    assert jev_rollout._QUESTION.model_dump() == QUESTION.model_dump()
