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

class EnemyBehavior(BaseModel):
    """Perfil de comportamento em combate (Fase 2.5b) — resolvido em Python."""
    profile: str = Field(description="'tatico' (esperto, foge por moral), 'feroz' (até a morte, frenesi), 'covarde' (foge cedo) ou 'implacavel' (nunca foge)")
    flee_below: float = Field(default=0.35, description="Foge com HP abaixo desta fração (só tatico/covarde)")
    pack_morale: bool = Field(default=False, description="True se foge quando a maioria do grupo cai")

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
    behavior: Optional[EnemyBehavior] = Field(None, description="Como a criatura luta: bestas = 'feroz'; soldados/bandidos = 'tatico'; presas = 'covarde'; mortos-vivos/constructos/bosses = 'implacavel'")
    regions: List[str] = Field(default_factory=list, description="Ids das regiões onde a criatura ocorre (ex.: 'skallgard')")

# --- PERSISTÊNCIA (spec isolar-cache-runtime) -------------------------------
# data/bestiary.json = base CURADA (2.5b), READ-ONLY em runtime. Criatura gerada
# pelo LLM vai pro OVERLAY gitignored (RPG_RUNTIME_CACHE_DIR/bestiary_runtime.json).

def _overlay_path() -> str:
    from gamedata import runtime_cache_path
    return runtime_cache_path("bestiary_runtime.json")


def _read_json(path: str) -> Dict:
    if not os.path.exists(path): return {}
    try:
        with open(path, 'r', encoding='utf-8') as f: return json.load(f)
    except Exception as e:
        print(f"⚠️ [BESTIARY] Falha ao ler {path}: {e}")
        return {}


def load_bestiary() -> Dict:
    """View unificada: curadoria ∪ overlay runtime (curadoria VENCE conflito de
    id — gerado nunca sombreia entrada curada)."""
    return {**_read_json(_overlay_path()), **_read_json(BESTIARY_FILE)}


def save_enemy(data: Dict):
    """Grava SÓ no overlay runtime — nunca em data/bestiary.json."""
    db = _read_json(_overlay_path())
    # Usa ID se existir, senão gera slug
    key = data.get("id", data["name"].lower().replace(" ", "_"))
    if "id" not in data: data["id"] = key

    db[key] = data
    path = _overlay_path()
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, 'w', encoding='utf-8') as f: json.dump(db, f, indent=4, ensure_ascii=False)

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
        # Fase 2.5b: garante behavior válido (LLM pode omitir/errar o enum)
        b = data.get("behavior") or {}
        if str(b.get("profile", "")).lower() not in ("tatico", "feroz", "covarde", "implacavel"):
            data["behavior"] = {"profile": "feroz"}

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