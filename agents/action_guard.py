from langchain_core.messages import AIMessage

from services.actor_lifecycle import evaluate_action
from services.turn_outcome import capture_baseline


def _latest_human_text(state: dict) -> str:
    for message in reversed(state.get("messages") or []):
        if getattr(message, "type", "") == "human":
            return str(getattr(message, "content", "") or "")
    return ""


def action_guard_node(state: dict) -> dict:
    decision = evaluate_action(state, _latest_human_text(state))
    if decision["allowed"]:
        return {"action_guard_blocked": False, "turn_baseline": capture_baseline(state),
                "last_action_outcome": dict(decision)}
    return {"action_guard_blocked": True, "last_action_outcome": dict(decision),
            "messages": [AIMessage(content=decision["message"])]}
