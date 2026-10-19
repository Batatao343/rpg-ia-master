"""SPEC-254: logs/metricas do Postgres (lease, versao, pool, timeouts) sem SQL, parametros ou DSN.

Todo campo e um codigo fechado, um rotulo estatico de chamada (``query_name``) ou um pseudonimo.
Nunca levanta: observabilidade nao pode derrubar uma transacao.
"""

from __future__ import annotations

import functools
import os
import time
from contextlib import contextmanager
from contextvars import ContextVar
from typing import Any
from collections.abc import Callable, Iterator

from observability.telemetry import log_event, pseudonym

_QUERY_NAME: ContextVar[str] = ContextVar("rpg_db_query_name", default="unlabeled")

LEASE_REASONS = frozenset({
    "game_busy", "operation_in_progress", "fence_invalid", "worker_late", "lease_lost",
    "job_fence_invalid",
})


def _ref(value: Any) -> str | None:
    return pseudonym(value) if value else None


def conflict(event: str, reason: str, *, op_kind: str | None = None, operation_id: Any = None,
             game_id: Any = None) -> None:
    """``db.lease_conflict`` | ``db.stale_version`` | ``db.idempotency_conflict`` (warning)."""
    try:
        log_event("db", event, level="warning", reason=reason, op_kind=op_kind,
                  op_ref=_ref(operation_id), game_ref=_ref(game_id))
    except Exception:  # silent-ok: o log nunca derruba a transacao
        pass


def slow_threshold_ms() -> int:
    try:
        return max(0, int(os.getenv("RPG_DB_SLOW_MS", "500")))
    except ValueError:
        return 500


def classify_error(exc: BaseException) -> str | None:
    """Codigo fechado a partir da CLASSE da excecao (sem importar psycopg)."""
    for klass in type(exc).__mro__:
        name = klass.__name__
        if name == "QueryCanceled":
            return "statement_timeout"
        if name == "LockNotAvailable":
            return "lock_timeout"
        if name == "PoolTimeout":
            return "pool_timeout"
    return None


def log_query_error(exc: BaseException) -> None:
    """``db.statement_timeout`` / ``db.lock_timeout`` (error) com o rotulo da chamada em curso."""
    code = classify_error(exc)
    if code in {"statement_timeout", "lock_timeout"}:
        try:
            log_event("db", code, level="error", query_name=_QUERY_NAME.get(),
                      error_type=type(exc).__name__)
        except Exception:  # silent-ok: o log nunca mascara a falha original
            pass


def log_checkout_failure(exc: BaseException, *, pool: str, waited_s: float, stats: dict | None) -> None:
    """``db.pool_timeout`` ou ``db.connect_failed`` (error): sem host, DSN ou mensagem."""
    try:
        if classify_error(exc) == "pool_timeout":
            size = int((stats or {}).get("pool_size", 0) or 0)
            avail = int((stats or {}).get("pool_available", 0) or 0)
            log_event("db", "pool_timeout", level="error", pool=pool, wait_ms=int(waited_s * 1000),
                      pool_size=size, in_use=max(0, size - avail),
                      requests_waiting=int((stats or {}).get("requests_waiting", 0) or 0))
        else:
            log_event("db", "connect_failed", level="error", pool=pool,
                      error_type=type(exc).__name__, wait_ms=int(waited_s * 1000), attempt=1)
    except Exception:  # silent-ok: o log nunca mascara a falha original
        pass


@contextmanager
def timed(query_name: str) -> Iterator[None]:
    """Mede uma chamada ao banco: ``rpg_db_query_seconds{query_name}`` + ``db.slow_query``."""
    token = _QUERY_NAME.set(query_name)
    started = time.perf_counter()
    try:
        yield
    finally:
        elapsed = time.perf_counter() - started
        _QUERY_NAME.reset(token)
        try:
            from observability.metrics import metrics
            metrics.observe("rpg_db_query_seconds", {"query_name": query_name}, elapsed)
            if elapsed * 1000 >= slow_threshold_ms():
                log_event("db", "slow_query", level="warning", query_name=query_name,
                          duration_ms=int(elapsed * 1000))
        except Exception:  # silent-ok: metrica best-effort
            pass


def timed_call(query_name: str) -> Callable:
    """Decorator de ``timed`` (sem reindentar o corpo do metodo)."""
    def wrap(fn: Callable) -> Callable:
        @functools.wraps(fn)
        def inner(*args: Any, **kwargs: Any) -> Any:
            with timed(query_name):
                return fn(*args, **kwargs)
        return inner
    return wrap
