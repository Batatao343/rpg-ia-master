"""Busca híbrida rastreável e sem geração sobre a crônica."""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass
from typing import Any, Iterable

from services.chronicle import ensure_chronicle_ids


@dataclass(frozen=True)
class ChronicleCandidate:
    document_id: str
    chapter_id: str
    source_kind: str
    score: float


def normalize_query(query: str) -> str:
    value = " ".join(query.split()).strip()
    if not 2 <= len(value) <= 300:
        raise ValueError("query deve ter entre 2 e 300 caracteres")
    return value


def _terms(value: str) -> set[str]:
    ascii_value = unicodedata.normalize("NFKD", value).encode("ascii", "ignore").decode().lower()
    return {term for term in re.findall(r"[a-z0-9_-]+", ascii_value) if len(term) > 1}


def lexical_candidates(chronicle: list[dict[str, Any]], query: str) -> list[ChronicleCandidate]:
    wanted = _terms(normalize_query(query))
    candidates: list[ChronicleCandidate] = []
    for chapter in ensure_chronicle_ids(chronicle):
        chapter_id = chapter["chapter_id"]
        for entry in chapter.get("entries") or []:
            overlap = wanted & _terms(str(entry.get("text", "")))
            if overlap:
                candidates.append(ChronicleCandidate(
                    entry["entry_id"], chapter_id, "entry", len(overlap) / max(1, len(wanted)),
                ))
        digest = chapter.get("digest") or {}
        overlap = wanted & _terms(str(digest.get("summary", "")))
        if overlap:
            candidates.append(ChronicleCandidate(
                f"{chapter_id}:digest", chapter_id, "digest", len(overlap) / max(1, len(wanted)),
            ))
    return sorted(candidates, key=lambda item: (-item.score, item.document_id))


def reciprocal_rank_fusion(rankings: Iterable[list[ChronicleCandidate]], *, k: int = 60) -> list[tuple[str, float, set[str]]]:
    scores: dict[str, float] = {}
    sources: dict[str, set[str]] = {}
    labels = ("lexical", "semantic")
    for index, ranking in enumerate(rankings):
        label = labels[index] if index < len(labels) else f"rank{index}"
        for rank, item in enumerate(ranking, 1):
            scores[item.document_id] = scores.get(item.document_id, 0.0) + 1 / (k + rank)
            sources.setdefault(item.document_id, set()).add(label)
    return sorted(((key, score, sources[key]) for key, score in scores.items()),
                  key=lambda item: (-item[1], item[0]))


def search_chronicle(chronicle: list[dict[str, Any]], query: str, *, top_k: int = 5,
                     semantic: list[ChronicleCandidate] | None = None) -> dict[str, Any]:
    if not 1 <= top_k <= 10:
        raise ValueError("top_k deve estar entre 1 e 10")
    chapters = ensure_chronicle_ids(chronicle)
    lexical = lexical_candidates(chapters, query)
    fused = reciprocal_rank_fusion([lexical, semantic or []])[:top_k]
    documents: dict[str, tuple[dict, dict | None, str]] = {}
    for chapter in chapters:
        for entry in chapter.get("entries") or []:
            documents[entry["entry_id"]] = (chapter, entry, "entry")
        if chapter.get("digest"):
            documents[f"{chapter['chapter_id']}:digest"] = (chapter, None, "digest")
    hits = []
    for document_id, _score, sources in fused:
        chapter, entry, source_kind = documents[document_id]
        digest = chapter.get("digest") or {}
        text = entry.get("text", "") if entry else digest.get("summary", "")
        turns = [int(row.get("turn", 0) or 0) for row in chapter.get("entries") or []]
        hits.append({
            "chapter_id": chapter["chapter_id"], "chapter_title": chapter.get("title", ""),
            "snippet": str(text)[:500], "source_kind": source_kind,
            "from_turn": min(turns, default=int(chapter.get("started_turn", 0) or 0)),
            "to_turn": max(turns, default=int(chapter.get("started_turn", 0) or 0)),
            "entry_ids": [entry["entry_id"]] if entry else digest.get("milestone_entry_ids", []),
            "event_ids": [entry["event_id"]] if entry and entry.get("event_id") else [],
            "match_kind": "hybrid" if len(sources) > 1 else next(iter(sources)),
        })
    return {"mode": "hybrid" if semantic else "lexical_fallback",
            "index_current": bool(semantic), "hits": hits}
