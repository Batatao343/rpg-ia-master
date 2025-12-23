import json
import os
from typing import Dict, List
from langchain_core.messages import SystemMessage, HumanMessage
from pydantic import BaseModel, Field
from llm_setup import ModelTier, get_llm

# --- INTEGRAÇÃO RAG ---
from rag import query_rag

BESTIARY_FILE = "data/bestiary.json"

# --- SCHEMA ---
class EnemySchema(BaseModel):
    name: str
    hp: int = Field(description="Hit Points Máximos")
    max_hp: int
    stamina: int = 10
    mana: int = 0
    defense: int = Field(description="Armor Class (10-20)")
    attack_mod: int = Field(description="Bônus de Ataque (+2 a +10)")
    attributes: Dict[str, int]
    abilities: List[str] = Field(description="Lista de nomes de habilidades especiais")
    active_conditions: List[str] = []
    desc: str = Field(description="Descrição visual breve")

# --- PERSISTÊNCIA ---
def load_bestiary() -> Dict:
    if not os.path.exists(BESTIARY_FILE): return {}
    try:
        with open(BESTIARY_FILE, 'r', encoding='utf-8') as f: return json.load(f)
    except: return {}

def save_enemy(data: Dict):
    db = load_bestiary()
    db[data['name']] = data
    if not os.path.exists("data"): os.makedirs("data")
    with open(BESTIARY_FILE, 'w', encoding='utf-8') as f: json.dump(db, f, indent=4, ensure_ascii=False)

def get_enemy_template(name: str) -> Dict:
    db = load_bestiary()
    for k, v in db.items():
        if name.lower() in k.lower(): return v
    return None


def _infer_tier_from_name(name: str) -> ModelTier:
    lowered = name.lower()
    boss_markers = ["dragon", "lich", "king", "queen", "lord", "tyrant"]
    if any(marker in lowered for marker in boss_markers):
        return ModelTier.SMART
    return ModelTier.FAST

# --- GERADOR (INTEGRADO COM RAG) ---
# Chamado pelo engine_utils.py quando um monstro novo é spawnado
def generate_new_enemy(name: str, context: str = "") -> Dict:
    print(f"👾 [BESTIARY] Consultando Lore (RAG) para criar: {name}...")

    # 1. BUSCA NA LORE (sempre consulta)
    lore_info = query_rag(f"{name} {context}", index_name="lore")

    if not lore_info:
        lore_info = "Fantasia genérica balanceada."

    cached = get_enemy_template(name)
    if cached:
        return cached

    tier = _infer_tier_from_name(name)
    llm = get_llm(temperature=0.5, tier=tier)
    
    sys_msg = SystemMessage(content=f"""
    <PERSONA>
    Você é um Game Designer responsável pelo Bestiário.
    
    <ECOLOGIA DO MUNDO (LORE)>
    {lore_info}
        
    <INSTRUÇÕES>
    1. Crie a ficha técnica (JSON) para o inimigo solicitado.
    2. Respeite a Lore: Se vampiros são robôs, dê habilidades tecnológicas.
    3. Balanceie HP e Dano de acordo com a dificuldade que o inimigo representa
    4. Seja criativo, evite clichês genéricos de fantasia se a Lore indicar o contrário.

    <EXAMPLE>
    Example: The enemy is a dragon. The enemy should have 120 HP and 10 attack. 
    The enemy should have the ability to breathe fire. 
    The enemy should have the ability to fly. 
    """)
    
    hum_msg = HumanMessage(content=f"Criar Inimigo: {name}. Contexto: {context}")
    
    try:
        designer = llm.with_structured_output(EnemySchema)
        res = designer.invoke([sys_msg, hum_msg])
        data = res.model_dump()
    except Exception as e:
        print(f"❌ Erro ao criar inimigo: {e}")
        data = {}

    # Fallback de emergência para não travar o combate
    if not data or "hp" not in data:
        data = {
            "name": name,
            "hp": 15,
            "max_hp": 15,
            "stamina": 10,
            "mana": 0,
            "defense": 12,
            "attack_mod": 3,
            "attributes": {
                "strength": 10,
                "dexterity": 10,
                "constitution": 10,
                "intelligence": 10,
                "wisdom": 10,
                "charisma": 10,
            },
            "abilities": ["Ataque Genérico"],
            "active_conditions": [],
            "desc": "Uma criatura indefinida.",
        }

    # Integridade mínima
    data["name"] = data.get("name") or name
    data["max_hp"] = data.get("max_hp", data.get("hp", 15))
    data.setdefault("abilities", ["Ataque Genérico"])
    data.setdefault("active_conditions", [])
    data.setdefault("desc", "Uma criatura indefinida.")
    data.setdefault("attributes", {
        "strength": 10,
        "dexterity": 10,
        "constitution": 10,
        "intelligence": 10,
        "wisdom": 10,
        "charisma": 10,
    })

    save_enemy(data) # Salva no "HD"
    return data
