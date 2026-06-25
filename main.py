"""
main.py
Definição da Arquitetura do Grafo (LangGraph).
"""

import os
import sys
from dotenv import load_dotenv
from langgraph.graph import END, START, StateGraph

# --- Console UTF-8 (Windows) ---
# Muitos nós imprimem emojis para log. No console Windows (cp1252) isso
# lança UnicodeEncodeError e derruba o turno inteiro. Forçamos UTF-8.
for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

# Adiciona raiz ao path para garantir imports
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

# --- IMPORTAÇÃO DOS ESTADOS E AGENTES ---
from state import GameState
from agents.campaign_manager import campaign_manager_node
from agents.combat import combat_node
from agents.npc import npc_actor_node
from agents.router import dm_router_node
from agents.storyteller import storyteller_node
from agents.loot import loot_node
from agents.archivist import archive_node # <--- NOVO

load_dotenv(override=True)  # .env canônico (sobrepõe env var do SO)

def build_game_graph():
    """Constrói e compila o grafo de estados do jogo."""
    
    workflow = StateGraph(GameState)

    # 1. Adicionar Nós
    workflow.add_node("campaign_manager", campaign_manager_node)
    workflow.add_node("dm_router", dm_router_node)
    workflow.add_node("storyteller", storyteller_node)
    workflow.add_node("combat_agent", combat_node)
    workflow.add_node("npc_actor", npc_actor_node)
    workflow.add_node("loot_agent", loot_node)
    workflow.add_node("archivist", archive_node) # <--- NOVO

    # 2. Definir o Fluxo Inicial
    workflow.add_edge(START, "campaign_manager")
    workflow.add_edge("campaign_manager", "dm_router")

    # 3. Roteamento Central
    workflow.add_conditional_edges(
        "dm_router",
        lambda state: state.get("next"),
        {
            "storyteller": "storyteller",
            "combat_agent": "combat_agent",
            "npc_actor": "npc_actor",
            "loot": "loot_agent",
            END: END,
        },
    )

    # 4. Encerramento com Arquivamento
    # Todo fim de turno passa pelo arquivista para atualizar memórias
    workflow.add_edge("storyteller", "archivist")
    workflow.add_edge("npc_actor", "archivist")
    workflow.add_edge("loot_agent", "archivist")

    # Combate: ao vencer, o nó sinaliza next="loot" para gerar espólio.
    # Nos demais casos segue direto para o arquivista.
    workflow.add_conditional_edges(
        "combat_agent",
        lambda state: "loot_agent" if state.get("next") == "loot" else "archivist",
        {
            "loot_agent": "loot_agent",
            "archivist": "archivist",
        },
    )
    
    workflow.add_edge("archivist", END) # O arquivista encerra o turno

    # Compila o grafo
    return workflow.compile()

# Instância global
app = build_game_graph()

if __name__ == "__main__":
    print("🤖 Grafo definido. Execute 'game_engine.py' para jogar.")