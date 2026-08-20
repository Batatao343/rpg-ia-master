"""Digest derivado da crônica; raw e milestones permanecem autoritativos."""

from __future__ import annotations

import hashlib
import json
from typing import Any

from langchain_core.messages import HumanMessage, SystemMessage
from pydantic import BaseModel, Field

from llm_setup import ModelTier, get_llm
from services.chronicle import ensure_chronicle_ids


PROFILE_VERSION = "chronicle-digest-v1"


class ChronicleDigestLLM(BaseModel):
    short_title: str = Field(min_length=1, max_length=100)
    summary: str = Field(min_length=1, max_length=1800)
    characters: list[str] = Field(default_factory=list, max_length=30)
    locations: list[str] = Field(default_factory=list, max_length=30)
    quests: list[str] = Field(default_factory=list, max_length=30)
    unique_items: list[str] = Field(default_factory=list, max_length=30)


def chapter_source_hash(chapter: dict[str, Any]) -> str:
    raw = [{key: entry.get(key) for key in ("entry_id", "text", "turn", "kind", "event_id")}
           for entry in chapter.get("entries") or []]
    return hashlib.sha256(json.dumps(raw, ensure_ascii=False, sort_keys=True,
                                     separators=(",", ":")).encode()).hexdigest()


def should_compress(chapter: dict[str, Any], *, closed: bool = False) -> bool:
    entries = chapter.get("entries") or []
    covered = int((chapter.get("digest") or {}).get("covered_entry_count", 0) or 0)
    return bool(entries) and (closed or len(entries) - covered >= 20)


def _protected_milestones(chapter: dict[str, Any]) -> list[dict[str, Any]]:
    return [
        {key: entry.get(key) for key in ("entry_id", "event_id", "turn", "text")}
        for entry in chapter.get("entries") or [] if entry.get("kind") == "milestone"
    ]


def extractive_digest(chapter: dict[str, Any], *, status: str = "extractive_fallback") -> dict[str, Any]:
    entries = chapter.get("entries") or []
    prose = [str(entry.get("text", "")).strip() for entry in entries if entry.get("text")]
    selected = prose[:2] + (prose[-2:] if len(prose) > 2 else [])
    turns = [int(entry.get("turn", 0) or 0) for entry in entries]
    return {
        "version": 1, "source_hash": chapter_source_hash(chapter),
        "profile_version": PROFILE_VERSION, "status": status,
        "covered_entry_count": len(entries),
        "from_turn": min(turns, default=int(chapter.get("started_turn", 0) or 0)),
        "to_turn": max(turns, default=int(chapter.get("started_turn", 0) or 0)),
        "short_title": str(chapter.get("title") or "Crônica")[:100],
        "summary": " ".join(dict.fromkeys(selected))[:1800],
        "characters": [], "locations": [chapter.get("location")] if chapter.get("location") else [],
        "quests": [], "unique_items": [],
        "milestones": _protected_milestones(chapter),
        "milestone_entry_ids": [item.get("entry_id") for item in _protected_milestones(chapter)],
    }


def compress_chapter(chapter: dict[str, Any], *, llm=None) -> dict[str, Any]:
    chapter = ensure_chronicle_ids([chapter])[0]
    entries = chapter.get("entries") or []
    public_payload = [
        {"turn": entry.get("turn"), "kind": entry.get("kind"), "text": entry.get("text")}
        for entry in entries
    ]
    try:
        model = llm or get_llm(temperature=0.1, tier=ModelTier.SMART)
        result = model.with_structured_output(ChronicleDigestLLM).invoke([
            SystemMessage(content=(
                "Comprima somente a crônica fornecida em PT-BR. Não invente fatos, "
                "personagens, locais, missões ou itens. Poses/imagens não são parte desta tarefa."
            )),
            HumanMessage(content=json.dumps(public_payload, ensure_ascii=False)),
        ])
        if not isinstance(result, ChronicleDigestLLM):
            return extractive_digest(chapter)
    except Exception:
        return extractive_digest(chapter)
    digest = extractive_digest(chapter, status="ready")
    digest.update(result.model_dump())
    return digest
