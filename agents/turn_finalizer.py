from services.actor_lifecycle import transition_readiness
from services.turn_outcome import finalize_outcome


_RECEIPT_BOUNDARIES = {"ready", "combat_active", "transition_death_pending"}


def turn_finalizer_node(state: dict) -> dict:
    from langgraph.types import Overwrite
    from services.narrative_evidence import guard_current_messages
    messages, audit = guard_current_messages(state)
    state = {**state, 'messages': messages}
    readiness = transition_readiness(state)
    if readiness["code"] not in _RECEIPT_BOUNDARIES:
        raise RuntimeError(
            "turn_boundary_not_ready:"
            f"{readiness['code']}:{readiness['phase']}"
        )
    outcome = finalize_outcome(state)
    outcome["transition_readiness"] = dict(readiness)
    updates = {"last_turn_outcome": outcome}
    if audit:
        updates['messages'] = Overwrite(messages)
        updates['evidence_rejections'] = [*(state.get('evidence_rejections') or []), *audit][-64:]
    return updates
