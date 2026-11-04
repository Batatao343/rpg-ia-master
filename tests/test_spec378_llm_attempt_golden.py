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


# --------------------------------------------------------------------------
# R23 estendido (P2-1): structured/retry semantico, 429, tool_use_failed, timeout,
# erro DENTRO de ``_apply`` (``_apply`` real), stream_structured e hedge.
# Fixture ``llm_attempts_ext.json`` gerada contra o merge-base (codigo sem ``_attempt``).
# --------------------------------------------------------------------------
from pydantic import BaseModel  # noqa: E402

from services import narrative_sink as sink  # noqa: E402
from tests.spec319_helpers import FakeStreamClient, install, slices, tool_args  # noqa: E402

GOLDEN_EXT = Path(__file__).parent / "fixtures" / "spec378" / "llm_attempts_ext.json"


class _Small(BaseModel):
    value: str


class _HttpErr(Exception):
    def __init__(self, status, code=None):
        super().__init__("http")
        self.status_code = status
        self.body = {"error": {"code": code, "message": "SEGREDO"}} if code else {}


def _good():
    return {"raw": None, "parsed": _Small(value="ok"), "parsing_error": None}


def _bad():
    return {"raw": None, "parsed": None, "parsing_error": ValueError("x")}


class _SClient:
    """Cliente falso com ``with_structured_output``; ``seq`` = retornos/excecoes por chamada."""

    def __init__(self, seq, apply_error=None):
        self.seq, self.apply_error, self.calls = list(seq), apply_error, 0

    def with_structured_output(self, *_a, **_k):
        if self.apply_error:
            raise self.apply_error
        return self

    def invoke(self, _input):
        item = self.seq[min(self.calls, len(self.seq) - 1)]
        self.calls += 1
        if isinstance(item, BaseException):
            raise item
        return item


@pytest.fixture
def run_ext(monkeypatch):
    monkeypatch.delenv("RPG_FORCE_MOCK", raising=False)
    monkeypatch.delenv("RPG_LLM_HEDGE_MS", raising=False)
    monkeypatch.setattr(llm_setup, "_kill_switch_disabled", lambda p, m: False)

    def go(fn, candidates, tier=ModelTier.CLASSIFY):
        llm_setup.reset_llm_circuit_breakers()
        events, legacy = [], []
        prev = llm_setup._ATTEMPT_TELEMETRY_HOOK
        llm_setup.set_llm_attempt_telemetry_hook(lambda e: events.append(_ev(e)))
        llm_setup.set_llm_telemetry_hook(lambda *a: legacy.append(str(a[0]) + ":" + str(a[1])))
        try:
            out = fn(RoutedLLM(tier, 0, candidates))
        finally:
            llm_setup.set_llm_attempt_telemetry_hook(prev)
            llm_setup.set_llm_telemetry_hook(None)
            llm_setup.reset_llm_circuit_breakers()
        for e in events:
            e["latency_ms"] = 0  # tempo real nao e determinístico aqui
        events.sort(key=lambda e: json.dumps(e, sort_keys=True))
        return {"events": events, "legacy": sorted(legacy), "out": out}

    return go


def _structured(monkeypatch, clients):
    monkeypatch.setattr(llm_setup, "_get_cached_client", lambda p, m, t: clients[p])

    def fn(llm):
        out = llm.with_structured_output(_Small).invoke("prompt")
        return repr(out)

    return fn


def _ext_scenarios(run_ext, monkeypatch):
    cands = [("groq", "m1"), ("gemini", "m2")]
    out = {}

    def inv(name, clients):
        out[name] = run_ext(_structured(monkeypatch, clients), cands)

    inv("s_ok", {"groq": _SClient([_good()]), "gemini": _SClient([_good()])})
    inv("s_retry_then_ok", {"groq": _SClient([_bad(), _good()]), "gemini": _SClient([_good()])})
    inv("s_always_invalid", {"groq": _SClient([_bad()]), "gemini": _SClient([_good()])})
    inv("s_429", {"groq": _SClient([_HttpErr(429)]), "gemini": _SClient([_good()])})
    inv(
        "s_tool_use_failed",
        {"groq": _SClient([_HttpErr(400, "tool_use_failed"), _good()]), "gemini": _SClient([])},
    )
    inv("s_timeout", {"groq": _SClient([TimeoutError("t")]), "gemini": _SClient([_good()])})
    inv(
        "s_apply_error",
        {"groq": _SClient([_good()], apply_error=_HttpErr(500)), "gemini": _SClient([_good()])},
    )
    inv("s_all_fail", {"groq": _SClient([_HttpErr(500)]), "gemini": _SClient([_HttpErr(429)])})
    return out


def _stream_structured_scenarios(run_ext, monkeypatch):
    out = {}

    def narrate(llm):
        events: list[tuple[str, str]] = []
        token = sink.bind(lambda kind, text: events.append((kind, text)))
        try:
            res = sink.narrate_structured(llm, _StoryLike, [])
        finally:
            sink.unbind(token)
        return repr([events, res])

    for name, hedge, clients in (
        (
            "ss_ok",
            None,
            {"deepseek": FakeStreamClient(slices(tool_args("A"), 4))},
        ),
        (
            "ss_fail_before_fallback",
            None,
            {
                "deepseek": FakeStreamClient(slices(tool_args("A"), 4), fail_before=True),
                "groq": FakeStreamClient(slices(tool_args("B"), 4)),
            },
        ),
        (
            "hedge_second_wins",
            "30",
            {
                "deepseek": FakeStreamClient(slices(tool_args("A"), 4), first_delay=0.4),
                "groq": FakeStreamClient(slices(tool_args("B"), 4)),
            },
        ),
    ):
        if hedge:
            monkeypatch.setenv("RPG_LLM_HEDGE_MS", hedge)
        else:
            monkeypatch.delenv("RPG_LLM_HEDGE_MS", raising=False)
        llm_setup._HEDGE_STATS.update(calls=100, hedges=0)
        llm_setup._CLIENT_CACHE.clear()
        install(monkeypatch, clients)
        out[name] = run_ext(
            narrate,
            [("deepseek", "m1"), ("groq", "m2")],
            ModelTier.FAST,
        )
    monkeypatch.delenv("RPG_LLM_HEDGE_MS", raising=False)
    return out


from agents.storyteller import StoryUpdate as _StoryLike  # noqa: E402


def test_attempt_events_ext_match_golden(run_ext, monkeypatch):
    got = _ext_scenarios(run_ext, monkeypatch)
    got.update(_stream_structured_scenarios(run_ext, monkeypatch))
    if os.environ.get("RPG_SPEC378_RECORD_EXT") == "1":
        GOLDEN_EXT.write_text(json.dumps(got, indent=1, sort_keys=True), encoding="utf-8")
    want = json.loads(GOLDEN_EXT.read_text(encoding="utf-8"))
    assert json.loads(json.dumps(got)) == want
