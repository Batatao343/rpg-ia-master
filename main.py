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
    # R4 (fix-playtest-achados): save morto (game_over) é MEMORIAL — o grafo NÃO
    # processa turno novo. Antes só a API barrava (409); runner/CLI e qualquer
    # chamador direto de app.invoke seguiam o jogo com um personagem morto
    # (achado do playtest real). O gate protege TODO chamador.
    # spec checkpoints-morte: death_pending (queda letal aguardando a tela de morte)
    # também barra o turno novo — o grafo NÃO processa com o herói caído até o
    # jogador escolher Continuar (restaura) ou Aceitar (memorial).
    workflow.add_conditional_edges(
        START,
        lambda s: "__end__" if (s.get("game_over") or s.get("death_pending")) else "campaign_manager",
        {"__end__": END, "campaign_manager": "campaign_manager"},
    )
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
    workflow.add_edge("loot_agent", "archivist")

    # spec npc-fallback-sem-alvo (R2): sem interlocutor, o npc_actor delega ao
    # storyteller (narra a ausência + gancho) em vez de "Ninguém responde.".
    # Caso normal (conversou) segue direto para o arquivista.
    workflow.add_conditional_edges(
        "npc_actor",
        lambda s: "storyteller" if s.get("next") == "storyteller" else "archivist",
        {"storyteller": "storyteller", "archivist": "archivist"},
    )

    # Storyteller pode disparar um ENCONTRO (mundo perigoso/dominado/ameaçado) → combate.
    # Caso contrário, segue para o arquivista normalmente.
    workflow.add_conditional_edges(
        "storyteller",
        lambda s: "combat_agent" if s.get("next") == "combat_agent" else "archivist",
        {"combat_agent": "combat_agent", "archivist": "archivist"},
    )

    # Combate: ao vencer, o nó sinaliza next="loot" para gerar espólio.
    # Nos demais casos segue direto para o arquivista.
    workflow.add_conditional_edges(
        "combat_agent",
        lambda state: (
            "__end__"
            if (state.get("combat_simulation") or {}).get("enabled")
            else "loot_agent" if state.get("next") == "loot" else "archivist"
        ),
        {
            "loot_agent": "loot_agent",
            "archivist": "archivist",
            "__end__": END,
        },
    )
    
    workflow.add_edge("archivist", END) # O arquivista encerra o turno

    # Compila o grafo
    return workflow.compile()

# Instância global
app = build_game_graph()

if __name__ == "__main__":
    print("🤖 Grafo definido. Execute 'game_engine.py' para jogar.")
