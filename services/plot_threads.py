"""services/plot_threads.py — camada de trama do mundo (SPEC-350 §3.3/§3.4).

Catálogo curado `data/world/plot_threads.json` (tramas, portas, elenco, ondas) e
API pura sobre ele. Sem LLM, sem rede, sem RAG, sem escrita (R20/R26). Arquivo
ausente ou inválido -> catálogo vazio + `log_event("plot", "catalog_invalid")`.

Nada aqui devolve `segredo_*`, `secret_ids` nem texto de doc oculto (R25).
"""

from __future__ import annotations

import os
import unicodedata
from functools import lru_cache
from typing import Any, Literal

from pydantic import BaseModel

CATALOG_PATH = os.path.join("data", "world", "plot_threads.json")
MODES = ("off", "on")
PERSONA_MAX_CHARS = 400

LinkKind = Literal["divida", "emprego", "testemunha", "vizinhanca", "encomenda", "achado"]
Tier = Literal["nucleo", "ponte", "borda"]


class QuestHint(BaseModel, frozen=True):
    kind: Literal["investigar_rumor", "entregar_material", "escoltar"]
    anchor_id: str  # rumor_id | route_id | npc_id (o próprio âncora)


class PlotDoor(BaseModel, frozen=True):
    id: str
    anchor_npc_id: str
    location_id: str
    link_kind: LinkKind
    hook_public: str
    rumor_ids: tuple[str, ...] = ()
    quest_hint: QuestHint | None = None


class InspirationRef(BaseModel, frozen=True):
    fonte: str
    url: str
    o_que_inspirou: str


class PlotThread(BaseModel, frozen=True):
    id: str
    region_id: str
    title: str
    pergunta: str
    resumo_publico: str
    core: tuple[str, ...]
    borda: tuple[str, ...]
    portas: tuple[PlotDoor, ...]
    factions: tuple[str, ...]
    locations: tuple[str, ...]
    rumor_ids: tuple[str, ...]
    secret_ids: tuple[str, ...] = ()
    lore_refs: tuple[str, ...]
    lore_keyword: str
    postura_afinidade: tuple[str, ...] = ()
    inspiracoes: tuple[InspirationRef, ...] = ()


class ThreadRole(BaseModel, frozen=True):
    thread_id: str
    papel: str


class Voice(BaseModel, frozen=True):
    registro: str
    fala: str


class CastSheet(BaseModel, frozen=True):
    npc_id: str = ""
    tier: Tier
    threads: tuple[ThreadRole, ...]
    desejo: str
    medo: str
    segredo_topico: str
    segredo_doc_id: str = ""
    voz: Voice
    home_location_id: str
    archetype: str
    fonte: str


class Wave(BaseModel, frozen=True):
    order: int
    regions: tuple[str, ...]
    status: Literal["pending", "in_progress", "done"]
    spec: str = ""


class PlotCatalog(BaseModel, frozen=True):
    version: int = 1
    threads: tuple[PlotThread, ...] = ()
    cast: dict[str, CastSheet] = {}
    waves: tuple[Wave, ...] = ()
    excluded: dict[str, str] = {}


# --------------------------------------------------------------------------- #
# Modo e carga
# --------------------------------------------------------------------------- #
def mode() -> Literal["off", "on"]:
    """`RPG_PLOT_THREADS` efetivo (default `off`, D6)."""
    raw = os.getenv("RPG_PLOT_THREADS", "").strip().lower()
    return "on" if raw == "on" else "off"


def parse_catalog(raw: Any) -> PlotCatalog:
    """Valida o dict cru (preenche `npc_id` do elenco pela chave). Levanta se inválido."""
    if not isinstance(raw, dict):
        raise ValueError("catálogo não é objeto")
    data = dict(raw)
    cast = {}
    for key, sheet in (data.get("cast") or {}).items():
        cast[key] = {**sheet, "npc_id": key} if isinstance(sheet, dict) else sheet
    data["cast"] = cast
    return PlotCatalog.model_validate(data)


def _load(path: str) -> PlotCatalog:
    import json

    try:
        with open(path, encoding="utf-8") as f:
            return parse_catalog(json.load(f))
    except Exception as exc:  # arquivo ausente/inválido nunca derruba o jogo (R20)
        try:
            from observability.telemetry import log_event

            log_event("plot", "catalog_invalid", level="warning", error=type(exc).__name__)
        except Exception:
            pass
        return PlotCatalog()


@lru_cache(maxsize=1)
def catalog() -> PlotCatalog:
    return _load(CATALOG_PATH)


def clear_cache() -> None:
    catalog.cache_clear()
    _name_index.cache_clear()
    getattr(_public_docs, "cache_clear", lambda: None)()


def _fold(text: object) -> str:
    nfkd = unicodedata.normalize("NFKD", str(text or ""))
    stripped = "".join(c for c in nfkd if not unicodedata.combining(c)).casefold()
    return " ".join(stripped.split())


# --------------------------------------------------------------------------- #
# Consultas
# --------------------------------------------------------------------------- #
def threads_for_region(region_id: str) -> list[PlotThread]:
    return sorted((t for t in catalog().threads if t.region_id == region_id), key=lambda t: t.id)


def thread(thread_id: str) -> PlotThread | None:
    return next((t for t in catalog().threads if t.id == thread_id), None)


def cast_sheet(npc_id: str) -> CastSheet | None:
    return catalog().cast.get(str(npc_id or ""))


def _graph_names(npc_id: str) -> list[str]:
    try:
        from services import graph_resolver as gr

        ent = gr.get_entity(npc_id)
    except Exception:
        ent = None
    if not isinstance(ent, dict):
        return []
    return [str(ent.get("name") or ""), *[str(a) for a in ent.get("aliases") or []]]


@lru_cache(maxsize=1)
def _name_index() -> dict[str, str]:
    """nome/alias dobrado do grafo -> id do elenco (primeiro por ordem de id vence)."""
    out: dict[str, str] = {}
    for cid in sorted(catalog().cast):
        for name in _graph_names(cid):
            key = _fold(name)
            if key:
                out.setdefault(key, cid)
    return out


def sheet_for_row(state: dict, npc_key: str, row: dict) -> CastSheet | None:
    """R21: ficha por `row['id']`, depois `npc_ref`, depois nome dobrado (name + aliases)."""
    cast = catalog().cast
    if not cast:
        return None
    row = row if isinstance(row, dict) else {}
    rid = str(row.get("id") or "")
    if rid and rid in cast:
        return cast[rid]
    ref = rid or str(npc_key or "")
    if ref in cast:
        return cast[ref]
    idx = _name_index()
    cands = [_fold(c) for c in (row.get("name"), npc_key) if c]
    for key in cands:
        if key in idx:
            return cast[idx[key]]
    # Nome de uma palavra só ("Bors") que prefixa exatamente um nome do elenco.
    for key in cands:
        if key and " " not in key:
            hits = {cid for name, cid in idx.items() if name.startswith(key + " ")}
            if len(hits) == 1:
                return cast[hits.pop()]
    return None


def region_cast(region_id: str) -> list[str]:
    """R24: ids do elenco com alguma trama da região, em ordem de id."""
    tids = {t.id for t in threads_for_region(region_id)}
    return sorted(
        cid for cid, s in catalog().cast.items() if any(r.thread_id in tids for r in s.threads)
    )


def _anchor_blocked(state: dict, door: PlotDoor, thr: PlotThread) -> bool:
    """Morto, capturado, desertou ou fora da região (R25)."""
    from services import npc_world as nw

    ref = door.anchor_npc_id
    _key, row = nw._row_for(state, ref)
    sim = state.get("npc_sim") or {}
    if nw._is_dead(state, ref, row, sim):
        return True
    entry = (sim.get("npcs") or {}).get(ref) or {}
    if str(row.get("status") or "") == "capturado" or entry.get("status") == "capturado":
        return True
    aff = ((state.get("world_projection") or {}).get("npc_affiliations") or {}).get(ref)
    if aff and str(aff) not in thr.factions:
        return True
    sheet = cast_sheet(ref)
    where, travelling = nw.presence(state, ref)
    if travelling:
        return True
    where = where or (sheet.home_location_id if sheet else "")
    if where:
        from services import world_pressures as wp

        region = wp.region_of(where)
        if region and region != thr.region_id:
            return True
    return False


def plot_doors(
    region_id: str, *, state: dict | None = None, postura: str | None = None
) -> list[PlotDoor]:
    """R25: portas da região (afinidade de Postura primeiro, depois id). `off` -> []."""
    if mode() != "on":
        return []
    ranked: list[tuple[int, str, PlotDoor]] = []
    for thr in threads_for_region(region_id):
        pref = 0 if postura and postura in thr.postura_afinidade else 1
        for door in thr.portas:
            if state is not None and _anchor_blocked(state, door, thr):
                continue
            ranked.append((pref, door.id, door))
    ranked.sort(key=lambda t: (t[0], t[1]))
    return [d for _p, _i, d in ranked]


def public_thread_brief(thread_id: str) -> str:
    """R25: `title` + `resumo_publico` + `pergunta` (nunca segredo nem núcleo)."""
    thr = thread(thread_id)
    if thr is None:
        return ""
    return f"{thr.title}. {thr.resumo_publico} Em aberto: {thr.pergunta}"


def stake_line(sheet: CastSheet) -> str:
    """R23: linha de papel na trama (primeira trama do NPC)."""
    if not sheet.threads:
        return ""
    return f"O que está em jogo para você: {sheet.threads[0].papel}"


# --------------------------------------------------------------------------- #
# Linha de runtime para a SPEC-351
# --------------------------------------------------------------------------- #
@lru_cache(maxsize=1)
def _public_docs() -> dict[str, str]:
    """id -> caminho do doc `visibility: public` em data/codex/npcs (nunca oculto)."""
    from services.codex_loader import CODEX_DIR, parse_codex_file

    out: dict[str, str] = {}
    base = os.path.join(CODEX_DIR, "npcs")
    for root, _dirs, files in os.walk(base):
        for fname in sorted(files):
            if not fname.endswith(".md"):
                continue
            path = os.path.join(root, fname)
            try:
                fm, _body = parse_codex_file(path)
            except Exception:
                continue
            if fm.get("visibility") == "public" and fm.get("id"):
                out.setdefault(str(fm["id"]), path)
    return out


def _persona_of(npc_id: str) -> str:
    path = _public_docs().get(npc_id)
    if not path:
        return ""
    from services.codex_loader import parse_codex_file

    try:
        _fm, body = parse_codex_file(path)
    except Exception:
        return ""
    for para in body.split("\n\n"):
        text = para.strip()
        if text and not text.startswith("#"):
            return " ".join(text.split())[:PERSONA_MAX_CHARS]
    return ""


def cast_npc_row(npc_id: str, *, game_id: str, home_location_id: str = "") -> dict:
    """R25: linha de runtime determinística (sem LLM) do NPC do elenco; {} se desconhecido."""
    sheet = cast_sheet(npc_id)
    if sheet is None:
        return {}
    from services import npc_layers
    from services import npc_world as nw

    names = _graph_names(npc_id)
    thr = thread(sheet.threads[0].thread_id) if sheet.threads else None
    faction = nw.npc_faction({}, npc_id) or (thr.factions[0] if thr and thr.factions else "")
    home = home_location_id or sheet.home_location_id
    row = {
        "id": npc_id,
        "name": names[0] if names and names[0] else npc_id,
        "role": sheet.threads[0].papel if sheet.threads else "",
        "persona": _persona_of(npc_id),
        "faction_id": faction,
        "plot_sheet_id": npc_id,
        "initial_relationship": 5,
        "relationship": 5,
        "location": home,
        "memory": [],
        "attributes": {k: 10 for k in ("str", "dex", "con", "int", "wis", "cha")},
        "combat_stats": {"hp": 10, "ac": 10, "attacks": []},
    }
    return npc_layers.ensure_npc_fields(row, str(game_id), home_location_id=home)
