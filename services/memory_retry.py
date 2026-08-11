"""Fila persistida e sanitizada de escritas RAG específicas de NPC.

Cada entrada representa exatamente uma operação ``add_npc_memory``. A fila é
pequena, deduplicada e não carrega texto livre além do fato observável já
sanitizado pelo nó de NPC.
"""
from __future__ import annotations

from typing import Dict, Iterable, List

MAX_PENDING_NPC_MEMORY = 50
MAX_NPC_ID_LENGTH = 120
MAX_MEMORY_FACT_LENGTH = 480


def _clean_text(value, *, limit: int) -> str:
    return " ".join(str(value or "").split())[:limit].strip()


def normalize_pending_npc_memory(rows: Iterable | None) -> List[Dict]:
    """Normaliza, deduplica e limita a fila, tolerando saves adulterados."""
    normalized: List[Dict] = []
    seen: set[tuple[str, str]] = set()
    for row in rows or []:
        if not isinstance(row, dict):
            continue
        if row.get("operation", "add_npc_memory") != "add_npc_memory":
            continue
        npc_id = _clean_text(row.get("npc_id"), limit=MAX_NPC_ID_LENGTH)
        raw_facts = row.get("facts")
        if isinstance(raw_facts, str):
            raw_facts = [raw_facts]
        if not npc_id or not isinstance(raw_facts, list):
            continue
        for raw_fact in raw_facts:
            if not isinstance(raw_fact, str):
                continue
            fact = _clean_text(raw_fact, limit=MAX_MEMORY_FACT_LENGTH)
            identity = (npc_id, fact)
            if not fact or identity in seen:
                continue
            seen.add(identity)
            normalized.append({
                "operation": "add_npc_memory",
                "npc_id": npc_id,
                "facts": [fact],
            })
    return normalized[-MAX_PENDING_NPC_MEMORY:]


def enqueue_npc_memory(rows: Iterable | None, npc_id: str, fact: str) -> List[Dict]:
    """Anexa uma escrita sem duplicá-la e reaplica o limite da fila."""
    return normalize_pending_npc_memory([
        *normalize_pending_npc_memory(rows),
        {
            "operation": "add_npc_memory",
            "npc_id": npc_id,
            "facts": [fact],
        },
    ])
