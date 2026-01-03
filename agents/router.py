"""
agents/router.py
Roteador de Intenções.
Agora com detecção explícita de início de combate para acionar o Spawner.
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
    loot_context: Optional[str] = Field(description="Se for LOOT: 'TREASURE', 'SHOP' ou 'CRAFT'.")
    target: Optional[str] = Field(description="Se for COMBAT, quem é o inimigo? Ex: 'Goblin', 'Guarda', 'O Vulto'.")
    reasoning: str
    confidence: float

def dm_router_node(state: GameState):
    messages = state.get("messages", [])
    if not messages: return {"next": RouteType.STORY.value}
    
    last_msg = messages[-1]
    # Evita loop se a IA acabou de falar (exceto tool calls)
    if isinstance(last_msg, AIMessage) and not getattr(last_msg, "tool_calls", None):
        return {"next": END}

    world = state.get("world", {})
    loc = world.get("current_location", "Desconhecido")
    
    system_instruction = f"""
    Roteador de RPG. Classifique a intenção da ÚLTIMA mensagem do jogador.
    
    Local Atual: {loc}
    
    REGRAS:
    - COMBAT: Jogador ataca, saca armas ou reage a uma ameaça narrada. IMPORTANTE: Identifique o 'target' (inimigo).
    - NPC: Conversa social, diplomacia.
    - LOOT: "Vasculhar corpo", "Pegar item", "Abrir baú" (TREASURE) ou "Comprar/Vender/Criar" (SHOP/CRAFT).
    - STORY: Movimentação, exploração, observar cenário.
    """

    llm = get_llm(temperature=0.0, tier=ModelTier.FAST)

    try:
        router_llm = llm.with_structured_output(RouterDecision)
        decision = router_llm.invoke([SystemMessage(content=system_instruction)] + messages[-3:])
    except Exception as e:
        print(f"⚠️ Router Error: {e}")
        return {"next": RouteType.STORY.value}

    print(f"🚦 [ROUTER] {decision.route.value} -> Alvo: {decision.target}")

    response_payload = {
        "next": decision.route.value,
        "world": world,
        "combat_target": decision.target, # Passa o alvo para ajudar o Spawner
    }

    if decision.route == RouteType.LOOT:
        response_payload["loot_source"] = decision.loot_context or "TREASURE"
    
    # GATILHO DE COMBATE:
    # Se for combate, adicionamos uma flag no histórico (temporária) para o Combat Agent saber que é o turno 1
    if decision.route == RouteType.COMBAT:
        if "messages" not in response_payload: response_payload["messages"] = []
        response_payload["messages"].append(SystemMessage(content=f"SYSTEM: COMBAT START. TARGET_HINT: {decision.target}"))

    return response_payload