"""
agents/loot.py
Gerencia Loot Inteligente, Lojas, XP e Level Up.
Implementa arquitetura Check-First para itens únicos.
Versão Corrigida: IDs sanitizados (sem acento) e controle de duplicidade.
"""
import random
import unicodedata
from typing import Dict, Any, List, Optional
from langchain_core.messages import SystemMessage, HumanMessage, AIMessage
from pydantic import BaseModel, Field, field_validator

from llm_setup import get_llm, ModelTier
from gamedata import (
    XP_TABLE, ARTIFACTS_DB, ALL_ARTIFACT_IDS, COMMON_LOOT_TABLE, 
    save_custom_artifact
)

# Tenta RAG
try:
    from rag import query_rag
    RAG_AVAILABLE = True
except ImportError:
    RAG_AVAILABLE = False
    def query_rag(*args, **kwargs): return ""

# --- HELPER: SANITIZAÇÃO DE ID ---
def sanitize_id(text: str) -> str:
    """Transforma 'Espada do Dragão' em 'espada_do_dragao'."""
    # Normaliza unicode (remove acentos: ã -> a, é -> e)
    normalized = unicodedata.normalize('NFKD', text).encode('ascii', 'ignore').decode('utf-8')
    # Remove caracteres especiais, passa para minúsculo e troca espaços por _
    clean = "".join(c for c in normalized if c.isalnum() or c == " ")
    return clean.lower().replace(" ", "_")

# --- SCHEMAS ROBUSTOS ---
class CombatStatsSchema(BaseModel):
    attack_bonus: int = 0
    damage_dice: str = "0"
    attribute: str = "none"
    ac_bonus: int = 0

    @field_validator('damage_dice', mode='before')
    @classmethod
    def set_damage_default(cls, v):
        return v or "0"

    @field_validator('attribute', mode='before')
    @classmethod
    def set_attr_default(cls, v):
        return v or "none"

class ActiveAbilitySchema(BaseModel):
    name: str
    cost: str
    effect: str

class MechanicsSchema(BaseModel):
    passive_effects: List[str] = []
    active_ability: Optional[ActiveAbilitySchema] = None

class NewItemSchema(BaseModel):
    """Estrutura completa para criar um item novo."""
    id_sugestion: str = Field(description="Sugestão de nome curto. Ex: 'cetro_zarkon'.")
    name: str
    type: str = Field(description="weapon, armor, accessory, consumable, material, currency")
    rarity: str = Field(description="common, uncommon, rare, legendary")
    description: str
    value_gold: int
    combat_stats: CombatStatsSchema
    mechanics: MechanicsSchema

class LootResult(BaseModel):
    """Decisão da IA."""
    gold_amount: int
    existing_item_ids: List[str] = Field(description="IDs do banco para itens comuns.")
    new_custom_items: List[NewItemSchema] = Field(description="Itens ÚNICOS. Para Bosses, gere APENAS UM item lendário.")

# --- LÓGICA DE XP E LEVEL UP ---

def calculate_xp_gain(enemies: List[Dict]) -> int:
    total_xp = 0
    for e in enemies:
        multiplier = 5 if e.get("type") == "BOSS" else 1
        base_xp = e.get("max_hp", 10) * 2
        total_xp += (base_xp * multiplier)
    return total_xp

def process_level_up(player: Dict) -> str:
    current_level = player.get("level", 1)
    if current_level >= 20: return ""
    
    current_xp = player.get("xp", 0)
    next_level = current_level + 1
    req_xp = XP_TABLE.get(next_level, 999999)
    
    if current_xp >= req_xp:
        player["level"] = next_level
        hp_gain = 6 + next_level 
        player["max_hp"] += hp_gain
        player["hp"] = player["max_hp"] 
        return f"\n✨ **LEVEL UP!** Você alcançou o Nível {next_level}! Max HP +{hp_gain}."
    
    return ""

# --- GERADOR CORE ---

def generate_loot_logic(context_type: str, context_data: Dict) -> Dict:
    region = context_data.get("region", "Desconhecido")
    enemies = context_data.get("enemies", [])
    
    prompt_context = ""
    boss_loot_needed = False
    
    if context_type == "COMBAT":
        enemy_names = ", ".join([e["name"] for e in enemies])
        bosses = [e for e in enemies if e.get("type") == "BOSS"]
        if bosses:
            boss_loot_needed = True
            # Limita a um boss principal para o nome do item
            boss_name = bosses[0]["name"]
            if RAG_AVAILABLE:
                lore = query_rag(f"Artifacts of {boss_name}", index_name="lore")
                prompt_context = f"BOSS FIGHT: {boss_name}. Lore: {lore}. Gere 1 item lendário temático."
        else:
            prompt_context = f"Inimigos comuns: {enemy_names}. Gere loot simples."

    elif context_type == "SHOP":
        if RAG_AVAILABLE:
            lore = query_rag(f"Trade items in {region}", index_name="lore")
        prompt_context = f"LOJA na região {region}. Lore: {lore}. Gere itens variados para venda."

    elif context_type == "TREASURE":
        prompt_context = f"Baú encontrado em {region}. Gere recompensas de exploração."

    llm = get_llm(temperature=0.7, tier=ModelTier.SMART)
    
    system_msg = SystemMessage(content=f"""
    Você é o Gerador de Itens de RPG.
    Modo: {context_type}
    
    ITENS EXISTENTES: {COMMON_LOOT_TABLE}
    
    TAREFA:
    1. Defina Ouro.
    2. Selecione itens comuns existentes.
    3. CRIE NOVOS ITENS (Custom) APENAS SE: BOSS (1 item único), LOJA (2-3 itens) ou BAÚ RARO.
    
    IMPORTANTE: Não crie itens duplicados no mesmo loot.
    """)
    
    try:
        gen = llm.with_structured_output(LootResult)
        decision = gen.invoke([system_msg, HumanMessage(content=prompt_context)])
        
        final_ids = []
        
        # 1. Itens Existentes
        for iid in decision.existing_item_ids:
            if iid in ARTIFACTS_DB: final_ids.append(iid)
        
        # 2. Itens Novos
        created_names = set() # Controle local de duplicidade
        
        for new_item in decision.new_custom_items:
            # Evita duplicatas na mesma geração (ex: 3 escudos iguais)
            if new_item.name in created_names:
                continue
            created_names.add(new_item.name)

            item_dict = new_item.model_dump()
            
            # Geração de ID Determinística e Segura
            if context_type == "COMBAT" and boss_loot_needed:
                # Usa a função sanitize para remover acentos
                boss_slug = sanitize_id(enemies[0]["name"])
                new_id = f"unique_loot_{boss_slug}"
            else:
                # Usa sugestão da IA ou fallback random
                sug = sanitize_id(item_dict.pop("id_sugestion", ""))
                if not sug: sug = f"custom_{random.randint(1000,9999)}"
                new_id = sug
            
            # Garante que o ID não sobrescreva algo vital, adiciona random se já existir E não for loot de boss fixo
            if new_id in ARTIFACTS_DB and not (context_type == "COMBAT" and boss_loot_needed):
                new_id = f"{new_id}_{random.randint(100,999)}"

            save_custom_artifact(new_id, item_dict)
            final_ids.append(new_id)
            
        return {"gold": decision.gold_amount, "items": final_ids}

    except Exception as e:
        print(f"❌ Erro Loot AI: {e}")
        return {"gold": 10, "items": ["moeda_ouro"]}

# --- NÓ PRINCIPAL ---

def loot_node(state: Dict[str, Any]):
    player = state["player"]
    loot_source = state.get("loot_source", "TREASURE") 
    world = state.get("world", {})
    
    messages = []
    
    if loot_source == "COMBAT":
        enemies = state.get("enemies", [])
        xp_gain = calculate_xp_gain(enemies)
        player["xp"] = player.get("xp", 0) + xp_gain
        lvl_msg = process_level_up(player)
        
        loot_data = generate_loot_logic("COMBAT", {"enemies": enemies, "region": world.get("current_location")})
        
        player["gold"] += loot_data["gold"]
        player["inventory"].extend(loot_data["items"])
        
        item_names = [ARTIFACTS_DB.get(i, {}).get("name", i) for i in loot_data["items"]]
        items_txt = ", ".join(item_names) if item_names else "Nenhum item."
        
        msg_text = (
            f"⚔️ **Vitória!**\n"
            f"Ganhou {xp_gain} XP. {lvl_msg}\n"
            f"💰 Encontrou {loot_data['gold']} Ouro.\n"
            f"🎒 Loot: {items_txt}"
        )
        messages.append(AIMessage(content=msg_text))

    elif loot_source == "SHOP":
        loot_data = generate_loot_logic("SHOP", {"region": world.get("current_location")})
        
        shop_list = []
        for iid in loot_data["items"]:
            item = ARTIFACTS_DB.get(iid, {})
            price = item.get('value_gold', 0)
            shop_list.append(f"- {item.get('name')} ({price} ouro) [ID: {iid}]")
        
        shop_txt = "\n".join(shop_list)
        msg_text = f"🏪 **Mercador Local:**\n\n{shop_txt}\n\n*(Use 'Compro [ID]' para adquirir)*"
        messages.append(AIMessage(content=msg_text))

    elif loot_source == "TREASURE":
        loot_data = generate_loot_logic("TREASURE", {"region": world.get("current_location")})
        player["gold"] += loot_data["gold"]
        player["inventory"].extend(loot_data["items"])
        
        item_names = [ARTIFACTS_DB.get(i, {}).get("name", i) for i in loot_data["items"]]
        msg_text = f"📦 **Baú Aberto!**\n{loot_data['gold']} Ouro e: {', '.join(item_names)}"
        messages.append(AIMessage(content=msg_text))
    
    state["loot_source"] = None
    
    return {
        "player": player,
        "messages": messages,
        "next": "storyteller"
    }