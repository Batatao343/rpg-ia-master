"""
world_validators.py — Valida propostas de evento contra o grafo e o estado (Fase 2.6).

Uma proposta (`dict`, vinda de `pending_world_events`) só vira `GameEvent` se
`validate_proposal` devolver `ok=True`. Rejeição NÃO quebra o turno — o processor
descarta com log. Revalida do zero via Pydantic (defesa em profundidade: o LLM pode
ter inventado id/tipo mesmo com o bloco <ENTIDADES_CANONICAS> no prompt).

Spec: specs/fase-2.6-structured-events.md §3.
"""

from __future__ import annotations

from typing import NamedTuple

from services import graph_resolver as gr
from services.structured_outputs import ProposedWorldEvent


class ValidationResult(NamedTuple):
    ok: bool
    reason: str = ""


# --- validadores por tipo ---------------------------------------------------
# Cada um recebe (ev: ProposedWorldEvent, state: dict, projection: dict) e devolve
# ValidationResult. A checagem comum (Pydantic, entidade-alvo, duplicata) roda antes.


def _v_npc_killed(ev: ProposedWorldEvent, state: dict, proj: dict) -> ValidationResult:
    ent = gr.get_entity(ev.target_id)
    if not ent:
        return ValidationResult(False, f"id desconhecido em entities.json: {ev.target_id}")
    if ent.get("type") != "npc":
        return ValidationResult(False, f"{ev.target_id} não é do type npc (é {ent.get('type')})")
    if not gr.is_alive(ev.target_id, proj):
        return ValidationResult(False, f"{ev.target_id} já está morto")
    return ValidationResult(True)


def _v_secret_revealed(ev: ProposedWorldEvent, state: dict, proj: dict) -> ValidationResult:
    if not gr.get_entity(ev.target_id):
        return ValidationResult(False, f"id desconhecido em entities.json: {ev.target_id}")
    # existe edge hidden/secret ligada ao alvo? (o segredo tem de EXISTIR no grafo)
    edges = gr.resolve_edges(proj, entity_id=ev.target_id, include_hidden=True)
    if not any(e.get("visibility") in ("hidden", "secret") for e in edges):
        return ValidationResult(False, f"nenhum segredo (edge hidden/secret) ligado a {ev.target_id}")
    # fato ainda não revelado?
    revealed = proj.get("revealed_facts", {}) or {}
    if any(rf.get("entity_id") == ev.target_id for rf in revealed.values()):
        return ValidationResult(False, f"segredo de {ev.target_id} já revelado")
    return ValidationResult(True)


def _v_location_control_changed(ev: ProposedWorldEvent, state: dict, proj: dict) -> ValidationResult:
    ent = gr.get_entity(ev.target_id)
    if not ent:
        return ValidationResult(False, f"id desconhecido em entities.json: {ev.target_id}")
    if ent.get("type") != "location":
        return ValidationResult(False, f"{ev.target_id} não é do type location")
    ncid = ev.payload.get("new_controller_id")
    if not ncid:
        return ValidationResult(False, "payload.new_controller_id ausente")
    nc = gr.get_entity(ncid)
    if not nc or nc.get("type") != "faction":
        return ValidationResult(False, f"new_controller_id {ncid} não é uma facção conhecida")
    if not gr.is_alive(ncid, proj):
        return ValidationResult(False, f"facção {ncid} está derrotada")
    return ValidationResult(True)


def _v_quest_completed(ev: ProposedWorldEvent, state: dict, proj: dict) -> ValidationResult:
    # Fase 3.3: side quest — payload.quest_id aponta pra GameState.quests (não pro grafo).
    qid = ev.payload.get("quest_id")
    if qid:
        ativas = {q.get("id") for q in state.get("quests", []) or [] if q.get("status") == "active"}
        if qid in ativas:
            return ValidationResult(True)
        return ValidationResult(False, f"quest_id {qid} não é uma quest ativa")
    # Modo beat (Fase 2.6, comportamento original — sem quest_id no payload).
    plan = state.get("campaign_plan") or {}
    beats = plan.get("beats") or []
    if not beats:
        return ValidationResult(False, "sem campaign_plan/beats para concluir")
    idx = ev.payload.get("beat_index")
    if idx is not None and not (0 <= int(idx) < len(beats)):
        return ValidationResult(False, f"beat_index {idx} fora do plano (0..{len(beats)-1})")
    return ValidationResult(True)


def _v_faction_relation_changed(ev: ProposedWorldEvent, state: dict, proj: dict) -> ValidationResult:
    other = ev.payload.get("other_faction_id") or ev.actor_id
    a, b = gr.get_entity(ev.target_id), gr.get_entity(other)
    if not a or a.get("type") != "faction":
        return ValidationResult(False, f"{ev.target_id} não é facção")
    if not b or b.get("type") != "faction":
        return ValidationResult(False, f"{other} não é facção")
    relation = ev.payload.get("relation") or ev.detail
    if relation not in gr.load_relation_types():
        return ValidationResult(False, f"relação desconhecida: {relation!r}")
    return ValidationResult(True)


def _v_reputation_changed(ev: ProposedWorldEvent, state: dict, proj: dict) -> ValidationResult:
    """Fase 3.4: evento enfileirado pelo Python (storyteller), não pelo LLM — a
    validação aqui é sanidade (fação existe/viva), não gate de alucinação."""
    f = gr.get_entity(ev.target_id)
    if not f or f.get("type") != "faction":
        return ValidationResult(False, f"{ev.target_id} não é facção")
    if not gr.is_alive(ev.target_id, proj):
        return ValidationResult(False, f"facção {ev.target_id} está derrotada")
    return ValidationResult(True)


def _v_level_up(ev: ProposedWorldEvent, state: dict, proj: dict) -> ValidationResult:
    """Fase 4.1: evento do motor (grant_xp). O gate anti-LLM (source='progression')
    fica em validate_proposal; aqui só sanidade do payload."""
    if ev.target_id != "player" or ev.actor_id != "player":
        return ValidationResult(False, "level_up é sempre do player")
    if not isinstance(ev.payload.get("new_level"), int):
        return ValidationResult(False, "payload.new_level ausente/inválido")
    return ValidationResult(True)


def _route_pair_blocked(proj: dict, a: str, b: str) -> bool:
    pair = frozenset((a, b))
    return any(frozenset((r.get("a"), r.get("b"))) == pair
               for r in (proj or {}).get("blocked_routes", []) or [])


def _v_route_blocked(ev: ProposedWorldEvent, state: dict, proj: dict) -> ValidationResult:
    """Fase 6.1: rota só existe entre locais DIRETAMENTE conectados no mapa."""
    from gamedata import get_location
    a = ev.target_id
    b = str(ev.payload.get("other_location_id") or "")
    if not get_location(a):
        return ValidationResult(False, f"{a} não é local do mapa")
    if not b or not get_location(b):
        return ValidationResult(False, f"{b!r} não é local do mapa")
    if b not in (get_location(a).get("connections") or []):
        return ValidationResult(False, f"{a} e {b} não têm conexão direta")
    if _route_pair_blocked(proj, a, b):
        return ValidationResult(False, f"rota {a}↔{b} já está bloqueada")
    return ValidationResult(True)


def _v_route_cleared(ev: ProposedWorldEvent, state: dict, proj: dict) -> ValidationResult:
    a = ev.target_id
    b = str(ev.payload.get("other_location_id") or "")
    if not _route_pair_blocked(proj, a, b):
        return ValidationResult(False, f"rota {a}↔{b} não está bloqueada")
    return ValidationResult(True)


def _v_player_died(ev: ProposedWorldEvent, state: dict, proj: dict) -> ValidationResult:
    """Fase 4.6: evento do motor (combate) — gate anti-LLM em validate_proposal."""
    if ev.target_id != "player":
        return ValidationResult(False, "player_died é sempre do player")
    return ValidationResult(True)


_VALIDATORS = {
    "npc_killed": _v_npc_killed,
    "secret_revealed": _v_secret_revealed,
    "location_control_changed": _v_location_control_changed,
    "quest_completed": _v_quest_completed,
    "faction_relation_changed": _v_faction_relation_changed,
    "reputation_changed": _v_reputation_changed,
    "level_up": _v_level_up,
    "player_died": _v_player_died,
    "route_blocked": _v_route_blocked,
    "route_cleared": _v_route_cleared,
}


def validate_proposal(proposal: dict, state: dict) -> ValidationResult:
    """Valida UMA proposta contra grafo + estado. Nunca levanta."""
    # 1. Revalida do zero — dict malformado / tipo desconhecido = rejeitado sem exceção.
    try:
        ev = ProposedWorldEvent.model_validate(proposal)
    except Exception as exc:
        return ValidationResult(False, f"proposta malformada: {exc}")

    # Fase 4.1: level_up só nasce no motor (grant_xp) — proposta do LLM chega sem
    # `source` (o schema ProposedWorldEvent não tem o campo) e é rejeitada aqui.
    if ev.type == "level_up" and proposal.get("source") != "progression":
        return ValidationResult(False, "level_up é gerado pelo motor, não proposto")
    # Fase 4.6: player_died idem — só o combate emite.
    if ev.type == "player_died" and proposal.get("source") != "combat":
        return ValidationResult(False, "player_died é gerado pelo motor, não proposto")

    projection = state.get("world_projection") or {}
    turn = (state.get("world") or {}).get("turn_count", 0)

    # 2. Sem duplicata (mesmo type+target já no event_log DESTE turno).
    #    Exceção: multi-level no mesmo turno (boss XP) — level_up distingue por new_level.
    for e in state.get("event_log") or []:
        if e.get("type") == ev.type and e.get("target_id") == ev.target_id and e.get("turn") == turn:
            if ev.type == "level_up" and (e.get("payload") or {}).get("new_level") != ev.payload.get("new_level"):
                continue
            # Fase 6.1: mesmo local pode bloquear/limpar rotas para PARES diferentes
            if ev.type in ("route_blocked", "route_cleared") and \
                    (e.get("payload") or {}).get("other_location_id") != ev.payload.get("other_location_id"):
                continue
            return ValidationResult(False, f"duplicata: {ev.type}/{ev.target_id} já no turno {turn}")

    # 3. Regra específica do tipo.
    return _VALIDATORS[ev.type](ev, state, projection)
