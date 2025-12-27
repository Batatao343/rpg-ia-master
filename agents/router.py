"""
agents/router.py
Roteador de Intenções (Incluindo Loot e Comércio).
"""
from enum import Enum
from typing import Optional
from langchain_core.messages import AIMessage, SystemMessage
from langgraph.graph import END
from pydantic import BaseModel, Field

from llm_setup import ModelTier, get_llm
from state import GameState

class RouteType(str, Enum):
    STORY = "storyteller"
    COMBAT = "combat_agent"
    NPC = "npc_actor"
    LOOT = "loot" # <--- Nova Rota unificada para Loot/Shop/Treasure
    NONE = "none"

class RouterDecision(BaseModel):
    route: RouteType
    loot_context: Optional[str] = Field(description="Se for LOOT, especifique: 'SHOP' ou 'TREASURE'.")
    target: Optional[str]
    reasoning: str
    confidence: float

def dm_router_node(state: GameState):
    messages = state.get("messages", [])
    if not messages: return {"next": RouteType.STORY.value}
    
    last_msg = messages[-1]
    if isinstance(last_msg, AIMessage) and not getattr(last_msg, "tool_calls", None):
        return {"next": END}

    world = state.get("world", {})
    loc = world.get("current_location", "Desconhecido")
    visible_npcs = list(state.get("npcs", {}).keys())

    system_instruction = f"""
    Roteador de RPG. Classifique a intenção do jogador.

    ROTA 'LOOT' (Use loot_context):
    - Se o jogador quer comprar/vender/visitar loja -> loot_context='SHOP'.
    - Se o jogador quer procurar/saquear/abrir baús -> loot_context='TREASURE'.
    
    ROTA 'COMBAT': Hostilidade, ataques.
    ROTA 'NPC': Conversa direta com {visible_npcs}.
    ROTA 'STORY': Exploração, viagem, narrar.

    Local: {loc}
    """

    llm = get_llm(temperature=0.0, tier=ModelTier.FAST)

    try:
        router_llm = llm.with_structured_output(RouterDecision)
        decision = router_llm.invoke([SystemMessage(content=system_instruction)] + messages[-5:])
    except Exception as e:
        print(f"⚠️ Router Error: {e}")
        return {"next": RouteType.STORY.value}

    print(f"🚦 [ROUTER] {decision.route.value} (Ctx: {decision.loot_context})")

    response_payload = {
        "next": decision.route.value,
        "world": world,
        "router_confidence": decision.confidence,
        "combat_target": decision.target,
    }

    # Configura Contexto de Loot para o próximo agente
    if decision.route == RouteType.LOOT:
        response_payload["loot_source"] = decision.loot_context or "TREASURE"
    
    # Handshake de Combate
    if decision.route == RouteType.COMBAT:
        if "messages" not in response_payload: response_payload["messages"] = []
        response_payload["messages"].append(SystemMessage(content="SYSTEM: COMBAT START."))

    return response_payload