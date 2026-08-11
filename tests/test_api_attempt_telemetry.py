"""A API registra requests/falhas de provider sem expor conteúdo."""

import api
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
