"""
agents/npc.py
Gerador de NPCs com Persistência, Memória e RAG.
Atualizado: Garante Atributos Completos (STR, DEX, CON, INT, WIS, CHA).
"""
import json
import os
from typing import Dict
from pydantic import BaseModel, Field
from langchain_core.messages import SystemMessage, HumanMessage, AIMessage
from state import GameState
from llm_setup import ModelTier, get_llm

try:
    from rag import query_rag
except ImportError:
    def query_rag(*args, **kwargs): return ""

from agents.librarian import find_existing_entity

NPC_DB_FILE = "data/npc_database.json"

# --- SCHEMAS ---
class NPCSchema(BaseModel):
    name: str
    role: str
    location: str
    persona: str
    appearance: str
    initial_relationship: int = 5
    # ADICIONADO: Atributos completos são obrigatórios agora
    attributes: Dict[str, int] = Field(
        description="Stats base: str, dex, con, int, wis, cha. Padrão humano é 10.",
        example={"str": 10, "dex": 12, "con": 10, "int": 14, "wis": 16, "cha": 18}
    )
    combat_stats: Dict = Field(description="HP, AC e Attacks")

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
    
    # Validação de Segurança: Se faltar atributo, preenche com 10
    if "attributes" not in data:
        data["attributes"] = {"str": 10, "dex": 10, "con": 10, "int": 10, "wis": 10, "cha": 10}
    
    db[key] = data
    if not os.path.exists("data"): os.makedirs("data")
    with open(NPC_DB_FILE, 'w', encoding='utf-8') as f: json.dump(db, f, indent=4, ensure_ascii=False)

def _infer_tier_from_name(name: str) -> ModelTier:
    lowered = name.lower()
    important_markers = ["king", "queen", "captain", "wizard", "archmage", "lord", "boss"]
    if any(marker in lowered for marker in important_markers):
        return ModelTier.SMART
    return ModelTier.FAST

# --- FERRAMENTA DE DESIGN ---
def generate_new_npc(name, context=""):
    # 1. CHECK-FIRST
    db = load_npc_db()
    existing_ids = list(db.keys())
    
    found_id = find_existing_entity(name, "NPC", existing_ids)
    if found_id:
        print(f"♻️ [NPC] Cache Hit: {found_id}")
        data = db[found_id]
        
        # Auto-Correção: Se for NPC antigo sem atributos, adiciona padrão
        if "attributes" not in data:
            print(f"🔧 [NPC] Corrigindo atributos faltantes para {name}")
            data["attributes"] = {"str": 10, "dex": 10, "con": 10, "int": 10, "wis": 10, "cha": 10}
            save_npc_template(data)
            
        return data

    # 2. GERAÇÃO
    print(f"🎭 [NPC] Criando: {name}...")
    lore_info = query_rag(f"{name} {context}", index_name="lore")
    if not lore_info: lore_info = "Dark Fantasy Padrão."

    tier = _infer_tier_from_name(name)
    llm = get_llm(temperature=0.7, tier=tier)
    
    try:
        designer = llm.with_structured_output(NPCSchema)
        res = designer.invoke([
            SystemMessage(content=f"""
            <role>RPG Character Designer</role>
            <lore>{lore_info}</lore>
            <task>Create NPC '{name}'. MUST include all 6 attributes (str, dex, con, int, wis, cha).</task>
            """), 
            HumanMessage(content=f"Context: {context}")
        ])
        
        data = res.model_dump()
        data["id"] = f"npc_{name.lower().replace(' ', '_')}"
        save_npc_template(data)
        
        return data
        
    except Exception as e: 
        print(f"❌ Erro NPC AI: {e}")
        return {
            "name": name, "role": "Desconhecido", "id": "fallback",
            "attributes": {"str":10, "dex":10, "con":10, "int":10, "wis":10, "cha":10},
            "combat_stats": {"hp": 10, "ac": 10, "attacks": []}
        }

# --- NÓ DE ATUAÇÃO ---
def npc_actor_node(state: GameState):
    messages = state["messages"]
    npc_name = state.get("active_npc_name")
    
    if not npc_name: return {"next": "storyteller"}
    
    npc_data = state.get('npcs', {}).get(npc_name)
    if not npc_data: return {"next": "storyteller"} 

    if 'persona' not in npc_data: npc_data['persona'] = "Genérico."

    mem_log = "\n".join(npc_data.get('memory', [])[-5:])
    
    llm = get_llm(temperature=0.5, tier=ModelTier.FAST)
    
    system_msg = SystemMessage(content=f"""
    <actor>
    Nome: {npc_data.get('name')}
    Persona: {npc_data['persona']}
    Relação: {npc_data.get('relationship', 5)}/10
    </actor>
    <memory>{mem_log}</memory>
    Responda IN-CHARACTER.
    """)
    
    try:
        actor = llm.with_structured_output(NPCResponse)
        res = actor.invoke([system_msg] + messages[-3:])
        
        npc_data['relationship'] = max(0, min(10, npc_data.get('relationship', 5) + res.relationship_change))
        npc_data['memory'].append(f"Turno {state.get('world', {}).get('turn_count', 0)}: {res.memory_update}")
        
        return {
            "messages": [AIMessage(content=f"**{npc_data['name']}:** \"{res.dialogue}\"\n*({res.action_description})*")],
            "npcs": {npc_name: npc_data}
        }
    except:
        return {"next": "storyteller"}