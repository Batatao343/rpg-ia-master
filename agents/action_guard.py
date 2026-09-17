from langchain_core.messages import AIMessage

from services.actor_lifecycle import (
    evaluate_action,
    orphan_transition,
    sanitize_interturn_state,
)
from services.turn_outcome import capture_baseline


def _latest_human_text(state: dict) -> str:
    for message in reversed(state.get("messages") or []):
        if getattr(message, "type", "") == "human":
            return str(getattr(message, "content", "") or "")
    return ""


def action_guard_node(state: dict) -> dict:
    orphan = orphan_transition(state)
    if orphan is not None:
        repaired = sanitize_interturn_state(state)
        decision = {
            "phase": orphan["phase"],
            "allowed": False,
            "code": "transition_repair_required",
            "action_kind": "none",
            "message": (
                "Uma transição antiga estava incompleta e foi reparada com segurança. "
                "Tente novamente; se você estiver inconsciente, peça descanso, "
                "tratamento ou socorro."
            ),
        }
        return {
            "action_guard_blocked": True,
            "last_action_outcome": decision,
            "messages": [AIMessage(content=decision["message"])],
            "player": repaired.get("player") or {},
            "death_pending": False,
            "game_over": False,
            "needs_replan": True,
        }
    decision = evaluate_action(state, _latest_human_text(state))
    if decision["allowed"]:
        return {"action_guard_blocked": False, "turn_baseline": capture_baseline(state),
                "last_action_outcome": dict(decision)}
    return {"action_guard_blocked": True, "last_action_outcome": dict(decision),
            "messages": [AIMessage(content=decision["message"])]}
