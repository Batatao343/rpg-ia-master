from services.turn_outcome import finalize_outcome


def turn_finalizer_node(state: dict) -> dict:
    return {"last_turn_outcome": finalize_outcome(state)}
