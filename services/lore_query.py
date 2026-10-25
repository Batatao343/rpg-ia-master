"""SPEC-311 R17-R25: query composta e preferência por região no RAG de lore.

Puro e determinístico: sem LLM, sem rede, sem RNG. A query só carrega o que o herói percebe
no lugar onde está (local, região, rótulo público do estado do local, estação, mês) mais o
input do jogador. Nunca estado de outro local, crise, pressão, facção ou número.
"""

from __future__ import annotations

import json
import os
import re
import unicodedata
from functools import cache

LORE_K: int = 3  # [BALANCEAR] chunks de lore por consulta (era 2)
LORE_QUERY_INPUT_MAX: int = 300  # [BALANCEAR] teto do input do jogador na query
RERANK_CANDIDATES: int = 6  # candidatos (já filtrados por visibilidade) antes da preferência

_ALIASES_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "data",
    "world",
    "region_lore_tags.json",
)


def slug(text: str) -> str:
    """Minúsculas, sem acento, não-alfanumérico vira `_` (sem `_` nas pontas)."""
    folded = unicodedata.normalize("NFKD", str(text or ""))
    folded = "".join(c for c in folded if not unicodedata.combining(c)).lower()
    return re.sub(r"[^a-z0-9]+", "_", folded).strip("_")


@cache
def _aliases() -> dict[str, tuple[str, ...]]:
    try:
        with open(_ALIASES_PATH, encoding="utf-8") as fh:
            raw = json.load(fh)
    except (OSError, ValueError):
        return {}
    return {
        str(k): tuple(slug(a) for a in v)
        for k, v in raw.items()
        if isinstance(v, list) and not str(k).startswith("_")
    }


def _identity_tags(region_id: str) -> frozenset[str]:
    """Tags que identificam a região em si: id, rótulo e aliases curados."""
    from services import world_pressures as wp

    out = {slug(region_id), slug(wp.region_label(region_id))}
    out.update(_aliases().get(region_id, ()))
    return frozenset(t for t in out if t)


@cache
def region_lore_tags(region_id: str) -> frozenset[str]:
    """R22: slugs que marcam um chunk como "desta região" (id, rótulo, locais, aliases)."""
    from services import world_pressures as wp

    if not region_id:
        return frozenset()
    out = set(_identity_tags(region_id))
    for loc in wp._map_index()[0].values():
        if loc.get("region_id") == region_id:
            out.add(slug(str(loc.get("id") or "")))
            out.add(slug(str(loc.get("name") or "")))
    out.discard("")
    return frozenset(out)


@cache
def _all_region_identity_tags() -> frozenset[str]:
    from services import world_pressures as wp

    out: set[str] = set()
    for rid in wp.region_ids():
        out |= _identity_tags(rid)
    return frozenset(out)


def _chunk_tags(doc) -> frozenset[str]:
    meta = getattr(doc, "metadata", None) or {}
    tags = meta.get("tags") or []
    if isinstance(tags, str):
        tags = [tags]
    try:
        return frozenset(t for t in (slug(str(x)) for x in tags) if t)
    except TypeError:
        return frozenset()


def rerank_by_region(docs: list, region_id: str | None, k: int) -> list:
    """R20/R21: ordenação estável em 3 faixas (da região · sem região · só de outra região).

    Opera sobre candidatos JÁ filtrados por visibilidade; nunca relaxa o filtro. Sem região (ou
    sem tags no metadado) é a ordem original, cortada em `k`."""
    docs = list(docs)
    if not region_id:
        return docs[:k]
    mine = region_lore_tags(region_id)
    every = _all_region_identity_tags()

    def band(doc) -> int:
        tags = _chunk_tags(doc)
        if tags & mine:
            return 0
        if tags & every:
            return 2
        return 1

    return sorted(docs, key=band)[:k]  # sorted é estável: a ordem do FAISS vale dentro da faixa


# --- query composta -------------------------------------------------------------------------


def _month_name(state: dict, world: dict) -> str:
    from services import world_calendar

    if world_calendar.mode() != "on":
        return ""
    day = int((world.get("world_clock") or {}).get("day", 1) or 1)
    cal = world_calendar.calendar_for_read((state or {}).get("world_sim"), day)
    if cal:
        return str(world_calendar.date_view(cal, day).get("month") or "")
    view = world.get("date")
    if isinstance(view, dict) and view.get("day") == day:
        return str(view.get("month") or "")
    return ""


def compose_lore_query(state: dict, base: str) -> str:
    """R17: local · região · rótulo do estado do local · estação · mês · `base` (truncada).

    Nunca levanta (erro devolve `base`). Parte repetida (já contida no que foi montado) é omitida."""
    try:
        import gamedata
        from services import location_states, world_calendar, world_engine
        from services import world_pressures as wp

        world = (state or {}).get("world") or {}
        loc_id = str(world.get("current_location_id") or "")
        loc_name = str((gamedata.get_location(loc_id) or {}).get("name") or "") or str(
            world.get("current_location") or ""
        )
        region = wp.region_of(loc_id)
        parts: list[str] = [loc_name]
        if region:
            parts.append(wp.region_label(region))
        if loc_id and world_engine.mode() == "on":
            parts.append(
                location_states.public_label(location_states.location_state(state, loc_id))
            )
        season = world_calendar.active_season(world)
        if season:
            parts.append(world_calendar.label_for(season, region))
        parts.append(_month_name(state, world))
        parts.append(str(base or "").strip()[:LORE_QUERY_INPUT_MAX])
        out: list[str] = []
        for part in (p.strip() for p in parts):
            if not part:
                continue
            if any(part.casefold() == seen.casefold() for seen in out):
                continue
            out.append(part)
        return " ".join(out)
    except Exception as exc:
        from observability.telemetry import log_fallback

        log_fallback("lore_query", "compose_failed", exc)
        return str(base or "").strip()[:LORE_QUERY_INPUT_MAX]
