"""SPEC-387 R7 / SPEC-389 R1-R2: por que a oferta de retrato pago foi omitida (causa medida).

Sem id de jogo, DSN nem nome. O `tally` por resposta (ContextVar) junta a causa do portao
(switch/preco/registro) com a de cada inimigo; `services.portrait_offer` emite 1 `offer_view`."""

from __future__ import annotations

from contextvars import ContextVar
from typing import Any

from observability.telemetry import log_event, log_fallback

CAUSES = ("price_peek_failed", "registry_read_failed", "image_gate_failed", "switches_unreadable")

_TALLY: ContextVar[dict[str, Any] | None] = ContextVar("portrait_offer_tally", default=None)


def tally() -> dict[str, Any] | None:
    return _TALLY.get()


def set_tally(value: dict[str, Any] | None) -> None:
    _TALLY.set(value)


def note_gate(cause: str, **extra: Any) -> None:
    """Guarda a causa do portao (a ultima vence) no tally da resposta, se houver."""
    current = _TALLY.get()
    if current is not None:
        if cause:
            current["gate"] = cause
        current.update(extra)


def log_offer_omitted(cause: str, exc: BaseException | None = None) -> None:
    """Registra a degradação (`creature_portrait.fallback`) e `creature_portrait.offer_omitted`."""
    note_gate(cause)
    if exc is not None:
        log_fallback("creature_portrait", cause, exc)
    log_event(
        "creature_portrait",
        "offer_omitted",
        level="warning",
        cause=cause,
        error_class=type(exc).__name__ if exc is not None else "",
    )
