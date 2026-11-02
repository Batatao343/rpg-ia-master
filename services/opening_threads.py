"""services/opening_threads.py — menu de tramas da abertura (SPEC-351 R1–R4, R11, R13).

O motor oferece, sem LLM, um menu de "portas de trama" e de NPCs na borda da
trama da região de início; a LLM do prólogo só ESCOLHE por id. Fonte preferencial:
SPEC-350 (`services/plot_threads.py`, import opcional); sem ela, fallback de
leitura sobre sementes de rumor + grafo. O menu só carrega texto PÚBLICO: nunca
`truth`/`fonte`/`confiabilidade` de rumor, nunca entidade secreta/oculta/líder.
"""

from __future__ import annotations

import os
import re
import unicodedata
from functools import lru_cache
from typing import Any, TypedDict

from observability.telemetry import log_event as _log_event

MENU_MAX_DOORS = 6
MENU_MAX_NPCS = 4
LORE_TOKENS_MAX = 900
MENU_TOKENS_MAX = 350
ARCS_LEFT_DEFAULT = 2
_BACKSTORY_QUERY_WORDS = 12
_MODES = ("off", "shadow", "on")


class ThreadDoor(TypedDict):
    door_id: str
    kind: str  # "rumor" | "entity" | "door"
    name: str
    hook: str
    entity_ids: list[str]
    location_id: str
    playable: bool  # semente com gancho de quest (preferida no desempate)


class ThreadMenu(TypedDict):
    region_id: str
    start_location_id: str
    doors: list[ThreadDoor]
    npcs: list[dict]
    source: str  # "350" | "fallback"


def mode() -> str:
    """`RPG_OPENING_THREAD` = off | shadow | on (default on; inválido → on)."""
    raw = str(os.getenv("RPG_OPENING_THREAD", "on") or "on").strip().lower()
    return raw if raw in _MODES else "on"


def _fold(text: object) -> str:
    raw = unicodedata.normalize("NFKD", str(text or "").lower())
    return " ".join("".join(c for c in raw if not unicodedata.combining(c)).split())


def _tokens(text: str, min_len: int = 5) -> set[str]:
    return {t for t in re.findall(r"\w+", _fold(text)) if len(t) >= min_len}


def _estimate(text: str) -> int:
    from services.context_builder import estimate_tokens

    return estimate_tokens(text)


def _clip(text: object, limit: int) -> str:
    return " ".join(str(text or "").replace("<", " ").replace(">", " ").split())[:limit]


# --------------------------------------------------------------------------- #
# Fontes do mundo (todas públicas, todas com guarda de borda)
# --------------------------------------------------------------------------- #
def _population_api() -> Any | None:
    """Adaptador da SPEC-350: `services.plot_threads.plot_doors` (None se ausente)."""
    try:
        from services import plot_threads  # type: ignore[attr-defined]
    except ImportError:
        return None
    return plot_threads if callable(getattr(plot_threads, "plot_doors", None)) else None


def region_of_location(location_id: str) -> str:
    from services import world_pressures

    return world_pressures.region_of(location_id)


def start_of_region(region_name: str) -> tuple[str, str]:
    """(region_id, start_location_id) de uma região escolhida pelo NOME."""
    import gamedata

    loc = gamedata.start_location_for_region(region_name) or {}
    loc_id = str(loc.get("id") or "")
    return str(loc.get("region_id") or region_of_location(loc_id)), loc_id


@lru_cache(maxsize=1)
def _secret_entity_ids() -> frozenset[str]:
    from services.secret_signatures import SECRET_ENTITY_IDS

    return frozenset(i for ids in SECRET_ENTITY_IDS.values() for i in ids)


def _public_entity(ref: str) -> dict | None:
    from services import graph_resolver as gr

    ent = gr.get_entity(ref)
    if not isinstance(ent, dict) or str(ent.get("visibility", "public")) != "public":
        return None
    if ref in _secret_entity_ids():
        return None
    return ent


def _eligible_npc(ref: str, region_id: str) -> dict | None:
    """NPC na borda (R2): público, com casa na região, não líder, não secreto."""
    from services import npc_world

    ent = _public_entity(ref)
    if not ent or ent.get("type") != "npc" or npc_world.is_leader(ref):
        return None
    home = npc_world.home_of({}, ref)
    if not home or region_of_location(home) != region_id:
        return None
    return {
        "entity_id": ref,
        "name": _clip(ent.get("name"), 60),
        "role": codex_role(ref),
        "home_location_id": home,
    }


@lru_cache(maxsize=256)
def codex_role(ref: str) -> str:
    """Linha "Papel:" do Codex PÚBLICO do NPC; sem ela, "" (tags são ids, não texto de papel)."""
    path = os.path.join(os.path.dirname(os.path.abspath(__file__)), os.pardir, "data", "codex", "npcs", f"{ref}.md")
    try:
        with open(path, encoding="utf-8") as fh:
            raw = fh.read()
    except OSError:
        raw = ""
    if raw.startswith("---") and "visibility: public" in raw.split("---", 2)[1]:
        match = re.search(r"^Papel:\s*(.+)$", raw, re.MULTILINE)
        if match:
            return _clip(match.group(1), 120)
    return ""


def _fallback_doors(region_id: str) -> list[ThreadDoor]:
    from services import graph_resolver as gr
    from services import rumors
    from services.faction_gate import is_secret

    doors: list[ThreadDoor] = []
    for sid, seed in sorted(rumors.load_seeds().items()):
        if region_id not in (seed.get("regions") or []) or seed.get("family") != "lore":
            continue
        if rumors._secret_locked({}, seed):  # noqa: SLF001 — segredo ainda não revelado
            continue
        doors.append(
            ThreadDoor(
                door_id=sid,
                kind="rumor",
                name=_clip(seed.get("title"), 80),
                hook=_clip(seed.get("gist"), 200),  # NUNCA truth/fonte/confiabilidade
                entity_ids=[str(e) for e in (seed.get("entities") or [])][:4],
                location_id=str(seed.get("location_id") or ""),
                playable=bool(seed.get("quest_eligible")),
            )
        )
    for eid, ent in sorted(gr.load_entities().items()):
        if ent.get("type") not in ("faction", "item"):
            continue
        if region_id not in (ent.get("tags") or []):
            continue
        if _public_entity(eid) is None or (ent["type"] == "faction" and is_secret(eid)):
            continue
        doors.append(
            ThreadDoor(
                door_id=eid,
                kind="entity",
                name=_clip(ent.get("name"), 80),
                hook="",
                entity_ids=[eid],
                location_id="",
                playable=False,
            )
        )
    return doors


def _doors_350(api: Any, region_id: str) -> list[ThreadDoor]:
    try:
        try:
            rows = api.plot_doors(region_id, state={}, postura=None)
        except TypeError:
            rows = api.plot_doors(region_id)
    except Exception as exc:  # noqa: BLE001 — a 350 nunca derruba o prólogo
        _log_event("prologue", "thread.api_350_failed", level="warning", error=type(exc).__name__)
        return []
    out: list[ThreadDoor] = []
    for row in rows or []:
        if not isinstance(row, dict) or str(row.get("visibility", "public")) != "public":
            continue
        door_id = str(row.get("door_id") or row.get("thread_id") or "")
        if not door_id or not row.get("name"):
            continue
        out.append(
            ThreadDoor(
                door_id=door_id,
                kind="door",
                name=_clip(row.get("name"), 80),
                hook=_clip(row.get("hook"), 200),
                entity_ids=[str(e) for e in (row.get("entity_ids") or [])][:4],
                location_id=str(row.get("location_id") or ""),
                playable=True,
            )
        )
        out[-1]["_anchors"] = [str(a) for a in (row.get("anchor_npc_ids") or [])]  # type: ignore[typeddict-unknown-key]
    return out


def _rank(items: list, text_of, backstory: str) -> list:
    """Ordem determinística: casa tokens da descrição (≥ 5 letras) primeiro, depois id."""
    want = _tokens(backstory)

    def key(item):
        hits = len(want & _tokens(text_of(item))) if want else 0
        return (-hits, not item.get("playable", True), str(item.get("door_id") or item.get("entity_id") or ""))

    return sorted(items, key=key)


def thread_menu(region_id: str, *, backstory: str = "", start_location_id: str = "") -> ThreadMenu:
    """Menu determinístico de portas e NPCs da borda (R1/R2); sem LLM, sem rede."""
    from services import graph_resolver as gr
    from services import npc_world

    source = "fallback"
    api = _population_api()
    doors: list[ThreadDoor] = []
    anchors: list[str] = []
    if api is not None:
        doors = _doors_350(api, region_id)
        if doors:
            source = "350"
            for door in doors:
                anchors += door.pop("_anchors", [])  # type: ignore[misc]
    if not doors:
        doors = _fallback_doors(region_id)
    doors = _rank(doors, lambda d: f"{d['name']} {d['hook']}", backstory)[:MENU_MAX_DOORS]

    npcs: list[dict] = []
    seen: set[str] = set()
    pool = list(dict.fromkeys(anchors))
    if not pool:
        pool = sorted(
            eid for eid, ent in gr.load_entities().items() if ent.get("type") == "npc"
        )
    for ref in pool:
        if ref in seen:
            continue
        seen.add(ref)
        row = _eligible_npc(ref, region_id)
        if row:
            npcs.append(row)
    if not npcs and source == "350":  # âncoras da 350 sem casa válida → leitura do grafo
        for eid, ent in sorted(gr.load_entities().items()):
            if ent.get("type") == "npc" and not npc_world.is_leader(eid):
                row = _eligible_npc(eid, region_id)
                if row:
                    npcs.append(row)
    npcs = _rank(npcs, lambda n: f"{n['name']} {n['role']}", backstory)[:MENU_MAX_NPCS]
    return ThreadMenu(
        region_id=region_id,
        start_location_id=start_location_id,
        doors=doors,
        npcs=npcs,
        source=source,
    )


# --------------------------------------------------------------------------- #
# Blocos de prompt
# --------------------------------------------------------------------------- #
def _menu_text(doors: list[ThreadDoor], npcs: list[dict]) -> str:
    lines = ["<PORTAS_DE_TRAMA>"]
    for d in doors:
        hook = f" — {d['hook']}" if d["hook"] else ""
        lines.append(f"- id={d['door_id']} | {d['name']}{hook}")
    lines.append("</PORTAS_DE_TRAMA>")
    lines.append("<NPCS_DA_TRAMA>")
    for n in npcs:
        role = f" ({n['role']})" if n["role"] else ""
        lines.append(f"- entity_id={n['entity_id']} | {n['name']}{role}")
    lines.append("</NPCS_DA_TRAMA>")
    return "\n".join(lines)


def menu_block(menu: ThreadMenu) -> str:
    doors, npcs = list(menu["doors"]), list(menu["npcs"])
    text = _menu_text(doors, npcs)
    if _estimate(text) > MENU_TOKENS_MAX:  # 1º corta os ganchos longos, só então remove itens
        doors = [{**d, "hook": d["hook"][:80]} for d in doors]
        text = _menu_text(doors, npcs)
    while _estimate(text) > MENU_TOKENS_MAX and (len(npcs) > 1 or len(doors) > 1):
        if len(npcs) > 1:
            npcs.pop()
        else:
            doors.pop()
        text = _menu_text(doors, npcs)
    return text


def lore_block(menu: ThreadMenu, backstory: str) -> str:
    """Exatamente 1 consulta RAG pública, preferindo a região; cortada no teto."""
    from rag import query_rag

    words = re.findall(r"\w+", str(backstory or ""))[:_BACKSTORY_QUERY_WORDS]
    query = " ".join([*(d["name"] for d in menu["doors"]), *words]).strip()
    if not query:
        return ""
    try:
        text = str(
            query_rag(
                query,
                index_name="lore",
                max_visibility="public",
                prefer_region=menu["region_id"] or None,
            )
            or ""
        )
    except Exception as exc:  # noqa: BLE001 — sem RAG o prólogo segue só com o menu
        _log_event("prologue", "thread.rag_failed", level="warning", error=type(exc).__name__)
        return ""
    words_all = text.split()
    while words_all and _estimate(" ".join(words_all)) > LORE_TOKENS_MAX:
        words_all = words_all[: int(len(words_all) * 0.85)]
    return " ".join(words_all).replace("<", " ").replace(">", " ")


# --------------------------------------------------------------------------- #
# Ficha do NPC da trama (R11)
# --------------------------------------------------------------------------- #
def plot_npc_sheet(npc: dict, game_id: str, start_location_id: str) -> dict:
    """Ficha local de um NPC do menu: id do grafo, stub, `in_scene` só na casa (D2)."""
    from services import npc_layers

    home = str(npc.get("home_location_id") or "")
    sheet = {
        "id": npc["entity_id"],
        "name": npc["name"],
        "role": npc.get("role") or "",
        "persona": "Figura conhecida na região; ainda pouco revelada ao herói.",
        "initial_relationship": 5,
        "relationship": 5,
        "location": home,
        "memory": [],
        "sheet_status": "stub",
        "attributes": {k: 10 for k in ("str", "dex", "con", "int", "wis", "cha")},
        "combat_stats": {"hp": 10, "ac": 10, "attacks": []},
    }
    sheet = npc_layers.ensure_npc_fields(
        sheet, game_id, home_location_id=home, in_scene=bool(home and home == start_location_id)
    )
    sheet["known_by_player"] = True
    return sheet


# --------------------------------------------------------------------------- #
# Planejador (R13)
# --------------------------------------------------------------------------- #
def _door_name(ref: str) -> str:
    from services import graph_resolver as gr
    from services import rumors

    seed = rumors.load_seeds().get(ref)
    if seed:
        return _clip(seed.get("title"), 80)
    ent = gr.get_entity(ref)
    if isinstance(ent, dict) and str(ent.get("visibility", "public")) == "public":
        return _clip(ent.get("name"), 80)
    api = _population_api()
    brief = getattr(api, "public_thread_brief", None) if api else None
    if callable(brief):
        try:
            info = brief(ref)
            return _clip(info.get("name") if isinstance(info, dict) else info, 80)
        except Exception:  # noqa: BLE001
            return ""
    return ""


def active_thread(state: dict) -> dict | None:
    """O fio de abertura, se ainda vivo e o herói está na região dele."""
    thread = ((state or {}).get("campaign_plan") or {}).get("opening_thread")
    if not isinstance(thread, dict) or int(thread.get("arcs_left", 0) or 0) <= 0:
        return None
    here = str(((state or {}).get("world") or {}).get("current_location_id") or "")
    if thread.get("region_id") and region_of_location(here) != thread["region_id"]:
        return None
    return thread


def door_names(thread: dict) -> list[str]:
    return [n for n in (_door_name(r) for r in thread.get("thread_refs") or []) if n]


def planner_thread_block(state: dict) -> str:
    """Bloco `<FIO_DE_ABERTURA>` para o planejador; "" sem fio ativo."""
    thread = active_thread(state)
    if not thread:
        return ""
    names = door_names(thread)
    npcs = (state or {}).get("npcs") or {}
    keys = [k for k in (thread.get("plot_npc_key"), thread.get("personal_npc_key")) if k]
    who = [str((npcs.get(k) or {}).get("name") or k) for k in keys]
    lines = ["<FIO_DE_ABERTURA>"]
    if names:
        lines.append(f"Tramas do mundo em que o herói tocou: {', '.join(names)}.")
    if who:
        lines.append(f"Personagens do fio: {', '.join(who)}.")
    if thread.get("seeking"):
        lines.append(f"O herói busca: {_clip(thread['seeking'], 200)}")
    lines.append(
        "Continue esta trama pelos beats, revelando-a aos poucos e ainda na borda; "
        "sem profecia, sem escolhido."
    )
    lines.append("</FIO_DE_ABERTURA>")
    return "\n".join(lines)


def consume_thread(plan: dict, state: dict) -> dict:
    """Plano novo herda o fio com `arcs_left - 1` (só se o bloco foi usado)."""
    thread = active_thread(state)
    if not thread:
        return plan
    new = dict(thread)
    new["arcs_left"] = max(0, int(thread.get("arcs_left", 0)) - 1)
    return {**plan, "opening_thread": new}
