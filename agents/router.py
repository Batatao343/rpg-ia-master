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

    llm = get_llm(temperature=0.0, tier=ModelTier.CLASSIFY)

    try:
        router_llm = llm.with_structured_output(RouterDecision)
        decision = router_llm.invoke([SystemMessage(content=system_instruction)] + messages[-3:])
    except Exception as e:
        print(f"⚠️ Router Error: {e}")
        return {"next": RouteType.STORY.value}

    # Sem API key (FallbackLLM) o invoke devolve um AIMessage, não um
    # RouterDecision. Nesse caso seguimos para o storyteller (modo degradado).
    if not isinstance(decision, RouterDecision):
        return {"next": RouteType.STORY.value}

    # RouteType.NONE ("nenhuma intenção clara": input sem ação, lixo ou injeção)
    # NÃO é um nó do grafo — o mapping condicional de main.py só conhece
    # storyteller/combat/npc/loot/END. O LLM real ESCOLHE NONE para a entrada do
    # troll (emoji, SQL, "ignore as instruções") e o router devolvia next="none"
    # → KeyError('none') no grafo. O MockLLM nunca escolhe NONE, então o bug só
    # aparecia no LLM real (achado do playtest da Fase 5). Normaliza para STORY:
    # o narrador descreve o ambiente em vez de derrubar o turno.
    if decision.route == RouteType.NONE:
        decision.route = RouteType.STORY

    print(f"🚦 [ROUTER] {decision.route.value} -> Alvo: {decision.target}")

    response_payload = {
        "next": decision.route.value,
        "world": world,
        "combat_target": decision.target, # Passa o alvo para ajudar o Spawner
    }

    if decision.route == RouteType.LOOT:
        response_payload["loot_source"] = decision.loot_context or "TREASURE"

    # GATILHO DE NPC:
    # O ator de NPC exige 'active_npc_name'. Sem isso ele responde "Ninguém responde".
    # Tentamos casar o alvo identificado com um NPC já presente na cena.
    if decision.route == RouteType.NPC:
        npcs = state.get("npcs", {}) or {}
        chosen = None
        if decision.target:
            tgt = decision.target.lower()
            for npc_name in npcs.keys():
                if tgt in npc_name.lower() or npc_name.lower() in tgt:
                    chosen = npc_name
                    break
        # Fallback: se só há um NPC na cena, fala com ele.
        if not chosen and len(npcs) == 1:
            chosen = next(iter(npcs.keys()))
        if not chosen and decision.target:
            chosen = decision.target  # deixa o ator tentar carregar do DB
        response_payload["active_npc_name"] = chosen

    # GATILHO DE COMBATE:
    # Se for combate, adicionamos uma flag no histórico (temporária) para o Combat Agent saber que é o turno 1
    if decision.route == RouteType.COMBAT:
        if "messages" not in response_payload: response_payload["messages"] = []
        response_payload["messages"].append(SystemMessage(content=f"SYSTEM: COMBAT START. TARGET_HINT: {decision.target}"))

    return response_payload