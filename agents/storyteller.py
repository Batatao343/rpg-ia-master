from typing import List
from pydantic import BaseModel, Field
from langchain_core.messages import SystemMessage, HumanMessage, AIMessage
from state import GameState
from llm_setup import get_llm

# Importa a função de criação (já integrada com RAG no npc.py)
from agents.npc import generate_new_npc

# --- INTEGRAÇÃO RAG ---
from rag import query_rag

# Schema de Saída
class StoryUpdate(BaseModel):
    narrative: str = Field(description="O texto narrativo da resposta.")
    introduced_npcs: List[str] = Field(default_factory=list, description="Lista de nomes de NOVOS personagens que entraram na cena nesta rodada.")

def storyteller_node(state: GameState):
    messages = state["messages"]
    if not messages:
        return {"messages": [AIMessage(content="Conte sua ação inicial para começarmos a história.")]}
    if not isinstance(messages[-1], HumanMessage):
        return {"messages": [AIMessage(content="Preciso da sua próxima ação para narrar o que acontece em seguida.")]}
    
    last_user_input = messages[-1].content
    loc = state['world']['current_location']
    existing_npcs = list(state.get('npcs', {}).keys())
    
    # 1. CONSULTA A LORE (RAG)
    # Busca contexto sobre o Local atual + o que o jogador falou
    # Ex: se o local é "Ruínas de Zarr" e o jogador pergunta "Quem viveu aqui?", o RAG busca a resposta.
    lore_context = query_rag(f"{loc} {last_user_input}", index_name="lore")
    
    if not lore_context:
        lore_context = "Nenhuma lore específica encontrada. Use criatividade Dark Fantasy."

    llm = get_llm(temperature=0.7)

    if getattr(llm, "is_fallback", False):
        return {"messages": [llm.invoke(None)]}
    
    sys = SystemMessage(content=f"""
    Você é o Narrador (Mestre) de um RPG.
    Local Atual: {loc}.
    NPCs já na cena: {existing_npcs}.

    === CONTEXTO DO MUNDO (LORE) ===
    {lore_context}
    ================================

    INSTRUÇÕES DE ESTILO:
    - Responda em 2 a 3 parágrafos curtos, claros e objetivos.
    - Termine SEMPRE oferecendo 1 a 3 opções numeradas OU uma pergunta direta que convide ação imediata.
    - Destaque ganchos relevantes (NPCs, objetos, saídas) para orientar a próxima decisão.
    - Evite cliffhangers longos ou respostas prolixas.

    REGRAS:
    1. Narre a cena com imersão, INTEGRANDO a Lore consultada acima.
       (Ex: Se a lore diz que as ruínas brilham verde, descreva o brilho verde).
    2. Se o jogador tentou falar com alguém que não existe, narre que a pessoa não está lá.
    3. Se a SUA narrativa introduzir um novo personagem (ex: "Um guarda entra"), adicione o nome em 'introduced_npcs'.
    4. NÃO adicione NPCs inventados pelo jogador na lista.
    """)
    
    try:
        story_engine = llm.with_structured_output(StoryUpdate)
        update = story_engine.invoke([sys] + messages)
        
        narrative_text = update.narrative
        
        # --- LÓGICA DE SPAWN ---
        if update.introduced_npcs:
            if 'npcs' not in state: state['npcs'] = {}
            
            for new_name in update.introduced_npcs:
                if new_name not in state['npcs']:
                    print(f"✨ [STORYTELLER] Invocando novo NPC: {new_name}")
                    
                    # O generate_new_npc (do agents.npc) JÁ usa RAG internamente também
                    tpl = generate_new_npc(new_name, context=f"Local: {loc}. Cena: {narrative_text}")
                    
                    if tpl:
                        state['npcs'][new_name] = {
                            "name": tpl['name'],
                            "role": tpl['role'],
                            "persona": tpl['persona'],
                            "location": loc,
                            "relationship": tpl['initial_relationship'],
                            "memory": [],
                            "last_interaction": ""
                        }
        
        return {
            "messages": [AIMessage(content=narrative_text)],
            "npcs": state.get('npcs', {})
        }
        
    except Exception as e:
        print(f"[STORYTELLER ERROR] {e}")
        return {"messages": [AIMessage(content="O vento sopra... (Erro técnico na narrativa).")]}