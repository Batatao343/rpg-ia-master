"""SPEC-317 R5 — vetor de consulta do contexto de STORY calculado em paralelo ao router.

``turn_prepare`` chama :func:`start_prefetch`: uma thread única embeda a consulta que o
narrador montará (``compose_lore_query``) enquanto router/planner rodam. Quando o
``build_context_pack`` chega, :func:`take` devolve o resultado pronto (ou espera o que
já está em voo, em vez de embedar duas vezes). Consulta diferente (viagem, descanso),
falha ou timeout => ``None`` e o caminho de sempre (embedding inline) segue valendo.

Cache por processo ``(game_id, turno, consulta)``, teto de 8 entradas. Nada é persistido;
cada instância serverless faz o seu próprio prefetch dentro do próprio turno.
"""

from __future__ import annotations

import os
import threading
from collections import OrderedDict
from concurrent.futures import Future, ThreadPoolExecutor
from contextvars import copy_context
from typing import Any

from observability.telemetry import log_event as _log_event

_MAX_ENTRIES = 8
_LOCK = threading.Lock()
_ENTRIES: OrderedDict[tuple[str, int, str], Future] = OrderedDict()
_EXECUTOR: ThreadPoolExecutor | None = None


def mode() -> str:
    """``RPG_CONTEXT_PREFETCH``: on | off. Sem env: on, exceto na suíte (``RPG_FORCE_MOCK``)."""
    value = os.environ.get("RPG_CONTEXT_PREFETCH", "").strip().lower()
    if value in ("on", "off"):
        return value
    return "off" if os.environ.get("RPG_FORCE_MOCK") == "1" else "on"


def _wait_seconds() -> float:
    try:
        return max(0.0, float(os.environ.get("RPG_CONTEXT_PREFETCH_WAIT_S", "2.0")))
    except ValueError:
        return 2.0


def _executor() -> ThreadPoolExecutor:
    global _EXECUTOR
    with _LOCK:
        if _EXECUTOR is None:
            _EXECUTOR = ThreadPoolExecutor(max_workers=1, thread_name_prefix="ctx-prefetch")
        return _EXECUTOR


def story_query(state: dict) -> str:
    """A consulta que o narrador usará, calculada só do estado de entrada do turno."""
    from langchain_core.messages import HumanMessage

    from services.lore_query import compose_lore_query

    messages = state.get("messages") or []
    last = messages[-1] if messages else None
    text = str(last.content) if isinstance(last, HumanMessage) else ""
    return compose_lore_query(state, text)


def _embed(query: str, game_id: str) -> Any:
    from services.context_sources import embed_context_query_uncached

    return embed_context_query_uncached(query, game_id=game_id, npc_id=None)


def start_prefetch(state: dict, turn: int | None = None) -> bool:
    """Dispara o prefetch (não bloqueia, nunca levanta). ``True`` se agendou."""
    try:
        if mode() != "on":
            return False
        game_id = str(state.get("game_id") or "")
        if not game_id or (state.get("combat") or {}).get("active"):
            return False
        world = state.get("world") or {}
        turn = int(turn if turn is not None else int(world.get("turn_count", 0) or 0) + 1)
        query = story_query(state)
        if not query.strip():
            return False
        key = (game_id, turn, query)
        with _LOCK:
            if key in _ENTRIES:
                return False
            future: Future = Future()
            _ENTRIES[key] = future
            while len(_ENTRIES) > _MAX_ENTRIES:
                _ENTRIES.popitem(last=False)
        ctx = copy_context()

        def run() -> None:
            try:
                future.set_result(ctx.run(_embed, query, game_id))
            except BaseException as exc:  # silent-ok: o consumidor cai no embedding inline
                future.set_exception(exc)

        _executor().submit(run)
        return True
    except Exception as exc:  # silent-ok: prefetch e otimizacao; o turno nunca depende dele
        _log_event("context", "prefetch_failed", level="warning", error=type(exc).__name__)
        return False


def take(game_id: str | None, turn: int | None, query: str) -> Any | None:
    """``EmbeddedContextQuery`` prefetchado para exatamente esta consulta, ou ``None``."""
    if not game_id or turn is None:
        return None
    key = (str(game_id), int(turn), query)
    with _LOCK:
        future = _ENTRIES.get(key)
    if future is None:
        return None
    try:
        result = future.result(timeout=_wait_seconds())
    except Exception as exc:  # silent-ok: falha/timeout => caminho inline
        _log_event("context", "prefetch_miss", level="debug", error=type(exc).__name__)
        return None
    _log_event("context", "prefetch_hit", level="debug")
    return result


def take_vector(game_id: str | None, turn: int | None, query: str) -> list[float] | None:
    result = take(game_id, turn, query)
    vector = getattr(result, "vector", None)
    return list(vector) if vector is not None else None


def clear() -> None:
    with _LOCK:
        _ENTRIES.clear()
