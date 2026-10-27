"""SPEC-336 R6: eventos de Carta no trace (SPEC-251) para pick rate / play rate.

Só ids de catálogo e contagens (nunca texto do jogador). Os eventos entram em
``observability/events.py`` (catálogo gerado) e são contados pelo ``playtest/`` via
``set_event_sink``. ``scripts/cards/metrics.py`` agrega a partir dos logs.
"""

from __future__ import annotations

import contextlib
import contextvars

from observability.telemetry import log_event

_source: contextvars.ContextVar[str] = contextvars.ContextVar("card_source", default="player")


@contextlib.contextmanager
def source_scope(source: str):
    """Marca a origem das escolhas (``auto`` = resolução automática, não é escolha do jogador)."""
    token = _source.set(source)
    try:
        yield
    finally:
        _source.reset(token)


def offered(card_ids: list[str], *, picked: str = "") -> None:
    """Cada Carta elegível apresentada numa escolha de nível (uma oferta por Carta)."""
    for cid in card_ids:
        log_event(
            "cards",
            "card_offered",
            card_id=str(cid),
            picked=str(cid) == str(picked),
            source=_source.get(),
        )


def picked(card_id: str) -> None:
    log_event("cards", "card_picked", card_id=str(card_id), source=_source.get())


def played(card_id: str, destino: str = "") -> None:
    """Carta jogada em conflito; ``destino`` = pilha (``descarte``/``exaurida``)."""
    log_event("cards", "card_played", card_id=str(card_id), pile=str(destino))
    if destino == "exaurida":
        exhausted(card_id)


def exhausted(card_id: str) -> None:
    log_event("cards", "card_exhausted", card_id=str(card_id))
