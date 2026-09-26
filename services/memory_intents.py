"""Normalização determinística de fatos antes do commit durável."""

from __future__ import annotations

import hashlib
import json
from dataclasses import replace
from threading import RLock

from infrastructure.contracts import Conflict, MemoryWriteIntent


def normalized_intent(intent: MemoryWriteIntent) -> MemoryWriteIntent:
    text = " ".join(intent.document.text.split()).strip()
    if not text:
        raise ValueError("fato vazio")
    metadata = dict(intent.document.metadata)
    visibility = metadata.get("visibility", "public")
    if visibility not in {"public", "hidden", "secret"}:
        raise ValueError("visibility inválida")
    document = replace(intent.document, text=text, metadata=metadata)
    return replace(intent, document=document)


def intent_sha256(intent: MemoryWriteIntent) -> str:
    normalized = normalized_intent(intent)
    body = {
        "id": normalized.document.document_id,
        "text": normalized.document.text,
        "scope": normalized.document.scope,
        "metadata": normalized.document.metadata,
        "owner_id": str(normalized.principal.user_id) if normalized.principal else None,
        "game_id": str(normalized.game_id) if normalized.game_id else None,
        "npc_id": normalized.npc_id,
        "timeline_epoch": normalized.timeline_epoch,
    }
    raw = json.dumps(body, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


class MemoryIntentCollector:
    def __init__(self) -> None:
        self._intents: dict[str, tuple[str, MemoryWriteIntent]] = {}
        self._lock = RLock()

    def add(self, intent: MemoryWriteIntent) -> None:
        normalized = normalized_intent(intent)
        digest = intent_sha256(normalized)
        with self._lock:
            existing = self._intents.get(normalized.document.document_id)
            if existing and existing[0] != digest:
                raise Conflict("memory_id reutilizado com conteúdo divergente")
            self._intents[normalized.document.document_id] = (digest, normalized)

    def drain(self) -> list[MemoryWriteIntent]:
        with self._lock:
            result = [item[1] for item in self._intents.values()]
            self._intents.clear()
        return result
