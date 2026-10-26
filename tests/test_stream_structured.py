"""SPEC-319 R2/R4/R9: `stream_structured` + `narrate_structured` (sink, guard, fallback)."""

from __future__ import annotations

import random

import pytest
from langchain_core.messages import AIMessage, HumanMessage

import llm_setup
from agents.storyteller import StoryUpdate
from mock_llm import MockLLM
from services import narrative_sink as sink
from tests.spec319_helpers import FakeStreamClient, install, routed, slices, tool_args


@pytest.fixture(autouse=True)
def _env(monkeypatch):
    monkeypatch.delenv("RPG_FORCE_MOCK", raising=False)
    monkeypatch.delenv("RPG_LLM_HEDGE_MS", raising=False)
    llm_setup._CLIENT_CACHE.clear()
    yield
    llm_setup._CLIENT_CACHE.clear()
    llm_setup.reset_llm_circuit_breakers()


def _collect():
    events: list[tuple[str, str]] = []
    token = sink.bind(lambda kind, text: events.append((kind, text)))
    return events, token


MSGS = [HumanMessage(content="olho ao redor")]


def test_mock_stream_equals_invoke_state():
    llm = MockLLM()
    random.seed(7)
    expected = llm.with_structured_output(StoryUpdate).invoke(MSGS)
    random.seed(7)
    events, token = _collect()
    try:
        got = sink.narrate_structured(llm, StoryUpdate, MSGS)
    finally:
        sink.unbind(token)
    assert isinstance(got, StoryUpdate)
    assert got.model_dump() == expected.model_dump()  # R9: mesmo estado final
    streamed = "".join(t for k, t in events if k == "delta")
    assert streamed == expected.narrative.strip()
    assert len([1 for k, _ in events if k == "delta"]) > 1  # chegou em varios deltas


def test_no_sink_uses_invoke():
    class Boom:
        def stream_structured(self, *a, **k):
            raise AssertionError("nao deveria streamar sem sink")

        def with_structured_output(self, schema):

            class _S:
                def invoke(self, msgs):
                    return StoryUpdate(narrative="via invoke")

            return _S()

    assert not sink.active()
    assert sink.narrate_structured(Boom(), StoryUpdate, MSGS).narrative == "via invoke"


def test_routed_stream_emits_tokens_and_parses_full_schema(monkeypatch):
    text = 'Você avança. "Quem vai lá?" gritam da torre.\n\nO que faz?'
    client = FakeStreamClient(slices(tool_args(text, introduced_npcs=["Guarda"])))
    install(monkeypatch, {"deepseek": client})
    llm = routed([("deepseek", "deepseek-chat")])
    events, token = _collect()
    try:
        result = sink.narrate_structured(llm, StoryUpdate, MSGS)
    finally:
        sink.unbind(token)
    assert isinstance(result, StoryUpdate)
    assert result.narrative == text and result.introduced_npcs == ["Guarda"]
    assert "".join(t for k, t in events if k == "delta") == text
    assert client.bound[1]["tool_choice"] == "StoryUpdate"


def test_interrupted_stream_falls_back_and_resets_sink(monkeypatch):
    raw = tool_args("Primeira tentativa que vai quebrar no meio do caminho.")
    broken = FakeStreamClient(slices(raw, 5), fail_after=8)
    good_text = "Segunda tentativa completa e valida."
    good = FakeStreamClient(slices(tool_args(good_text), 5))
    install(monkeypatch, {"deepseek": broken, "groq": good})
    attempts = []
    llm_setup.set_llm_attempt_telemetry_hook(attempts.append)
    try:
        llm = routed([("deepseek", "m1"), ("groq", "m2")])
        events, token = _collect()
        try:
            result = sink.narrate_structured(llm, StoryUpdate, MSGS)
        finally:
            sink.unbind(token)
    finally:
        llm_setup.set_llm_attempt_telemetry_hook(None)
    assert isinstance(result, StoryUpdate) and result.narrative == good_text
    kinds = [k for k, _ in events]
    assert "reset" in kinds
    after_reset = events[kinds.index("reset") + 1 :]
    assert "".join(t for k, t in after_reset if k == "delta") == good_text
    outcomes = [a.outcome for a in attempts]
    assert outcomes == ["stream_interrupted", "success"]


def test_failure_before_first_chunk_does_not_reset(monkeypatch):
    bad = FakeStreamClient([], fail_before=True)
    good = FakeStreamClient(slices(tool_args("ok depois do erro."), 4))
    install(monkeypatch, {"deepseek": bad, "groq": good})
    llm = routed([("deepseek", "m1"), ("groq", "m2")])
    events, token = _collect()
    try:
        result = sink.narrate_structured(llm, StoryUpdate, MSGS)
    finally:
        sink.unbind(token)
    assert isinstance(result, StoryUpdate)
    assert "reset" not in [k for k, _ in events]


def test_invalid_structured_goes_to_next_candidate(monkeypatch):
    garbage = FakeStreamClient(['{"narrative": "abc', " sem fechar"])
    good = FakeStreamClient(slices(tool_args("valida."), 3))
    install(monkeypatch, {"deepseek": garbage, "groq": good})
    llm = routed([("deepseek", "m1"), ("groq", "m2")])
    events, token = _collect()
    try:
        result = sink.narrate_structured(llm, StoryUpdate, MSGS)
    finally:
        sink.unbind(token)
    assert isinstance(result, StoryUpdate) and result.narrative == "valida."
    assert "reset" in [k for k, _ in events]  # o parcial "abc sem fechar" foi descartado


def test_non_openai_compat_uses_invoke(monkeypatch):
    class _Struct:
        def invoke(self, _msgs):
            return {
                "raw": AIMessage(content=""),
                "parsed": StoryUpdate(narrative="via gemini invoke"),
                "parsing_error": None,
            }

    class _Gemini:
        def with_structured_output(self, schema, **kw):
            return _Struct()

        def stream(self, _input):  # nao deve ser usado
            raise AssertionError("gemini nao streama (D4)")

    llm_setup.reset_llm_circuit_breakers()
    monkeypatch.setattr(llm_setup, "_get_cached_client", lambda p, m, t: _Gemini())
    llm = routed([("gemini", "flash")])
    events, token = _collect()
    try:
        result = sink.narrate_structured(llm, StoryUpdate, MSGS)
    finally:
        sink.unbind(token)
    assert isinstance(result, StoryUpdate) and result.narrative == "via gemini invoke"
    assert events == []  # sem deltas: cai no pseudo-streaming da 316


def test_fallbackllm_returns_aimessage_guarded():
    fb = llm_setup.FallbackLLM("sem chave")
    events, token = _collect()
    try:
        result = sink.narrate_structured(fb, StoryUpdate, MSGS)
    finally:
        sink.unbind(token)
    assert isinstance(result, AIMessage) and not isinstance(result, StoryUpdate)
    assert events == []


def test_all_candidates_exhausted_returns_aimessage(monkeypatch):
    bad = FakeStreamClient([], fail_before=True)
    install(monkeypatch, {"deepseek": bad, "groq": bad})
    llm = routed([("deepseek", "m1"), ("groq", "m2")])
    events, token = _collect()
    try:
        result = sink.narrate_structured(llm, StoryUpdate, MSGS)
    finally:
        sink.unbind(token)
    assert isinstance(result, AIMessage)
    assert events == []


def test_streamed_text_is_guarded_receipt_and_concealed_names(monkeypatch):
    """Recibo `[RESULTADO]` e nome oculto (SPEC-293) nunca saem crus, nem partidos entre deltas."""
    text = (
        "A Ordem do Corvo Negro cerca a praça.\n[RESULTADO] +50 ouro\nVocê recua devagar, atento."
    )
    deltas = slices(tool_args(text), 3)  # fatias pequenas partem o nome oculto
    client = FakeStreamClient(deltas)
    install(monkeypatch, {"deepseek": client})
    llm = routed([("deepseek", "m1")])
    monkeypatch.setattr(
        sink, "_conceal_map", lambda state: {"Ordem do Corvo Negro": "uma ordem sombria"}
    )
    events, token = _collect()
    try:
        result = sink.narrate_structured(llm, StoryUpdate, MSGS)
    finally:
        sink.unbind(token)
    shown = "".join(t for k, t in events if k == "delta")
    assert isinstance(result, StoryUpdate)
    assert "Corvo" not in shown and "RESULTADO" not in shown and "+50" not in shown
    assert shown.startswith("A uma ordem sombria cerca a praça.")
    assert shown.rstrip().endswith("atento.")
    # nenhum delta intermediario continha o nome (nem pedaco dele que o veu reescreveria)
    assert all("Corvo" not in t and "[RES" not in t for k, t in events if k == "delta")


def test_stream_guard_final_flush_and_broken_prefix():
    guard = sink.StreamGuard({"Segredo": "algo"})
    out = guard.feed("Isto e um Segr") + guard.feed("edo antigo. ") + guard.finish()
    assert out == "Isto e um algo antigo."
