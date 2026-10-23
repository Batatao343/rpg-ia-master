"""shared_pool_store.py — armazenamento do pool compartilhado (SPEC-297 §3).

`SharedPoolStore` é a porta; `JsonSharedPoolStore` é o adapter do perfil legacy
(um JSON no diretório de cache de runtime, lock + escrita atômica). O adapter
Postgres vive no mesmo módulo (`PostgresSharedPoolStore`, RLS na migração).

Regras da porta:
- `insert`/`update` não aplicam política (quem decide é `services/shared_pool`);
- o único bloqueio aqui é a imutabilidade de conteúdo de entrada `promoted` (R26):
  `update` recusa alterar `document`/`name`/`legend`/`seed` de uma promovida.
"""

from __future__ import annotations

import json
import threading
from collections.abc import Callable, Iterable
from datetime import datetime
from pathlib import Path
from typing import Any, Protocol
from uuid import UUID

from services.shared_pool_models import PoolNamespace, PoolStatus, SharedPoolEntry

IMMUTABLE_AFTER_PROMOTION = frozenset(
    {"document", "name", "name_fold", "legend", "seed", "seed_signature", "namespace", "region_id"}
)


class PoolImmutableError(ValueError):
    """Tentativa de alterar o conteúdo de uma entrada promovida (R26)."""


class SharedPoolStore(Protocol):
    def insert(self, entry: SharedPoolEntry) -> None: ...

    def get(self, entry_id: str) -> SharedPoolEntry | None: ...

    def update(self, entry_id: str, fields: dict[str, Any]) -> SharedPoolEntry: ...

    def select(
        self,
        *,
        namespace: PoolNamespace | None = None,
        statuses: Iterable[PoolStatus] | None = None,
        region_id: str | None = None,
        name_fold: str | None = None,
        seed_signature: str | None = None,
        origin_game_id: str | None = None,
        limit: int | None = None,
    ) -> list[SharedPoolEntry]: ...

    def due(self, now: datetime, limit: int) -> list[SharedPoolEntry]: ...

    def count_submissions(self, owner_id: UUID | None, since: datetime) -> int: ...

    def count_evaluated(self, since: datetime) -> int: ...


def _check_immutable(current: SharedPoolEntry, fields: dict[str, Any]) -> None:
    if current.status == PoolStatus.PROMOTED and IMMUTABLE_AFTER_PROMOTION & set(fields):
        raise PoolImmutableError("entrada promovida é imutável (R26)")


class JsonSharedPoolStore:
    """Perfil legacy: `{"entries": {entry_id: {...}}}` num arquivo JSON."""

    def __init__(self, path_provider: Callable[[], str | Path]) -> None:
        self._path_provider = path_provider
        self._lock = threading.RLock()

    @property
    def path(self) -> Path:
        return Path(self._path_provider())

    def _load(self) -> dict[str, dict]:
        path = self.path
        if not path.exists():
            return {}
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return {}
        entries = data.get("entries") if isinstance(data, dict) else None
        return entries if isinstance(entries, dict) else {}

    def _save(self, entries: dict[str, dict]) -> None:
        from infrastructure.local_adapters import _atomic_json

        _atomic_json(self.path, {"entries": entries})

    @staticmethod
    def _dump(entry: SharedPoolEntry) -> dict:
        return json.loads(entry.model_dump_json())

    def insert(self, entry: SharedPoolEntry) -> None:
        with self._lock:
            entries = self._load()
            if entry.entry_id in entries:
                raise ValueError("entry_id duplicado")
            entries[entry.entry_id] = self._dump(entry)
            self._save(entries)

    def get(self, entry_id: str) -> SharedPoolEntry | None:
        with self._lock:
            raw = self._load().get(entry_id)
        return SharedPoolEntry.model_validate(raw) if raw else None

    def update(self, entry_id: str, fields: dict[str, Any]) -> SharedPoolEntry:
        with self._lock:
            entries = self._load()
            raw = entries.get(entry_id)
            if raw is None:
                raise KeyError(entry_id)
            current = SharedPoolEntry.model_validate(raw)
            _check_immutable(current, fields)
            merged = SharedPoolEntry.model_validate({**current.model_dump(mode="json"), **fields})
            entries[entry_id] = self._dump(merged)
            self._save(entries)
            return merged

    def _all(self) -> list[SharedPoolEntry]:
        with self._lock:
            raws = list(self._load().values())
        out = [SharedPoolEntry.model_validate(raw) for raw in raws]
        out.sort(key=lambda e: (e.created_at, e.entry_id))
        return out

    def select(
        self,
        *,
        namespace: PoolNamespace | None = None,
        statuses: Iterable[PoolStatus] | None = None,
        region_id: str | None = None,
        name_fold: str | None = None,
        seed_signature: str | None = None,
        origin_game_id: str | None = None,
        limit: int | None = None,
    ) -> list[SharedPoolEntry]:
        wanted = set(statuses) if statuses is not None else None
        out = []
        for entry in self._all():
            if namespace is not None and entry.namespace != namespace:
                continue
            if wanted is not None and entry.status not in wanted:
                continue
            if region_id is not None and entry.region_id != region_id:
                continue
            if name_fold is not None and entry.name_fold != name_fold:
                continue
            if seed_signature is not None and entry.seed_signature != seed_signature:
                continue
            if origin_game_id is not None and entry.origin_game_id != origin_game_id:
                continue
            out.append(entry)
            if limit is not None and len(out) >= limit:
                break
        return out

    def due(self, now: datetime, limit: int) -> list[SharedPoolEntry]:
        out = [e for e in self._all() if e.status == PoolStatus.HELD and e.promote_after <= now]
        return out[: max(0, limit)]

    def count_submissions(self, owner_id: UUID | None, since: datetime) -> int:
        return sum(
            1
            for e in self._all()
            if e.origin_owner_id == owner_id
            and e.created_at >= since
            and e.status != PoolStatus.LOCAL_ONLY
        )

    def count_evaluated(self, since: datetime) -> int:
        return sum(1 for e in self._all() if e.evaluated_at is not None and e.evaluated_at >= since)
