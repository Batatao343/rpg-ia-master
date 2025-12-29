"""
agents/router.py
Roteador de Intenções.
Agora capaz de distinguir 'Conversa Social' de 'Ação de Comércio/Crafting'.
"""
from enum import Enum
from typing import Optional
from langchain_core.messages import AIMessage, SystemMessage, HumanMessage
from langgraph.graph import END
from pydantic import BaseModel, Field

from llm_setup import ModelTier, get_llm
from state import GameState

class RouteType(str, Enum):
    STORY = "storyteller"
    COMBAT = "combat_agent"
    NPC = "npc_actor"
    LOOT = "loot" 
    NONE = "none"

class RouterDecision(BaseModel):
    route: RouteType
    loot_context: Optional[str] = Field(description="Se for LOOT, especifique: 'TREASURE' (saque), 'SHOP' (comprar/vender) ou 'CRAFT' (criar/melhorar).")
    target: Optional[str]
    reasoning: str
    confidence: float

def dm_router_node(state: GameState):
    messages = state.get("messages", [])
    if not messages: return {"next": RouteType.STORY.value}
    
    last_msg = messages[-1]
    # Se a última msg for da IA e não for tool call, encerra o turno
    if isinstance(last_msg, AIMessage) and not getattr(last_msg, "tool_calls", None):
        return {"next": END}

    world = state.get("world", {})
    loc = world.get("current_location", "Desconhecido")
    
    # Contexto para a IA decidir
    system_instruction = f"""
    Roteador de RPG. Classifique a intenção da ÚLTIMA mensagem do jogador.

    regras:
    - LOOT/CRAFT: Se o jogador quer explicitamente TROCAR itens, COMPRAR, VENDER, FORJAR ou MELHORAR equipamento.
      Ex: "Compro a poção", "Faça uma espada melhor com isso", "Vendo meu escudo".
      -> Use loot_context='SHOP' (comércio) ou 'CRAFT' (manufatura).
    
    - LOOT/TREASURE: Se o jogador está vasculhando, saqueando corpos ou abrindo baús.
      -> Use loot_context='TREASURE'.

    - NPC: Conversa social, perguntas, intimidação, persuasão (sem troca de itens imediata).
    - COMBAT: Ataques, agressão.
    - STORY: Exploração, olhar em volta, ir para outro lugar.

    Local: {loc}
    """

    llm = get_llm(temperature=0.0, tier=ModelTier.FAST)

    try:
        router_llm = llm.with_structured_output(RouterDecision)
        # Analisa as ultimas 3 mensagens para ter contexto
        decision = router_llm.invoke([SystemMessage(content=system_instruction)] + messages[-3:])
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
    
    # Se for combate, adiciona flag de inicio
    if decision.route == RouteType.COMBAT:
        if "messages" not in response_payload: response_payload["messages"] = []
        response_payload["messages"].append(SystemMessage(content="SYSTEM: COMBAT START."))

    return response_payload