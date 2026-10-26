"""SPEC-319 R5: hedge na cauda do narrador (2o candidato quando o 1o demora a emitir)."""

from __future__ import annotations

import pytest
from langchain_core.messages import HumanMessage

import llm_setup
from agents.storyteller import StoryUpdate
from services import narrative_sink as sink
from tests.spec319_helpers import FakeStreamClient, install, routed, slices, tool_args

MSGS = [HumanMessage(content="olho ao redor")]


@pytest.fixture(autouse=True)
def _env(monkeypatch):
    monkeypatch.delenv("RPG_FORCE_MOCK", raising=False)
    monkeypatch.delenv("RPG_LLM_HEDGE_MS", raising=False)
    llm_setup._CLIENT_CACHE.clear()
    llm_setup._HEDGE_STATS.update(calls=100, hedges=0)
    yield
    llm_setup._CLIENT_CACHE.clear()
    llm_setup._HEDGE_STATS.update(calls=0, hedges=0)
    llm_setup.reset_llm_circuit_breakers()


def _run(llm):
    events: list[tuple[str, str]] = []
    token = sink.bind(lambda kind, text: events.append((kind, text)))
    attempts = []
    llm_setup.set_llm_attempt_telemetry_hook(attempts.append)
    try:
        result = sink.narrate_structured(llm, StoryUpdate, MSGS)
    finally:
        sink.unbind(token)
        llm_setup.set_llm_attempt_telemetry_hook(None)
    return result, events, attempts


def _pair(first_delay_a=0.0, first_delay_b=0.0, gap_a=0.0):
    a = FakeStreamClient(slices(tool_args("texto do A"), 4), first_delay=first_delay_a, gap=gap_a)
    b = FakeStreamClient(slices(tool_args("texto do B"), 4), first_delay=first_delay_b)
    return a, b


def test_hedge_off_by_default(monkeypatch):
    a, b = _pair(first_delay_a=0.15)
    install(monkeypatch, {"deepseek": a, "groq": b})
    result, _events, _att = _run(routed([("deepseek", "m1"), ("groq", "m2")]))
    assert result.narrative == "texto do A" and b.calls == 0


def test_hedge_not_started_when_first_token_in_time(monkeypatch):
    monkeypatch.setenv("RPG_LLM_HEDGE_MS", "400")
    a, b = _pair(first_delay_a=0.02)
    install(monkeypatch, {"deepseek": a, "groq": b})
    result, events, attempts = _run(routed([("deepseek", "m1"), ("groq", "m2")]))
    assert result.narrative == "texto do A"
    assert b.calls == 0
    assert "".join(t for k, t in events if k == "delta") == "texto do A"
    assert [x.outcome for x in attempts] == ["success"]


def test_hedge_started_after_threshold_and_second_wins(monkeypatch):
    monkeypatch.setenv("RPG_LLM_HEDGE_MS", "80")
    logged = []
    monkeypatch.setattr(llm_setup, "_log_hedge", lambda *a, **k: logged.append(k))
    a, b = _pair(first_delay_a=1.0, first_delay_b=0.0)
    install(monkeypatch, {"deepseek": a, "groq": b})
    result, events, attempts = _run(routed([("deepseek", "m1"), ("groq", "m2")]))
    assert result.narrative == "texto do B"
    assert b.calls == 1
    # so os deltas do vencedor chegam ao sink, sem reset nem mistura
    assert [k for k, _ in events] == ["delta"] * len(events)
    assert "".join(t for _k, t in events) == "texto do B"
    outcomes = {(x.model, x.outcome) for x in attempts}
    assert ("m1", "hedge_lost") in outcomes and ("m2", "success") in outcomes
    assert logged and logged[0]["winner"] == 1 and logged[0]["first"] == 0  # hedge_won


def test_first_wins_even_if_slow_after_first_token(monkeypatch):
    monkeypatch.setenv("RPG_LLM_HEDGE_MS", "80")
    logged = []
    monkeypatch.setattr(llm_setup, "_log_hedge", lambda *a, **k: logged.append(k))
    a, b = _pair(first_delay_a=0.15, gap_a=0.03)  # A passa do limiar, mas emite antes de B
    b.first_delay = 0.6
    install(monkeypatch, {"deepseek": a, "groq": b})
    result, events, attempts = _run(routed([("deepseek", "m1"), ("groq", "m2")]))
    assert result.narrative == "texto do A"
    assert "".join(t for _k, t in events) == "texto do A"
    outcomes = {(x.model, x.outcome) for x in attempts}
    assert ("m2", "hedge_lost") in outcomes and ("m1", "success") in outcomes
    assert logged and logged[0]["winner"] == 0  # hedged, mas o 1o venceu


def test_hedge_telemetry_outcomes_and_no_double_result(monkeypatch):
    monkeypatch.setenv("RPG_LLM_HEDGE_MS", "50")
    a, b = _pair(first_delay_a=0.5)
    install(monkeypatch, {"deepseek": a, "groq": b})
    result, _events, attempts = _run(routed([("deepseek", "m1"), ("groq", "m2")]))
    assert isinstance(result, StoryUpdate)
    success = [x for x in attempts if x.outcome == "success"]
    lost = [x for x in attempts if x.outcome == "hedge_lost"]
    assert len(success) == 1 and len(lost) == 1  # efeito colateral so do vencedor


def test_hedge_budget_caps_extra_calls(monkeypatch):
    monkeypatch.setenv("RPG_LLM_HEDGE_MS", "30")
    llm_setup._HEDGE_STATS.update(calls=19, hedges=2)  # +1 chamada e +1 hedge > 10%
    a, b = _pair(first_delay_a=0.2)
    install(monkeypatch, {"deepseek": a, "groq": b})
    result, _events, _att = _run(routed([("deepseek", "m1"), ("groq", "m2")]))
    assert result.narrative == "texto do A" and b.calls == 0


def test_hedge_only_for_fast_tier(monkeypatch):
    monkeypatch.setenv("RPG_LLM_HEDGE_MS", "30")
    a, b = _pair(first_delay_a=0.2)
    install(monkeypatch, {"deepseek": a, "groq": b})
    llm = routed([("deepseek", "m1"), ("groq", "m2")], tier=llm_setup.ModelTier.SMART)
    result, _events, _att = _run(llm)
    assert result.narrative == "texto do A" and b.calls == 0


def test_hedge_first_fails_fast_moves_to_second(monkeypatch):
    monkeypatch.setenv("RPG_LLM_HEDGE_MS", "400")
    a = FakeStreamClient([], fail_before=True)
    b = FakeStreamClient(slices(tool_args("texto do B"), 4))
    install(monkeypatch, {"deepseek": a, "groq": b})
    result, events, _att = _run(routed([("deepseek", "m1"), ("groq", "m2")]))
    assert result.narrative == "texto do B"
    assert "".join(t for _k, t in events) == "texto do B"


def test_hedge_cold_instance_needs_min_calls(monkeypatch):
    monkeypatch.setenv("RPG_LLM_HEDGE_MS", "30")
    llm_setup._HEDGE_STATS.update(calls=0, hedges=0)  # instancia fria: nao hedgeia a 1a chamada
    a, b = _pair(first_delay_a=0.2)
    install(monkeypatch, {"deepseek": a, "groq": b})
    result, _events, _att = _run(routed([("deepseek", "m1"), ("groq", "m2")]))
    assert result.narrative == "texto do A" and b.calls == 0


def test_failed_first_is_not_reported_as_hedge_lost(monkeypatch):
    """P2-2: o candidato que ja falhou nao vira `hedge_lost` (sem dupla contagem)."""
    monkeypatch.setenv("RPG_LLM_HEDGE_MS", "400")
    a = FakeStreamClient([], fail_before=True)
    b = FakeStreamClient(slices(tool_args("texto do B"), 4))
    install(monkeypatch, {"deepseek": a, "groq": b})
    result, _events, attempts = _run(routed([("deepseek", "m1"), ("groq", "m2")]))
    assert result.narrative == "texto do B"
    assert [(x.model, x.outcome) for x in attempts] == [("m1", "stream_error"), ("m2", "success")]
