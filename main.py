"""
main.py
Graph assembly for the tabletop RPG engine workflow.

ATUALIZAÇÃO V8 (Re-Act Architecture):
- Removeu 'rules_agent' (agora integrado via logic/ruler.py).
- Removeu 'tools' node (agora executado internamente via engine_utils.py).
- Fluxo simplificado: Router -> Agente Especialista -> Fim.
"""

import os
from dotenv import load_dotenv
from langgraph.graph import END, START, StateGraph

# --- IMPORTAÇÃO DOS AGENTES ---
from agents.campaign_manager import campaign_manager_node
from agents.combat import combat_node
from agents.npc import npc_actor_node
from agents.router import dm_router_node
from agents.storyteller import storyteller_node
# from agents.rules import rules_node  <-- REMOVIDO (Obsoleto)

# --- IMPORTAÇÃO DO ESTADO ---
from state import GameState

load_dotenv()

# --- CONSTUÇÃO DO GRAFO ---
workflow = StateGraph(GameState)

# 1. Adicionar Nós (Agentes)
workflow.add_node("campaign_manager", campaign_manager_node)
workflow.add_node("dm_router", dm_router_node)
workflow.add_node("storyteller", storyteller_node)
workflow.add_node("combat_agent", combat_node)
workflow.add_node("npc_actor", npc_actor_node)

# 2. Definir o Início
# Sempre passamos pelo Campaign Manager para verificar quests/progressão antes de rotear
workflow.add_edge(START, "campaign_manager")
workflow.add_edge("campaign_manager", "dm_router")

# 3. Roteamento Central
# O Router decide quem narra o turno com base na intenção do usuário e estado do jogo
workflow.add_conditional_edges(
    "dm_router",
    lambda s: s.get("next"),
    {
        "storyteller": "storyteller",
        "combat_agent": "combat_agent",
        "npc_actor": "npc_actor",
        # "rules_agent": "rules_agent", <-- REMOVIDO
        END: END,
    },
)

# 4. Encerramento do Turno
# Como os agentes agora usam 'execute_engine' (que roda dados e atualiza HP internamente),
# quando eles retornam, o turno está concluído e aguardamos o próximo input do usuário.
workflow.add_edge("storyteller", END)
workflow.add_edge("combat_agent", END)
workflow.add_edge("npc_actor", END)

# Compilação do App
app = workflow.compile()

if __name__ == "__main__":
    print("🤖 RPG Engine V8 (Internal Loop Edition) carregada e pronta!")
    # Opcional: Gerar imagem do grafo para visualização
    # try:
    #     with open("graph_v8.png", "wb") as f:
    #         f.write(app.get_graph().draw_mermaid_png())
    #     print("📸 Grafo salvo como graph_v8.png")
    # except Exception:
    #     pass