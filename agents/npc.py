"""
agents/npc.py
Gerador de NPCs com Persistência, Memória, RAG e Filtro de Ignorância.
Contém tanto a fábrica de NPCs (generate_new_npc) quanto o ator (npc_actor_node).
"""
import json
import os
from typing import Dict, Any, Optional
from pydantic import BaseModel, Field
from langchain_core.messages import SystemMessage, HumanMessage, AIMessage
from state import GameState
from llm_setup import ModelTier, get_llm

# Fallback para RAG
try:
    from rag import query_rag
    RAG_AVAILABLE = True
except ImportError:
    RAG_AVAILABLE = False
    def query_rag(*args, **kwargs): return ""

# Importa Librarian para verificar duplicatas
try:
    from agents.librarian import find_existing_entity
except ImportError:
    def find_existing_entity(*args, **kwargs): return None

NPC_DB_FILE = "data/npc_database.json"

# --- SCHEMAS ---
class NPCSchema(BaseModel):
    name: str
    role: str
    location: str
    persona: str
    appearance: str
    initial_relationship: int = 5
    attributes: Dict[str, int] = Field(
        description="Stats base: str, dex, con, int, wis, cha. Padrão humano é 10.",
        example={"str": 10, "dex": 12, "con": 10, "int": 14, "wis": 16, "cha": 18}
    )
    combat_stats: Dict = Field(description="HP, AC e Attacks", default={"hp": 10, "ac": 10, "attacks": []})

class NPCResponse(BaseModel):
    dialogue: str
    action_description: str
    memory_update: str
    relationship_change: int = 0

# --- PERSISTÊNCIA ---
def load_npc_db():
    if not os.path.exists(NPC_DB_FILE): return {}
    try:
        with open(NPC_DB_FILE, 'r', encoding='utf-8') as f: return json.load(f)
    except: return {}

def save_npc_template(data):
    db = load_npc_db()
    key = data.get("id", f"npc_{data['name'].lower().replace(' ', '_')}")
    if "id" not in data: data["id"] = key
    
    # Garante atributos mínimos
    if "attributes" not in data:
        data["attributes"] = {"str": 10, "dex": 10, "con": 10, "int": 10, "wis": 10, "cha": 10}
    
    db[key] = data
    if not os.path.exists("data"): os.makedirs("data")
    with open(NPC_DB_FILE, 'w', encoding='utf-8') as f: json.dump(db, f, indent=4, ensure_ascii=False)

def _infer_tier_from_name(name: str) -> ModelTier:
    lowered = name.lower()
    if any(m in lowered for m in ["king", "queen", "boss", "lord", "archmage"]): return ModelTier.SMART
    return ModelTier.FAST

# --- FÁBRICA DE NPCs (A FUNÇÃO QUE FALTAVA) ---
def generate_new_npc(name, context=""):
    """
    Gera um novo NPC do zero usando IA ou recupera do cache se já existir.
    Usado pelo Storyteller para popular o mundo dinamicamente.
    """
    # 1. CHECK-FIRST: Verifica se já existe
    db = load_npc_db()
    existing_ids = list(db.keys())
    
    found_id = find_existing_entity(name, "NPC", existing_ids)
    if found_id:
        print(f"♻️ [NPC] Cache Hit: {found_id}")
        data = db[found_id]
        if "attributes" not in data: # Auto-fix
            data["attributes"] = {"str": 10, "dex": 10, "con": 10, "int": 10, "wis": 10, "cha": 10}
            save_npc_template(data)
        return data

    # 2. GERAÇÃO
    print(f"🎭 [NPC] Criando: {name}...")
    lore_info = query_rag(f"{name} {context}", index_name="lore")
    
    llm = get_llm(temperature=0.7, tier=_infer_tier_from_name(name))
    
    try:
        designer = llm.with_structured_output(NPCSchema)
        res = designer.invoke([
            SystemMessage(content=f"""
            <role>RPG Character Designer</role>
            <lore>{lore_info}</lore>
            <task>Create NPC '{name}'. Include all 6 attributes and a detailed persona.</task>
            """), 
            HumanMessage(content=f"Context: {context}")
        ])
        
        data = res.model_dump()
        data["id"] = f"npc_{name.lower().replace(' ', '_')}"
        save_npc_template(data)
        return data
        
    except Exception as e: 
        print(f"❌ Erro NPC AI: {e}")
        # Fallback de segurança
        return {
            "name": name, "role": "Desconhecido", "id": "fallback", "persona": "Genérico",
            "attributes": {"str":10, "dex":10, "con":10, "int":10, "wis":10, "cha":10},
            "combat_stats": {"hp": 10, "ac": 10, "attacks": []}
        }

# --- NÓ DE ATUAÇÃO (COM FILTRO DE IGNORÂNCIA) ---
def npc_actor_node(state: GameState):
    messages = state.get("messages", [])
    npc_name = state.get("active_npc_name")
    
    if not npc_name: return {"messages": [AIMessage(content="Ninguém responde.")]}
    
    # Busca dados (Prioridade: Estado -> DB -> Fallback)
    npcs_db = state.get("npcs", {})
    npc_data = npcs_db.get(npc_name)
    
    if not npc_data:
        db = load_npc_db()
        npc_data = db.get(npc_name)
        if not npc_data: return {"messages": [AIMessage(content="NPC não encontrado.")]}

    # Contexto RAG (Filtrado pelo Prompt)
    last_msg = messages[-1].content if messages else ""
    lore = query_rag(last_msg, index_name="lore") if RAG_AVAILABLE else ""

    llm = get_llm(temperature=0.8, tier=ModelTier.SMART)
    
    system_msg = SystemMessage(content=f"""
    <ROLE>
    Você é {npc_data.get('name')}.
    Ocupação: {npc_data.get('role')}.
    Persona: {npc_data.get('persona')}.
    Local: {npc_data.get('location')}.
    </ROLE>

    <MEMORIA>
    {npc_data.get('memory', [])[-3:]}
    </MEMORIA>

    <CONTEXTO_EXTERNO>
    {lore}
    </CONTEXTO_EXTERNO>

    <REGRAS DE ATUAÇÃO - CRÍTICO>
    1. NÃO SEJA UMA WIKIPÉDIA. Você é uma pessoa limitada pela sua ocupação e local.
    2. FILTRO DE CONHECIMENTO: Ignore fatos do Contexto Externo que seu personagem não saberia (ex: um soldado não sabe magia antiga). Se não souber, invente rumores ou seja cínico.
    3. Mantenha a persona (gírias, erros, arrogância) o tempo todo.
    4. Resposta curta e direta.
    """)

    try:
        actor = llm.with_structured_output(NPCResponse)
        res = actor.invoke([system_msg] + messages[-5:])
        
        # Atualiza memória e relação
        npc_data['relationship'] = max(0, min(10, npc_data.get('relationship', 5) + res.relationship_change))
        npc_data['memory'].append(f"Turno {state.get('world', {}).get('turn_count', 0)}: {res.memory_update}")
        
        # Atualiza o estado global
        new_npcs = npcs_db.copy()
        new_npcs[npc_name] = npc_data

        return {
            "messages": [AIMessage(content=f"**{npc_data['name']}:** \"{res.dialogue}\"\n*({res.action_description})*")],
            "npcs": new_npcs
        }
    except Exception as e:
        print(f"Erro NPC Actor: {e}")
        return {"messages": [AIMessage(content="...")]}