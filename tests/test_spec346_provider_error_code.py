"""SPEC-346 R27: o codigo de erro do provider entra na telemetria (nunca a mensagem)."""

import pytest

import llm_setup


class _FakeBadRequest(Exception):
    status_code = 400

    def __init__(self, body):
        super().__init__("bad request")
        self.body = body


def test_attempt_records_groq_error_code():
    body = {"error": {"code": "tool_use_failed", "message": "PROMPT-SECRETO do jogador"}}
    exc = _FakeBadRequest(body)
    assert llm_setup._http_status(exc) == 400
    assert llm_setup._provider_error_code(exc) == "tool_use_failed"


def test_attempt_event_carries_code_without_message(monkeypatch):
    captured = []
    import observability.telemetry as tel

    monkeypatch.setattr(tel, "log_event", lambda *a, **k: captured.append((a, k)))
    exc = _FakeBadRequest({"error": {"code": "tool_use_failed", "message": "PROMPT-SECRETO"}})
    llm_setup._log_attempt(
        "groq",
        "openai/gpt-oss-20b",
        llm_setup.ModelTier.CLASSIFY,
        0,
        "invoke_error",
        error=type(exc).__name__,
        http_status=400,
        provider_error_code=llm_setup._provider_error_code(exc),
    )
    (_, kw) = captured[0]
    assert kw["provider_error_code"] == "tool_use_failed"
    assert kw["http_status"] == 400
    assert "PROMPT-SECRETO" not in repr(captured)


@pytest.mark.parametrize("code", ["has space", "<script>", "", 7, None])
def test_error_code_rejects_non_ident(code):
    assert llm_setup._provider_error_code(_FakeBadRequest({"error": {"code": code}})) is None


def test_error_code_without_body_is_none():
    assert llm_setup._provider_error_code(RuntimeError("x")) is None


def test_groq_tool_use_failed_is_semantic_retry(monkeypatch):
    from pydantic import BaseModel

    calls = {"n": 0}

    class Small(BaseModel):
        value: str

    class Fake:
        def with_structured_output(self, *_a, **_k):
            return self

        def invoke(self, _input):
            calls["n"] += 1
            if calls["n"] == 1:
                raise _FakeBadRequest({"error": {"code": "tool_use_failed", "message": "x"}})
            return {"raw": None, "parsed": Small(value="ok"), "parsing_error": None}

    events = []
    monkeypatch.setattr(llm_setup, "_get_cached_client", lambda *_a: Fake())
    monkeypatch.setattr(llm_setup, "_ATTEMPT_TELEMETRY_HOOK", events.append)
    out = (
        llm_setup.RoutedLLM(llm_setup.ModelTier.CLASSIFY, 0, [("groq", "m1"), ("gemini", "m2")])
        .with_structured_output(Small)
        .invoke("prompt")
    )
    assert out.value == "ok"
    assert calls["n"] == 2
    assert [e.provider for e in events] == ["groq", "groq"]
    assert events[0].structured_failure_code == "provider_tool_use_failed"
    assert events[0].provider_error_code == "tool_use_failed"


def test_other_400_stays_transport(monkeypatch):
    from pydantic import BaseModel

    class Small(BaseModel):
        value: str

    calls = {"n": 0}

    class Fake:
        def with_structured_output(self, *_a, **_k):
            return self

        def invoke(self, _input):
            calls["n"] += 1
            raise _FakeBadRequest({"error": {"code": "invalid_request_error"}})

    monkeypatch.setattr(llm_setup, "_get_cached_client", lambda *_a: Fake())
    llm_setup.RoutedLLM(llm_setup.ModelTier.CLASSIFY, 0, [("groq", "m1")]).with_structured_output(
        Small
    ).invoke("prompt")
    assert calls["n"] == 1
