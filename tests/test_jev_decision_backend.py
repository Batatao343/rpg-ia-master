"""Offline contract tests for SPEC-177; no key or provider traffic needed."""

from __future__ import annotations

import json
import threading
import time
from pathlib import Path

import httpx
import pytest
from pydantic import ValidationError

from services.jev_decision import (
    ChoiceAnswer,
    ChoiceQuestion,
    DecisionRequest,
    DecisionState,
    JevAuthenticationError,
    JevConfigurationError,
    JevCreditsError,
    JevDecisionBackend,
    JevRateLimitError,
    JevResponseError,
    JevTimeoutError,
    JevTransportError,
    JevUpstreamError,
    JevValidationError,
    NoulAnswer,
    NoulQuestion,
    ScoreAnswer,
    ScoreQuestion,
)


FIXTURE = json.loads(
    (Path(__file__).parent / "fixtures" / "jev_decision_success.json").read_text(encoding="utf-8")
)


@pytest.fixture(autouse=True)
def clear_jev_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("services.jev_decision.load_dotenv", lambda **_: False)
    monkeypatch.delenv("JEVMODEL_API_KEY", raising=False)
    monkeypatch.delenv("JEV_API_KEY", raising=False)


def _request() -> DecisionRequest:
    return DecisionRequest(
        state=DecisionState(
            action="Conversar com a capitã.",
            location_id="porto",
            active_npc="capita",
        ),
        questions={
            "route": ChoiceQuestion(
                instructions="Qual rota?",
                criteria={"story": "Cena", "npc": "Conversa"},
            ),
            "urgent": NoulQuestion(instructions="Precisa de atenção imediata?"),
            "danger": ScoreQuestion(instructions="Qual o perigo?", criteria=["baixo", "médio", "alto"]),
        },
    )


def test_success_is_typed_and_sends_only_minimal_state() -> None:
    sent: list[httpx.Request] = []
    events = []

    def handler(request: httpx.Request) -> httpx.Response:
        sent.append(request)
        return httpx.Response(200, json=FIXTURE)

    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        backend = JevDecisionBackend(api_key="test-secret", client=client, telemetry_hook=events.append)
        result = backend.decide(_request(), idempotency_key="turn-17", correlation_id="trace-17")

    assert isinstance(result.answers["route"], ChoiceAnswer)
    assert isinstance(result.answers["urgent"], NoulAnswer)
    assert isinstance(result.answers["danger"], ScoreAnswer)
    assert result.answers["route"].choice == "npc"
    assert result.usage.input_tokens == 136
    assert result.model == "jev-latest"
    assert sent[0].url == "https://jevmodel.org/v1/systemone"
    assert sent[0].headers["authorization"] == "Bearer test-secret"
    assert sent[0].headers["idempotency-key"] == "turn-17"
    body = json.loads(sent[0].content)
    assert set(body) == {"model", "state", "questions"}
    assert set(body["state"]) == {"action", "location_id", "in_combat", "active_npc"}
    assert "test-secret" not in sent[0].content.decode()
    assert "test-secret" not in repr(events)
    assert "Conversar" not in repr(events)
    assert events[0].correlation_id == "trace-17"
    assert events[0].input_tokens == 136
    assert events[0].cost_usd is None  # The endpoint reports usage, not per-call cost.


@pytest.mark.parametrize(
    ("status", "error_type", "attempts"),
    [
        (401, JevAuthenticationError, 1),
        (402, JevCreditsError, 1),
        (422, JevValidationError, 1),
        (429, JevRateLimitError, 2),
        (500, JevUpstreamError, 1),
        (502, JevUpstreamError, 2),
    ],
)
def test_http_failures_are_typed_and_only_documented_statuses_retry(
    status: int, error_type: type[Exception], attempts: int
) -> None:
    keys: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        keys.append(request.headers["idempotency-key"])
        return httpx.Response(status, json={"error": {"message": "private state", "type": "error"}})

    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        backend = JevDecisionBackend(api_key="test-secret", client=client, sleep=lambda _: None)
        with pytest.raises(error_type) as caught:
            backend.decide(_request(), idempotency_key="same-logical-turn")

    assert len(keys) == attempts
    assert set(keys) == {"same-logical-turn"}
    assert "private state" not in str(caught.value)


def test_timeout_is_terminal_and_does_not_leak_request() -> None:
    calls = 0

    def handler(_request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        raise httpx.ReadTimeout("private state")

    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        backend = JevDecisionBackend(api_key="test-secret", client=client)
        with pytest.raises(JevTimeoutError) as caught:
            backend.decide(_request())
    assert calls == 1
    assert "private state" not in str(caught.value)


def test_total_deadline_rejects_slow_success() -> None:
    def handler(_request: httpx.Request) -> httpx.Response:
        time.sleep(0.2)
        return httpx.Response(200, json=FIXTURE)

    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        backend = JevDecisionBackend(
            api_key="test-secret", client=client, timeout_seconds=1, total_timeout_seconds=0.02
        )
        start = time.monotonic()
        with pytest.raises(JevTimeoutError):
            backend.decide(_request())
        assert time.monotonic() - start < 0.15


def test_total_deadline_covers_response_parsing() -> None:
    class SlowJsonResponse(httpx.Response):
        def json(self, **kwargs):
            time.sleep(0.2)
            return FIXTURE

    with httpx.Client(transport=httpx.MockTransport(lambda _: SlowJsonResponse(200))) as client:
        backend = JevDecisionBackend(
            api_key="test-secret", client=client, timeout_seconds=1, total_timeout_seconds=0.02
        )
        start = time.monotonic()
        with pytest.raises(JevTimeoutError):
            backend.decide(_request())
        assert time.monotonic() - start < 0.15


def test_timed_out_worker_is_quarantined_and_close_blocks_new_calls() -> None:
    release = threading.Event()
    entered = threading.Event()
    calls = 0

    def handler(_request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        entered.set()
        release.wait(timeout=1)
        return httpx.Response(200, json=FIXTURE)

    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        backend = JevDecisionBackend(
            api_key="test-secret", client=client, timeout_seconds=1, total_timeout_seconds=0.02
        )
        try:
            with pytest.raises(JevTimeoutError):
                backend.decide(_request())
            assert entered.is_set()
            for _ in range(3):
                with pytest.raises(JevTransportError, match="still active"):
                    backend.decide(_request())
            assert calls == 1
            backend.close()
            with pytest.raises(JevTransportError, match="closed"):
                backend.decide(_request())
        finally:
            release.set()
            for _ in range(100):
                if not backend._inflight.locked():
                    break
                time.sleep(0.01)
        assert not backend._inflight.locked()


@pytest.mark.parametrize(
    "mutate",
    [
        lambda body: body["answers"]["route"].update(choice="invented"),
        lambda body: body["answers"]["urgent"].update(noul=1.1),
        lambda body: body["answers"]["danger"].update(score=99),
        lambda body: body["answers"].pop("route"),
        lambda body: body.update(model=""),
        lambda body: body["answers"]["urgent"].update(noul=True),
        lambda body: body["usage"].update(input_tokens="136"),
        lambda body: body["usage"].update(output_tokens=True),
    ],
)
def test_incompatible_200_never_becomes_a_decision(mutate) -> None:
    body = json.loads(json.dumps(FIXTURE))
    mutate(body)
    with httpx.Client(transport=httpx.MockTransport(lambda _: httpx.Response(200, json=body))) as client:
        backend = JevDecisionBackend(api_key="test-secret", client=client)
        with pytest.raises(JevResponseError):
            backend.decide(_request())


def test_request_budget_and_closed_state_are_enforced_before_transport() -> None:
    with pytest.raises(ValidationError):
        DecisionState(action="olhar", player={"gold": 999, "secret": "x"})
    with pytest.raises(ValidationError):
        ChoiceQuestion(instructions="Rota?", criteria={str(i): "label" for i in range(21)})
    with pytest.raises(ValidationError):
        ScoreQuestion(instructions="Risco?", criteria=["x"])
    with pytest.raises(ValidationError):
        DecisionRequest(
            state=DecisionState(action="olhar"),
            questions={f"q{i}": NoulQuestion(instructions="Sim?") for i in range(9)},
        )


def test_mutated_request_is_revalidated_and_retry_body_is_stable() -> None:
    request = _request()
    request.questions.update(
        {f"extra_{i}": NoulQuestion(instructions="Sim?") for i in range(8)}
    )
    with httpx.Client(transport=httpx.MockTransport(lambda _: pytest.fail("network called"))) as client:
        backend = JevDecisionBackend(api_key="test-secret", client=client)
        with pytest.raises(ValidationError):
            backend.decide(request)

    request = _request()
    sent_bodies: list[dict] = []

    def handler(http_request: httpx.Request) -> httpx.Response:
        sent_bodies.append(json.loads(http_request.content))
        if len(sent_bodies) == 1:
            request.questions["route"].criteria["injected"] = "late mutation"
            return httpx.Response(502)
        return httpx.Response(200, json=FIXTURE)

    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        backend = JevDecisionBackend(api_key="test-secret", client=client, sleep=lambda _: None)
        result = backend.decide(request)
    assert result.answers["route"].choice == "npc"
    assert sent_bodies[0] == sent_bodies[1]
    assert "injected" not in sent_bodies[1]["questions"]["route"]["criteria"]


def test_key_migration_and_conflicting_variables_fail_closed(monkeypatch: pytest.MonkeyPatch) -> None:
    with pytest.raises(JevConfigurationError, match="JEVMODEL_API_KEY"):
        JevDecisionBackend()
    monkeypatch.setenv("JEV_API_KEY", "legacy-secret")
    with pytest.raises(JevConfigurationError, match="Rename"):
        JevDecisionBackend()
    monkeypatch.setenv("JEVMODEL_API_KEY", "different-secret")
    with pytest.raises(JevConfigurationError, match="Conflicting"):
        JevDecisionBackend()
