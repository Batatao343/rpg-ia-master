"""SPEC-317 R5 — vetor de consulta pré-computado no turn_prepare."""

from __future__ import annotations

import threading

import pytest
from langchain_core.messages import HumanMessage

from services import context_prefetch, context_sources
from services.context_sources import EmbeddedContextQuery


def _state(text="sigo pela estrada", turn=4):
    return {
        "game_id": "g-prefetch",
        "messages": [HumanMessage(content=text)],
        "world": {
            "current_location": "Brekmar",
            "current_location_id": "brekmar",
            "turn_count": turn,
        },
        "combat": None,
    }


@pytest.fixture(autouse=True)
def _clean(monkeypatch):
    monkeypatch.setenv("RPG_CONTEXT_PREFETCH", "on")
    context_prefetch.clear()
    yield
    context_prefetch.clear()


def _fake_embedder(monkeypatch, *, fail=False):
    calls: list[str] = []

    def fake(text, **_kw):
        calls.append(text)
        if fail:
            raise RuntimeError("provider down")
        return EmbeddedContextQuery(text, (0.1, 0.2), "fake", "m")

    monkeypatch.setattr(context_sources, "embed_context_query_uncached", fake)
    return calls


def test_take_vector_returns_prefetched_for_same_query(monkeypatch):
    calls = _fake_embedder(monkeypatch)
    state = _state()
    assert context_prefetch.start_prefetch(state, 5)
    query = context_prefetch.story_query(state)
    assert context_prefetch.take_vector("g-prefetch", 5, query) == [0.1, 0.2]
    assert context_prefetch.take_vector("g-prefetch", 6, query) is None  # outro turno
    assert context_prefetch.take_vector("g-prefetch", 5, query + " x") is None  # outra consulta
    assert calls == [query]


def test_prefetch_failure_falls_back_to_inline_embedding(monkeypatch):
    _fake_embedder(monkeypatch, fail=True)
    state = _state()
    context_prefetch.start_prefetch(state, 5)
    query = context_prefetch.story_query(state)
    assert context_prefetch.take("g-prefetch", 5, query) is None


def test_embedding_called_once_per_turn(monkeypatch):
    calls = _fake_embedder(monkeypatch)
    state = _state()
    context_prefetch.start_prefetch(state, 5)
    context_prefetch.start_prefetch(state, 5)  # duplicata é ignorada
    query = context_prefetch.story_query(state)
    out = context_sources.embed_context_query(query, game_id="g-prefetch", turn=5)
    assert out.vector == (0.1, 0.2)
    assert len(calls) == 1  # o consumo reaproveitou o prefetch


def test_consumer_waits_for_inflight_prefetch(monkeypatch):
    gate = threading.Event()
    calls: list[str] = []

    def slow(text, **_kw):
        calls.append(text)
        gate.wait(2)
        return EmbeddedContextQuery(text, (1.0,), "fake", "m")

    monkeypatch.setattr(context_sources, "embed_context_query_uncached", slow)
    state = _state()
    context_prefetch.start_prefetch(state, 5)
    query = context_prefetch.story_query(state)
    threading.Timer(0.1, gate.set).start()
    out = context_sources.embed_context_query(query, game_id="g-prefetch", turn=5)
    assert out.vector == (1.0,) and len(calls) == 1


def test_no_prefetch_in_combat_or_when_off(monkeypatch):
    _fake_embedder(monkeypatch)
    assert not context_prefetch.start_prefetch({**_state(), "combat": {"active": True}}, 5)
    monkeypatch.setenv("RPG_CONTEXT_PREFETCH", "off")
    assert not context_prefetch.start_prefetch(_state(), 5)


def test_turn_prepare_node_starts_prefetch(monkeypatch):
    calls = _fake_embedder(monkeypatch)
    from services.turn_pipeline import turn_prepare_node

    state = _state(turn=4)
    update = turn_prepare_node(state)
    assert update["world"]["turn_count"] == 5
    query = context_prefetch.story_query(state)
    assert context_prefetch.take("g-prefetch", 5, query) is not None
    assert calls == [query]
