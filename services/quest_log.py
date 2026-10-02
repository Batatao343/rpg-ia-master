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

Spec: specs/SPEC-008-fase-3.3-quest-log.md §3.
"""

from __future__ import annotations

import difflib
import re
import unicodedata
import uuid
from typing import Dict, List, Tuple, Union

import gamedata
from services import graph_resolver as gr

MAX_ACTIVE_QUESTS = 8
TITLE_SIMILARITY = 0.75
QUEST_REWARD_GOLD = 20
QUEST_ACTION_RE = re.compile(
    r"\b(?:investig|procur|examin|rastre|interrog|pergunt|seguir|retom|"
    r"vasculh|averigu|miss[aã]o|pista)",
    re.IGNORECASE,
)


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
            "progress_log": [{"kind": "created", "turn": int(turn), "detail": ""}],
            "reward_gold": 0,
            "reward_delivered": False,
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


def sync_location_progress(quests: List[Dict], location_id: str, *, turn: int = 0) -> List[Dict]:
    """Registra chegada ao alvo uma única vez, sem concluir a missão."""
    out: List[Dict] = []
    for original in quests or []:
        q = dict(original)
        progress = list(q.get("progress_log") or [])
        if (q.get("status") == "active" and location_id
                and q.get("location_id") == location_id
                and not any(row.get("kind") == "location_reached" for row in progress)):
            progress.append({"kind": "location_reached", "turn": int(turn),
                             "detail": str(location_id)})
            q["progress_log"] = progress
        out.append(q)
    return out


def _normalized_words(value: str) -> set[str]:
    folded = unicodedata.normalize("NFKD", str(value or ""))
    plain = "".join(char for char in folded if not unicodedata.combining(char))
    return {
        word for word in re.findall(r"[a-z0-9]+", plain.casefold())
        if len(word) >= 4
    }


def sync_action_progress(
    quests: List[Dict],
    location_id: str,
    action_text: str,
    *,
    turn: int = 0,
) -> Tuple[List[Dict], List[str]]:
    """Registra investigação verificável e sinaliza conclusão determinística.

    A ação precisa ocorrer no local-alvo já alcançado, conter um verbo de busca
    e citar a missão (título/descrição) ou usar vocabulário explícito de missão.
    Duas ações distintas fecham o objetivo; repetição literal é idempotente.
    """
    action = " ".join(str(action_text or "").split())[:240]
    if not action or not QUEST_ACTION_RE.search(action):
        return [dict(q) for q in (quests or [])], []
    action_words = _normalized_words(action)
    generic_reference = bool(
        action_words & {"missao", "pista", "investigo", "investigar", "retomo"}
    )
    ready_ids: List[str] = []
    out: List[Dict] = []
    fingerprint = unicodedata.normalize("NFKC", action).casefold()
    for original in quests or []:
        q = dict(original)
        progress = [dict(row) for row in (q.get("progress_log") or [])]
        quest_words = _normalized_words(
            f"{q.get('title', '')} {q.get('description', '')}"
        )
        relevant = generic_reference or bool(action_words & quest_words)
        reached = any(row.get("kind") == "location_reached" for row in progress)
        already_ready = bool(q.get("completion_ready"))
        fresh = int(q.get("created_turn", -1) or -1) < int(turn)
        if (
            q.get("status") == "active"
            and q.get("location_id") == location_id
            and reached
            and relevant
            and fresh
            and not already_ready
        ):
            fingerprints = {
                str(row.get("fingerprint") or "")
                for row in progress if row.get("kind") == "investigation"
            }
            if fingerprint not in fingerprints:
                progress.append({
                    "kind": "investigation",
                    "turn": int(turn),
                    "detail": action,
                    "fingerprint": fingerprint,
                })
            investigations = {
                str(row.get("fingerprint") or "")
                for row in progress if row.get("kind") == "investigation"
            }
            if len(investigations) >= 2:
                q["completion_ready"] = True
                progress.append({
                    "kind": "completion_ready",
                    "turn": int(turn),
                    "detail": "objetivo verificado por ações distintas",
                })
                ready_ids.append(str(q.get("id") or ""))
            q["progress_log"] = progress
        out.append(q)
    return out, [quest_id for quest_id in ready_ids if quest_id]


def complete_quest_with_reward(quests: List[Dict], quest_id: str,
                               turn: int = 0) -> Tuple[List[Dict], int]:
    """Conclui e materializa a recompensa fixa uma vez. Retorna ouro concedido."""
    out: List[Dict] = []
    reward = 0
    for original in quests or []:
        q = dict(original)
        if q.get("id") == quest_id and q.get("status") == "active":
            progress = list(q.get("progress_log") or [])
            progress.append({"kind": "completed", "turn": int(turn), "detail": ""})
            q.update({
                "status": "completed", "resolved_turn": int(turn),
                "progress_log": progress, "reward_gold": QUEST_REWARD_GOLD,
                "reward_delivered": True,
            })
            reward = QUEST_REWARD_GOLD
        out.append(q)
    return out, reward


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
