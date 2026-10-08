"""SPEC-182: RoutedLLM emits usage once per provider attempt without content."""

from __future__ import annotations

from langchain_core.messages import AIMessage, AIMessageChunk
from pydantic import BaseModel

import llm_setup


class SmallAnswer(BaseModel):
    value: str


def test_plain_invoke_captures_only_usage_metadata(monkeypatch) -> None:
    class FakeClient:
        def invoke(self, _input):
            return AIMessage(
                content="SECRET_NARRATIVE",
                usage_metadata={"input_tokens": 100, "output_tokens": 20,
                                "total_tokens": 120,
                                "input_token_details": {"cache_read": 30}},
            )

    events = []
    monkeypatch.setattr(llm_setup, "_get_cached_client", lambda *_args: FakeClient())
    monkeypatch.setattr(llm_setup, "_ATTEMPT_TELEMETRY_HOOK", events.append)
    llm_setup.RoutedLLM(llm_setup.ModelTier.FAST, 0, [("usage-test", "model")]).invoke("prompt")
    assert len(events) == 1
    assert events[0].usage == {
        "input_tokens": 100, "output_tokens": 20, "cached_tokens": 30,
    }
    assert "SECRET_NARRATIVE" not in repr(events[0])


def test_structured_result_preserves_raw_usage_across_parsing(monkeypatch) -> None:
    class FakeClient:
        def with_structured_output(self, _schema, **_kwargs):
            return self

        def invoke(self, _input):
            return {
                "raw": AIMessage(content="SECRET_RAW", usage_metadata={
                    "input_tokens": 60, "output_tokens": 10, "total_tokens": 70,
                }),
                "parsed": SmallAnswer(value="ok"), "parsing_error": None,
            }

    events = []
    monkeypatch.setattr(llm_setup, "_get_cached_client", lambda *_args: FakeClient())
    monkeypatch.setattr(llm_setup, "_ATTEMPT_TELEMETRY_HOOK", events.append)
    answer = llm_setup.RoutedLLM(
        llm_setup.ModelTier.CLASSIFY, 0, [("usage-test", "model")],
    ).with_structured_output(SmallAnswer).invoke("prompt")
    assert answer.value == "ok"
    assert events[0].usage == {"input_tokens": 60, "output_tokens": 10}
    assert "SECRET_RAW" not in repr(events[0])


def test_stream_final_usage_is_emitted_once(monkeypatch) -> None:
    class FakeClient:
        def stream(self, _input):
            yield AIMessageChunk(content="SECRET_PART_1")
            yield AIMessageChunk(content="SECRET_PART_2")
            yield AIMessageChunk(content="", usage_metadata={
                "input_tokens": 90, "output_tokens": 25, "total_tokens": 115,
            })

    events = []
    monkeypatch.setattr(llm_setup, "_get_cached_client", lambda *_args: FakeClient())
    monkeypatch.setattr(llm_setup, "_ATTEMPT_TELEMETRY_HOOK", events.append)
    list(llm_setup.RoutedLLM(
        llm_setup.ModelTier.FAST, 0, [("usage-test", "model")],
    ).stream("prompt"))
    assert len(events) == 1
    assert events[0].usage == {"input_tokens": 90, "output_tokens": 25}
    assert "SECRET_PART" not in repr(events[0])


def test_provider_cache_units_survive_langchain_usage_metadata(monkeypatch) -> None:
    class FakeClient:
        def invoke(self, _input):
            return AIMessage(
                content="SECRET_NARRATIVE",
                usage_metadata={"input_tokens": 200, "output_tokens": 10,
                                "total_tokens": 210},
                response_metadata={"token_usage": {"prompt_cache_hit_tokens": 75}},
            )

    events = []
    monkeypatch.setattr(llm_setup, "_get_cached_client", lambda *_args: FakeClient())
    monkeypatch.setattr(llm_setup, "_ATTEMPT_TELEMETRY_HOOK", events.append)
    llm_setup.RoutedLLM(llm_setup.ModelTier.FAST, 0, [("usage-test", "model")]).invoke("prompt")
    assert events[0].usage == {
        "input_tokens": 200, "output_tokens": 10, "cached_tokens": 75,
    }


def test_closed_stream_still_emits_one_attempt_without_content(monkeypatch) -> None:
    class FakeClient:
        def stream(self, _input):
            yield AIMessageChunk(content="SECRET_FIRST_CHUNK")
            yield AIMessageChunk(content="SECRET_NOT_CONSUMED")

    events = []
    monkeypatch.setattr(llm_setup, "_get_cached_client", lambda *_args: FakeClient())
    monkeypatch.setattr(llm_setup, "_ATTEMPT_TELEMETRY_HOOK", events.append)
    stream = llm_setup.RoutedLLM(
        llm_setup.ModelTier.FAST, 0, [("usage-test", "model")],
    ).stream("prompt")
    assert next(stream).content == "SECRET_FIRST_CHUNK"
    stream.close()
    assert len(events) == 1
    assert events[0].outcome == "stream_error"
    assert events[0].error == "consumer_closed"
    assert "SECRET" not in repr(events[0])
