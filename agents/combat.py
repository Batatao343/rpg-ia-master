from langchain_core.messages import SystemMessage, AIMessage, HumanMessage
from state import GameState
from llm_setup import get_llm
from gamedata import ITEMS_DB
from engine_utils import execute_engine

# --- INTEGRAÇÃO RAG ---
from rag import query_rag

def get_mod(score: int) -> int: return (score - 10) // 2

def combat_node(state: GameState):
    player = state["player"]
    
    # Cálculos Básicos
    attrs = player['attributes']
    mods = {k: get_mod(v) for k, v in attrs.items()}
    
    best_bonus = 0
    active_attr = "strength"
    for i in player.get('inventory', []):
        d = ITEMS_DB.get(i)
        if d and d['type'] == 'weapon' and d['bonus'] > best_bonus: 
            best_bonus = d['bonus']; active_attr = d['attr']
    total_atk = mods[active_attr] + best_bonus

    # Inimigos Ativos
    enemies = state.get('enemies', [])
    active_enemies = [e for e in enemies if e['status'] == 'ativo']
    enemy_str = "\n".join([f"{idx+1}. {e['name']} (ID:{e['id']} | HP:{e['hp']} | Cond:{e.get('active_conditions',[])})" for idx, e in enumerate(active_enemies)])

    # Verifica última intenção do jogador para buscar regra
    last_msg = state["messages"][-1]
    player_already_acted = isinstance(last_msg, AIMessage) and not last_msg.tool_calls
    
    last_user_intent = ""
    if isinstance(last_msg, HumanMessage):
        last_user_intent = last_msg.content

    # 1. CONSULTA O RAG (REGRAS DE COMBATE)
    # Se o jogador disse "Agarrar", o RAG busca a regra de Grapple no rules.txt
    combat_rules = ""
    if last_user_intent:
        combat_rules = query_rag(last_user_intent, index_name="rules")
        if not combat_rules:
            combat_rules = "Regras Padrão: Ataque x AC. Dano reduz HP."

    system_msg = SystemMessage(content=f"""
    <role>General de Combate (Game Engine).</role>
    
    <state>
    Player: HP {player['hp']} | ATK +{total_atk} | AC {player['defense']}
    Condições Atuais: {player.get('active_conditions',[])}
    Inimigos Visíveis:
    {enemy_str}
    
    Player Já Agiu Neste Turno? {player_already_acted}
    </state>
    
    <consulted_rules>
    {combat_rules}
    </consulted_rules>

    <protocol>
    1. AÇÃO JOGADOR (Se não agiu):
       - Analise a intenção. Se for Ataque, requer Tool 'Ataque Jogador'.
       - Se for Manobra (Desarmar, Empurrar), siga a regra em <consulted_rules>.
    
    2. REAÇÃO INIMIGA (Se Player já agiu ou sobrou ação):
       - Inimigos vivos contra-atacam. 
       - Se Inimigo tem condição 'Cego/Caído', aplique penalidade (Desvantagem).
    </protocol>
    """)
    
    llm = get_llm(temperature=0.1)
    return execute_engine(llm, system_msg, state["messages"], state, "Combate")