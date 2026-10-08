"""A API registra requests/falhas de provider sem expor conteúdo."""

import api
from decimal import Decimal
from types import SimpleNamespace
from uuid import uuid4

from infrastructure.contracts import OperationClaim, Principal
from infrastructure.request_context import principal_scope
from llm_setup import LLMAttemptEvent, ModelTier


def test_api_log_fields_include_failed_network_attempt():
    success_token = api._llm_turn_events.set([])
    attempt_token = api._llm_attempt_events.set([])
    try:
        api._attempt_telemetry_hook(LLMAttemptEvent(
            provider="deepseek",
            model="deepseek-v4-flash",
            tier=ModelTier.FAST,
            attempt_index=0,
            latency_ms=12,
            fell_back=False,
            outcome="invoke_error",
            error="timeout",
            structured=False,
        ))
        api._attempt_telemetry_hook(LLMAttemptEvent(
            provider="groq",
            model="llama-3.3-70b-versatile",
            tier=ModelTier.FAST,
            attempt_index=1,
            latency_ms=20,
            fell_back=True,
            outcome="success",
            error=None,
            structured=False,
        ))
        api._telemetry_hook(
            "groq", "llama-3.3-70b-versatile", ModelTier.FAST, 20, True)
        fields = api._llm_log_fields(
            api._llm_turn_events.get(), api._llm_attempt_events.get())
    finally:
        api._llm_turn_events.reset(success_token)
        api._llm_attempt_events.reset(attempt_token)

    assert fields["llm_calls"] == 1
    assert fields["llm_requests"] == 2
    assert fields["llm_attempts"] == 2
    assert fields["llm_failures"] == 1
    assert fields["llm_attempt_outcomes"] == {
        "invoke_error": 1, "success": 1}
    assert fields["fell_back"] is True
    assert fields["cost_usd_est"] > 0


def test_api_commit_passes_one_normalized_consolidate_for_all_attempts(monkeypatch):
    operation_id, game_id, owner_id = uuid4(), uuid4(), uuid4()
    principal = Principal(owner_id, "test", str(owner_id), local=True)
    claim = OperationClaim(operation_id, uuid4(), game_id, 1, "a" * 64)
    captured = {}

    class Coordinator:
        def commit_game(self, _principal, _claim, _state, **kwargs):
            captured.update(kwargs)
            return 2, {"committed_version": 2}

    from infrastructure import runtime

    monkeypatch.setattr(runtime, "get_runtime", lambda: SimpleNamespace(
        turn_coordinator=Coordinator()))
    monkeypatch.setattr(api, "_schedule_chronicle_jobs", lambda _state: None)
    response = api.GameResponse.model_construct(game_id=str(game_id), message="Texto privado")
    state = {"game_id": str(game_id), "messages": [], "world": {"turn_count": 1}}
    attempts = [
        {"provider": "groq", "model": "openai/gpt-oss-20b", "outcome": "invalid_structured",
         "network_attempted": True, "usage": {"input_tokens": 1000, "output_tokens": 100}},
        {"provider": "groq", "model": "openai/gpt-oss-120b", "outcome": "success",
         "network_attempted": True, "usage": {"input_tokens": 800, "output_tokens": 200}},
    ]
    with principal_scope(principal):
        api._commit_turn(state, response, claim=claim, request_hash="a" * 64,
                         checkpoint=False, latency_ms=100, llm_events=[],
                         llm_attempts=attempts)
    assert len(captured["usage_events"]) == 2
    assert captured["llm_cost_usd"] == sum(
        (event.cost_usd for event in captured["usage_events"]), Decimal("0"))
    assert captured["llm_cost_usd"] == Decimal("0.000345000")
    assert state["_storage_version"] == 2
    assert "Texto privado" not in repr(captured["usage_events"])
