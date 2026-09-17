from services.actor_lifecycle import transition_readiness
from services.turn_outcome import finalize_outcome


_RECEIPT_BOUNDARIES = {"ready", "combat_active", "transition_death_pending"}


def turn_finalizer_node(state: dict) -> dict:
    readiness = transition_readiness(state)
    if readiness["code"] not in _RECEIPT_BOUNDARIES:
        raise RuntimeError(
            "turn_boundary_not_ready:"
            f"{readiness['code']}:{readiness['phase']}"
        )
    outcome = finalize_outcome(state)
    outcome["transition_readiness"] = dict(readiness)
    return {"last_turn_outcome": outcome}
