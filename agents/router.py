from typing import Literal, Optional, TypedDict
from langchain_core.messages import SystemMessage, AIMessage
from state import GameState
from llm_setup import get_llm
from langgraph.graph import END

class RouteDecision(TypedDict):
    destination: Literal["storyteller", "combat_agent", "rules_agent", "npc_actor"]
    npc_name: Optional[str]
    reasoning: str

def dm_router_node(state: GameState):
    messages = state["messages"]
    # Se a última msg foi da IA (e não foi tool call), o turno acabou.
    if isinstance(messages[-1], AIMessage) and not messages[-1].tool_calls: 
        return {"next": END} 

    # 1. FILTRO DE REALIDADE (Quem está na cena?)
    loc = state['world']['current_location']
    # Lista apenas NPCs que estão no local atual OU na Party
    visible_npcs = [n for n, d in state.get('npcs', {}).items() 
                   if d['location'] == loc or d['location'] == 'Party']

    llm = get_llm(temperature=0.1)
    
    # 2. PROMPT COM REGRAS DE INTERAÇÃO
    sys = SystemMessage(content=f"""
    <role>Supervisor de Fluxo RPG.</role>
    <context>
    Local Atual: {loc}
    NPCs Visíveis/Existentes: {visible_npcs}
    </context>
    <rules>
    1. INTERAÇÃO SOCIAL ('npc_actor'): 
       - O jogador SÓ pode falar com NPCs listados em 'NPCs Visíveis'.
       - Se ele tentar falar com alguém que NÃO está na lista (ex: "Falo com o Rei" e o Rei não está lá), envie para 'storyteller'.
    
    2. COMBATE ('combat_agent'):
       - Ataques, agressão física ou início de hostilidades.
    
    3. REGRAS/PERÍCIA ('rules_agent'):
       - Ações físicas (escalar, esconder), uso de itens ou magia utilitária.
    
    4. NARRATIVA ('storyteller'):
       - Exploração, perguntas sobre o ambiente, falar sozinho ou tentar falar com NPCs inexistentes.
    </rules>
    """)
    
    try:
        router = llm.with_structured_output(RouteDecision)
        decision = router.invoke([sys] + messages)
        
        dest = decision['destination']
        target = decision['npc_name']

        # 3. VALIDAÇÃO DE SEGURANÇA (O "LEÃO DE CHÁCARA")
        # Mesmo que a IA decida 'npc_actor', o Python verifica se é possível.
        if dest == 'npc_actor' and target:
            # Normalização para comparação (case insensitive)
            visible_lower = [n.lower() for n in visible_npcs]
            
            # Se o alvo não existe, bloqueia e manda pro Narrador explicar
            if target.lower() not in visible_lower:
                return {"next": "storyteller"}
            
            # Se existe, libera o acesso
            return {"next": "npc_actor", "active_npc_name": target}
            
        return {"next": dest}
        
    except: return {"next": "storyteller"}