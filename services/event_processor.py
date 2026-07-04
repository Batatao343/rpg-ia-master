"""
event_processor.py — Proposta válida → GameEvent → world_projection (Fase 2.6).

`process_pending_events` é o único ponto que escreve no `event_log` e na
`world_projection`. Roda no `archivist` (fim de todo turno). Fecha o ciclo:
LLM/combate PROPÕE (pending_world_events) → aqui VALIDA → APLICA ou descarta com log.

`apply_event` é PURA (recebe/retorna projection, sem cascata). A cascata sistêmica
(Fase 2.7) roda LOGO APÓS cada `apply_event`, via `rule_engine.run_rules`: líder morre →
facção desestabiliza → controle do local muda → rival ocupa. `run_rules` é dono da cascata
(aplica os derivados na projection e recursa até depth 2); aqui só anexamos os derivados ao
`event_log` (não re-aplicamos).

Spec: specs/fase-2.6-structured-events.md §3 · specs/fase-2.7-rules-engine.md §3.
"""

from __future__ import annotations

import copy
import uuid
from typing import Dict

from services import graph_resolver as gr
from services import quest_log
from services import rule_engine
from services.chronicle import append_entry, render_milestone
from services.world_validators import validate_proposal


def apply_event(event: Dict, projection: Dict) -> Dict:
    """Efeito DIRETO de um GameEvent na projection. Puro: não muta o argumento."""
    proj = copy.deepcopy(projection or {})
    etype = event.get("type")
    target = event.get("target_id")
    event_id = event.get("event_id", "")
    turn = event.get("turn", 0)
    payload = event.get("payload", {}) or {}

    if etype == "npc_killed":
        entities = proj.setdefault("entities", {})
        entities[target] = {**entities.get(target, {}), "alive": False}

    elif etype == "secret_revealed":
        facts = proj.setdefault("revealed_facts", {})
        facts[event_id] = {
            "entity_id": target,
            "fact": payload.get("detail", "") or "",
            "revealed_at_turn": turn,
            "revealed_by_event": event_id,
        }

    elif etype == "location_control_changed":
        new_controller = payload.get("new_controller_id")
        # desativa a edge 'controls' vigente (base) apontando para o local
        controls = gr.resolve_edges(proj, edge_type="controls", include_hidden=True)
        for edge in controls:
            if edge.get("target") == target and edge.get("id"):
                proj.setdefault("disabled_edges", []).append(
                    {"edge_id": edge["id"], "disabled_by_event": event_id}
                )
        proj.setdefault("dynamic_edges", []).append({
            "id": f"dyn_{event_id[:12]}",
            "source": new_controller,
            "type": "controls",
            "target": target,
            "created_by_event": event_id,
        })

    elif etype == "faction_relation_changed":
        other = payload.get("other_faction_id") or event.get("actor_id")
        relation = payload.get("relation") or event.get("detail", "")
        proj.setdefault("dynamic_edges", []).append({
            "id": f"dyn_{event_id[:12]}",
            "source": target,
            "type": relation,
            "target": other,
            "created_by_event": event_id,
        })

    # quest_completed: nada na projection — o registro no event_log já é o efeito.

    return proj


def _build_event(proposal: Dict, turn: int) -> Dict:
    """Proposta validada → GameEvent (uuid, turn, source). Preserva `detail` no payload."""
    payload = dict(proposal.get("payload", {}) or {})
    detail = proposal.get("detail", "")
    if detail and "detail" not in payload:
        payload["detail"] = detail
    return {
        "event_id": uuid.uuid4().hex,
        "turn": turn,
        "type": proposal.get("type"),
        "actor_id": proposal.get("actor_id", "player"),
        "target_id": proposal.get("target_id"),
        "payload": payload,
        "source": proposal.get("source", "storyteller"),
    }


def process_pending_events(state: Dict) -> Dict:
    """Valida/aplica a fila `pending_world_events`. Retorna updates parciais do GameState.

    Fila vazia → `{}` (no-op barato). Caso contrário devolve
    `{"event_log": [...], "world_projection": {...}, "pending_world_events": []}`.
    Nunca levanta — proposta inválida é descartada com log.
    """
    pending = state.get("pending_world_events") or []
    if not pending:
        return {}

    turn = (state.get("world") or {}).get("turn_count", 0)
    event_log = list(state.get("event_log") or [])
    projection = copy.deepcopy(state.get("world_projection") or {})
    chronicle = state.get("chronicle") or []
    chronicle_changed = False
    quests = list(state.get("quests") or [])
    quests_changed = False
    quests_completed = 0  # Fase 4.1: cada conclusão vale XP_PER_QUEST

    def _chronicle_milestone(ev: Dict, proj: Dict) -> None:
        nonlocal chronicle, chronicle_changed
        milestone = render_milestone(ev, proj)
        if milestone:
            chronicle = append_entry(chronicle, text=milestone, turn=ev.get("turn", 0),
                                     kind="milestone", event_id=ev["event_id"])
            chronicle_changed = True

    # Estado de trabalho: valida cada proposta contra o já-aplicado nesta rodada
    # (pega duplicatas dentro do mesmo lote).
    working = dict(state)

    for proposal in pending:
        working["event_log"] = event_log
        working["world_projection"] = projection
        result = validate_proposal(proposal, working)
        if not result.ok:
            print(f"🚫 [EVENT] proposta rejeitada ({proposal.get('type')}/"
                  f"{proposal.get('target_id')}): {result.reason}")
            continue
        event = _build_event(proposal, turn)
        event_log.append(event)
        projection = apply_event(event, projection)

        # Fase 3.3: conclusão de side quest — nada na projection (apply_event não
        # mexe), só em `quests`. Embute o título no payload ANTES do milestone.
        if event["type"] == "quest_completed":
            qid = event["payload"].get("quest_id")
            if qid:
                origem = next((q for q in quests if q.get("id") == qid), None)
                if origem:
                    event["payload"]["quest_title"] = origem.get("title", "")
                quests = quest_log.complete_quest(quests, qid, turn)
                quests_changed = True
                quests_completed += 1

        print(f"✅ [EVENT] {event['type']} → {event['target_id']} (id={event['event_id'][:8]})")
        _chronicle_milestone(event, projection)  # Fase 3.1: evento aplicado → crônica

        # Fase 2.7: cascata sistêmica. run_rules muta a projection in place e recursa
        # (depth <= 2); aqui só logamos os derivados (source="rule_engine").
        working["world_projection"] = projection
        working["event_log"] = event_log
        for d in rule_engine.run_rules(event, working, depth=0):
            event_log.append(d)
            print(f"⚙️ [RULE] {d['type']} → {d['target_id']} (src=rule_engine, id={d['event_id'][:8]})")
            _chronicle_milestone(d, working["world_projection"])
        projection = working["world_projection"]

        # Fase 3.3 (R4): NPC canônico morto → toda quest órfã falha sistemicamente.
        if event["type"] == "npc_killed":
            quests, qfailed = quest_log.fail_orphan_quests(quests, event.get("target_id"), turn)
            if qfailed:
                quests_changed = True
                for qf in qfailed:
                    event_log.append(qf)
                    print(f"⚰️ [QUEST] {qf['payload'].get('quest_title','?')} fracassou "
                          f"(origem morta, id={qf['event_id'][:8]})")
                    _chronicle_milestone(qf, projection)

    updates = {
        "event_log": event_log,
        "world_projection": projection,
        "pending_world_events": [],
    }

    # Fase 4.1: quest concluída dá XP determinístico. Level ups são eventos do
    # motor (sãos por construção) — entram direto no log + crônica, sem revalidar.
    if quests_completed:
        from progression import XP_PER_QUEST, grant_xp
        player, lvl_props = grant_xp(dict(state.get("player") or {}),
                                     XP_PER_QUEST * quests_completed)
        updates["player"] = player
        for prop in lvl_props:
            ev = _build_event(prop, turn)
            event_log.append(ev)
            print(f"⬆️ [XP] level_up → nível {ev['payload'].get('new_level')} (id={ev['event_id'][:8]})")
            _chronicle_milestone(ev, projection)

    if chronicle_changed:
        updates["chronicle"] = chronicle
    if quests_changed:
        updates["quests"] = quests
    return updates
