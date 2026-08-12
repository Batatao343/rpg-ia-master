"""Identidade canônica de entidades visuais — nunca depende da prosa da LLM."""
from __future__ import annotations

import re
import unicodedata
from functools import lru_cache
from typing import Any, Mapping, Optional

from services import graph_resolver as gr


def normalize_entity_label(value: str) -> str:
    text = unicodedata.normalize("NFKD", str(value or ""))
    text = "".join(char for char in text if not unicodedata.combining(char))
    return re.sub(r"[^a-z0-9]+", " ", text.casefold()).strip()


@lru_cache(maxsize=1)
def _npc_index() -> tuple[dict[str, str], set[str]]:
    by_label: dict[str, str] = {}
    ids: set[str] = set()
    for entity_id, entity in gr.load_entities().items():
        if entity.get("type") != "npc":
            continue
        ids.add(entity_id)
        labels = [entity.get("name", ""), *(entity.get("aliases") or [])]
        # Títulos separados por vírgula também aceitam a forma sem pontuação.
        name = str(entity.get("name", ""))
        labels.append(name.replace(",", ""))
        for label in labels:
            normalized = normalize_entity_label(str(label))
            if normalized:
                by_label.setdefault(normalized, entity_id)
    return by_label, ids


def resolve_npc_entity_id(npc: Mapping[str, Any], fallback_name: str = "") -> Optional[str]:
    by_label, ids = _npc_index()
    explicit = str(npc.get("id") or "")
    if explicit in ids:
        return explicit
    for candidate in (npc.get("name"), fallback_name):
        normalized = normalize_entity_label(str(candidate or ""))
        if normalized in by_label:
            return by_label[normalized]
    return None
