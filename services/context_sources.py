"""Concurrent, deterministic acquisition of independent context sources."""
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
from contextvars import copy_context
import asyncio
from dataclasses import dataclass
import os
import threading
import time
from typing import Callable


_LIMITERS: dict[tuple[str, int], threading.BoundedSemaphore] = {}
_LIMITERS_LOCK = threading.Lock()


def _limit(name: str, default: int) -> threading.BoundedSemaphore:
    try:
        value = max(1, min(64, int(os.getenv(name, str(default)) or default)))
    except ValueError:
        value = default
    key = (name, value)
    with _LIMITERS_LOCK:
        return _LIMITERS.setdefault(key, threading.BoundedSemaphore(value))


@dataclass(frozen=True)
class EmbeddedContextQuery:
    text: str
    vector: tuple[float, ...] | None
    embedding_provider: str | None
    embedding_model: str | None

    @property
    def dimensions(self) -> int | None:
        return len(self.vector) if self.vector is not None else None


@dataclass(frozen=True)
class ContextSourceResult:
    source: str
    text: str = ""
    status: str = "empty"
    error_code: str | None = None
    latency_ms: int = 0


def embed_context_query(text: str, *, game_id: str | None = None,
                        npc_id: str | None = None) -> EmbeddedContextQuery:
    import rag
    from observability.telemetry import span

    with _limit("RPG_EMBEDDING_MAX_CONCURRENCY", 2):
        with span("context.embed"):
            vector, provider, model = rag.prepare_shared_query_vector(
                text,
                rag.context_index_paths(game_id=game_id, npc_id=npc_id),
            )
    return EmbeddedContextQuery(
        text=text,
        vector=tuple(vector) if vector is not None else None,
        embedding_provider=provider,
        embedding_model=model,
    )


def _default_readers(query: EmbeddedContextQuery, *, game_id: str | None,
                     npc_id: str | None) -> dict[str, Callable[[], str]]:
    import rag

    vector = list(query.vector) if query.vector is not None else None
    # A compatible profile was selected but its one shared embedding failed:
    # fail this context acquisition closed. Falling back to each textual API
    # here would retry the same provider once per scope and multiply latency.
    shared_embedding_failed = (
        query.vector is None and query.embedding_provider is not None
    )
    readers: dict[str, Callable[[], str]] = {
        "lore": (
            (lambda: rag.query_global_by_vector(vector, "lore", "public"))
            if vector is not None else
            ((lambda: "") if shared_embedding_failed else
             (lambda: rag.query_rag(query.text, index_name="lore", max_visibility="public")))
        ),
    }
    if game_id:
        readers["session"] = (
            (lambda: rag.query_session_by_vector(vector, game_id))
            if vector is not None else
            ((lambda: "") if shared_embedding_failed else
             (lambda: rag.query_session_memory(query.text, game_id)))
        )
    if game_id and npc_id:
        readers["npc"] = (
            (lambda: rag.query_npc_by_vector(vector, game_id, npc_id))
            if vector is not None else
            ((lambda: "") if shared_embedding_failed else
             (lambda: rag.query_npc_memory(game_id, npc_id, query.text)))
        )
    return readers


def acquire_context_sources(query: EmbeddedContextQuery, *, game_id: str | None,
                            npc_id: str | None, max_workers: int = 3,
                            readers: dict[str, Callable[[], str]] | None = None,
                            ) -> tuple[ContextSourceResult, ...]:
    readers = dict(readers or _default_readers(query, game_id=game_id, npc_id=npc_id))
    order = [source for source in ("lore", "session", "npc") if source in readers]

    def run(source: str) -> ContextSourceResult:
        started = time.perf_counter()
        try:
            from observability.telemetry import span
            with _limit("RPG_CONTEXT_GLOBAL_CONCURRENCY", 12):
                with span(f"context.{source}"):
                    value = str(readers[source]() or "")
            return ContextSourceResult(
                source=source, text=value, status="ok" if value else "empty",
                latency_ms=int((time.perf_counter() - started) * 1000),
            )
        except Exception as exc:
            return ContextSourceResult(
                source=source, status="degraded", error_code=type(exc).__name__,
                latency_ms=int((time.perf_counter() - started) * 1000),
            )

    if max_workers <= 1 or len(order) <= 1:
        return tuple(copy_context().run(run, source) for source in order)
    completed: dict[str, ContextSourceResult] = {}
    with ThreadPoolExecutor(max_workers=min(max_workers, len(order)),
                            thread_name_prefix="context-source") as executor:
        # One Context per task: a Context cannot be entered concurrently. Preserve
        # request identity/correlation without leaking a reader's assignments.
        futures = {executor.submit(copy_context().run, run, source): source for source in order}
        for future in as_completed(futures):
            result = future.result()
            completed[result.source] = result
    return tuple(completed[source] for source in order)


async def acquire_context_sources_async(
    query: EmbeddedContextQuery,
    *,
    game_id: str | None,
    npc_id: str | None,
    max_concurrency: int = 3,
    readers: dict[str, Callable[[], str]] | None = None,
) -> tuple[ContextSourceResult, ...]:
    """Async facade over the same bounded, deterministic sync implementation.

    Retrieval adapters in this project are synchronous. Keeping one shared
    implementation prevents scope/filter drift while the worker thread keeps
    an async API server's event loop responsive.
    """
    return await asyncio.to_thread(
        acquire_context_sources,
        query,
        game_id=game_id,
        npc_id=npc_id,
        max_workers=max_concurrency,
        readers=readers,
    )
