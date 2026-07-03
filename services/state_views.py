"""
state_views.py — Derivações puras de estado pra interface (Fase 3.4).

Tudo aqui é VIEW: nenhum campo novo persistido, só leitura/agregação do que já existe
(event_log, world_projection, world.threat_alerts). Não-onisciência preservada: quem
chama filtra por `intel.known`/`world.visited` ANTES de usar estas funções (elas não
sabem de intel — recebem só o que já foi liberado pro jogador).

Spec: specs/fase-3.4-visualizacao-estado.md §3.
"""

from __future__ import annotations

from typing import Dict, List, Optional

from services import graph_resolver as gr
from world_utils import _ALERT_TTL

RECENT_TURNS = 30
# Limiares ASCENDENTES: primeiro em que stability <= threshold vence. Nenhum bate
# (stability > 30) -> "estável" (fallback, cobre ausência de dado também).
STABILITY_LABELS = ((-100, "em colapso"), (-30, "instável"), (30, "estável"))


def reputation_history(event_log: List[Dict], faction_id: str, limit: int = 20) -> List[Dict]:
    """Últimos `limit` eventos `reputation_changed` da fação, em ordem cronológica."""
    events = [e for e in (event_log or [])
              if e.get("type") == "reputation_changed" and e.get("target_id") == faction_id]
    events.sort(key=lambda e: e.get("turn", 0))
    events = events[-limit:]
    return [{"turn": e.get("turn", 0),
             "delta": (e.get("payload") or {}).get("delta", 0),
             "value": (e.get("payload") or {}).get("new_value", 0)}
            for e in events]


def stability_label(projection: Optional[Dict], faction_id: str) -> str:
    """Rótulo qualitativo — o número interno de stability NUNCA sai daqui pra fora."""
    ent = ((projection or {}).get("entities") or {}).get(faction_id) or {}
    stability = ent.get("stability")
    if stability is None:
        return "estável"
    stability = int(stability)
    for threshold, label in STABILITY_LABELS:
        if stability <= threshold:
            return label
    return "estável"


def recent_control_changes(event_log: List[Dict], visited: List[str], current_turn: int,
                           window: int = RECENT_TURNS) -> List[Dict]:
    """`location_control_changed` recentes em locais visitados (fog of war vale aqui também)."""
    visited_set = set(visited or [])
    out = []
    for ev in event_log or []:
        if ev.get("type") != "location_control_changed":
            continue
        loc_id = ev.get("target_id")
        if loc_id not in visited_set:
            continue
        turn = int(ev.get("turn", 0))
        if int(current_turn) - turn > window:
            continue
        controller_id = (ev.get("payload") or {}).get("new_controller_id", "")
        ent = gr.get_entity(controller_id)
        out.append({"location_id": loc_id,
                    "controller_name": (ent or {}).get("name", controller_id),
                    "turn": turn})
    return out


def active_threats(world: Optional[Dict], current_turn: int) -> List[Dict]:
    """`threat_alerts` não expirados — só LEITURA (não consome; isso é check_encounter)."""
    out = []
    for a in (world or {}).get("threat_alerts") or []:
        if int(current_turn) - int(a.get("turn", -99)) > _ALERT_TTL:
            continue
        out.append({"region_id": a.get("region_id", ""), "hint": a.get("hint", ""),
                    "turn": int(a.get("turn", 0))})
    return out


def visible_controllers(world: Optional[Dict], projection: Optional[Dict]) -> Dict[str, str]:
    """Local visitado -> NOME de quem controla (projection 2.5+ vence legado Fase 2)."""
    world = world or {}
    legacy = world.get("controlled") or {}
    out: Dict[str, str] = {}
    for loc_id in world.get("visited") or []:
        controller_id = gr.get_current_controller(loc_id, projection, include_hidden=False)
        controller_id = controller_id or legacy.get(loc_id)
        if not controller_id:
            continue
        ent = gr.get_entity(controller_id)
        out[loc_id] = (ent or {}).get("name", controller_id)
    return out
