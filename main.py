"""
main.py
Definição da Arquitetura do Grafo (LangGraph).
Conecta os agentes especialistas: Router, Combat, Storyteller, NPC e Loot.
"""

import os
import sys
from dotenv import load_dotenv
from langgraph.graph import END, START, StateGraph

# Adiciona raiz ao path para garantir imports
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

# --- IMPORTAÇÃO DOS ESTADOS E AGENTES ---
from state import GameState
from agents.campaign_manager import campaign_manager_node
from agents.combat import combat_node
from agents.npc import npc_actor_node
from agents.router import dm_router_node
from agents.storyteller import storyteller_node
from agents.loot import loot_node  # <--- Nó de Loot Integrado

load_dotenv()

def build_game_graph():
    """Constrói e compila o grafo de estados do jogo."""
    
    workflow = StateGraph(GameState)

    # 1. Adicionar Nós (Os Agentes Especialistas)
    workflow.add_node("campaign_manager", campaign_manager_node)
    workflow.add_node("dm_router", dm_router_node)
    workflow.add_node("storyteller", storyteller_node)
    workflow.add_node("combat_agent", combat_node)
    workflow.add_node("npc_actor", npc_actor_node)
    workflow.add_node("loot_agent", loot_node)

    # 2. Definir o Fluxo Inicial
    # Sempre passa pelo Campaign Manager para atualizar quests/beats antes de rotear
    workflow.add_edge(START, "campaign_manager")
    workflow.add_edge("campaign_manager", "dm_router")

    # 3. Roteamento Central (Router Decision)
    # O Router define o campo 'next' no estado, e aqui mapeamos para o nó correto
    workflow.add_conditional_edges(
        "dm_router",
        lambda state: state.get("next"),
        {
            "storyteller": "storyteller",
            "combat_agent": "combat_agent",
            "npc_actor": "npc_actor",
            "loot": "loot_agent",  # Router retorna "loot" -> vai para nó "loot_agent"
            END: END,
        },
    )

    # 4. Encerramento do Turno (Loop Interno)
    # Após o especialista agir, o turno da IA encerra e volta para o input do usuário
    workflow.add_edge("storyteller", END)
    workflow.add_edge("combat_agent", END)
    workflow.add_edge("npc_actor", END)
    workflow.add_edge("loot_agent", END)

    # Compila o grafo
    return workflow.compile()

# Instância global do grafo para ser importada pelo engine
app = build_game_graph()

if __name__ == "__main__":
    # Apenas gera o diagrama se rodar direto, para debug
    print("🤖 Grafo definido. Execute 'game_engine.py' para jogar.")
    try:
        with open("graph_architecture.png", "wb") as f:
            f.write(app.get_graph().draw_mermaid_png())
        print("📸 Diagrama salvo em graph_architecture.png")
    except:
        pass