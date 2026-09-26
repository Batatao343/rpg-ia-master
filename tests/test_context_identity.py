"""Principal and correlation must survive every context acquisition boundary."""
from __future__ import annotations

import asyncio
from concurrent.futures import ThreadPoolExecutor
from contextvars import ContextVar
import threading
from types import SimpleNamespace
from uuid import uuid4

import pytest

from infrastructure.contracts import Principal
from infrastructure.request_context import current_principal, principal_scope, set_current_principal
from services.context_sources import (
    EmbeddedContextQuery, acquire_context_sources, acquire_context_sources_async,
)


def _principal() -> Principal:
    return Principal(uuid4(), "test", "audit")


@pytest.mark.parametrize("mode", ["serial", "parallel", "async"])
def test_real_rag_readers_keep_request_identity(monkeypatch, mode: str) -> None:
    import rag
    monkeypatch.setenv("RPG_RUNTIME_PROFILE", "portable")
    principal = _principal()
    game_id = uuid4()
    requests = []

    def query(request):
        assert request.principal == principal
        assert request.game_id == game_id
        requests.append(request.scope)
        return [SimpleNamespace(text=request.scope)]

    monkeypatch.setattr("infrastructure.runtime.get_runtime", lambda: SimpleNamespace(
        memory_store=SimpleNamespace(query=query)))
    readers = {"session": lambda: rag.query_session_memory("x", str(game_id)),
               "npc": lambda: rag.query_npc_memory(str(game_id), "npc_a", "x")}
    args = dict(game_id=str(game_id), npc_id="npc_a", readers=readers)
    with principal_scope(principal):
        embedded = EmbeddedContextQuery("x", None, None, None)
        if mode == "async":
            results = asyncio.run(acquire_context_sources_async(embedded, **args))
        else:
            results = acquire_context_sources(embedded, max_workers=1 if mode == "serial" else 3, **args)
        assert current_principal() == principal
    assert [result.status for result in results] == ["ok", "ok"]
    assert sorted(requests) == ["npc", "session"]


@pytest.mark.parametrize("workers", [1, 3])
def test_reader_context_mutation_is_isolated_from_siblings_and_caller(workers: int) -> None:
    principal = _principal()
    trace = ContextVar("audit_trace", default="none")
    trace_token = trace.set("original")

    def mutate() -> str:
        assert current_principal() == principal
        assert trace.get() == "original"
        trace.set("changed")
        set_current_principal(_principal())
        return "mutated"

    def read() -> str:
        assert current_principal() == principal
        assert trace.get() == "original"
        return "original"

    try:
        with principal_scope(principal):
            results = acquire_context_sources(EmbeddedContextQuery("x", None, None, None),
                game_id=str(uuid4()), npc_id=None, max_workers=workers,
                readers={"lore": mutate, "session": read})
            assert current_principal() == principal
            assert trace.get() == "original"
        assert [row.text for row in results] == ["mutated", "original"]
    finally:
        trace.reset(trace_token)


def test_simultaneous_users_never_share_principal() -> None:
    barrier = threading.Barrier(4, timeout=5)

    def request(principal: Principal) -> list[str]:
        def read() -> str:
            barrier.wait()
            return str(current_principal().user_id)
        with principal_scope(principal):
            rows = acquire_context_sources(EmbeddedContextQuery("x", None, None, None),
                game_id=str(uuid4()), npc_id="npc_a", readers={"session": read, "npc": read})
        return [row.text for row in rows]

    principals = [_principal(), _principal()]
    with ThreadPoolExecutor(max_workers=2) as pool:
        futures = [pool.submit(request, p) for p in principals]
        for future, principal in zip(futures, principals):
            assert future.result(timeout=8) == [str(principal.user_id)] * 2


def test_missing_principal_still_fails_closed() -> None:
    with principal_scope(None):
        rows = acquire_context_sources(EmbeddedContextQuery("x", None, None, None),
            game_id=str(uuid4()), npc_id="npc_a", readers={
                "session": lambda: str(current_principal().user_id),
                "npc": lambda: str(current_principal().user_id)})
    assert [row.error_code for row in rows] == ["Unauthorized", "Unauthorized"]
