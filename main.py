import os
from dotenv import load_dotenv
from langgraph.graph import StateGraph, START, END
from langgraph.prebuilt import ToolNode

from agents.campaign_manager import campaign_manager_node
from agents.router import dm_router_node
from agents.storyteller import storyteller_node
from agents.combat import combat_node
from agents.rules import rules_node
from agents.npc import npc_actor_node
from state import GameState
from tools import roll_dice

load_dotenv()

workflow = StateGraph(GameState)

workflow.add_node("campaign_manager", campaign_manager_node)
workflow.add_node("dm_router", dm_router_node)
workflow.add_node("storyteller", storyteller_node)
workflow.add_node("combat_agent", combat_node)
workflow.add_node("rules_agent", rules_node)
workflow.add_node("npc_actor", npc_actor_node)
workflow.add_node("tools", ToolNode([roll_dice]))

workflow.add_edge(START, "campaign_manager")
workflow.add_edge("campaign_manager", "dm_router")

workflow.add_conditional_edges(
    "dm_router",
    lambda s: s.get("next"),
    {
        "campaign_manager": "campaign_manager",
        "storyteller": "storyteller",
        "combat_agent": "combat_agent",
        "rules_agent": "rules_agent",
        "npc_actor": "npc_actor",
        END: END,
    },
)

workflow.add_edge("storyteller", END)
workflow.add_edge("npc_actor", END)


def rules_next_step(state: GameState):
    enemies = state.get('enemies', [])
    if any(e['status'] == 'ativo' for e in enemies):
        return "combat_agent"
    return END


workflow.add_conditional_edges(
    "rules_agent",
    lambda s: "tools" if s["messages"][-1].tool_calls else rules_next_step(s),
    {"tools": "tools", "combat_agent": "combat_agent", END: END},
)

workflow.add_conditional_edges(
    "combat_agent",
    lambda s: "tools" if s["messages"][-1].tool_calls else END,
    {"tools": "tools", END: END},
)

workflow.add_edge("tools", "dm_router")

app = workflow.compile()

if __name__ == "__main__":
    print("🤖 RPG Engine V8 Modular carregada!")
