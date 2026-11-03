"""SPEC-387 R7: por que a oferta de retrato pago foi omitida (causa medida, sem id nem DSN)."""

from __future__ import annotations

from observability.telemetry import log_event, log_fallback

CAUSES = ("price_peek_failed", "registry_read_failed", "image_gate_failed", "switches_unreadable")


def offer_omitted(cause: str, exc: BaseException | None = None) -> None:
    """Registra a degradação (`creature_portrait.fallback`) e `creature_portrait.offer_omitted`."""
    if exc is not None:
        log_fallback("creature_portrait", cause, exc)
    log_event(
        "creature_portrait",
        "offer_omitted",
        level="warning",
        cause=cause,
        error_class=type(exc).__name__ if exc is not None else "",
    )
