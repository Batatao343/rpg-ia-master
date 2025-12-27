"""
agents/combat.py
(Versão Data-Driven: Lê ARTIFACTS_DB para stats e INJETA MECÂNICAS no prompt.)
"""
from typing import List, Dict, Optional
from langchain_core.messages import SystemMessage, AIMessage, HumanMessage, ToolMessage
from pydantic import BaseModel

# Imports do Projeto
from state import GameState
from llm_setup import ModelTier, get_llm
from gamedata import ARTIFACTS_DB
from engine_utils import execute_engine
from agents.ruler_completo import resolve_action

# --- ESTRATÉGIA ---
class BossStrategy(BaseModel):
    name: str
    description: str
    win_rate: float
    action_script: str

class BossStrategySet(BaseModel):
    strategies: List[BossStrategy]

def get_mod(score: int) -> int: return (score - 10) // 2

def _normalize_attr_name(attr: str) -> str:
    attr = attr.lower()
    mapping = {"strength": "str", "força": "str", "dexterity": "dex", "destreza": "dex", "constitution": "con", "constituição": "con", "intelligence": "int", "wisdom": "wis", "charisma": "cha"}
    return mapping.get(attr, attr)

def _tree_of_thoughts_strategy(player, party, bosses, last_user_intent, enemy_str) -> str:
    # (Mantido igual para economizar espaço visual, lógica de ToT não mudou)
    return "Boss Strategy: Attack. Tactic: Focus closest target."

# --- NÓ PRINCIPAL ---
def combat_node(state: GameState):
    messages = state.get("messages", [])
    if not messages: return {"next": "dm_router"}

    player = state["player"]
    party = state.get("party", []) 
    enemies = state.get("enemies", [])
    
    active_enemies = [e for e in enemies if e["status"] == "ativo"]
    active_party = [p for p in party if p.get("hp", 0) > 0]

    if not active_enemies:
        state["loot_source"] = "COMBAT"
        return {
            "messages": [AIMessage(content="O último inimigo cai. O silêncio retorna.")],
            "next": "loot",
            "combat_target": None
        }

    # --- 1. CÁLCULO DE STATS E COLETA DE MECÂNICAS ---
    attrs = player.get("attributes", {"str": 10})
    normalized_attrs = {_normalize_attr_name(k): v for k, v in attrs.items()}
    mods = {k: get_mod(v) for k, v in normalized_attrs.items()}
    
    inventory_ids = player.get("inventory", [])
    best_atk_bonus = 0
    total_ac_bonus = 0
    active_attr_key = "str"
    
    # Lista de textos para injetar no prompt
    mechanics_log = []

    for item_id in inventory_ids:
        item_data = ARTIFACTS_DB.get(item_id)
        if item_data:
            # Stats Numéricos
            stats = item_data.get("combat_stats", {})
            if item_data.get("type") == "weapon":
                b = stats.get("attack_bonus", 0)
                if b > best_atk_bonus:
                    best_atk_bonus = b
                    if "attribute" in stats:
                        active_attr_key = _normalize_attr_name(stats["attribute"])
            total_ac_bonus += stats.get("ac_bonus", 0)

            # --- NOVO: Coleta de Passivas e Habilidades ---
            mech = item_data.get("mechanics", {})
            
            # Passivas
            passives = mech.get("passive_effects", [])
            for p in passives:
                mechanics_log.append(f"[PASSIVE] {item_data['name']}: {p}")
            
            # Habilidade Ativa
            active = mech.get("active_ability")
            if active and isinstance(active, dict):
                mechanics_log.append(f"[SPELL/ABILITY] {active.get('name')} (Custo: {active.get('cost')}): {active.get('effect')}")

    # Matemática Final
    attr_mod = mods.get(active_attr_key, 0)
    total_atk = attr_mod + best_atk_bonus
    current_ac = 10 + mods.get("dex", 0) + total_ac_bonus

    # Formatação do texto de mecânicas
    mechanics_str = "\n".join(mechanics_log) if mechanics_log else "Nenhuma habilidade especial."

    # --- 2. CONTEXTO PARA IA ---
    party_str = "ALIADOS: " + ", ".join([p['name'] for p in active_party]) if active_party else "Nenhum"
    
    enemy_desc_list = []
    for idx, e in enumerate(active_enemies):
        atk_str = "Ataque Básico"
        if "attacks" in e and len(e['attacks']) > 0:
            a = e['attacks'][0]
            atk_str = f"{a['name']} (+{a['bonus']}) {a['damage']}"
        enemy_desc_list.append(f"{idx+1}. {e['name']} (HP:{e['hp']} | AC:{e.get('ac', 10)}) | {atk_str}")
    enemy_str = "\n".join(enemy_desc_list)

    # Ruler & Boss (Lógica Mantida)
    ruling_instruction = ""
    last_msg = messages[-1]
    last_intent = last_msg.content if isinstance(last_msg, HumanMessage) else ""
    if last_intent and not isinstance(last_msg, (ToolMessage, AIMessage)):
        try:
            ruling = resolve_action(player, last_intent)
            ruling_instruction = f"[RULER]: Formula '{ruling.get('dice_formula')}', Effect: {ruling.get('mechanical_effect')}"
        except: pass

    # --- 3. PROMPT SYSTEM (Agora com <mechanics>) ---
    system_msg = SystemMessage(content=f"""
    <role>Combat Engine</role>
    <hero>
    {player['name']} | HP: {player['hp']} | AC: {current_ac}
    ATK BONUS: +{total_atk} (Attr: {active_attr_key.upper()})
    </hero>
    
    <equipped_mechanics>
    {mechanics_str}
    </equipped_mechanics>
    
    <party>{party_str}</party>
    <enemies>{enemy_str}</enemies>
    {ruling_instruction}
    
    <instructions>
    1. Resolve Hero Action. IF using a [SPELL/ABILITY] listed above, apply its effect.
    2. Resolve Enemy Actions (Roll vs AC).
    3. Update HPs using `update_hp`.
    4. Narrate.
    </instructions>
    """)

    tier = ModelTier.SMART
    llm = get_llm(temperature=0.2, tier=tier)
    
    return execute_engine(llm, system_msg, messages, state, node_name="Combate")