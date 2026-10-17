"""Dossiês vivos do Codex e do Bestiário (SPEC-211).

Projeção SOMENTE LEITURA sobre o save, calculada sob demanda. Zero LLM, nada
persistido (sem migração). Toda entrada passa primeiro pela projeção
player-facing da SPEC-206 (`player_codex`): entidade `hidden`/`secret` não
revelada some inteira (nome, contagem, arte). Esta camada só ENRIQUECE entradas
já visíveis — nunca lê `hidden_traits`, `npc.memory` bruta, docs hidden/secret
nem cartas/resistências acima do revelado.

Vocabulário de conhecimento: `KnowledgeStamp` da SPEC-206, sem rótulos locais.
"""
from __future__ import annotations

import os
from typing import Any, Dict, List, Mapping, Optional

from services import discovery
from services import graph_resolver as gr
from services.chronicle import CHRONICLE_EVENT_TYPES
from services.entity_identity import resolve_npc_entity_id
from services.player_knowledge import entity_is_player_visible

MAX_ENCOUNTERS = 20

# Faixa de `relationship` (0–10, default 5) -> rótulo. Tabela fixa, sem LLM.
_DISPOSITION_BANDS = (
    (1, "Hostil"),
    (3, "Desconfiado"),
    (6, "Neutro"),
    (8, "Amistoso"),
    (10, "Leal"),
)

_EVENT_OUTCOME = {
    "npc_killed": "morreu",
    "quest_completed": "missão concluída",
    "quest_failed": "missão fracassada",
    "location_control_changed": "controle mudou",
    "secret_revealed": "segredo revelado",
}


def disposition_label(relationship: Any) -> str:
    try:
        value = int(relationship)
    except (TypeError, ValueError):
        value = 5
    value = max(0, min(10, value))
    for ceiling, label in _DISPOSITION_BANDS:
        if value <= ceiling:
            return label
    return _DISPOSITION_BANDS[-1][1]


def _turn(value: Any) -> Optional[int]:
    if isinstance(value, bool) or value is None:
        return None
    try:
        number = int(value)
    except (TypeError, ValueError):
        return None
    return number if number >= 0 else None


def _max_turn(*values: Any) -> int:
    turns = [t for t in (_turn(v) for v in values) if t is not None]
    return max(turns) if turns else 0


def _art(subject_type: str, subject_id: Optional[str]) -> Optional[dict]:
    """Arte só por ID canônico com asset público no catálogo (R9)."""
    if not subject_id:
        return None
    try:
        from services.visual_catalog import visual_for
        asset = visual_for(subject_type, subject_id)
    except Exception:
        return None
    if not asset:
        return None
    return {
        "asset_id": asset["asset_id"],
        "alt": asset.get("alt", ""),
        "placeholder_color": asset.get("placeholder_color"),
        "variants": asset.get("variants"),
    }


def _notes_turn(notes: List[dict]) -> int:
    return _max_turn(*[n.get("last_updated_turn") for n in notes])


def _events_about(state: Mapping, entity_id: Optional[str]) -> List[dict]:
    """Eventos canônicos de tipo público que citam a entidade (alvo)."""
    if not entity_id or not entity_is_player_visible(entity_id, state):
        return []
    out: List[dict] = []
    for event in state.get("event_log") or []:
        if not isinstance(event, Mapping) or event.get("target_id") != entity_id:
            continue
        etype = str(event.get("type") or "")
        if etype not in CHRONICLE_EVENT_TYPES or etype not in _EVENT_OUTCOME:
            continue
        turn = _turn(event.get("turn"))
        if turn is None:
            continue
        out.append({"turn": turn, "location_id": "", "outcome": _EVENT_OUTCOME[etype]})
    out.sort(key=lambda e: e["turn"])
    return out[-MAX_ENCOUNTERS:]


def _claim(note: Mapping) -> dict:
    knowledge = {k: v for k, v in note.items() if k not in ("memory_id", "text")}
    return {"text": note.get("text", ""), "knowledge": knowledge}


# ---------------------------------------------------------------------------
# NPC
# ---------------------------------------------------------------------------

def _npc_index(state: Mapping) -> Dict[str, tuple]:
    """nome exibível -> (chave, npc) dos NPCs do runtime."""
    out: Dict[str, tuple] = {}
    for key, npc in (state.get("npcs") or {}).items():
        if isinstance(npc, dict):
            out.setdefault(str(npc.get("name", key)), (key, npc))
    return out


def npc_dossier(entry: Mapping, state: Mapping, npc_index: Mapping) -> dict:
    """`entry` = entrada JÁ projetada (SPEC-206) do bloco `characters`."""
    from services.npc_layers import npc_alive
    name = str(entry.get("name", ""))
    key, npc = npc_index.get(name, (name, {}))
    entity_id = resolve_npc_entity_id(npc, name) if npc else None
    notes = list(entry.get("notes") or [])
    claims = [_claim(n) for n in notes]
    # R3: só observações do próprio jogador; nunca memória bruta/estado privado.
    appears = [_claim(n) for n in notes
               if n.get("source_kind") == "player_observation"
               and n.get("knowledge_kind") in ("perception", "suspicion")]
    encounters: List[dict] = []
    created = _turn(npc.get("created_turn"))
    if created is not None and (npc.get("knowledge_source", "met") or "met") == "met":
        encounters.append({"turn": created, "location_id": "", "outcome": "primeiro contato"})
    encounters += _events_about(state, entity_id)
    encounters.sort(key=lambda e: e["turn"])
    encounters = encounters[-MAX_ENCOUNTERS:]
    last_seen = _turn(npc.get("last_seen_turn"))
    updated = _max_turn(last_seen, created, _notes_turn(notes),
                        *[e["turn"] for e in encounters])
    relationship = npc.get("relationship", 5)
    status = "morto" if npc and not npc_alive(npc) else str(npc.get("status") or "")
    return {
        "id": entity_id or str(key), "kind": "npc", "title": name,
        "last_updated_turn": updated, "version": updated,
        "art": _art("npc", entity_id),
        "knowledge": entry["knowledge"], "notes": notes,
        "role": entry.get("role", ""), "location": entry.get("location", ""),
        "status": status,
        "relationship": int(relationship) if isinstance(relationship, (int, float)) else 5,
        "disposition_label": disposition_label(relationship),
        "knowledge_source": entry.get("knowledge_source", "met"),
        "revealed_traits": list(entry.get("revealed_traits") or []),
        "claims": claims, "appears_to_know": appears, "encounters": encounters,
        "last_seen_turn": last_seen, "body": entry.get("body", ""),
    }


# ---------------------------------------------------------------------------
# Local / Facção / Segredo
# ---------------------------------------------------------------------------

def location_dossier(entry: Mapping, state: Mapping, npcs: List[dict],
                     creatures: List[dict]) -> dict:
    loc_id = str(entry["id"])
    name = str(entry.get("name", loc_id))
    ent = gr.get_entity(loc_id) or {}
    region = ent.get("region") if isinstance(ent.get("region"), str) else ""
    here = [n["title"] for n in npcs if n.get("location") == name]
    seen = [c["title"] for c in creatures if loc_id in (c.get("regions") or [])]
    events = _events_about(state, loc_id)
    notes = list(entry.get("notes") or [])
    updated = _max_turn(_notes_turn(notes), *[e["turn"] for e in events])
    return {
        "id": loc_id, "kind": "location", "title": name,
        "last_updated_turn": updated, "version": updated,
        "art": _art("location", loc_id),
        "knowledge": entry["knowledge"], "notes": notes,
        "body": entry.get("body", ""), "region": region or "",
        "npcs": here, "creatures": seen, "events": events,
    }


def faction_dossier(entry: Mapping, state: Mapping) -> dict:
    fid = str(entry["id"])
    faction = next((f for f in state.get("factions") or []
                    if isinstance(f, dict) and f.get("id") == fid), {})
    intel = (state.get("faction_intel") or {}).get(fid) or {}
    knowledge = entry["knowledge"]
    seen = intel.get("progress_seen")
    stale = bool(knowledge.get("stale"))
    progress = None if (stale or seen is None) else int(seen)
    notes = list(entry.get("notes") or [])
    updated = _max_turn(intel.get("intel_turn"), _notes_turn(notes))
    return {
        "id": fid, "kind": "faction", "title": str(entry.get("name", fid)),
        "last_updated_turn": updated, "version": updated,
        "art": None, "knowledge": knowledge, "notes": notes,
        "body": entry.get("body", ""),
        "goal": entry.get("goal", ""), "knows_goal": bool(entry.get("knows_goal")),
        "region": str(faction.get("region", "")),
        "disposition": str(faction.get("disposition", "neutro")),
        "reputation": int(faction.get("reputation", 0) or 0),
        "progress": progress,
        "intel_stale": stale,
        "stale_label": "informação defasada" if stale else "",
    }


def secret_dossier(entry: Mapping) -> dict:
    knowledge = entry["knowledge"]
    entity_id = str(entry.get("entity_id", ""))
    ent = gr.get_entity(entity_id) or {}
    turn = _turn(entry.get("turn")) or 0
    return {
        "id": str(knowledge.get("source_ref") or entity_id), "kind": "secret",
        "title": str(ent.get("name") or entity_id),
        "last_updated_turn": turn, "version": turn,
        "art": None, "knowledge": knowledge, "notes": list(entry.get("notes") or []),
        "fact": entry.get("fact", ""), "entity_id": entity_id, "turn": turn,
    }


# ---------------------------------------------------------------------------
# Criatura (Bestiário)
# ---------------------------------------------------------------------------

def _revealed_for(base: Mapping, tier: int) -> tuple:
    """Cartas/resistências reveladas pelo bestiário (overlay) — só tier >= 2 e
    nunca as exclusivas de variante."""
    if tier < 2:
        return [], []
    # O overlay é escopo do dono LEGADO (jogador local único). Em perfil com
    # banco (multi-tenant) esse escopo é compartilhado: lê-lo mostraria a um
    # jogador o que outro revelou. Fail-closed até existir escopo por dono/jogo.
    if os.getenv("RPG_RUNTIME_PROFILE", "legacy").strip().lower() != "legacy":
        return [], []
    try:
        from services import bestiary_knowledge as bk
        from services import cards
        data = bk._load_all().get(bk._archetype_id(base), {})
        exclusive = set(base.get("variant_exclusive_cards") or [])
        out_cards: List[Dict[str, str]] = []
        for card_id in data.get("revealed_cards") or []:
            if card_id in exclusive:
                continue
            card = cards.get_card(str(card_id)) or {}
            if card:
                out_cards.append({"id": str(card_id), "name": str(card.get("name", card_id))})
        return out_cards, [str(r) for r in data.get("revealed_resistances") or []]
    except Exception:
        return [], []


def creature_dossier(entry: Mapping, state: Mapping) -> dict:
    cid = str(entry["id"])
    rec = (state.get("bestiary_knowledge") or {}).get(cid) or {}
    base = dict(discovery._bestiary_db().get(cid) or {})
    base.setdefault("id", cid)
    tier = int(entry["tier"])
    notes = list(entry.get("notes") or [])
    updated = _max_turn(rec.get("last_update_turn"), _notes_turn(notes))
    out: Dict[str, Any] = {
        "id": cid, "kind": "creature", "title": str(entry.get("name", "")),
        "last_updated_turn": updated, "version": updated,
        "art": _art("creature", cid),
        "knowledge": entry["knowledge"], "notes": notes,
        "tier": tier, "tier_name": entry["tier_name"],
        "regions": list(entry.get("regions") or []),
        "first_seen_turn": _turn(rec.get("first_seen_turn")),
    }
    if entry.get("rarity_note"):
        out["rarity_note"] = entry["rarity_note"]
    # Campos acima do tier: AUSENTES (chave não enviada), nunca máscara no cliente.
    for field in ("description", "type", "max_hp", "defense", "attacks", "behavior", "loot"):
        if field in entry:
            out[field] = entry[field]
    revealed_cards, revealed_res = _revealed_for(base, tier)
    if revealed_cards:
        out["revealed_cards"] = revealed_cards
    if revealed_res:
        out["revealed_resistances"] = revealed_res
    return out


# ---------------------------------------------------------------------------
# Crônica (índice por capítulo)
# ---------------------------------------------------------------------------

def chronicle_index(state: Mapping, known_ids: set) -> List[dict]:
    targets = {e.get("event_id"): e.get("target_id")
               for e in state.get("event_log") or [] if isinstance(e, Mapping)}
    out: List[dict] = []
    for cap in state.get("chronicle") or []:
        if not isinstance(cap, Mapping):
            continue
        entries = [e for e in cap.get("entries") or []
                   if isinstance(e, Mapping) and str(e.get("text", "")).strip()]
        ids: List[str] = []
        for e in entries:
            tid = targets.get(e.get("event_id"))
            if tid and tid in known_ids and tid not in ids:
                ids.append(str(tid))
        out.append({
            "chapter_id": str(cap.get("chapter_id", "")),
            "arc_title": str(cap.get("title", "")),
            "started_turn": _turn(cap.get("started_turn")) or 0,
            "location": str(cap.get("location", "")),
            "entry_count": len(entries),
            "entity_ids": ids,
        })
    return out


# ---------------------------------------------------------------------------
# Agregado
# ---------------------------------------------------------------------------

def build_dossiers(state: Mapping) -> dict:
    from services.player_knowledge import TAXONOMY_VERSION
    codex = discovery.player_codex(dict(state))  # já projetado + fail-closed
    npc_index = _npc_index(state)
    npcs: List[dict] = []
    for entry in codex["characters"]:
        try:
            npcs.append(npc_dossier(entry, state, npc_index))
        except Exception:  # dado malformado -> omite, nunca 500
            continue
    creatures = [creature_dossier(e, state) for e in codex["creatures"]]
    locations = [location_dossier(e, state, npcs, creatures) for e in codex["locations"]]
    factions = [faction_dossier(e, state) for e in codex["factions"]]
    secrets = [secret_dossier(e) for e in codex["secrets"]]
    known_ids = {d["id"] for d in npcs + locations + factions}
    every = npcs + locations + factions + secrets + creatures
    turn = _turn((state.get("world") or {}).get("turn_count")) or 0
    return {
        "version": _max_turn(*[d["version"] for d in every]),
        "generated_at_turn": turn,
        "sections": {
            "npcs": npcs, "locations": locations, "factions": factions,
            "secrets": secrets, "chronicle_index": chronicle_index(state, known_ids),
        },
        "bestiary": creatures,
        "meta": {"taxonomy_version": TAXONOMY_VERSION},
    }
