import json
import os
from typing import Dict
from pydantic import BaseModel, Field
from langchain_core.messages import SystemMessage, HumanMessage, AIMessage
from state import GameState
from llm_setup import ModelTier, get_llm

# --- INTEGRAÇÃO RAG ---
# Importamos a função de consulta para ler o world_lore.txt
from rag import query_rag

NPC_DB_FILE = "data/npc_database.json"

# --- SCHEMAS ---
class NPCSchema(BaseModel):
    name: str = Field(description="Nome do personagem.")
    role: str = Field(description="Ocupação ou título.")
    location: str = Field(description="Onde ele vive/foi encontrado.")
    persona: str = Field(description="Personalidade detalhada, crenças e estilo de fala.")
    appearance: str = Field(description="Descrição visual (roupas, traços físicos).")
    initial_relationship: int = Field(default=5, description="0 (Hostil) a 10 (Aliado).")
    combat_stats: Dict = Field(default={}, description="Se necessário (HP, etc).")

class NPCResponse(BaseModel):
    dialogue: str
    action_description: str
    memory_update: str
    relationship_change: int = 0

# --- PERSISTÊNCIA GLOBAL (Banco de Dados JSON) ---
def load_npc_db():
    if not os.path.exists(NPC_DB_FILE): return {}
    try:
        with open(NPC_DB_FILE, 'r', encoding='utf-8') as f: return json.load(f)
    except: return {}

def save_npc_template(data):
    db = load_npc_db()
    db[data['name']] = data
    if not os.path.exists("data"): os.makedirs("data")
    with open(NPC_DB_FILE, 'w', encoding='utf-8') as f: json.dump(db, f, indent=4, ensure_ascii=False)

def get_npc_template(name):
    db = load_npc_db()
    # Busca Case Insensitive
    for k, v in db.items():
        if name.lower() in k.lower(): return v
    return None


def _infer_tier_from_name(name: str) -> ModelTier:
    lowered = name.lower()
    important_markers = ["king", "queen", "captain", "wizard", "archmage", "emperor"]
    if any(marker in lowered for marker in important_markers):
        return ModelTier.SMART
    return ModelTier.FAST

# --- FERRAMENTA DE DESIGN (INTEGRADA COM RAG) ---
# Esta função é chamada pelo storyteller.py quando um novo NPC aparece.
def generate_new_npc(name, context=""):
    print(f"🎭 [DESIGNER] Consultando Lore (RAG) para criar: {name}...")
    
    # 1. BUSCA CONTEXTUAL NA LORE
    # Procura referências no world_lore.txt (ex: "Elfo", "Vampiro", "Tecnologia")
    lore_info = query_rag(f"{name} {context}", index_name="lore")
    
    if not lore_info:
        lore_info = "Nenhuma lore específica encontrada. Use criatividade Dark Fantasy padrão."

    tier = _infer_tier_from_name(name)
    llm = get_llm(temperature=0.6, tier=tier)
    
    try:
        designer = llm.with_structured_output(NPCSchema)
        res = designer.invoke([
            SystemMessage(content=f"""
            <PERSONA>
            Você é um Criador de Personagens para RPG. Você deve criar um NPC consistente com a lore abaixo
            
            <LORE DO MUNDO (LEI SUPREMA)>
            {lore_info}
            
            <INSTRUÇÕES>
            1. Crie um NPC consistente com a Lore acima. 
               Ex: Se a Lore diz que Elfos são canibais, o NPC deve refletir isso na aparência/persona.
            2. Seja criativo, evite clichês genéricos de fantasia se a Lore indicar o contrário.
            """), 
            HumanMessage(content=f"Nome: {name}. Contexto da cena: {context}")
        ])
        
        data = res.model_dump()
        save_npc_template(data) # Salva no "HD" para o futuro
        return data
        
    except Exception as e: 
        print(f"❌ Erro ao criar NPC: {e}")
        return None

# --- NÓ DE ATUAÇÃO (Passivo) ---
# Este nó apenas interpreta quem JÁ EXISTE no save game.
def npc_actor_node(state: GameState):
    messages = state["messages"]
    npc_name = state.get("active_npc_name")
    
    # Validação de Segurança
    if not npc_name or npc_name not in state.get('npcs', {}):
        return {"next": "storyteller"} 

    npc_data = state['npcs'][npc_name]
    
    # Fallback para saves antigos
    if 'persona' not in npc_data:
        tpl = get_npc_template(npc_name)
        npc_data['persona'] = tpl['persona'] if tpl else "Um habitante local genérico."

    # Memória Recente
    mem_log = "\n".join(npc_data.get('memory', [])[-5:])
    
    llm = get_llm(temperature=0.5, tier=ModelTier.FAST)
    
    system_msg = SystemMessage(content=f"""
    <actor_profile>
    Nome: {npc_name}
    Persona: {npc_data['persona']}
    Relação Atual: {npc_data['relationship']}/10
    </actor_profile>
    
    <memory_log>
    {mem_log}
    </memory_log>
    
    <instruction>
    Responda IN-CHARACTER como o personagem.
    Se a relação for baixa, seja hostil ou seco. Se alta, seja amigável.
    </instruction>
    """)
    
    try:
        actor = llm.with_structured_output(NPCResponse)
        res = actor.invoke([system_msg] + messages)
        
        # Atualiza Estado
        npc_data['relationship'] = max(0, min(10, npc_data['relationship'] + res.relationship_change))
        npc_data['memory'].append(f"Turno {state['world']['turn_count']}: {res.memory_update}")
        
        return {
            "messages": [AIMessage(content=f"**{npc_name}:** \"{res.dialogue}\"\n*({res.action_description})*")],
            "npcs": {npc_name: npc_data}
        }
    except:
        return {"next": "storyteller"}
