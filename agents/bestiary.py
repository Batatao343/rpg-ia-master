"""
agents/bestiary.py
Gerador de Inimigos V8 (Refatorado Check-First + RAG).
Correção: Prompt reforçado para garantir lista de ataques estruturada.
"""
import json
import os
from typing import Dict, List, Optional
from langchain_core.messages import SystemMessage, HumanMessage
from pydantic import BaseModel, Field
from llm_setup import ModelTier, get_llm

try:
    from rag import query_rag
except ImportError:
    def query_rag(*args, **kwargs): return ""

from agents.librarian import find_existing_entity

BESTIARY_FILE = "data/bestiary.json"

# --- SCHEMA ---
class AttackAction(BaseModel):
    name: str = Field(description="Nome do ataque. Ex: 'Mordida', 'Espada Longa'")
    type: str = Field(description="'melee', 'ranged', 'magic' ou 'area'")
    bonus: int = Field(description="Bônus de acerto. Ex: 5")
    damage: str = Field(description="Fórmula de dano. Ex: '1d8+3 slashing'")
    range: str = "1.5m"
    save_dc: Optional[str] = Field(None, description="Se houver save. Ex: 'DC 12 Con'")

class EnemySchema(BaseModel):
    name: str
    description: str
    type: str # Minion, Elite, BOSS
    hp: int
    max_hp: int
    ac: int
    attacks: List[AttackAction] = Field(description="LISTA OBRIGATÓRIA de objetos AttackAction. NÃO use strings.")
    attributes: Dict[str, int] = Field(description="Atributos: str, dex, con, int, wis, cha")
    abilities: List[str] = []
    loot: List[str] = []

# --- PERSISTÊNCIA ---
def load_bestiary() -> Dict:
    if not os.path.exists(BESTIARY_FILE): return {}
    try:
        with open(BESTIARY_FILE, 'r', encoding='utf-8') as f: return json.load(f)
    except: return {}

def save_enemy(data: Dict):
    db = load_bestiary()
    # Usa ID se existir, senão gera slug
    key = data.get("id", data["name"].lower().replace(" ", "_"))
    if "id" not in data: data["id"] = key
    
    db[key] = data
    if not os.path.exists("data"): os.makedirs("data")
    with open(BESTIARY_FILE, 'w', encoding='utf-8') as f: json.dump(db, f, indent=4, ensure_ascii=False)

def _infer_tier_from_name(name: str) -> ModelTier:
    if any(x in name.lower() for x in ["dragon", "lich", "boss", "god", "lord"]): return ModelTier.SMART
    return ModelTier.FAST

# --- GERADOR ---
def generate_new_enemy(name: str, context: str = "") -> Dict:
    # 1. CHECK-FIRST
    db = load_bestiary()
    existing_ids = list(db.keys())
    
    found_id = find_existing_entity(name, "Monster", existing_ids)
    if found_id:
        print(f"♻️ [BESTIARY] Cache Hit: {found_id}")
        data = db[found_id]
        
        # Auto-correção de legado
        if "id" not in data:
             print(f"🔧 [BESTIARY] Corrigindo monstro legado sem ID: {name}")
             data["id"] = found_id
             save_enemy(data)

        data["hp"] = data["max_hp"]
        data["status"] = "ativo"
        return data

    # 2. GERAÇÃO
    print(f"👾 [BESTIARY] Criando: {name}...")
    
    lore = query_rag(f"{name} {context}", index_name="lore")
    if not lore: lore = "Standard RPG Monster."

    llm = get_llm(temperature=0.5, tier=_infer_tier_from_name(name))
    
    # Prompt Reforçado com One-Shot Example para o Array de Ataques
    sys_msg = SystemMessage(content=f"""
    <role>D&D 5e Monster Designer</role>
    <lore_context>{lore}</lore_context>
    
    <CRITICAL_INSTRUCTION>
    You MUST populate the 'attacks' field as a LIST OF OBJECTS (JSON), not strings.
    
    WRONG:
    "attacks": ["Bite attack dealing 1d6 damage", "Claw attack..."]
    
    CORRECT:
    "attacks": [
      {{ "name": "Bite", "type": "melee", "bonus": 5, "damage": "1d6+3 piercing" }},
      {{ "name": "Claw", "type": "melee", "bonus": 5, "damage": "1d4+3 slashing" }}
    ]
    
    Include all 6 attributes (str, dex, con, int, wis, cha).
    </CRITICAL_INSTRUCTION>
    """)
    
    try:
        designer = llm.with_structured_output(EnemySchema)
        res = designer.invoke([sys_msg, HumanMessage(content=f"Create monster: {name}. Context: {context}")])
        data = res.model_dump()
        
        data["status"] = "ativo"
        data["id"] = f"enemy_{data['name'].lower().replace(' ', '_')}"
        
        save_enemy(data)
        return data
        
    except Exception as e:
        print(f"❌ [BESTIARY ERROR] {e}")
        # Fallback de segurança para não quebrar o jogo
        return {
            "name": name, 
            "type": "Minion", 
            "hp": 20, "max_hp": 20, "ac": 12, 
            "status": "ativo", 
            "id": "fallback_monster",
            "description": "Monstro genérico (Erro de Geração).", 
            "attributes": {"str":10, "dex":10, "con":10, "int":10, "wis":10, "cha":10},
            "attacks": [{"name": "Ataque Básico", "type": "melee", "bonus": 3, "damage": "1d4+1"}]
        }