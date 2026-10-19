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

Spec: specs/SPEC-003-fase-2.6-structured-events.md §3 · specs/SPEC-004-fase-2.7-rules-engine.md §3.
"""

from __future__ import annotations

import copy
import uuid
from typing import Dict

from observability.telemetry import log_event as _log_event
from services import graph_resolver as gr
from services import quest_log, rule_engine
from services.chronicle import append_entry, render_milestone
from services.world_validators import (
    ValidationResult,
    canonical_secret_detail,
    is_engine_proposal,
    reason_class,
    scene_anchor_ids,
    validate_proposal,
)

_MAX_EVENT_REJECTIONS = 100


def _safe_int(value, default: int = 0) -> int:
    """Coage inteiros de saves legados sem violar o contrato ``Nunca levanta``."""
    try:
        return int(value or default)
    except (TypeError, ValueError, OverflowError):
        return default


def _bounded_rejections(rows: list[dict]) -> list[dict]:
    """Mantém auditoria útil sem deixar o save crescer indefinidamente."""
    unique: dict[tuple, dict] = {}
    for row in rows:
        if not isinstance(row, dict):
            continue
        sanitized = {
            "turn": _safe_int(row.get("turn", 0)),
            "type": str(row.get("type") or ""),
            "target_id": str(row.get("target_id") or ""),
            "reason": str(row.get("reason") or "")[:240],
        }
        key = (
            sanitized["turn"],
            sanitized["type"],
            sanitized["target_id"],
            sanitized["reason"],
        )
        unique[key] = sanitized
    return list(unique.values())[-_MAX_EVENT_REJECTIONS:]


def _log_proposal_rejected(proposal: dict, reason: str) -> None:
    """SPEC-252 R1: `reason_code` (enum fechado), `target_ref` (so id de catalogo) e `source`.
    O texto livre do motivo continua so em `event_rejections`."""
    try:
        from typing import get_args

        from services.structured_outputs import EventType
        from services.world_validators import catalog_ref, reason_code, rejection_source

        etype = str(proposal.get("type") or "")
        if etype not in get_args(EventType):
            etype = "other"
        fields = {
            "type": etype,
            "reason_code": reason_code(reason),
            "source": rejection_source(proposal),
        }
        ref = catalog_ref(proposal.get("target_id"))
        if ref:
            fields["target_ref"] = ref
        _log_event("event", "proposal_rejected", level="info", **fields)
    except Exception:  # silent-ok: log best-effort; a rejeicao ja esta em event_rejections
        pass


def _record_rejection_metric(proposal: dict, reason: str) -> None:
    """SPEC-223 R8: `rpg_world_events_rejected_total{type, reason_class}` (labels fechados)."""
    try:
        from typing import get_args

        from observability.metrics import metrics
        from services.structured_outputs import EventType

        etype = str(proposal.get("type") or "")
        if etype not in get_args(EventType):
            etype = "other"
        metrics.increment(
            "rpg_world_events_rejected_total", {"type": etype, "reason_class": reason_class(reason)}
        )
    except Exception:  # silent-ok: metrica best-effort; a rejeicao ja esta em event_rejections
        pass


def _canonicalize_proposal(
    proposal: dict, state: dict | None = None, projection: dict | None = None
) -> dict:
    """SPEC-223 R2: o LLM só SINALIZA a revelação; o texto vem do grafo
    (restrito às edges ancoradas na cena quando o alvo não está nela)."""
    if proposal.get("type") != "secret_revealed" or is_engine_proposal(proposal):
        return proposal
    anchors = scene_anchor_ids(state) if state is not None else None
    detail = canonical_secret_detail(
        str(proposal.get("target_id") or ""), projection or {}, anchors
    )
    payload = {**(proposal.get("payload") or {}), "detail": detail}
    return {**proposal, "detail": detail, "payload": payload}


def apply_event(event: dict, projection: dict) -> dict:
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
        proj.setdefault("dynamic_edges", []).append(
            {
                "id": f"dyn_{event_id[:12]}",
                "source": new_controller,
                "type": "controls",
                "target": target,
                "created_by_event": event_id,
            }
        )

    elif etype == "faction_relation_changed":
        other = payload.get("other_faction_id") or event.get("actor_id")
        relation = payload.get("relation") or event.get("detail", "")
        proj.setdefault("dynamic_edges", []).append(
            {
                "id": f"dyn_{event_id[:12]}",
                "source": target,
                "type": relation,
                "target": other,
                "created_by_event": event_id,
            }
        )

    elif etype == "route_blocked":
        # Fase 6.1: par não-direcionado; dedupe defensivo (validator já barra)
        pair = frozenset((target, payload.get("other_location_id")))
        routes = proj.setdefault("blocked_routes", [])
        if not any(frozenset((r.get("a"), r.get("b"))) == pair for r in routes):
            routes.append(
                {"a": target, "b": payload.get("other_location_id"), "blocked_by_event": event_id}
            )

    elif etype == "unique_item_claimed":
        # Fase 6.2: um por mundo — registra o dono atual (claim re-escreve holder)
        uniques = proj.setdefault("unique_items", {})
        uniques[target] = {
            "holder": payload.get("holder", "player"),
            "event_id": event_id,
            "turn": turn,
        }

    elif etype == "unique_item_lost":
        uniques = proj.setdefault("unique_items", {})
        uniques[target] = {
            "holder": payload.get("holder", "unknown"),
            "event_id": event_id,
            "turn": turn,
        }

    elif etype == "route_cleared":
        pair = frozenset((target, payload.get("other_location_id")))
        proj["blocked_routes"] = [
            r
            for r in proj.get("blocked_routes", []) or []
            if frozenset((r.get("a"), r.get("b"))) != pair
        ]

    # quest_completed: nada na projection — o registro no event_log já é o efeito.

    return proj


def _build_event(proposal: dict, turn: int) -> dict:
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


def prevalidate_event_batch(
    proposals: list[dict],
    state: dict,
) -> list[ValidationResult]:
    """Pré-valida um lote na mesma ordem em que o processor o aplicaria.

    O preview trabalha sobre cópias de ``event_log``/``world_projection`` e roda
    também a cascata de regras. Assim, a proposta N+1 enxerga os efeitos válidos
    de N sem escrever no estado real. A função é deliberadamente read-only e
    devolve um resultado por entrada, inclusive para payload malformado.
    """
    working = copy.deepcopy(state or {})
    event_log = list(working.get("event_log") or [])
    projection = copy.deepcopy(working.get("world_projection") or {})
    quests = list(working.get("quests") or [])
    turn = _safe_int((working.get("world") or {}).get("turn_count", 0))
    results: list[ValidationResult] = []

    for raw_proposal in proposals or []:
        proposal = raw_proposal if isinstance(raw_proposal, dict) else {}
        working["event_log"] = event_log
        working["world_projection"] = projection
        working["quests"] = quests
        try:
            result = validate_proposal(raw_proposal, working)
        # silent-ok: vira ValidationResult(False) => event_rejections + metrica
        except Exception as exc:
            result = ValidationResult(False, f"proposta malformada: {exc}")
        results.append(result)
        if not result.ok:
            continue

        event = _build_event(proposal, turn)
        event_log.append(event)
        projection = apply_event(event, projection)

        if event["type"] == "quest_completed":
            quest_id = event["payload"].get("quest_id")
            if quest_id:
                quests = quest_log.complete_quest(quests, quest_id, turn)

        working["event_log"] = event_log
        working["world_projection"] = projection
        for derived in rule_engine.run_rules(event, working, depth=0):
            event_log.append(derived)
        projection = working["world_projection"]

    return results


def _revert_reputation(factions: list, proposal: dict) -> list:
    """SPEC-226 R8: o storyteller aplica a reputação ao propor; se o pipeline
    rejeita o `reputation_changed`, o delta exato aplicado é desfeito (estado e
    log nunca divergem). Só proposta do motor (`source=storyteller`) com delta."""
    if proposal.get("source") != "storyteller":
        return factions
    payload = proposal.get("payload") or {}
    try:
        delta = int(payload.get("delta", 0) or 0)
        new_value = int(payload.get("new_value"))
    except (TypeError, ValueError):
        return factions
    if not delta:
        return factions
    from world_utils import REP_MAX, REP_MIN, _disposition_for

    out = []
    for f in factions:
        f = dict(f) if isinstance(f, dict) else f
        if (
            isinstance(f, dict)
            and f.get("id") == proposal.get("target_id")
            and int(f.get("reputation", 0) or 0) == new_value
        ):
            old = max(REP_MIN, min(REP_MAX, new_value - delta))
            f["reputation"] = old
            f["disposition"] = _disposition_for(old)
        out.append(f)
    return out


def process_pending_events(state: dict) -> dict:
    """Valida/aplica a fila `pending_world_events`. Retorna updates parciais do GameState.

    Fila vazia → `{}` (no-op barato). Caso contrário devolve
    `{"event_log": [...], "world_projection": {...}, "pending_world_events": []}`.
    Nunca levanta — proposta inválida é descartada com log.
    """
    pending = state.get("pending_world_events") or []
    if not pending:
        return {}

    turn = _safe_int((state.get("world") or {}).get("turn_count", 0))
    event_log = list(state.get("event_log") or [])
    projection = copy.deepcopy(state.get("world_projection") or {})
    chronicle = state.get("chronicle") or []
    chronicle_changed = False
    quests = list(state.get("quests") or [])
    quests_changed = False
    quests_completed = 0  # Fase 4.1: cada conclusão vale XP_PER_QUEST
    quest_reward_gold = 0
    killed_targets: list = []  # SPEC-230 R4
    factions_reverted = None  # SPEC-226 R8: reputação de proposta rejeitada é desfeita
    original_rejections = list(state.get("event_rejections") or [])
    event_rejections = _bounded_rejections(original_rejections)
    rejection_count_before = len(event_rejections)

    def _chronicle_milestone(ev: dict, proj: dict) -> None:
        nonlocal chronicle, chronicle_changed
        milestone = render_milestone(ev, proj)
        if milestone:
            chronicle = append_entry(
                chronicle,
                text=milestone,
                turn=ev.get("turn", 0),
                kind="milestone",
                event_id=ev["event_id"],
            )
            chronicle_changed = True

    # Estado de trabalho: valida cada proposta contra o já-aplicado nesta rodada
    # (pega duplicatas dentro do mesmo lote).
    working = dict(state)

    for raw_proposal in pending:
        proposal = raw_proposal if isinstance(raw_proposal, dict) else {}
        working["event_log"] = event_log
        working["world_projection"] = projection
        if proposal.get("_prevalidation_rejected") is True:
            # Envelope de auditoria do storyteller: o payload livre já foi
            # descartado na fronteira narrativa; nunca tente promovê-lo de novo.
            result = ValidationResult(
                False,
                str(
                    proposal.get("_prevalidation_reason") or "rejeitada na pré-validação narrativa"
                )[:240],
            )
        else:
            try:
                result = validate_proposal(raw_proposal, working)
            # silent-ok: vira ValidationResult(False) => event_rejections + metrica
            except Exception as exc:
                result = ValidationResult(False, f"proposta malformada: {exc}")
        if not result.ok:
            _log_proposal_rejected(proposal, result.reason)
            event_rejections = _bounded_rejections(
                [
                    *event_rejections,
                    {
                        "turn": turn,
                        "type": str(proposal.get("type") or ""),
                        "target_id": str(proposal.get("target_id") or ""),
                        "reason": str(result.reason or "")[:240],
                    },
                ]
            )
            _record_rejection_metric(proposal, result.reason)
            if proposal.get("type") == "reputation_changed":
                factions_reverted = _revert_reputation(
                    factions_reverted
                    if factions_reverted is not None
                    else list(state.get("factions") or []),
                    proposal,
                )
            continue
        event = _build_event(_canonicalize_proposal(proposal, state, projection), turn)
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
                was_active = any(q.get("id") == qid and q.get("status") == "active" for q in quests)
                quests, delivered = quest_log.complete_quest_with_reward(quests, qid, turn)
                quest_reward_gold += delivered
                quests_changed = True
                if was_active:  # SPEC-226 R2: XP só na transição real
                    quests_completed += 1
                working["quests"] = quests

        _log_event(
            "event", "applied", level="debug", type=event["type"], event_id=event["event_id"][:8]
        )
        _chronicle_milestone(event, projection)  # Fase 3.1: evento aplicado → crônica

        # Fase 2.7: cascata sistêmica. run_rules muta a projection in place e recursa
        # (depth <= 2); aqui só logamos os derivados (source="rule_engine").
        working["world_projection"] = projection
        working["event_log"] = event_log
        for d in rule_engine.run_rules(event, working, depth=0):
            event_log.append(d)
            if d.get("type") == "npc_killed":
                killed_targets.append(d.get("target_id"))
            _log_event("rule", "derived", level="debug", type=d["type"], event_id=d["event_id"][:8])
            _chronicle_milestone(d, working["world_projection"])
        projection = working["world_projection"]

        if event["type"] == "npc_killed":
            killed_targets.append(event.get("target_id"))

        # Fase 3.3 (R4): NPC canônico morto → toda quest órfã falha sistemicamente.
        if event["type"] == "npc_killed":
            quests, qfailed = quest_log.fail_orphan_quests(quests, event.get("target_id"), turn)
            if qfailed:
                quests_changed = True
                for qf in qfailed:
                    event_log.append(qf)
                    _log_event("quest", "failed", level="info")
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

        player, lvl_props = grant_xp(
            dict(state.get("player") or {}), XP_PER_QUEST * quests_completed
        )
        player["gold"] = int(player.get("gold", 0) or 0) + quest_reward_gold
        updates["player"] = player
        # SPEC-226 R10: cada conclusão é um ganho individual (XP e ouro).
        from services.turn_outcome import record_gain

        bl = state.get("turn_baseline")
        for _ in range(quests_completed):
            bl = record_gain(bl, "xp", XP_PER_QUEST, "quest")
        for _ in range(quests_completed if quest_reward_gold else 0):
            bl = record_gain(bl, "gold", quest_reward_gold // quests_completed, "quest")
        if bl is not state.get("turn_baseline"):
            updates["turn_baseline"] = bl
        for prop in lvl_props:
            ev = _build_event(prop, turn)
            event_log.append(ev)
            _log_event("xp", "level_up", level="info", new_level=ev["payload"].get("new_level"))
            _chronicle_milestone(ev, projection)

    if factions_reverted is not None and factions_reverted != list(state.get("factions") or []):
        updates["factions"] = factions_reverted

    if killed_targets:
        from services.npc_layers import apply_npc_death

        npcs_now, party_now = state.get("npcs") or {}, state.get("party") or []
        for tid in killed_targets:
            if tid:
                npcs_now, party_now = apply_npc_death(npcs_now, party_now, str(tid), turn)
        if npcs_now != (state.get("npcs") or {}):
            updates["npcs"] = npcs_now
        if party_now != (state.get("party") or []):
            updates["party"] = party_now
    if chronicle_changed:
        updates["chronicle"] = chronicle
    if quests_changed:
        updates["quests"] = quests
    if len(event_rejections) != rejection_count_before or event_rejections != original_rejections:
        updates["event_rejections"] = event_rejections
    return updates
