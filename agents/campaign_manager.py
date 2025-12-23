"""Campaign planning node used to keep multi-step story arcs coherent."""

from typing import List

from langchain_core.messages import HumanMessage, SystemMessage
from pydantic import BaseModel, Field, field_validator

from llm_setup import ModelTier, get_llm
from state import CampaignBeat, CampaignPlan, GameState

# --- INTEGRAÇÃO RAG ---
from rag import query_rag  # <--- Importação necessária


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
    """Generate a structured campaign plan for the current scene using RAG context."""

    world = state.get("world", {})
    messages = state.get("messages", [])
    current_loc = world.get("current_location", "Unknown")
    
    last_human = next((m for m in reversed(messages) if isinstance(m, HumanMessage)), None)
    last_intent = last_human.content if last_human else ""

    # --- 1. BUSCA DE LORE (RAG) ---
    # Buscamos informações sobre o local atual e o que o jogador quer fazer
    search_query = f"{current_loc} {last_intent}"
    try:
        lore_context = query_rag(search_query, index_name="lore")
    except Exception as exc:  # noqa: BLE001
        print(f"[CAMPAIGN RAG ERROR] {exc}")
        lore_context = "No specific lore available for this location."

    # --- 2. CONFIGURAÇÃO DO LLM ---
    planner_llm = get_llm(temperature=0.4, tier=ModelTier.SMART) # Aumentei levemente a temp para criatividade
    
    system_msg = SystemMessage(
        content=(
            "<PERSONA>\n"
            "You are the Campaign Architect for a rich, immersive tabletop RPG.\n"
            
            "<CONTEXT>\n"
            f"Location: {current_loc}\n"
            f"Weather/Time: {world.get('weather', 'unknown')} / {world.get('time_of_day', 'unknown')}\n"
            
            "<LORE_CONTEXT>\n"
            f"{lore_context}\n"
            "</LORE_CONTEXT>\n"

            "<INSTRUCTIONS>\n"
            "Design a concise plot roadmap (3-5 beats) for the current scene.\n"
            "1. USE THE LORE: If the lore mentions specific dangers, factions, or secrets, weave them into the beats.\n"
            "2. PACING: Start with atmosphere/hook, rise tension, and lead to a climax.\n"
            "3. ACTIONABLE: Beats must be clear instructions for the Storyteller AI (e.g., 'Reveal the ancient inscription on the wall').\n"

            "<EXAMPLE>\n"
            "Lore: 'The Whispering Caves are haunted by echoes of the past.'\n"
            "Beats: ['Describe the unsettling echoes mimicking the party', 'Player finds a skeleton with a warning note', 'The echoes coalesce into a spectral guardian']\n"
            "Climax: 'Confrontation with the Specter or solving its riddle.'"
        )
    )

    prefix = "Recent player intent: " if last_human else "Initial setup: "
    human_msg = HumanMessage(
        content=prefix + (last_intent if last_intent else "Start the scene with strong hooks.")
    )

    try:
        structured = planner_llm.with_structured_output(CampaignPlanModel)
        # Passamos o histórico recente para ele entender o fluxo imediato
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
            {"description": f"Explore the mysteries of {current_loc}.", "status": "pending"},
            {"description": "Encounter a challenge related to the local environment.", "status": "pending"},
            {"description": "Make a significant discovery or face a threat.", "status": "pending"},
        ]
        return {
            "location": current_loc,
            "beats": fallback_beats,
            "climax": "Resolve the immediate conflict.",
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

    print(f"🗺️ [CAMPAIGN] Generating new plot for: {world.get('current_location')}")
    new_plan = _build_plan(state)
    
    updated_state = {
        "campaign_plan": new_plan,
        "needs_replan": False,
        "world": world,
        # Importante: Não sobrescrevemos 'messages' aqui para não perder histórico
        "next": "dm_router",
    }
    return updated_state