from __future__ import annotations

import asyncio
from concurrent.futures import ThreadPoolExecutor
import threading

from services import context_sources


def test_context_query_embeds_once_and_sources_overlap_in_stable_order(monkeypatch):
    import rag

    calls = []
    monkeypatch.setattr(rag, "context_index_paths", lambda **_kwargs: ["lore", "session", "npc"])
    monkeypatch.setattr(
        rag,
        "prepare_shared_query_vector",
        lambda text, paths: calls.append((text, tuple(paths))) or ([0.1, 0.2], "fake", "v1"),
    )
    query = context_sources.embed_context_query("ponte", game_id="g", npc_id="n")
    barrier = threading.Barrier(3, timeout=2)

    def reader(value):
        def run():
            barrier.wait()
            return value
        return run

    results = context_sources.acquire_context_sources(
        query,
        game_id="g",
        npc_id="n",
        readers={
            "npc": reader("npc"),
            "lore": reader("lore"),
            "session": reader("session"),
        },
    )

    assert len(calls) == 1
    assert query.dimensions == 2
    assert [result.source for result in results] == ["lore", "session", "npc"]
    assert [result.text for result in results] == ["lore", "session", "npc"]


def test_context_source_failure_is_isolated_and_limit_one_is_serial():
    query = context_sources.EmbeddedContextQuery("x", None, None, None)
    order = []

    def ok(source):
        def run():
            order.append(source)
            return source
        return run

    def fail():
        order.append("session")
        raise RuntimeError("offline")

    results = context_sources.acquire_context_sources(
        query,
        game_id="g",
        npc_id="n",
        max_workers=1,
        readers={"lore": ok("lore"), "session": fail, "npc": ok("npc")},
    )

    assert order == ["lore", "session", "npc"]
    assert [result.status for result in results] == ["ok", "degraded", "ok"]


def test_context_async_uses_same_order_and_keeps_event_loop_responsive():
    query = context_sources.EmbeddedContextQuery("x", None, None, None)

    def slow(value):
        def run():
            threading.Event().wait(0.04)
            return value
        return run

    async def scenario():
        ticks = 0

        async def ticker():
            nonlocal ticks
            for _ in range(4):
                await asyncio.sleep(0.01)
                ticks += 1

        results, _ = await asyncio.gather(
            context_sources.acquire_context_sources_async(
                query, game_id="g", npc_id="n", readers={
                    "npc": slow("npc"), "lore": slow("lore"),
                    "session": slow("session"),
                },
            ),
            ticker(),
        )
        return results, ticks

    results, ticks = asyncio.run(scenario())
    assert [result.source for result in results] == ["lore", "session", "npc"]
    assert ticks == 4


def test_failed_shared_embedding_does_not_retry_once_per_scope(monkeypatch):
    import rag

    calls = []
    monkeypatch.setattr(
        rag, "query_rag",
        lambda *_args, **_kwargs: calls.append("lore") or "unexpected",
    )
    monkeypatch.setattr(
        rag, "query_session_memory",
        lambda *_args, **_kwargs: calls.append("session") or "unexpected",
    )
    monkeypatch.setattr(
        rag, "query_npc_memory",
        lambda *_args, **_kwargs: calls.append("npc") or "unexpected",
    )
    query = context_sources.EmbeddedContextQuery(
        "x", None, "jina", "jina-embeddings-v3",
    )

    results = context_sources.acquire_context_sources(
        query, game_id="g", npc_id="n",
    )

    assert calls == []
    assert [result.status for result in results] == ["empty", "empty", "empty"]


def test_global_context_limit_bounds_different_requests(monkeypatch):
    monkeypatch.setenv("RPG_CONTEXT_GLOBAL_CONCURRENCY", "1")
    query = context_sources.EmbeddedContextQuery("x", None, None, None)
    first_entered = threading.Event()
    release_first = threading.Event()
    second_entered = threading.Event()
    call_lock = threading.Lock()
    calls = 0

    def reader():
        nonlocal calls
        with call_lock:
            calls += 1
            call = calls
        if call == 1:
            first_entered.set()
            assert release_first.wait(2)
        else:
            second_entered.set()
        return "ok"

    def acquire():
        return context_sources.acquire_context_sources(
            query, game_id=None, npc_id=None, max_workers=1,
            readers={"lore": reader},
        )

    with ThreadPoolExecutor(max_workers=2) as executor:
        first = executor.submit(acquire)
        assert first_entered.wait(2)
        second = executor.submit(acquire)
        assert second_entered.wait(0.05) is False
        release_first.set()
        assert first.result(timeout=2)[0].text == "ok"
        assert second.result(timeout=2)[0].text == "ok"


def test_shared_embedding_refuses_same_provider_with_different_model(monkeypatch):
    import rag

    monkeypatch.setenv("RPG_RUNTIME_PROFILE", "legacy")
    monkeypatch.setattr(rag, "_has_faiss_index", lambda _path: True)
    monkeypatch.setattr(rag, "_read_meta", lambda path: {
        "provider": "jina", "model": "jina-embeddings-v3" if path == "lore" else "obsolete",
    })
    def forbidden(_provider):
        raise AssertionError("Não deve chamar embeddings incompatíveis")
    monkeypatch.setattr(rag, "get_embeddings_for", forbidden)

    vector, provider, _model = rag.prepare_shared_query_vector("ponte", ["lore", "session"])
    assert vector is None and provider == "jina"


def test_shared_embedding_refuses_explicit_dimension_mismatch(monkeypatch):
    import rag
    from types import SimpleNamespace

    monkeypatch.setenv("RPG_RUNTIME_PROFILE", "legacy")
    monkeypatch.setattr(rag, "_has_faiss_index", lambda _path: True)
    monkeypatch.setattr(rag, "_read_meta", lambda _path: {
        "provider": "jina", "model": "jina-embeddings-v3", "dimensions": 1024,
    })
    monkeypatch.setattr(rag, "get_embeddings_for", lambda _provider: SimpleNamespace(
        embed_query=lambda _text: [0.1, 0.2],
    ))
    vector, provider, _model = rag.prepare_shared_query_vector("ponte", ["lore"])
    assert vector is None and provider == "jina"
