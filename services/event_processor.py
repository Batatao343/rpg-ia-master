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

    elif etype == "location_state_changed":
        # SPEC-302 R17: unica escrita de estado de local. Estado vazio remove.
        rows = proj.setdefault("location_states", {})
        new_state = payload.get("state") or ""
        if new_state:
            row = {
                "state": new_state,
                "severity": int(payload.get("severity", 1) or 1),
                "since_day": int(payload.get("day", turn) or 0),
                "crisis_id": str(payload.get("crisis_id") or ""),
                "cause": str(payload.get("cause") or ""),
            }
            for extra in ("faction_id", "prev_controller", "festival_id"):
                if payload.get(extra):
                    row[extra] = str(payload[extra])
            rows[target] = row
        else:
            rows.pop(target, None)

    elif etype == "world_crisis_warning":
        pass  # aviso: so event_log/propagacao; sem efeito na projection

    elif etype == "faction_relation_changed" and (payload.get("relation") == "neutral"):
        # SPEC-302: volta a faixa neutra desativa as arestas dinamicas do par.
        other = payload.get("other_faction_id") or event.get("actor_id")
        pair = {target, other}
        proj["dynamic_edges"] = [
            e
            for e in proj.get("dynamic_edges", []) or []
            if not (
                e.get("type") in ("enemy_of", "allied_with")
                and {e.get("source"), e.get("target")} == pair
            )
        ]

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

    elif etype in ("world_quest_relief", "quest_failed"):
        # SPEC-305 R13/R17: marcas no estado de local (a projection segue sendo a fonte da
        # verdade). Liberacao eleva a chance de retomada; falha de libertar consolida.
        if payload.get("world_kind") == "libertar_ocupado":
            row = (proj.get("location_states") or {}).get(payload.get("location_id") or target)
            if isinstance(row, dict) and row.get("state") == "ocupado":
                day = int(payload.get("day", turn) or 0)
                if etype == "world_quest_relief":
                    row["liberation_day"] = day
                else:
                    from services import world_pressures as _wp

                    consolidation = int(
                        _wp._load_json("world_quests.json")["constants"][
                            "OCCUPATION_CONSOLIDATION_DAYS"
                        ]
                    )
                    row["consolidated_until_day"] = day + consolidation

    # quest_completed: nada na projection — o registro no event_log já é o efeito.

    return proj


def _build_event(proposal: dict, turn: int) -> dict:
    """Proposta validada → GameEvent (uuid, turn, source). Preserva `detail` no payload."""
    payload = dict(proposal.get("payload", {}) or {})
    detail = proposal.get("detail", "")
    if detail and "detail" not in payload:
        payload["detail"] = detail
    # SPEC-302 R2: o motor de mundo traz event_id DETERMINISTICO (replay = mesmo id).
    eid = proposal.get("event_id")
    if proposal.get("source") != "engine" or not isinstance(eid, str) or not eid:
        eid = uuid.uuid4().hex
    return {
        "event_id": eid,
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


def _clock_day(state: dict) -> int:
    clock = (state.get("world") or {}).get("world_clock") or {}
    return _safe_int(clock.get("day", 1)) or 1


def _world_quest_derived(quest: dict, state: dict, turn: int) -> tuple[list[dict], tuple | None]:
    """SPEC-305 R13. Derivados do motor para a conclusao de uma quest de mundo: o
    `world_quest_relief` (causa lida pelo tick seguinte) e, por tipo, `route_cleared`.
    Devolve `(eventos, (faction_id, pontos) | None)`. Ids deterministicos."""
    from services import world_director as wd
    from services import world_pressures as wp

    cfg = wp._load_json("world_quests.json")
    consts = cfg["constants"]
    kind = str(quest.get("world_kind"))
    relief = (cfg["kinds"].get(kind) or {}).get("relief") or {}
    day = _clock_day(state)
    gid = str(state.get("game_id", ""))
    loc = str(quest.get("location_id") or "")
    payload: dict = {
        "quest_id": quest.get("id"),
        "world_kind": kind,
        "world_source_id": quest.get("world_source_id", ""),
        "region_id": quest.get("region_id", ""),
        "location_id": loc,
        "day": day,
    }
    if relief.get("pressure"):
        payload["pressure"] = relief["pressure"]
        payload["delta"] = int(relief.get("delta", consts["RELIEF_DEFAULT"]))
    setback = None
    if relief.get("setback"):
        rec = next(
            (
                c
                for c in (state.get("world_sim") or {}).get("crises") or []
                if c.get("crisis_id") == quest.get("world_source_id")
            ),
            None,
        )
        fid = str((rec or {}).get("faction_id") or "")
        if fid:
            payload["faction_id"] = fid
            setback = (fid, int(consts["ASCENSION_SETBACK"]))
    events = [
        {
            "event_id": wd.event_id(gid, "world_quest_relief", day, str(quest.get("id"))),
            "turn": turn,
            "type": "world_quest_relief",
            "actor_id": "engine",
            "target_id": loc,
            "payload": payload,
            "source": "engine",
        }
    ]
    other = str(quest.get("other_location_id") or "")
    if relief.get("emit") == "route_cleared" and loc and other:
        events.append(
            {
                "event_id": wd.event_id(gid, "route_cleared", day, loc, f"quest:{quest.get('id')}"),
                "turn": turn,
                "type": "route_cleared",
                "actor_id": "player",
                "target_id": loc,
                "payload": {"other_location_id": other, "quest_id": quest.get("id")},
                "source": "engine",
            }
        )
    return events, setback


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
    faction_setbacks: list[tuple[str, int]] = []  # SPEC-305 R13: (faction_id, pontos)
    killed_targets: list = []  # SPEC-230 R4
    accepted_events: list[dict] = []  # SPEC-298: feitos aceitos -> services.reputation
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

    # SPEC-301: estado de fação (vínculo/influência/intel/jogador) tocado por missões e
    # reputação neste lote; mesclado em `updates` no fim. Notas viram avisos do turno.
    fm_over: dict = {}
    fm_notes: list[tuple[str, str]] = []

    def _fm_state() -> dict:
        return {**state, "quests": quests, **fm_over}

    def _apply_fm(result: tuple[dict, list[dict], str], fid: str = "") -> None:
        nonlocal quests, quests_changed
        upd, props, note = result
        for key, value in upd.items():
            if key == "quests":
                quests = value
                quests_changed = True
            else:
                fm_over[key] = value
        for prop in props:
            fm_ev = _build_event(prop, turn)
            event_log.append(fm_ev)
            _chronicle_milestone(fm_ev, projection)
        if note:
            fm_notes.append((fid, note))

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
            continue
        event = _build_event(_canonicalize_proposal(proposal, state, projection), turn)
        event_log.append(event)
        accepted_events.append(event)
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
                    if origem and origem.get("faction_id"):
                        # SPEC-301 R12: mérito, promoção, contra-jogo e rito de entrada.
                        from services import faction_membership

                        done_q = next((q for q in quests if q.get("id") == qid), origem)
                        _apply_fm(
                            faction_membership.on_mission_completed(_fm_state(), done_q),
                            str(origem.get("faction_id")),
                        )
                working["quests"] = quests
                if was_active and origem and origem.get("world_kind"):
                    # SPEC-305 R13: conclusao de quest de mundo = alivio (derivado do motor).
                    derived, setback = _world_quest_derived(origem, state, turn)
                    for dev in derived:
                        event_log.append(dev)
                        projection = apply_event(dev, projection)
                        _log_event("world_quest", "relief", level="info", kind=dev["type"])
                    if setback:
                        faction_setbacks.append(setback)

        # SPEC-305 R15: falha de quest por prazo (so o motor chega aqui; validador exige
        # quest ativa, entao uma quest nunca recebe duas falhas).
        if event["type"] == "quest_failed":
            qid = event["payload"].get("quest_id") or event.get("target_id")
            quests = quest_log.fail_quest(
                quests,
                str(qid),
                turn,
                str(event["payload"].get("reason") or "prazo"),
                _clock_day(state),
            )
            quests_changed = True
            working["quests"] = quests
            _log_event("quest", "failed", level="info")

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
            accepted_events.append(d)
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
                    failed_id = (qf.get("payload") or {}).get("quest_id")
                    failed_q = next((q for q in quests if q.get("id") == failed_id), None)
                    if failed_q and failed_q.get("faction_id"):
                        from services import faction_membership

                        fm_over.update(faction_membership.on_mission_failed(_fm_state(), failed_q))

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
            dict(fm_over.get("player") or state.get("player") or {}),
            XP_PER_QUEST * quests_completed,
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

    # SPEC-298 R12/R13/R14: feitos aceitos -> fação (se testemunhou) / pendência / fama.
    # A reputação NUNCA muda antes do aceite; rejeitado = nada a desfazer.
    if accepted_events:
        try:
            from services import reputation

            rep = reputation.process_deeds(
                {
                    **state,
                    "event_log": event_log,
                    "world_projection": projection,
                    "quests": quests,
                    **fm_over,
                },
                accepted_events,
            )
        except Exception as exc:  # silent-ok: reputação nunca derruba o turno
            _log_event("reputation", "process_failed", level="warning", error=type(exc).__name__)
            rep = {}
        rep_props = rep.pop("reputation_events", []) or []
        for rep_prop in rep_props:
            rep_event = _build_event(rep_prop, turn)
            event_log.append(rep_event)
            _chronicle_milestone(rep_event, projection)
        if rep:
            updates.update(rep)
            if chronicle_changed:
                updates["chronicle"] = chronicle
        if rep_props and "factions" in rep:
            # SPEC-301 R15/R18: reputação APLICADA move a influência (±1) e, contra a
            # própria fação, vira ofensa (suspeito -> traição). Sem proposta aceita, nada.
            from services import faction_membership

            factions_now = rep["factions"]
            for rep_prop in rep_props:
                fid = str(rep_prop.get("target_id") or "")
                delta = int((rep_prop.get("payload") or {}).get("delta") or 0)
                if fid and delta:
                    factions_now = faction_membership.bump_influence(
                        factions_now, fid, 1 if delta > 0 else -1
                    )
            fm_over["factions"] = factions_now
            for rep_prop in rep_props:
                fid = str(rep_prop.get("target_id") or "")
                delta = int((rep_prop.get("payload") or {}).get("delta") or 0)
                if delta < 0 and faction_membership.is_member(_fm_state(), fid):
                    _apply_fm(faction_membership.register_offense(_fm_state(), fid), fid)
    if state.get("faction_membership") or fm_over.get("faction_membership"):
        from services import faction_membership

        _apply_fm(faction_membership.check_expulsion(_fm_state()))

    if faction_setbacks:
        base_factions = updates.get("factions", state.get("factions")) or []
        facs = [dict(f) for f in base_factions if isinstance(f, dict)]
        for fid, points in faction_setbacks:
            for f in facs:
                if f.get("id") == fid and not f.get("completed"):
                    f["progress"] = max(0, int(f.get("progress", 0) or 0) - int(points))
        if facs:
            updates["factions"] = facs

    if killed_targets:
        from services.npc_layers import apply_npc_death

        npcs_now = updates.get("npcs", state.get("npcs") or {})
        party_now = state.get("party") or []
        for tid in killed_targets:
            if tid:
                npcs_now, party_now = apply_npc_death(npcs_now, party_now, str(tid), turn)
        if npcs_now != (state.get("npcs") or {}) or "npcs" in updates:
            updates["npcs"] = npcs_now
        if party_now != (state.get("party") or []):
            updates["party"] = party_now
    if fm_over:
        for key, value in fm_over.items():
            if key == "player" and "player" in updates:
                continue  # grant_xp já partiu do jogador atualizado
            updates[key] = value
    if fm_notes:
        notices = list(updates.get("reputation_notices", state.get("reputation_notices")) or [])
        known = _fm_state().get("faction_intel") or {}
        for fid, text in fm_notes:
            if fid and not (known.get(fid) or {}).get("known"):
                continue
            notices.append({"kind": "faction", "subject_id": fid, "text": text, "turn": turn})
        updates["reputation_notices"] = notices[-16:]
    if chronicle_changed:
        updates["chronicle"] = chronicle
    if quests_changed:
        updates["quests"] = quests
    if len(event_rejections) != rejection_count_before or event_rejections != original_rejections:
        updates["event_rejections"] = event_rejections
    return updates
