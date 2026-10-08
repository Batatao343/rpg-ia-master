"""A API registra requests/falhas de provider sem expor conteúdo."""

import api
import pytest
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
                         llm_attempts=attempts,
                         embedding_attempts=[{
                             "provider": "jina", "model": "jina-embeddings-v3",
                             "outcome": "response", "network_attempted": True,
                             "usage": {"input_tokens": 17},
                         }])
    assert len(captured["usage_events"]) == 3
    assert captured["llm_cost_usd"] == sum(
        (event.cost_usd for event in captured["usage_events"]), Decimal("0"))
    assert captured["llm_cost_usd"] == Decimal("1.000345000")
    assert state["_storage_version"] == 2
    assert "Texto privado" not in repr(captured["usage_events"])


def test_failed_api_turn_forwards_billable_attempts_to_failed_operation(monkeypatch):
    from fastapi import HTTPException
    import rag
    from services import turn_execution
    from infrastructure import runtime

    operation_id, game_id, owner_id = uuid4(), uuid4(), uuid4()
    claim = OperationClaim(operation_id, uuid4(), game_id, 1, "b" * 64)
    captured = {}

    class Coordinator:
        def fail(self, _claim, _error_code, *, usage_events=()):
            captured["events"] = list(usage_events)

    def graph_failure(_graph, _state, *, progress=None):
        rag._emit_embedding_attempt("jina", "jina-embeddings-v3", "response",
                                    {"prompt_tokens": 17})
        api._attempt_telemetry_hook(LLMAttemptEvent(
            provider="groq", model="openai/gpt-oss-20b", tier=ModelTier.FAST,
            attempt_index=0, latency_ms=10, fell_back=False,
            outcome="invoke_error", error="SECRET_PROVIDER_PROMPT",
            structured=False, usage={"input_tokens": 100, "output_tokens": 10},
        ))
        raise RuntimeError("graph failed")

    monkeypatch.setattr(turn_execution, "execute_graph", graph_failure)
    monkeypatch.setattr(runtime, "get_runtime", lambda: SimpleNamespace(
        turn_coordinator=Coordinator()))
    monkeypatch.setattr(api, "_log_turn", lambda *_args, **_kwargs: None)
    state = {"game_id": str(game_id), "messages": [], "world": {"turn_count": 0}}
    with pytest.raises(HTTPException) as exc, principal_scope(
        Principal(owner_id, "test", str(owner_id), local=True)):
        api._run_turn(state, "ação", claim=claim, request_hash="b" * 64)
    assert exc.value.status_code == 500
    assert len(captured["events"]) == 2
    assert captured["events"][0].component == f"llm:{claim.lease_token}"
    assert captured["events"][1].component == f"embedding:{claim.lease_token}"
    assert captured["events"][1].input_units == 17
    assert "SECRET" not in repr(captured["events"])


def test_auxiliary_prologue_collects_llm_usage_without_response_text(monkeypatch):
    from infrastructure import runtime

    owner_id = uuid4()
    principal = Principal(owner_id, "test", str(owner_id), local=True)
    captured = {}

    class Coordinator:
        def claim(self, _principal, operation_id, **kwargs):
            assert kwargs["kind"] == "prologue"
            return OperationClaim(operation_id, uuid4(), None, None,
                                  kwargs["request_hash"])

        def complete(self, _claim, **kwargs):
            captured.update(kwargs)

    monkeypatch.setattr(api, "_database_profile", lambda: True)
    monkeypatch.setattr(runtime, "get_runtime", lambda: SimpleNamespace(
        turn_coordinator=Coordinator()))
    with principal_scope(principal), api._meter_auxiliary_operation("prologue"):
        api._attempt_telemetry_hook(LLMAttemptEvent(
            provider="groq", model="openai/gpt-oss-20b", tier=ModelTier.SMART,
            attempt_index=0, latency_ms=9, fell_back=False, outcome="success",
            error=None, structured=True,
            usage={"input_tokens": 100, "output_tokens": 20},
        ))
    assert len(captured["usage_events"]) == 1
    assert captured["receipt"] == {"status": "completed"}
    assert "prologue text" not in repr(captured)


def test_failed_new_game_records_player_creation_attempt(monkeypatch):
    from infrastructure import runtime

    claim = OperationClaim(uuid4(), uuid4(), None, None, "a" * 64)
    captured = {}

    class Coordinator:
        def fail(self, _claim, _code, *, usage_events=()):
            captured["events"] = list(usage_events)

    def fail_create(_req, _claim):
        api._attempt_telemetry_hook(LLMAttemptEvent(
            provider="groq", model="openai/gpt-oss-20b", tier=ModelTier.SMART,
            attempt_index=0, latency_ms=9, fell_back=False,
            outcome="invoke_error", error="private input", structured=True,
            usage={"input_tokens": 25, "output_tokens": 3},
        ))
        raise RuntimeError("creation failed")

    monkeypatch.setattr(api, "_begin_create_operation",
                        lambda _req: (claim, "a" * 64, None))
    monkeypatch.setattr(api, "_create_game", fail_create)
    monkeypatch.setattr(runtime, "get_runtime", lambda: SimpleNamespace(
        turn_coordinator=Coordinator()))
    with pytest.raises(RuntimeError):
        api.new_game(SimpleNamespace())
    assert len(captured["events"]) == 1
    assert captured["events"][0].component == f"llm:{claim.lease_token}"
    assert "private input" not in repr(captured)
