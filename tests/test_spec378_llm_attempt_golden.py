"""SPEC-378 E4: golden dos eventos de tentativa do RoutedLLM (invoke/stream).

O golden foi gravado com o codigo anterior a ``_attempt``; refatorar nao pode muda-lo.
Regrave so com ``RPG_SPEC378_RECORD=1`` (e justifique no commit).
"""

from __future__ import annotations

import dataclasses
import json
import os
from pathlib import Path

import pytest
from langchain_core.messages import AIMessage

import llm_setup
from llm_setup import ModelTier, RoutedLLM

GOLDEN = Path(__file__).parent / "fixtures" / "spec378" / "llm_attempts.json"


class _Boom(Exception):
    pass


class _Client:
    def __init__(self, invoke=None, stream=None):
        self._invoke = invoke
        self._stream = stream

    def invoke(self, _input):
        if isinstance(self._invoke, BaseException):
            raise self._invoke
        return self._invoke

    def stream(self, _input):
        if isinstance(self._stream, BaseException):
            raise self._stream
        return iter(self._stream or [])


def _ev(e):
    d = dataclasses.asdict(e)
    d["tier"] = str(d["tier"])
    return d


@pytest.fixture
def run(monkeypatch):
    monkeypatch.delenv("RPG_FORCE_MOCK", raising=False)
    llm_setup.reset_llm_circuit_breakers()
    monkeypatch.setattr(llm_setup.time, "perf_counter", lambda: 1.0)
    monkeypatch.setattr(RoutedLLM, "_apply", lambda self, client, provider: client)

    def go(kind, clients, killed=(), build_errors=(), circuit=()):
        llm_setup.reset_llm_circuit_breakers()
        for key in circuit:
            llm_setup._OPEN_CIRCUITS[key] = "forced"

        def cached(p, m, t, tier):
            if p in build_errors:
                raise _Boom("build")
            return clients[p]

        monkeypatch.setattr(llm_setup, "_cached_for_tier", cached)
        monkeypatch.setattr(llm_setup, "_kill_switch_disabled", lambda p, m: p in killed)
        events, legacy = [], []
        prev = llm_setup._ATTEMPT_TELEMETRY_HOOK
        llm_setup.set_llm_attempt_telemetry_hook(lambda e: events.append(_ev(e)))
        llm_setup.set_llm_telemetry_hook(lambda *a: legacy.append([str(x) for x in a]))
        try:
            llm = RoutedLLM(ModelTier.FAST, 0.7, [("a", "m1"), ("b", "m2")])
            out = llm.invoke("x") if kind == "invoke" else list(llm.stream("x"))
        finally:
            llm_setup.set_llm_attempt_telemetry_hook(prev)
            llm_setup.set_llm_telemetry_hook(None)
            llm_setup.reset_llm_circuit_breakers()
        return {"events": events, "legacy": legacy, "out": repr(out)}

    return go


def _scenarios(run):
    ok = AIMessage(content="ok")
    return {
        "invoke_success": run("invoke", {"a": _Client(ok), "b": _Client(ok)}),
        "invoke_error_fallback": run("invoke", {"a": _Client(_Boom("x")), "b": _Client(ok)}),
        "invoke_build_error": run("invoke", {"b": _Client(ok)}, build_errors=("a",)),
        "invoke_kill": run("invoke", {"b": _Client(ok)}, killed=("a",)),
        "invoke_circuit": run("invoke", {"b": _Client(ok)}, circuit=(("a", "m1"),)),
        "invoke_all_fail": run("invoke", {"a": _Client(_Boom("x")), "b": _Client(_Boom("y"))}),
        "stream_success": run("stream", {"a": _Client(stream=[ok, ok])}),
        "stream_empty": run("stream", {"a": _Client(stream=[])}),
        "stream_error_fallback": run(
            "stream", {"a": _Client(stream=_Boom("s")), "b": _Client(stream=[ok])}
        ),
        "stream_build_error": run("stream", {"b": _Client(stream=[ok])}, build_errors=("a",)),
        "stream_kill": run("stream", {"b": _Client(stream=[ok])}, killed=("a",)),
        "stream_circuit": run("stream", {"b": _Client(stream=[ok])}, circuit=(("a", "m1"),)),
    }


def test_attempt_events_match_golden(run):
    got = _scenarios(run)
    if os.environ.get("RPG_SPEC378_RECORD") == "1":
        GOLDEN.write_text(json.dumps(got, indent=1, sort_keys=True), encoding="utf-8")
    want = json.loads(GOLDEN.read_text(encoding="utf-8"))
    assert json.loads(json.dumps(got)) == want
