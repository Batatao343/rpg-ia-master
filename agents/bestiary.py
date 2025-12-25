"""
agents/bestiary.py
Gerador de Inimigos V8.
Gera monstros com Ficha Técnica Completa (HP, AC, Ataques com Fórmulas)
compatível com a Engine de Combate Re-Act.
"""
import json
import os
from typing import Dict, List, Optional
from langchain_core.messages import SystemMessage, HumanMessage
from pydantic import BaseModel, Field
from llm_setup import ModelTier, get_llm

# --- INTEGRAÇÃO RAG ---
from rag import query_rag

BESTIARY_FILE = "data/bestiary.json"

# --- SCHEMA V8 (Compatível com Engine de Combate) ---

class AttackAction(BaseModel):
    name: str = Field(description="Nome do ataque. Ex: 'Espada Longa', 'Mordida'.")
    type: str = Field(description="'melee', 'ranged' ou 'magic'.")
    bonus: int = Field(description="Bônus de acerto (apenas o número). Ex: 5 (para 1d20+5).")
    damage: str = Field(description="Fórmula de dano para a Engine. Ex: '1d8+3 slashing', '2d6 fire'.")
    range: str = Field(default="1.5m", description="Alcance.")
    save_dc: Optional[str] = Field(default=None, description="Se for magia/habilidade, ex: 'DC 13 Dex'.")

class EnemySchema(BaseModel):
    name: str
    description: str = Field(description="Descrição visual breve e ameaçadora.")
    type: str = Field(description="Tipo: 'Minion', 'Elite', 'BOSS'.")
    
    # Atributos Vitais
    hp: int = Field(description="Hit Points Máximos.")
    max_hp: int
    ac: int = Field(description="Armor Class (Defesa).")
    
    # A Mágica: Lista estruturada para a Engine usar Tools
    attacks: List[AttackAction] = Field(description="Lista de ataques que o inimigo pode usar.")
    
    # Atributos (para testes resistidos se necessário)
    attributes: Dict[str, int] = Field(description="For, Des, Con, Int, Sab, Car.")
    
    abilities: List[str] = Field(default=[], description="Nomes de habilidades passivas.")
    loot: List[str] = Field(default=[], description="Itens carregados.")

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
    boss_markers = ["dragon", "lich", "king", "queen", "lord", "tyrant", "god", "titan"]
    if any(marker in lowered for marker in boss_markers):
        return ModelTier.SMART
    return ModelTier.FAST

# --- GERADOR ---
def generate_new_enemy(name: str, context: str = "") -> Dict:
    print(f"👾 [BESTIARY] Consultando Lore para criar: {name}...")

    # 1. Consulta RAG (Lore)
    lore_info = ""
    try:
        lore_info = query_rag(f"{name} {context}", index_name="lore")
    except:
        lore_info = "Fantasia Sombria Padrão."

    if not lore_info: lore_info = "Criatura desconhecida."

    # Verifica Cache
    cached = get_enemy_template(name)
    if cached: return cached

    tier = _infer_tier_from_name(name)
    llm = get_llm(temperature=0.6, tier=tier)
    
    sys_msg = SystemMessage(content=f"""
    <role>D&D 5e Monster Designer</role>
    
    <lore>
    {lore_info}
    </lore>
        
    <instructions>
    1. Create a STAT BLOCK for "{name}".
    2. COMBAT READY: You MUST provide explicit dice formulas for attacks.
       - Bad: "Strong Attack"
       - Good: "Greataxe", Bonus: 6, Damage: "1d12+4 slashing"
    3. BALANCE:
       - Minion: HP 10-30, AC 12-14, Dmg 1d6
       - Boss: HP 100+, AC 17+, Dmg 3d8+
    4. If the creature uses magic/breath, use 'save_dc' field (e.g., "DC 15 Dex").
    </instructions>
    """)
    
    hum_msg = HumanMessage(content=f"Create Enemy: {name}. Context: {context}")
    
    try:
        designer = llm.with_structured_output(EnemySchema)
        res = designer.invoke([sys_msg, hum_msg])
        data = res.model_dump()
        
        # Garante status e ID para o sistema de combate
        data["status"] = "ativo"
        data["id"] = f"{data['name'].lower().replace(' ', '_')}"
        
    except Exception as e:
        print(f"❌ [BESTIARY ERROR] {e}")
        # Fallback Robusto (Compatível com Engine V8)
        data = {
            "name": name,
            "type": "Minion",
            "hp": 20, "max_hp": 20, "ac": 13,
            "status": "ativo",
            "id": "fallback_enemy",
            "description": "Uma criatura genérica das sombras.",
            "attacks": [
                {
                    "name": "Ataque Desesperado",
                    "type": "melee",
                    "bonus": 4,
                    "damage": "1d6+2 bludgeoning",
                    "range": "1.5m",
                    "save_dc": None
                }
            ],
            "attributes": {"str": 10, "dex": 10, "con": 10, "int": 10, "wis": 10, "cha": 10},
            "abilities": [],
            "loot": []
        }

    save_enemy(data)
    return data

# Teste Rápido
if __name__ == "__main__":
    e = generate_new_enemy("Goblin Pyromancer", context="Vulcão")
    print(json.dumps(e, indent=2))