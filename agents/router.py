from enum import Enum
from typing import List

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
from langgraph.graph import END
from pydantic import BaseModel, Field

from llm_setup import ModelTier, get_llm
from state import GameState


class RouteType(str, Enum):
    STORY = "storyteller"
    COMBAT = "combat_agent"
    RULES = "rules_agent"
    NPC = "npc_actor"
    NONE = "none"


class RouterDecision(BaseModel):
    route: RouteType = Field(description="Chosen route node")
    reasoning: str = Field(description="Why this route was selected")
    confidence: float = Field(ge=0, le=1, description="Confidence from 0 to 1")


def _detect_visible_npcs(state: GameState) -> List[str]:
    loc = state["world"]["current_location"]
    return [
        name
        for name, data in state.get("npcs", {}).items()
        if data.get("location") in {loc, "Party"}
    ]


def _infer_target_npc(messages, visible_npcs: List[str]):
    last_human = next((m for m in reversed(messages) if isinstance(m, HumanMessage)), None)
    if not last_human:
        return None
    text = last_human.content.lower()
    for npc in visible_npcs:
        if npc.lower() in text:
            return npc
    return None


def dm_router_node(state: GameState):
    messages = state["messages"]
    if not messages:
        return {"next": RouteType.STORY.value}

    if isinstance(messages[-1], AIMessage) and not getattr(messages[-1], "tool_calls", None):
        return {"next": END}

    loc = state["world"]["current_location"]
    visible_npcs = _detect_visible_npcs(state)

    llm = get_llm(temperature=0.1, tier=ModelTier.FAST)

    system_msg = SystemMessage(
        content=(
            "You are the flow supervisor for a modular RPG engine. "
            "Read the conversation and choose the correct route.\n"
            f"Current location: {loc}\n"
            f"Visible NPCs: {visible_npcs}\n"
            "Return a structured RouterDecision with route, reasoning, confidence (0-1)."
        )
    )

    try:
        router = llm.with_structured_output(RouterDecision)
        decision = router.invoke([system_msg] + messages)
    except Exception as exc:  # noqa: BLE001
        print(f"[ROUTER ERROR] {exc}")
        fail_msg = AIMessage(content="I'm not sure what you want to do. Let's continue the story for now.")
        return {"messages": [fail_msg], "next": RouteType.STORY.value}

    if decision.confidence < 0.4:
        clarification = AIMessage(
            content=(
                "I didn't clearly understand your intent. Could you clarify if you want to fight, talk, explore, or test a rule?"
            )
        )
        return {"messages": [clarification], "next": RouteType.STORY.value}

    target_npc = _infer_target_npc(messages, visible_npcs) if decision.route == RouteType.NPC else None

    if decision.route == RouteType.NPC:
        if not target_npc:
            fallback_msg = AIMessage(content="I don't see that character here. Try addressing someone present.")
            return {"messages": [fallback_msg], "next": RouteType.STORY.value}
        return {"next": RouteType.NPC.value, "active_npc_name": target_npc}

    return {"next": decision.route.value}
