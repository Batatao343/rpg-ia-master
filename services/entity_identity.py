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


def normalize_runtime_npc_ref(value: str) -> str:
    """Nome/ID runtime na mesma chave semântica, incluindo prefixos legados."""
    parts = normalize_entity_label(value).split()
    while parts and parts[0] in {"npc", "mv"}:
        parts.pop(0)
    return " ".join(parts)


def runtime_npc_aliases(key: str, npc: Mapping[str, Any] | None = None) -> set[str]:
    row = npc or {}
    known_aliases = row.get("aliases") or []
    if not isinstance(known_aliases, (list, tuple)):
        known_aliases = []
    return {
        alias
        for value in (key, row.get("id"), row.get("name"), *known_aliases)
        if (alias := normalize_runtime_npc_ref(str(value or "")))
    }


def find_runtime_npc_key(
    npcs: Mapping[str, Any] | None,
    reference: str,
    candidate: Mapping[str, Any] | None = None,
) -> Optional[str]:
    """Resolve referência por chave, nome ou id para UMA ficha já existente."""
    wanted = runtime_npc_aliases(reference, candidate)
    if not wanted:
        return None
    for key, row in (npcs or {}).items():
        if isinstance(row, Mapping) and wanted & runtime_npc_aliases(str(key), row):
            return str(key)
    return None


_NPC_DYNAMIC_FIELDS = {
    "home_location_id", "location", "in_scene", "last_seen_turn",
    "last_interaction", "status", "relationship", "interaction_count",
    "known_by_player", "knowledge_source", "active_conditions",
    "vitalidade", "max_vitalidade", "ferimentos", "ferimento_espacos",
}


def _merge_runtime_npc(primary: dict, incoming: dict) -> dict:
    """Prefere a ficha de origem mais antiga; dinâmica vem do último encontro.

    Sem datas de criação confiáveis, mantém a primeira identidade (não é
    possível deduzir a aparência verdadeira de duas descrições livres).
    """
    primary_created = primary.get("created_turn")
    incoming_created = incoming.get("created_turn")
    if (
        isinstance(primary_created, int)
        and isinstance(incoming_created, int)
        and incoming_created < primary_created
    ):
        primary, incoming = incoming, primary
    merged = dict(primary)
    merged["aliases"] = sorted(
        runtime_npc_aliases("", primary) | runtime_npc_aliases("", incoming)
    )
    for key, value in incoming.items():
        if key not in merged or merged[key] in (None, "", [], {}):
            merged[key] = value
    primary_seen = int(primary.get("last_seen_turn", -1)) if primary.get("last_seen_turn") is not None else -1
    incoming_seen = int(incoming.get("last_seen_turn", -1)) if incoming.get("last_seen_turn") is not None else -1
    if incoming_seen >= primary_seen:
        for key in _NPC_DYNAMIC_FIELDS:
            if key in incoming:
                merged[key] = incoming[key]
    created = [
        int(value) for value in (primary.get("created_turn"), incoming.get("created_turn"))
        if isinstance(value, int)
    ]
    if created:
        merged["created_turn"] = min(created)
    for field in ("memory", "revealed_traits"):
        values = [
            *list(primary.get(field) or []),
            *list(incoming.get(field) or []),
        ]
        if values:
            merged[field] = list(dict.fromkeys(
                value for value in values if isinstance(value, str) and value
            ))
    return merged


def coalesce_runtime_npcs(npcs: Mapping[str, Any] | None) -> dict[str, Any]:
    """Remove aliases duplicados do mesmo NPC, preservando a primeira chave."""
    out: dict[str, Any] = {}
    for raw_key, raw_row in (npcs or {}).items():
        key = str(raw_key)
        if not isinstance(raw_row, Mapping):
            out[key] = raw_row
            continue
        row = dict(raw_row)
        row["aliases"] = sorted(runtime_npc_aliases(key, row))
        existing = find_runtime_npc_key(out, key, row)
        if existing is None:
            out[key] = row
        else:
            merged = _merge_runtime_npc(dict(out[existing]), row)
            # A bridge may join multiple groups already seen. Preserve the
            # first runtime key, not the incidental order of the alias rows.
            while True:
                aliases = runtime_npc_aliases(existing, merged)
                linked = next((other for other, value in out.items()
                               if other != existing and isinstance(value, Mapping)
                               and aliases & runtime_npc_aliases(other, value)), None)
                if linked is None:
                    break
                merged = _merge_runtime_npc(merged, dict(out.pop(linked)))
            out[existing] = merged
    return out


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
