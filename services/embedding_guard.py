"""SPEC-419 — prazo curto e disjuntor para o embedding da consulta interativa do turno.

Só ``embed_context_query_uncached`` entra no escopo (``interactive_query``). Dentro dele,
o cliente Jina (``rag._JinaEmbeddingsHTTPX._embed``) tem um orçamento total de ``T``
segundos, e um timeout abre um disjuntor por ``B`` segundos (por instância, em memória).
Fora do escopo (jobs, escrita, reindex) nada muda: 30 s x 2 tentativas.

Não importa ``rag`` (rag importa este módulo). Nunca grava texto da consulta.
"""

from __future__ import annotations

import os
import threading
import time
from collections.abc import Iterator
from contextlib import contextmanager
from contextvars import ContextVar
from datetime import UTC, datetime
from email.utils import parsedate_to_datetime

from observability.telemetry import log_event, log_provider_attempt

MAX_BACKOFF_SECONDS: float = 60.0
_MIN_ATTEMPT_S = 0.1
_DEFAULT_TIMEOUT_S = 6.0
_DEFAULT_BREAKER_S = 60.0


class EmbeddingSkipped(RuntimeError):
    """Disjuntor aberto: a consulta interativa pula o provedor sem tocar a rede."""


def parse_retry_after(value: str | None) -> float | None:
    """Retry-After em segundos ou data HTTP -> segundos (>= 0), ou None se ilegível."""
    if not value:
        return None
    try:
        return max(0.0, float(value))
    except ValueError:
        pass
    try:
        when = parsedate_to_datetime(value)
    except (TypeError, ValueError):
        return None
    if when.tzinfo is None:
        when = when.replace(tzinfo=UTC)
    return max(0.0, (when - datetime.now(UTC)).total_seconds())


_SCOPE: ContextVar[bool] = ContextVar("embedding_interactive_scope", default=False)
_DEADLINE: ContextVar[float | None] = ContextVar("embedding_interactive_deadline", default=None)
_LOCK = threading.Lock()
_open_until: float = 0.0  # time.monotonic()


def enabled() -> bool:
    return os.environ.get("RPG_EMBEDDING_QUERY_DEADLINE", "on").strip().lower() != "off"


def _env_float(name: str, default: float, low: float, high: float) -> float:
    try:
        value = float(os.environ.get(name, ""))
    except ValueError:
        return default
    return value if low <= value <= high else default


def query_timeout_s() -> float:
    return _env_float("RPG_EMBEDDING_QUERY_TIMEOUT_S", _DEFAULT_TIMEOUT_S, 0.1, 30.0)


def breaker_s() -> float:
    return _env_float("RPG_EMBEDDING_BREAKER_S", _DEFAULT_BREAKER_S, 0.0, 86400.0)


@contextmanager
def interactive_query() -> Iterator[None]:
    """Marca a consulta como interativa (no-op com o kill switch ``off``)."""
    if not enabled():
        yield
        return
    scope = _SCOPE.set(True)
    budget = _DEADLINE.set(None)
    try:
        yield
    finally:
        _DEADLINE.reset(budget)
        _SCOPE.reset(scope)


def in_scope() -> bool:
    return _SCOPE.get()


def deadline() -> float | None:
    """``monotonic()+T`` fixado na 1ª chamada dentro do escopo; ``None`` fora dele."""
    if not _SCOPE.get():
        return None
    end = _DEADLINE.get()
    if end is None:
        end = time.monotonic() + query_timeout_s()
        _DEADLINE.set(end)
    return end


def remaining(end: float) -> float:
    return end - time.monotonic()


def min_attempt_s() -> float:
    return _MIN_ATTEMPT_S


def _degraded(reason: str, waited_ms: int) -> None:
    log_event(
        "embedding",
        "query_degraded",
        level="warning",
        reason=reason,
        waited_ms=waited_ms,
        budget_ms=int(query_timeout_s() * 1000),
        breaker_s=int(breaker_s()),
    )


def check_breaker(model: str) -> None:
    """No escopo e com o disjuntor aberto: loga e levanta ``EmbeddingSkipped`` (sem rede)."""
    if not _SCOPE.get():
        return
    with _LOCK:
        is_open = time.monotonic() < _open_until
    if not is_open:
        return
    log_provider_attempt("embedding", "jina", model, "circuit_open")
    _degraded("breaker_open", 0)
    raise EmbeddingSkipped("embedding breaker open")


def note_timeout(started: float) -> None:
    """Timeout da Jina dentro do escopo: abre o disjuntor (se ``B`` > 0) e registra o evento.

    ``started`` é um ``time.perf_counter()`` do início da tentativa."""
    if not _SCOPE.get():
        return
    global _open_until
    window = breaker_s()
    if window > 0:
        with _LOCK:
            _open_until = max(_open_until, time.monotonic() + window)
    _degraded("timeout", int((time.perf_counter() - started) * 1000))


def prefetch_wait(base: float) -> float:
    return max(base, query_timeout_s() + 0.5) if enabled() else base


def reset_for_tests() -> None:
    global _open_until
    with _LOCK:
        _open_until = 0.0
