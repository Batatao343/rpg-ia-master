"""
discovery.py — Codex do jogador + bestiário progressivo (Fase 3.2).

100% Python determinístico — zero LLM. Contadores por criatura (`bestiary_knowledge`)
alimentam graus de conhecimento; `player_codex` agrega o que o jogador já registrou
(locais visitados, fações conhecidas, NPCs, segredos revelados, criaturas) a partir
do que já está no save — sem estado novo além do bestiário.
Spec: specs/SPEC-007-fase-3.2-conhecimento-revelavel.md.
"""

from __future__ import annotations

import re
from typing import Dict, List, Optional

import gamedata
from services import graph_resolver as gr
from services.codex_loader import codex_body

def _bestiary_db() -> Dict:
    """spec isolar-cache-runtime (R2): view unificada curadoria ∪ overlay —
    criatura GERADA em jogo também entra no codex do jogador (lazy import p/
    não puxar o módulo de geração no import do serviço)."""
    from agents.bestiary import load_bestiary
    return load_bestiary() or {}


# grau -> (nome, contador, limiar)
BESTIARY_TIERS = {
    1: ("Rumores", "seen", 1),
    2: ("Encontrada", "fought", 1),
    3: ("Estudada", "defeated", 3),
    4: ("Dominada", "defeated", 7),
}


def normalize_bestiary_id(enemy: Dict) -> str:
    """Id de instância de combate -> chave real de data/bestiary.json.

    `enemy["id"]` de instância vem como `{bestiary_id}_{N}` (spawn em
    agents/combat.py). Tenta o id cru, depois sem sufixo numérico, depois slug
    do nome. Não achou no bestiário -> "" (criatura ad-hoc não entra no codex).
    """
    db = _bestiary_db()
    raw = str(enemy.get("id") or "").strip()
    if raw and raw in db:
        return raw
    base = re.sub(r"_\d+$", "", raw)
    if base and base in db:
        return base
    name = str(enemy.get("name") or "").strip()
    slug = re.sub(r"_\d+$", "", re.sub(r"\s+", "_", name.lower()))
    slug_id = f"enemy_{slug}" if slug and not slug.startswith("enemy_") else slug
    if slug_id and slug_id in db:
        return slug_id
    return ""


def _bump(bk: Dict, creature_id: str, turn: int, **deltas: int) -> Dict:
    entry = dict(bk.get(creature_id) or {})
    for field, delta in deltas.items():
        entry[field] = int(entry.get(field, 0)) + delta
    entry.setdefault("first_seen_turn", int(turn))
    entry["last_update_turn"] = int(turn)
    return entry


def record_encounter(bk: Dict, enemies: List[Dict], turn: int = 0) -> Dict:
    """Spawn de combate: cada criatura distinta ganha seen+1 e fought+1 (1x/combate)."""
    bk = dict(bk or {})
    seen_ids = set()
    for enemy in enemies:
        cid = normalize_bestiary_id(enemy)
        if not cid or cid in seen_ids:
            continue
        seen_ids.add(cid)
        bk[cid] = _bump(bk, cid, turn, seen=1, fought=1)
    return bk


def record_kills(bk: Dict, dead: List[Dict], turn: int = 0) -> Dict:
    """Uma instância morta = defeated+1 (conta por instância, não por espécie)."""
    bk = dict(bk or {})
    for enemy in dead:
        cid = normalize_bestiary_id(enemy)
        if not cid:
            continue
        bk[cid] = _bump(bk, cid, turn, defeated=1)
    return bk


def record_rumor(bk: Dict, creature_id: str, turn: int = 0) -> Dict:
    """Criatura nomeada num hint/alerta antes do combate: só seen+1."""
    if not creature_id:
        return dict(bk or {})
    bk = dict(bk or {})
    bk[creature_id] = _bump(bk, creature_id, turn, seen=1)
    return bk


def knowledge_tier(entry: Dict) -> int:
    """Maior grau alcançado pelos contadores. 0 = não mostra no codex."""
    entry = entry or {}
    tier = 0
    for level, (_name, field, threshold) in BESTIARY_TIERS.items():
        if int(entry.get(field, 0)) >= threshold:
            tier = max(tier, level)
    return tier


def bestiary_view(bk: Dict, turn: int = 0) -> List[Dict]:
    """Junta contadores + bestiário (curadoria ∪ overlay), revelando por grau.
    Fase 6.3: entrada ganha rótulo de raridade regional (pressão de caça)."""
    from services.ecology import regional_rarity_label
    db = _bestiary_db()
    out: List[Dict] = []
    for creature_id, entry in (bk or {}).items():
        tier = knowledge_tier(entry)
        if tier <= 0:
            continue
        base = db.get(creature_id)
        if not base:
            continue
        view: Dict = {
            "id": creature_id,
            "tier": tier,
            "tier_name": BESTIARY_TIERS[tier][0],
            "name": base.get("name", ""),
            "regions": base.get("regions", []),
        }
        rarity_note = regional_rarity_label(creature_id, bk, turn)
        if rarity_note:
            view["rarity_note"] = rarity_note
        if tier >= 2:
            view["description"] = base.get("description", "")
            view["type"] = base.get("type", "")
        if tier >= 3:
            view["max_hp"] = base.get("max_hp")
            view["defense"] = base.get("ac", base.get("defense"))
            view["attacks"] = [a.get("name", "") for a in (base.get("attacks") or [])]
        if tier >= 4:
            view["attacks"] = base.get("attacks", [])
            view["behavior"] = base.get("behavior", {})
            view["loot"] = base.get("loot", [])
        out.append(view)
    out.sort(key=lambda v: v["id"])
    return out


def _locations_block(state: Dict) -> List[Dict]:
    world = state.get("world") or {}
    out = []
    for loc_id in world.get("visited", []) or []:
        ent = gr.get_entity(loc_id)
        out.append({
            "id": loc_id,
            "name": (ent or {}).get("name", loc_id),
            "body": codex_body(loc_id),
        })
    return out


def _factions_block(state: Dict) -> List[Dict]:
    intel = state.get("faction_intel") or {}
    out = []
    for faction in state.get("factions") or []:
        if not isinstance(faction, dict) or faction.get("defeated"):
            continue
        fid = faction.get("id", "")
        rec = intel.get(fid, {})
        if not rec.get("known"):
            continue
        knows_goal = bool(rec.get("knows_goal"))
        out.append({
            "id": fid,
            "name": faction.get("name", ""),
            "goal": faction.get("goal", "") if knows_goal else "",
            "knows_goal": knows_goal,
            "body": codex_body(fid),
        })
    return out


def _characters_block(state: Dict) -> List[Dict]:
    out = []
    from services.npc_layers import trait_names
    from services.entity_identity import resolve_npc_entity_id
    for npc_name, npc in (state.get("npcs") or {}).items():
        if not isinstance(npc, dict):
            continue
        # spec npcs-3-camadas (R8): só camada 2 (conhecidos); traits só revelados
        if not npc.get("known_by_player", True):
            continue
        entity_id = resolve_npc_entity_id(npc, str(npc.get("name", npc_name)))
        out.append({
            "name": npc.get("name", npc_name),
            "role": npc.get("role", ""),
            "location": npc.get("location", ""),
            "knowledge_source": npc.get("knowledge_source", "met"),
            "revealed_traits": trait_names(npc.get("revealed_traits") or []),
            "body": codex_body(entity_id) if entity_id else "",
        })
    return out


def _secrets_block(state: Dict) -> List[Dict]:
    facts = ((state.get("world_projection") or {}).get("revealed_facts") or {})
    out = []
    for fact in facts.values():
        out.append({
            "entity_id": fact.get("entity_id", ""),
            "fact": fact.get("fact", ""),
            "turn": fact.get("revealed_at_turn", 0),
        })
    out.sort(key=lambda f: f["turn"])
    return out


def player_codex(state: Dict) -> Dict[str, List[Dict]]:
    """Codex agregado — só o que já está registrado no save. Zero LLM."""
    return {
        "locations": _locations_block(state),
        "factions": _factions_block(state),
        "characters": _characters_block(state),
        "creatures": bestiary_view(state.get("bestiary_knowledge") or {},
                                   turn=int((state.get("world") or {}).get("turn_count", 0) or 0)),
        "secrets": _secrets_block(state),
    }
