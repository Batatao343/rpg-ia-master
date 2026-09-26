"""Request-scoped outbox: no SQL effects escape the canonical commit."""
from __future__ import annotations

from collections.abc import Callable, Iterator
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import replace
from threading import Lock
from typing import Any
from uuid import UUID

from infrastructure.contracts import Conflict, Principal
from services.memory_intents import MemoryIntentCollector


class TurnEffects:
    def __init__(self) -> None:
        self.memory = MemoryIntentCollector()
        self._writes: list[Callable] = []
        self._lock = Lock()

    def defer(self, write: Callable) -> None:
        with self._lock:
            self._writes.append(write)

    def flush(self, connection: Any, *, memory_store: Any, principal: Principal,
              game_id: UUID, epoch: int, version: int) -> None:
        for intent in self.memory.drain():
            if intent.game_id != game_id or intent.principal != principal:
                raise Conflict('effect_scope_mismatch')
            metadata = dict(intent.document.metadata)
            for name in ('provenance', 'confidence', 'source_id', 'source_turn', 'canonical_entity_ids'):
                if f'memory_{name}' in metadata:
                    metadata[name] = metadata[f'memory_{name}']
            if 'memory_entity_ids' in metadata:
                metadata['canonical_entity_ids'] = [
                    value.strip() for value in str(metadata['memory_entity_ids']).split(',') if value.strip()
                ]
            metadata.update(commit_version=version, timeline_epoch=epoch)
            memory_store.stage_on(connection, replace(intent, timeline_epoch=epoch,
                document=replace(intent.document, metadata=metadata,
                    document_id=f'{intent.document.document_id}:epoch:{epoch}')))
        for write in self._writes:
            write(connection, epoch, version)


_effects: ContextVar[TurnEffects | None] = ContextVar('turn_effects', default=None)


def current_effects() -> TurnEffects | None:
    return _effects.get()


@contextmanager
def effect_scope() -> Iterator[TurnEffects]:
    existing = current_effects()
    if existing is not None:
        yield existing
        return
    effects = TurnEffects()
    token = _effects.set(effects)
    try:
        yield effects
    finally:
        _effects.reset(token)
