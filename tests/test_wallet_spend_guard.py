"""SPEC-184: paid routing requires an authoritative pre-dispatch permit."""

from __future__ import annotations

import pytest
from langchain_core.messages import AIMessage

import llm_setup


class _Client:
    def __init__(self, calls: list[str], model: str, *, fail: bool = False):
        self.calls = calls
        self.model = model
        self.fail = fail

    def invoke(self, _input):
        self.calls.append(self.model)
        if self.fail:
            raise RuntimeError("provider failed after network")
        return AIMessage(content="ok")

    def stream(self, _input):
        self.calls.append(self.model)
        yield AIMessage(content="ok")


def test_guard_blocks_invoke_before_provider_network(monkeypatch):
    calls = []
    monkeypatch.setattr(llm_setup, "_get_cached_client",
                        lambda _p, model, _t: _Client(calls, model))
    route = llm_setup.RoutedLLM(llm_setup.ModelTier.FAST, 0,
                                [("guard-test", "first")])
    with llm_setup.llm_spend_guard_scope(lambda *_: (_ for _ in ()).throw(
            RuntimeError("ceiling exhausted"))):
        with pytest.raises(RuntimeError, match="ceiling exhausted"):
            route.invoke("prompt")
    assert calls == []


def test_guard_runs_again_for_fallback_and_stops_when_ceiling_exhausted(monkeypatch):
    calls = []
    permits = []
    monkeypatch.setattr(llm_setup, "_get_cached_client",
                        lambda _p, model, _t: _Client(calls, model, fail=model == "first"))
    route = llm_setup.RoutedLLM(llm_setup.ModelTier.FAST, 0,
                                [("guard-test", "first"), ("guard-test", "second")])

    def permit(_provider, model):
        permits.append(model)
        if model == "second":
            raise RuntimeError("second exceeds ceiling")

    with llm_setup.llm_spend_guard_scope(permit):
        with pytest.raises(RuntimeError, match="second exceeds ceiling"):
            route.invoke("prompt")
    assert permits == ["first", "second"]
    assert calls == ["first"]


def test_stream_guard_blocks_before_first_chunk(monkeypatch):
    calls = []
    monkeypatch.setattr(llm_setup, "_get_cached_client",
                        lambda _p, model, _t: _Client(calls, model))
    route = llm_setup.RoutedLLM(llm_setup.ModelTier.FAST, 0,
                                [("guard-test", "stream")])
    with llm_setup.llm_spend_guard_scope(lambda *_: (_ for _ in ()).throw(
            RuntimeError("no ticket"))):
        with pytest.raises(RuntimeError, match="no ticket"):
            list(route.stream("prompt"))
    assert calls == []
