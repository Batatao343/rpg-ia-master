from services.actor_lifecycle import transition_readiness
from services.turn_outcome import finalize_outcome

_RECEIPT_BOUNDARIES = {"ready", "combat_active", "transition_death_pending"}


def turn_finalizer_node(state: dict) -> dict:
    from langgraph.types import Overwrite

    from services.narrative_evidence import guard_current_messages

    messages, audit = guard_current_messages(state)
    state = {**state, "messages": messages}
    readiness = transition_readiness(state)
    if readiness["code"] not in _RECEIPT_BOUNDARIES:
        raise RuntimeError(f"turn_boundary_not_ready:{readiness['code']}:{readiness['phase']}")
    # SPEC-300: ÚNICO escritor da alma dos companheiros (aprovação, aviso, partida, missão
    # pessoal, romance). Roda ANTES do recibo (P2-2): ouro roubado, eventos companion_* e a
    # missão pessoal concluída entram no `receipt_id`. `off` = no-op; falha nunca derruba o turno.
    companion_updates: dict = {}
    try:
        from services import companion_soul

        if companion_soul.mode() != "off":
            companion_updates = companion_soul.apply_turn(state)
            state = {**state, **companion_updates}
    except Exception as exc:
        from observability.telemetry import log_fallback

        log_fallback("companion_soul", "apply_turn_failed", exc)
        companion_updates = {}
    outcome = finalize_outcome(state)
    outcome["transition_readiness"] = dict(readiness)
    from services.interlocutor import speaker_for_turn

    updates = {
        "last_turn_outcome": outcome,
        # SPEC-202 R9: único escritor de last_speaker num turno processado.
        "last_speaker": speaker_for_turn(state),
        **companion_updates,
    }
    # SPEC-203 R7: o desfecho do encontro referencia o recibo SPEC-199 do turno de
    # término (uma vez só; replays/turnos seguintes não reescrevem).
    combat = state.get("combat") or {}
    result = combat.get("result") or {}
    if combat.get("phase") == "ended" and result and not result.get("xp_event_ref"):
        updates["combat"] = {**combat, "result": {**result, "xp_event_ref": outcome["receipt_id"]}}
    # SPEC-215: ponto ÚNICO de entrega de notícias (depois de qualquer avanço de
    # relógio do turno — viagem, descanso ou fuga). `off` = no-op; falha interna
    # nunca derruba o turno.
    try:
        from services import npc_knowledge

        if npc_knowledge.mode() != "off":
            updates.update(npc_knowledge.turn_updates(state))
    except Exception as exc:
        import logging

        logging.getLogger("rpg.npc_knowledge").warning(
            "turn_updates falhou: %s", type(exc).__name__
        )
    # SPEC-298: fama por notícia entregue, pendências de fação, reação de NPCs e avisos.
    try:
        from services import reputation

        updates.update(reputation.turn_updates({**state, **updates}))
    except Exception as exc:  # silent-ok: reputação nunca derruba o turno
        import logging

        logging.getLogger("rpg.reputation").warning("turn_updates falhou: %s", type(exc).__name__)
    if audit:
        updates["messages"] = Overwrite(messages)
        updates["evidence_rejections"] = [*(state.get("evidence_rejections") or []), *audit][-64:]
    return updates
