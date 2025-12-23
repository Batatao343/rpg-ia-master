"""Campaign planning node used to keep multi-step story arcs coherent."""

from typing import List

from langchain_core.messages import HumanMessage, SystemMessage
from pydantic import BaseModel, Field, field_validator

from llm_setup import ModelTier, get_llm
from state import CampaignBeat, CampaignPlan, GameState


class CampaignPlanModel(BaseModel):
    """Structured response format for the campaign planner LLM."""

    location: str = Field(description="Scene location the plan is for")
    beats: List[str] = Field(
        min_length=3, max_length=5, description="Ordered story beats leading to the climax"
    )
    climax: str = Field(description="The intended climactic moment")

    @field_validator("beats")
    @classmethod
    def validate_beats(cls, beats: List[str]) -> List[str]:
        """Trim whitespace and drop empty beats returned by the model."""

        return [b.strip() for b in beats if b.strip()]


def _should_replan(state: GameState) -> bool:
    """Determine if the campaign plan needs to be regenerated."""

    world = state.get("world", {})
    plan = state.get("campaign_plan")
    turn_count = world.get("turn_count", 0)

    if state.get("needs_replan"):
        return True

    if not plan:
        return True

    location_moved = plan.get("location") and plan["location"] != world.get("current_location")
    if location_moved:
        return True

    last_turn = plan.get("last_planned_turn", -10)
    if turn_count - last_turn >= 10:
        return True

    beats = plan.get("beats") or []
    current_step = plan.get("current_step", 0)
    finished = current_step >= len(beats)
    return finished


def _build_plan(state: GameState) -> CampaignPlan:
    """Generate a structured campaign plan for the current scene."""

    world = state.get("world", {})
    messages = state.get("messages", [])
    last_human = next((m for m in reversed(messages) if isinstance(m, HumanMessage)), None)

    planner_llm = get_llm(temperature=0.35, tier=ModelTier.SMART)
    system_msg = SystemMessage(
        content=(
            "You are the campaign manager for a tabletop RPG. "
            "Design a concise plot roadmap for the current scene with clear beats and climax.\n"
            f"Location: {world.get('current_location', 'Unknown')}\n"
            f"Weather/Time: {world.get('weather', 'unknown')} / {world.get('time_of_day', 'unknown')}\n"
            "Focus on actionable beats that a storyteller can follow to reach the climax."
        )
    )

    prefix = "Recent player intent: " if last_human else "Initial setup: "
    human_msg = HumanMessage(
        content=prefix + (last_human.content if last_human else "Start the scene with strong hooks.")
    )

    try:
        structured = planner_llm.with_structured_output(CampaignPlanModel)
        plan = structured.invoke([system_msg, human_msg])
        beats: List[CampaignBeat] = [
            {"description": beat, "status": "pending"} for beat in plan.beats
        ]
        return {
            "location": plan.location,
            "beats": beats,
            "climax": plan.climax,
            "current_step": 0,
            "last_planned_turn": world.get("turn_count", 0),
        }
    except Exception as exc:  # noqa: BLE001
        print(f"[CAMPAIGN MANAGER ERROR] {exc}")
        fallback_beats: List[CampaignBeat] = [
            {"description": "Set up immediate tension tied to the location.", "status": "pending"},
            {"description": "Reveal a twist, clue, or ally that escalates stakes.", "status": "pending"},
            {"description": "Drive toward a decisive confrontation or choice.", "status": "pending"},
        ]
        return {
            "location": world.get("current_location", "Unknown"),
            "beats": fallback_beats,
            "climax": "Resolve the major conflict with a clear outcome for the party.",
            "current_step": 0,
            "last_planned_turn": world.get("turn_count", 0),
        }


def campaign_manager_node(state: GameState):
    """Ensure a coherent multi-step campaign plan exists and is refreshed periodically."""

    world = dict(state.get("world", {}))
    if world.get("turn_count") is None:
        world["turn_count"] = 0

    if not _should_replan(state):
        return {
            "next": "dm_router",
            "world": world,
            "campaign_plan": state.get("campaign_plan"),
            "needs_replan": False,
        }

    new_plan = _build_plan(state)
    updated_state = {
        "campaign_plan": new_plan,
        "needs_replan": False,
        "world": world,
        "messages": state.get("messages", []),
        "next": "dm_router",
    }
    return updated_state
