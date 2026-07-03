"""
quest_log.py — Side quests persistentes (Fase 3.3).

Main quest = view derivada do campaign_plan (api.py). Side quests são estado novo
(`GameState.quests`), propostas pelo LLM (storyteller/npc_actor) e validadas/criadas
aqui — 100% Python determinístico, funções puras (dict novo, nunca mutam argumento).

Conclusão de quest reusa o pipeline de eventos estruturados (Fase 2.6): o LLM propõe
`ProposedWorldEvent(type="quest_completed", target_id=<quest_id>, payload={"quest_id":
...})`; `services/event_processor.py` chama `complete_quest` quando o evento é aplicado.
Falha sistêmica (`fail_orphan_quests`) roda após `npc_killed` aplicado — 100% sistêmico,
nunca passa pelo pipeline de propostas do LLM (`source="system"`).

Spec: specs/fase-3.3-quest-log.md §3.
"""

from __future__ import annotations

import difflib
import uuid
from typing import Dict, List, Tuple, Union

import gamedata
from services import graph_resolver as gr

MAX_ACTIVE_QUESTS = 8
TITLE_SIMILARITY = 0.75


def _as_dict(proposal: Union[Dict, object]) -> Dict:
    """Normaliza ProposedQuest (Pydantic) ou dict cru pro mesmo formato."""
    if hasattr(proposal, "model_dump"):
        return proposal.model_dump()
    return dict(proposal or {})


def _valid_location_ids() -> set:
    locations = (gamedata.WORLD_MAP or {}).get("locations", [])
    return {loc.get("id") for loc in locations if isinstance(loc, dict) and loc.get("id")}


def _valid_entity_ids() -> set:
    try:
        return set(gr.load_entities().keys())
    except Exception:
        return set()


def register_proposed_quests(quests: List[Dict], proposals: List, *, turn: int = 0) -> Tuple[List[Dict], List[Dict]]:
    """PURO. Valida/cria side quests a partir de propostas do LLM.

    Retorna (lista_nova, criadas). Regras (nunca levanta, só ignora ou zera campo):
    - título vazio -> ignora
    - similaridade de título (SequenceMatcher >= 0.75) contra quests ATIVAS -> ignora
    - location_id fora de data/world_map.json -> ""
    - origin_entity_id fora do grafo canônico -> ""
    - já no teto de ativas (MAX_ACTIVE_QUESTS) -> ignora com log
    """
    quests = list(quests or [])
    created: List[Dict] = []
    if not proposals:
        return quests, created

    valid_locs = _valid_location_ids()
    valid_entities = _valid_entity_ids()

    for raw in proposals:
        p = _as_dict(raw)
        title = str(p.get("title") or "").strip()
        if not title:
            continue

        active_titles = [q for q in quests if q.get("status") == "active"]
        if any(difflib.SequenceMatcher(None, title.lower(), q.get("title", "").lower()).ratio()
               >= TITLE_SIMILARITY for q in active_titles):
            print(f"🚫 [QUEST] proposta ignorada (duplicata por similaridade): {title!r}")
            continue

        if len(active_titles) >= MAX_ACTIVE_QUESTS:
            print(f"🚫 [QUEST] teto de {MAX_ACTIVE_QUESTS} quests ativas — ignorada: {title!r}")
            continue

        location_id = str(p.get("location_id") or "")
        if location_id and location_id not in valid_locs:
            location_id = ""
        origin_entity_id = str(p.get("origin_entity_id") or "")
        if origin_entity_id and origin_entity_id not in valid_entities:
            origin_entity_id = ""

        quest = {
            "id": uuid.uuid4().hex,
            "title": title,
            "description": str(p.get("description") or ""),
            "status": "active",
            "origin_name": str(p.get("origin_name") or ""),
            "origin_entity_id": origin_entity_id,
            "location_id": location_id,
            "created_turn": int(turn),
            "resolved_turn": 0,
            "reward_hint": str(p.get("reward_hint") or ""),
        }
        quests = quests + [quest]
        created.append(quest)

    return quests, created


def complete_quest(quests: List[Dict], quest_id: str, turn: int = 0) -> List[Dict]:
    """PURO. Quest ATIVA com esse id -> completed. Id ausente/já resolvida -> sem mudança."""
    out = []
    for q in quests or []:
        if q.get("id") == quest_id and q.get("status") == "active":
            q = {**q, "status": "completed", "resolved_turn": int(turn)}
        out.append(q)
    return out


def fail_orphan_quests(quests: List[Dict], dead_entity_id: str, turn: int = 0) -> Tuple[List[Dict], List[Dict]]:
    """PURO. Quests ATIVAS com origin_entity_id == dead_entity_id -> failed.

    Retorna (lista_nova, eventos `quest_failed` — 1 por quest, source="system").
    Id vazio nunca casa (quest sem origem canônica não falha sistemicamente).
    """
    if not dead_entity_id:
        return list(quests or []), []
    out = []
    events: List[Dict] = []
    for q in quests or []:
        if q.get("status") == "active" and q.get("origin_entity_id") == dead_entity_id:
            q = {**q, "status": "failed", "resolved_turn": int(turn)}
            events.append({
                "event_id": uuid.uuid4().hex,
                "turn": int(turn),
                "type": "quest_failed",
                "actor_id": "system",
                "target_id": dead_entity_id,
                "payload": {"quest_id": q["id"], "quest_title": q.get("title", ""),
                           "reason": "origin_killed"},
                "source": "system",
            })
        out.append(q)
    return out, events


def quest_markers(quests: List[Dict]) -> List[Dict]:
    """Quests ativas com local válido -> [{"quest_id", "location_id"}] pro mapa."""
    return [{"quest_id": q["id"], "location_id": q["location_id"]}
            for q in (quests or [])
            if q.get("status") == "active" and q.get("location_id")]
