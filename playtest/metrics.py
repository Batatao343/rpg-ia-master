"""Métricas puras compartilhadas entre telemetria e oráculos do playtest."""

from __future__ import annotations

from typing import Iterable


def _field(record, name: str, default=0):
    if isinstance(record, dict):
        return record.get(name, default)
    return getattr(record, name, default)


def quest_request_conversion_count(records: Iterable, *, window: int = 3) -> int:
    """Associa pedido a criação de quest entre D+0 e D+``window``.

    Cada pedido e cada unidade criada são consumidos no máximo uma vez. Isso
    representa o fluxo real NPC(D) -> registro estruturado pelo grafo(D+1), sem
    inflar conversões quando há pedidos sobrepostos.
    """
    rows = list(records or [])
    creation_slots: list[int] = []
    for index, row in enumerate(rows):
        delta = max(
            0,
            int(_field(row, "quests_after", 0) or 0)
            - int(_field(row, "quests_before", 0) or 0),
        )
        creation_slots.extend([index] * delta)

    used: set[int] = set()
    conversions = 0
    for request_index, row in enumerate(rows):
        if not bool(_field(row, "quest_requested", False)):
            continue
        candidate = next(
            (
                slot_index
                for slot_index, creation_index in enumerate(creation_slots)
                if slot_index not in used
                and request_index <= creation_index <= request_index + int(window)
            ),
            None,
        )
        if candidate is not None:
            used.add(candidate)
            conversions += 1
    return conversions
