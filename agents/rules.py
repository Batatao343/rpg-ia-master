from langchain_core.messages import SystemMessage
from state import GameState
from llm_setup import get_llm
from engine_utils import execute_engine

# --- INTEGRAÇÃO RAG ---
from rag import query_rag

def rules_node(state: GameState):
    player = state["player"]
    last_action = state["messages"][-1].content
    
    # Busca se existe alguma regra específica para o que o jogador tentou
    # Ex: "Escalar muro" -> Busca regras de atletismo/queda em rules.txt
    rules_context = query_rag(last_action, index_name="rules")
    
    if not rules_context:
        rules_context = "Use o bom senso e regras padrão de D&D 5e simplificadas."

    system_msg = SystemMessage(content=f"""
    <role>Mestre de Regras e Física do Mundo.</role>
    <player_stats>Stamina Atual: {player['stamina']}</player_stats>
    
    <consulted_rules>
    {rules_context}
    </consulted_rules>

    <protocol>
    1. Interprete a intenção do jogador.
    2. Se houver uma regra consultada acima aplicável, USE-A (ex: DC específica, dano de queda).
    3. Defina a DC (Dificuldade).
    4. Gere a Tool Call `roll_dice` se houver chance de falha.
    </protocol>
    """)
    
    llm = get_llm(temperature=0.4)
    return execute_engine(llm, system_msg, state["messages"], state, "Regras")