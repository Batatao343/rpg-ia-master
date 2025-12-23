"""Routing agent that selects the next node for the LangGraph workflow."""

from enum import Enum
from typing import List, Optional

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
from langgraph.graph import END
from pydantic import BaseModel, Field

from llm_setup import ModelTier, get_llm
from state import GameState


class RouteType(str, Enum):
    """Supported destinations within the graph."""

    STORY = "storyteller"
    COMBAT = "combat_agent"
    RULES = "rules_agent"
    NPC = "npc_actor"
    NONE = "none"


class RouterDecision(BaseModel):
    """Structured router output expected from the LLM."""

    route: RouteType = Field(description="Chosen route node")
    reasoning: str = Field(description="Why this route was selected")
    confidence: float = Field(ge=0, le=1, description="Confidence from 0 to 1")


def _detect_visible_npcs(state: GameState) -> List[str]:
    """Return NPC names that are currently colocated with the party."""

    loc = state["world"]["current_location"]
    return [
        name
        for name, data in state.get("npcs", {}).items()
        if data.get("location") in {loc, "Party"}
    ]


def _infer_target_npc(messages, visible_npcs: List[str]) -> Optional[str]:
    """Infer the NPC the player is addressing based on the latest human message."""

    last_human = next((m for m in reversed(messages) if isinstance(m, HumanMessage)), None)
    if not last_human:
        return None
    text = last_human.content.lower()
    for npc in visible_npcs:
        if npc.lower() in text:
            return npc
    return None


def _active_campaign_step(state: GameState) -> Optional[str]:
    """Return the description of the current campaign beat or climax."""

    plan = state.get("campaign_plan") or {}
    beats = plan.get("beats") or []
    idx = plan.get("current_step", 0)
    if idx < len(beats):
        return beats[idx].get("description")
    return plan.get("climax")


def dm_router_node(state: GameState):
    """Route execution to the correct node using LLM reasoning and campaign context."""

    messages = state["messages"]
    world = dict(state.get("world", {}))

    if messages and isinstance(messages[-1], HumanMessage):
        world["turn_count"] = world.get("turn_count", 0) + 1

    if not messages:
        return {
            "next": RouteType.STORY.value,
            "world": world,
            "active_plan_step": _active_campaign_step(state),
        }

    if isinstance(messages[-1], AIMessage) and not getattr(messages[-1], "tool_calls", None):
        return {"next": END}

    loc = world["current_location"]
    visible_npcs = _detect_visible_npcs(state)

    active_plan_step = _active_campaign_step(state)

    llm = get_llm(temperature=0.1, tier=ModelTier.FAST)

    system_msg = SystemMessage(
        content=(
            "You are the flow supervisor for a modular RPG engine. "
            "Read the conversation and choose the correct route.\n"
            f"Current location: {loc}\n"
            f"Visible NPCs: {visible_npcs}\n"
            f"Active campaign step: {active_plan_step}\n"
            "Return a structured RouterDecision with route, reasoning, confidence (0-1)."
        )
    )

    try:
        router = llm.with_structured_output(RouterDecision)
        decision = router.invoke([system_msg] + messages)
    except Exception as exc:  # noqa: BLE001
        print(f"[ROUTER ERROR] {exc}")
        fail_msg = AIMessage(content="I'm not sure what you want to do. Let's continue the story for now.")
        return {
            "messages": [fail_msg],
            "next": RouteType.STORY.value,
            "world": world,
            "active_plan_step": active_plan_step,
        }

    if decision.confidence < 0.4:
        clarification = AIMessage(
            content=(
                "I didn't clearly understand your intent. Could you clarify if you want to fight, talk, explore, or test a rule?"
            )
        )
        return {
            "messages": [clarification],
            "next": RouteType.STORY.value,
            "world": world,
            "active_plan_step": active_plan_step,
        }

    target_npc = _infer_target_npc(messages, visible_npcs) if decision.route == RouteType.NPC else None

    if decision.route == RouteType.NPC:
        if not target_npc:
            fallback_msg = AIMessage(content="I don't see that character here. Try addressing someone present.")
            return {
                "messages": [fallback_msg],
                "next": RouteType.STORY.value,
                "world": world,
                "active_plan_step": active_plan_step,
            }
        return {
            "next": RouteType.NPC.value,
            "active_npc_name": target_npc,
            "world": world,
            "active_plan_step": active_plan_step,
        }

    return {"next": decision.route.value, "world": world, "active_plan_step": active_plan_step}
