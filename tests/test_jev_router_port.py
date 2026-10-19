"""SPEC-217 R14: frozen J2 hybrid policy ported behind RPG_JEV_ROUTER_MODE.

* ``off`` is byte-identical to the pre-port router (golden payloads recorded
  from ``agents/router.py`` before the port, ``tests/fixtures/router_off_golden.json``).
* The policy production uses is the frozen J1/J1b code (digests pinned).
* Primary: covered decisions skip CLASSIFY, fallbacks use CLASSIFY, deadline ≤ 1 s,
  gated by an owner-only approval flag.
* Shadow: CLASSIFY decides; agreement metadata only, no player text.
"""

from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

import pytest
from langchain_core.messages import HumanMessage

import agents.router as router_mod
from agents.router import RouterDecision, RouteType, dm_router_node
from services import jev_rollout
from services.jev_decision import ChoiceAnswer, DecisionResult, JevTimeoutError, Usage

GOLDEN = Path(__file__).parent / "fixtures" / "router_off_golden.json"


# ---------------------------------------------------------------------------
# Scenarios (shared with the golden recorder)
# ---------------------------------------------------------------------------

def _base(text: str, **extra: Any) -> dict[str, Any]:
    state: dict[str, Any] = {
        "game_id": "g-spec217-port",
        "messages": [HumanMessage(content=text)] if text else [],
        "world": {"current_location": "Brekmar", "current_location_id": "brekmar",
                  "turn_count": 10},
        "npcs": {
            "Brunna Ponte-Alta": {"name": "Brunna Ponte-Alta", "role": "Barqueira",
                                  "in_scene": True, "home_location_id": "brekmar"},
            "Velha Magda": {"name": "Velha Magda", "role": "Vidente", "in_scene": True,
                            "home_location_id": "brekmar"},
            "Gorim": {"name": "Gorim", "role": "Ferreiro", "in_scene": False,
                      "home_location_id": "skallgard"},
        },
        "party": [],
        "combat": None,
    }
    state.update(extra)
    return state


def scenarios() -> list[tuple[str, dict[str, Any], dict[str, Any] | None]]:
    """(id, state, CLASSIFY decision kwargs | None = CLASSIFY raises)."""
    ended = {"active": False, "phase": "ended", "result": {"outcome": "victory"},
             "outcome": "victory"}
    return [
        ("story", _base("Sigo pela rua"), {"route": "storyteller"}),
        ("npc_named", _base("Brunna, você viu o barco?"),
         {"route": "npc_actor", "target": "Brunna"}),
        ("npc_unknown", _base("Falo com o estranho"), {"route": "npc_actor", "target": "estranho"}),
        ("combat_npc", _base("Ataco a Velha Magda"),
         {"route": "combat_agent", "target": "Velha Magda"}),
        ("combat_free", _base("Ataco o lobo"), {"route": "combat_agent", "target": None}),
        ("combat_regional", _base("Reajo ao barulho"), {"route": "combat_agent", "target": "Lobo"}),
        ("loot_shop", _base("Compro uma corda"), {"route": "loot", "loot_context": "shop"}),
        ("loot_default", _base("Pego a moeda"), {"route": "loot"}),
        ("none", _base("SELECT * FROM users"), {"route": "none"}),
        ("resume_combat", _base("Olho os corpos", combat=ended), {"route": "combat_agent"}),
        ("resume_npc", _base("Falo com a Brunna", combat=ended),
         {"route": "npc_actor", "target": "Brunna"}),
        ("classify_raises", _base("Sigo pela rua"), None),
        ("travel_gate", _base("Viajo para Skallgard"), {"route": "combat_agent"}),
        ("meta_gate", _base("Pergunto ao narrador o que a Velha Magda sente"),
         {"route": "npc_actor", "target": "Velha Magda"}),
        ("combat_active", _base("Corro para a ponte", combat={"active": True, "round": 2}),
         {"route": "storyteller"}),
    ]


class _LLM:
    def __init__(self, decision: dict[str, Any] | None) -> None:
        self.decision = decision
        self.calls = 0

    def with_structured_output(self, *_a: Any, **_k: Any) -> _LLM:
        return self

    def invoke(self, _messages: Any) -> RouterDecision:
        self.calls += 1
        if self.decision is None:
            raise RuntimeError("down")
        return RouterDecision(**{"loot_context": None, "target": None, "reasoning": "fake",
                                 "confidence": 0.9, **self.decision})


def serialize(payload: Any) -> Any:
    """Canonical, comparable view of a router payload (messages -> type/content)."""
    if isinstance(payload, dict):
        return {str(k): serialize(v) for k, v in sorted(payload.items(), key=lambda kv: str(kv[0]))}
    if isinstance(payload, (list, tuple)):
        return [serialize(v) for v in payload]
    if hasattr(payload, "content") and hasattr(payload, "type"):
        return {"type": payload.type, "content": payload.content}
    if isinstance(payload, (str, int, float, bool)) or payload is None:
        return payload
    return repr(payload)


def run_scenario(monkeypatch: pytest.MonkeyPatch, state: dict[str, Any],
                 decision: dict[str, Any] | None) -> tuple[Any, _LLM]:
    llm = _LLM(decision)
    monkeypatch.setattr(router_mod, "get_llm", lambda *a, **k: llm)
    return dm_router_node(state), llm


# ---------------------------------------------------------------------------
# off: byte-identical to the pre-port router
# ---------------------------------------------------------------------------

def test_off_is_byte_identical_to_pre_port_router(monkeypatch: pytest.MonkeyPatch) -> None:
    golden = json.loads(GOLDEN.read_text(encoding="utf-8"))
    monkeypatch.delenv("RPG_JEV_ROUTER_MODE", raising=False)
    started = []
    monkeypatch.setattr(jev_rollout, "_pool", lambda: started.append(1))
    events: list[Any] = []
    jev_rollout.set_jev_rollout_telemetry_hook(events.append)
    try:
        for case_id, state, decision in scenarios():
            payload, llm = run_scenario(monkeypatch, state, decision)
            record = {"payload": serialize(payload), "classify_calls": llm.calls}
            assert json.dumps(record, ensure_ascii=False, sort_keys=True) == json.dumps(
                golden[case_id], ensure_ascii=False, sort_keys=True), case_id
    finally:
        jev_rollout.set_jev_rollout_telemetry_hook(None)
    assert not started and not events
    assert set(golden) == {case_id for case_id, _s, _d in scenarios()}


# ---------------------------------------------------------------------------
# Frozen policy pinned (Astra J2 requirements a, c)
# ---------------------------------------------------------------------------

def test_production_uses_the_frozen_policy_and_calibration() -> None:
    from evals.experiments import jev_router_hybrid as hybrid
    from evals.experiments import spec238_loot as loot

    assert jev_rollout.PRIMARY_CALIBRATION == ("SPEC-217-J2-20261018T134801Z", 0.50)
    assert jev_rollout.POLICY_VARIANT == loot.FROZEN_J1B_POLICY.variant_id
    assert loot.FROZEN_J1B_LOCATION_FEATURES is False
    # One τ in the calibration; the frozen policy uses the same value everywhere.
    tau = jev_rollout.PRIMARY_CALIBRATION[1]
    assert loot.FROZEN_J1B_POLICY.base.tau == loot.FROZEN_J1B_POLICY.loot_tau == tau
    assert loot.FROZEN_J1B_POLICY.base == hybrid.FROZEN_J1_POLICY
    # Recomputed from the code production imports: any edit breaks the freeze.
    assert hybrid.structure_digest(hybrid.FROZEN_J1_POLICY) == (
        "sha256:80225d161ff31f226919c67b34195bdd864d5aece3c5dfc95f411093f3dd10f5")
    assert loot.structure_digest(loot.FROZEN_J1B_POLICY) == (
        "sha256:75635c8994f8a421989653e1383052017feccde024ceaab731da69e739ef2247")
    assert jev_rollout.JEV_DEADLINE_SECONDS <= 1.0


def _scene(text: str = "x") -> dict[str, Any]:
    return _base(text, enemies=[{"id": "mon_lobo_cinzento", "name": "Lobo Cinzento", "hp": 5}])


def test_request_is_the_j2_request_without_location_features() -> None:
    from evals.experiments import spec238_loot as loot

    state = _scene()
    request = jev_rollout.frozen_request(state, "Ataco o lobo")
    expected = loot.frozen_j1b_request({"action": "Ataco o lobo", "state": state})
    assert request.wire_body() == expected.wire_body()
    assert request.state.merchant_here is None and request.state.craft_station is None
    assert sorted(request.questions) == ["loot_source", "route", "target"]


def test_target_id_name_parity_with_map_target_to_id() -> None:
    """Astra J2 requirement b: Jev ID -> router name -> J2 map_target_to_id is identity."""
    from evals.experiments import jev_router_hybrid as hybrid
    from evals.experiments.spec217_j2 import map_target_to_id

    state = _scene()
    actors = hybrid.scene_view(state).actors
    assert {a.id for a in actors} >= {"mon_lobo_cinzento", "npc_velha_magda"}
    for actor in actors:
        name = jev_rollout.target_name_for_id(state, actor.id)
        assert name is not None and map_target_to_id(state, name) == actor.id
    assert jev_rollout.target_name_for_id(state, "npc_velha_magda") == "Velha Magda"
    assert jev_rollout.target_name_for_id(state, "unknown_id") is None
    assert jev_rollout.target_name_for_id(state, None) is None


# ---------------------------------------------------------------------------
# Fake Jev
# ---------------------------------------------------------------------------

class FakeJev:
    def __init__(self, route: str = "storyteller", target: str = "none",
                 loot_source: str = "none", confidence: float = 0.95,
                 error: Exception | None = None, delay: float = 0.0) -> None:
        self.choices = {"route": route, "target": target, "loot_source": loot_source}
        self.confidence = confidence
        self.error = error
        self.delay = delay
        self.calls: list[Any] = []

    def decide(self, request: Any, **kwargs: Any) -> DecisionResult:
        self.calls.append((request, kwargs))
        if self.delay:
            time.sleep(self.delay)
        if self.error:
            raise self.error
        answers = {}
        for name, question in request.questions.items():
            choice = self.choices[name] if self.choices[name] in question.criteria else "none"
            answers[name] = ChoiceAnswer(
                type="choice", choice=choice,
                probabilities={k: float(k == choice) for k in question.criteria},
                confidence=self.confidence)
        return DecisionResult(model="fixture-jev", answers=answers,
                              usage=Usage(input_tokens=10, output_tokens=3),
                              correlation_id="fixture", latency_ms=4)


def _use(monkeypatch: pytest.MonkeyPatch, mode: str, backend: FakeJev,
         approved: bool = True) -> list[Any]:
    monkeypatch.setenv("RPG_JEV_ROUTER_MODE", mode)
    if approved:
        monkeypatch.setenv("RPG_JEV_ROUTER_PRIMARY_APPROVED", "1")
    else:
        monkeypatch.delenv("RPG_JEV_ROUTER_PRIMARY_APPROVED", raising=False)
    monkeypatch.setattr(jev_rollout, "_default_backend", lambda: backend)
    monkeypatch.setattr(jev_rollout, "_jev_switched_off", lambda: False)
    events: list[Any] = []
    jev_rollout.set_jev_rollout_telemetry_hook(events.append)
    _SHADOW_EVENTS.append(events)
    return events


def _run_shadow(monkeypatch: pytest.MonkeyPatch, state: dict[str, Any],
                decision: dict[str, Any] | None, events: list[Any] | None = None,
                ) -> tuple[Any, _LLM]:
    """Shadow observes off the turn's path: wait for its (single) event."""
    sink = events if events is not None else _SHADOW_EVENTS[-1]
    before = len(sink)
    result = run_scenario(monkeypatch, state, decision)
    deadline = time.monotonic() + 3
    while len(sink) == before and time.monotonic() < deadline:
        time.sleep(0.01)
    return result


_SHADOW_EVENTS: list[list[Any]] = []


@pytest.fixture(autouse=True)
def _reset_hook():
    yield
    jev_rollout.set_jev_rollout_telemetry_hook(None)


# ---------------------------------------------------------------------------
# primary
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("text,jev,expected", [
    ("Olho o altar com atenção", {"route": "storyteller"}, {"next": "storyteller"}),
    ("Falo com a Velha Magda", {"route": "npc_actor", "target": "npc_velha_magda"},
     {"next": "npc_actor", "active_npc_name": "Velha Magda"}),
    ("Ataco o lobo", {"route": "combat_agent", "target": "mon_lobo_cinzento"},
     {"next": "combat_agent", "combat_target": "Lobo Cinzento",
      "combat_origin_hint": "player_provoked"}),
    ("Ataco a Velha Magda", {"route": "combat_agent", "target": "npc_velha_magda"},
     {"next": "combat_agent", "combat_target": "Velha Magda",
      "combat_target_ref": "npc:Velha Magda"}),
    ("Compro uma corda", {"route": "loot", "loot_source": "shop"},
     {"next": "loot", "loot_source": "SHOP"}),
    ("Pego a moeda do chão", {"route": "loot", "loot_source": "treasure"},
     {"next": "loot", "loot_source": "TREASURE"}),
])
def test_primary_covered_skips_classify(monkeypatch: pytest.MonkeyPatch, text: str,
                                        jev: dict[str, str], expected: dict[str, Any]) -> None:
    backend = FakeJev(**jev)
    events = _use(monkeypatch, "primary", backend)
    payload, llm = run_scenario(monkeypatch, _scene(text), {"route": "storyteller"})
    assert llm.calls == 0 and len(backend.calls) == 1
    for key, value in expected.items():
        assert payload[key] == value, key
    assert events[-1].outcome == "primary" and events[-1].covered


@pytest.mark.parametrize("text,jev,reason", [
    ("Olho o altar", {"route": "none"}, "abstain"),
    ("Olho o altar", {"route": "storyteller", "confidence": 0.49}, "low_confidence"),
    ("Investo contra o lobo", {"route": "combat_agent", "target": "mon_lobo_cinzento"},
     "combat_guard"),
    ("Olho a moeda", {"route": "loot", "loot_source": "treasure"}, "loot_guard"),
    ("Compro uma corda", {"route": "loot", "loot_source": "none"}, "loot_source_abstain"),
])
def test_primary_fallback_uses_classify(monkeypatch: pytest.MonkeyPatch, text: str,
                                        jev: dict[str, Any], reason: str) -> None:
    backend = FakeJev(**jev)
    events = _use(monkeypatch, "primary", backend)
    payload, llm = run_scenario(monkeypatch, _scene(text),
                                {"route": "combat_agent", "target": "Guarda"})
    assert llm.calls == 1 and payload["next"] == "combat_agent"
    assert events[-1].outcome == "fallback" and events[-1].reason == reason
    assert events[-1].covered is False


def test_primary_requires_owner_approval_flag(monkeypatch: pytest.MonkeyPatch) -> None:
    backend = FakeJev()
    events = _use(monkeypatch, "primary", backend, approved=False)
    _payload, llm = run_scenario(monkeypatch, _scene("Olho o altar"), {"route": "storyteller"})
    assert llm.calls == 1 and not backend.calls
    assert [e.outcome for e in events] == ["approval_required"]
    monkeypatch.setenv("RPG_JEV_ROUTER_PRIMARY_APPROVED", "yes")
    run_scenario(monkeypatch, _scene("Olho o altar"), {"route": "storyteller"})
    assert not backend.calls


def test_primary_uncalibrated_never_calls(monkeypatch: pytest.MonkeyPatch) -> None:
    backend = FakeJev()
    events = _use(monkeypatch, "primary", backend)
    monkeypatch.setattr(jev_rollout, "PRIMARY_CALIBRATION", None)
    _payload, llm = run_scenario(monkeypatch, _scene("Olho o altar"), {"route": "storyteller"})
    assert llm.calls == 1 and not backend.calls
    assert events[-1].outcome == "uncalibrated_threshold"


def test_primary_slow_jev_bounded_by_deadline(monkeypatch: pytest.MonkeyPatch) -> None:
    """Astra J2 risk 3: latency <= deadline + CLASSIFY with a slow backend."""
    monkeypatch.setattr(jev_rollout, "JEV_DEADLINE_SECONDS", 0.2)
    backend = FakeJev(delay=1.5)
    events = _use(monkeypatch, "primary", backend)
    start = time.monotonic()
    payload, llm = run_scenario(monkeypatch, _scene("Olho o altar"), {"route": "storyteller"})
    elapsed = time.monotonic() - start
    assert llm.calls == 1 and payload["next"] == "storyteller"
    assert elapsed < 0.2 + 0.6, elapsed
    assert events[-1].outcome == "timeout"


def test_primary_error_falls_back_without_provider_text(monkeypatch: pytest.MonkeyPatch) -> None:
    backend = FakeJev(error=JevTimeoutError("secret provider text"))
    events = _use(monkeypatch, "primary", backend)
    payload, llm = run_scenario(monkeypatch, _scene("Olho o altar"), {"route": "loot"})
    assert llm.calls == 1 and payload["next"] == "loot"
    assert events[-1].outcome not in {"primary", "covered"}
    assert "secret" not in json.dumps(events[-1].__dict__, default=str)


def test_python_gates_precede_jev(monkeypatch: pytest.MonkeyPatch) -> None:
    backend = FakeJev(route="combat_agent", target="mon_lobo_cinzento")
    _use(monkeypatch, "primary", backend)
    for text in ("Viajo para Skallgard", "Pergunto ao narrador o que a Velha Magda sente"):
        run_scenario(monkeypatch, _scene(text), {"route": "storyteller"})
    active = _scene("Ataco o lobo")
    active["combat"] = {"active": True, "round": 1}
    run_scenario(monkeypatch, active, {"route": "storyteller"})
    assert not backend.calls


def test_kill_switch_returns_to_classify(monkeypatch: pytest.MonkeyPatch) -> None:
    backend = FakeJev()
    events = _use(monkeypatch, "shadow", backend)
    monkeypatch.setattr(jev_rollout, "_jev_switched_off", lambda: True)
    _payload, llm = run_scenario(monkeypatch, _scene("Olho o altar"), {"route": "storyteller"})
    assert llm.calls == 1 and not backend.calls
    assert events[-1].outcome == "kill_switch"


# ---------------------------------------------------------------------------
# shadow
# ---------------------------------------------------------------------------

def test_shadow_keeps_classify_and_logs_agreement_without_text(
        monkeypatch: pytest.MonkeyPatch) -> None:
    backend = FakeJev(route="npc_actor", target="npc_velha_magda")
    events = _use(monkeypatch, "shadow", backend, approved=False)
    state = _scene("Falo com a Velha Magda sobre o rio")
    payload, llm = _run_shadow(monkeypatch, state, {"route": "npc_actor", "target": "Magda"})
    assert llm.calls == 1 and len(backend.calls) == 1
    assert payload["next"] == "npc_actor"
    event = events[-1]
    assert event.mode == "shadow" and event.outcome == "covered" and event.covered
    assert event.classify_route == "npc_actor" and event.jev_route == "npc_actor"
    assert event.agree_route is True and event.agree_target is True and event.agree_loot is None
    dumped = json.dumps(event.__dict__, ensure_ascii=False, default=str)
    assert "Magda" not in dumped and "rio" not in dumped


def test_shadow_disagreement_and_combat(monkeypatch: pytest.MonkeyPatch) -> None:
    backend = FakeJev(route="combat_agent", target="mon_lobo_cinzento")
    events = _use(monkeypatch, "shadow", backend)
    payload, _llm = _run_shadow(monkeypatch, _scene("Ataco o lobo"),
                                 {"route": "combat_agent", "target": "Velha Magda"})
    assert payload["combat_target"] == "Velha Magda"
    assert events[-1].agree_route is True and events[-1].agree_target is False
    payload, _llm = _run_shadow(monkeypatch, _scene("Ataco o lobo"), {"route": "storyteller"})
    assert payload["next"] == "storyteller"
    assert events[-1].agree_route is False and events[-1].jev_route == "combat_agent"


def test_shadow_loot_agreement(monkeypatch: pytest.MonkeyPatch) -> None:
    backend = FakeJev(route="loot", loot_source="shop")
    events = _use(monkeypatch, "shadow", backend)
    _run_shadow(monkeypatch, _scene("Compro uma corda"),
                 {"route": "loot", "loot_context": "SHOP"})
    assert events[-1].agree_loot is True
    _run_shadow(monkeypatch, _scene("Compro uma corda"), {"route": "loot"})
    assert events[-1].agree_loot is False


def test_shadow_slow_jev_never_delays_the_turn(monkeypatch: pytest.MonkeyPatch) -> None:
    """Astra R14 review: shadow does not wait for the Jev at all (not even up to the deadline)."""
    monkeypatch.setattr(jev_rollout, "JEV_DEADLINE_SECONDS", 0.2)
    backend = FakeJev(delay=0.6)
    events = _use(monkeypatch, "shadow", backend)
    start = time.monotonic()
    payload, llm = run_scenario(monkeypatch, _scene("Olho o altar"), {"route": "loot"})
    assert time.monotonic() - start < 0.15
    assert payload["next"] == "loot" and llm.calls == 1
    assert not events  # observation still pending
    deadline = time.monotonic() + 3
    while not events and time.monotonic() < deadline:
        time.sleep(0.02)
    assert events[-1].outcome == "timeout" and events[-1].covered is False
    assert events[-1].wait_ms == 0 and events[-1].classify_route == "loot"


def test_shadow_late_jev_within_deadline_is_still_observed(
        monkeypatch: pytest.MonkeyPatch) -> None:
    """CLASSIFY faster than the Jev: the late (in-deadline) answer is compared, no wait."""
    backend = FakeJev(route="loot", loot_source="shop", delay=0.3)
    events = _use(monkeypatch, "shadow", backend)
    start = time.monotonic()
    run_scenario(monkeypatch, _scene("Compro uma corda"),
                 {"route": "loot", "loot_context": "SHOP"})
    assert time.monotonic() - start < 0.2
    deadline = time.monotonic() + 3
    while not events and time.monotonic() < deadline:
        time.sleep(0.02)
    assert events[-1].outcome == "covered" and events[-1].agree_loot is True
    assert events[-1].wait_ms == 0


def test_primary_unmapped_target_falls_back(monkeypatch: pytest.MonkeyPatch) -> None:
    """Astra R14 review (6): a Jev actor ID the router cannot name never routes."""
    backend = FakeJev(route="npc_actor", target="npc_velha_magda")
    events = _use(monkeypatch, "primary", backend)
    monkeypatch.setattr(jev_rollout, "target_name_for_id", lambda *_a, **_k: None)
    payload, llm = run_scenario(monkeypatch, _scene("Falo com a Velha Magda"),
                                {"route": "storyteller"})
    assert llm.calls == 1 and len(backend.calls) == 1  # CLASSIFY decided this turn
    assert payload.get("interlocutor_reason") != "jev"
    assert events[-1].outcome == "fallback" and events[-1].reason == "target_unmapped"
    assert events[-1].covered is False


def test_missing_key_falls_back_to_classify(monkeypatch: pytest.MonkeyPatch) -> None:
    """No TypeSafe key: configuration error -> CLASSIFY, no network, no retry."""
    import services.jev_decision as jd

    monkeypatch.setenv("RPG_JEV_ROUTER_MODE", "primary")
    monkeypatch.setenv("RPG_JEV_ROUTER_PRIMARY_APPROVED", "1")
    for name in ("TYPESAFE_API_KEY", "JEVMODEL_API_KEY", "JEV_API_KEY"):
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setattr(jd, "load_dotenv", lambda *a, **k: False)
    monkeypatch.setattr(jev_rollout, "_jev_switched_off", lambda: False)
    # Isolation (flaked under xdist as "timeout"): the shared httpx client (SSL context,
    # slow on a loaded box) and the module pool (may hold other tests' work) are built
    # inside the 1 s deadline. Neither matters here: the missing key raises before any
    # request. Placeholder client + private pool keep only the key check on the clock.
    from concurrent.futures import ThreadPoolExecutor
    pool = ThreadPoolExecutor(max_workers=1)
    monkeypatch.setattr(jev_rollout, "_client", object())
    monkeypatch.setattr(jev_rollout, "_pool", lambda: pool)
    events: list[Any] = []
    jev_rollout.set_jev_rollout_telemetry_hook(events.append)
    try:
        payload, llm = run_scenario(monkeypatch, _scene("Olho o altar"), {"route": "loot"})
    finally:
        jev_rollout.set_jev_rollout_telemetry_hook(None)
        pool.shutdown(wait=True)
    assert llm.calls == 1 and payload["next"] == "loot"
    assert events[-1].outcome == "configuration"


def test_frozen_policy_import_is_outside_the_deadline(monkeypatch: pytest.MonkeyPatch) -> None:
    """Cold imports run before the deadline clock starts (was the flaky timeout)."""
    order: list[str] = []
    real_frozen, real_monotonic = jev_rollout._frozen, jev_rollout.time.monotonic

    def frozen() -> Any:
        order.append("frozen")
        return real_frozen()

    class _Clock:
        def monotonic(self) -> float:
            order.append("clock")
            return real_monotonic()

    monkeypatch.setenv("RPG_JEV_ROUTER_MODE", "shadow")
    monkeypatch.setattr(jev_rollout, "_jev_switched_off", lambda: False)
    monkeypatch.setattr(jev_rollout, "_frozen", frozen)
    monkeypatch.setattr(jev_rollout, "time", _Clock())
    jev_rollout.begin(_scene("Olho o altar"), "Olho o altar", backend=FakeJev(route="storyteller"))
    assert order[:2] == ["frozen", "clock"]


def test_more_python_gates_precede_jev(monkeypatch: pytest.MonkeyPatch) -> None:
    """Explicit rest, scene description and an empty action never reach the Jev."""
    backend = FakeJev(route="combat_agent", target="mon_lobo_cinzento")
    _use(monkeypatch, "primary", backend)
    for text in ("Descanso aqui", "Descrevo a cena", "O que vejo ao redor?"):
        run_scenario(monkeypatch, _scene(text), {"route": "storyteller"})
    empty = _scene("")
    run_scenario(monkeypatch, empty, {"route": "storyteller"})
    assert not backend.calls


def test_shadow_classify_failure_still_observed(monkeypatch: pytest.MonkeyPatch) -> None:
    backend = FakeJev(route="storyteller")
    events = _use(monkeypatch, "shadow", backend)
    payload, _llm = _run_shadow(monkeypatch, _scene("Olho o altar"), None)
    assert payload["interlocutor_reason"] == "classify_fallback"
    assert events[-1].classify_route == "storyteller" and events[-1].agree_route is True


def test_shadow_does_not_mutate_state(monkeypatch: pytest.MonkeyPatch) -> None:
    from copy import deepcopy

    backend = FakeJev(route="npc_actor", target="npc_velha_magda")
    events = _use(monkeypatch, "shadow", backend)
    state = _scene("Falo com a Velha Magda")
    original = deepcopy(state)
    _run_shadow(monkeypatch, state, {"route": "npc_actor", "target": "Velha Magda"},
                events=events)
    assert state == original
