"""
agents/combat.py
(Versão Justa: Inimigos rolam dados usando stats do Bestiário)
"""
from typing import List, Dict, Optional
from langchain_core.messages import SystemMessage, AIMessage, HumanMessage, ToolMessage
from pydantic import BaseModel, Field

# Imports do Projeto
from state import GameState
from llm_setup import ModelTier, get_llm
from gamedata import ITEMS_DB
from engine_utils import execute_engine

# AJUSTE O IMPORT CONFORME O SEU NOME DE ARQUIVO REAL:
# from agents.ruler_completo import resolve_action
from agents.ruler_completo import resolve_action

# --- ESTRATÉGIA ---
class BossStrategy(BaseModel):
    name: str
    description: str
    win_rate: float = Field(ge=0, le=10)
    action_script: str

class BossStrategySet(BaseModel):
    strategies: List[BossStrategy]

# --- FUNÇÕES AUXILIARES ---
def get_mod(score: int) -> int: return (score - 10) // 2

def _is_complex_action(intent: str) -> bool:
    if not intent: return False
    keywords = ["conjuro", "uso", "habilidade", "tento", "invoco", "magia", "poder", "cast", "spell", "escondo", "ataque", "golpe"]
    return len(intent.split()) > 3 or any(k in intent.lower() for k in keywords)

def _normalize_attr_name(attr: str) -> str:
    attr = attr.lower()
    mapping = {"strength": "str", "força": "str", "dexterity": "dex", "destreza": "dex", "constitution": "con", "constituição": "con", "intelligence": "int", "inteligência": "int", "wisdom": "wis", "sabedoria": "wis", "charisma": "cha", "carisma": "cha"}
    return mapping.get(attr, attr)

# --- TREE OF THOUGHTS ---
def _tree_of_thoughts_strategy(player, bosses, combat_rules, last_user_intent, enemy_str) -> str:
    print(f"\n\033[95m🧠 [BOSS AI] Iniciando Tree of Thoughts (ToT)...\033[0m")
    llm = get_llm(temperature=0.4, tier=ModelTier.SMART)
    
    system_msg = SystemMessage(content=f"""
    You are a Tactical AI for a Boss in a D&D game.
    Context: Player HP {player['hp']}, Bosses: {enemy_str}
    Generate 3 distinct strategies (Aggressive, Defensive, Control) and assign a win_rate (0-10).
    """)
    human_msg = HumanMessage(content=f"Player Action: {last_user_intent}")

    try:
        planner = llm.with_structured_output(BossStrategySet)
        plan = planner.invoke([system_msg, human_msg])
        strategies = plan.strategies
        for idx, s in enumerate(strategies):
            print(f"\033[95m   Opção {idx+1}: {s.name} (WinRate: {s.win_rate})\n      -> {s.description}\033[0m")
        
        best = max(strategies, key=lambda s: s.win_rate)
        print(f"\033[95m✅ [BOSS AI] Estratégia Escolhida: {best.name.upper()}\033[0m")
        return f"Boss Strategy: {best.name}. Tactic: {best.action_script}"
    except Exception as e:
        print(f"❌ [BOSS AI ERROR] {e}")
        return "Atacar com força total."

# --- NÓ PRINCIPAL ---
def combat_node(state: GameState):
    messages = state.get("messages", [])
    if not messages: return {"next": "dm_router"}

    player = state["player"]
    
    # Cálculos de Atributo do Jogador
    attrs = player.get("attributes", {})
    if not attrs: attrs = {"str": 10, "dex": 10, "con": 10, "int": 10, "wis": 10, "cha": 10}
    normalized_attrs = {_normalize_attr_name(k): v for k, v in attrs.items()}
    mods = {k: get_mod(v) for k, v in normalized_attrs.items()}

    # Melhor Bônus de Ataque
    best_bonus = 0
    active_attr_key = "str"
    for item_name in player.get("inventory", []):
        d = ITEMS_DB.get(item_name)
        if d and d.get("type") == "weapon":
            bonus = d.get("bonus", 0)
            if bonus > best_bonus:
                best_bonus = bonus
                active_attr_key = _normalize_attr_name(d.get("attr", "str"))
    
    if active_attr_key not in mods: active_attr_key = "str"
    total_atk = mods[active_attr_key] + best_bonus

    # Inimigos Ativos
    enemies = state.get("enemies", [])
    active_enemies = [e for e in enemies if e["status"] == "ativo"]
    
    last_msg = messages[-1]
    last_user_intent = last_msg.content if isinstance(last_msg, HumanMessage) else ""

    # Conversão de NPC (Omitido para brevidade, mantenha sua lógica de conversion se necessário)
    if not active_enemies:
        return {"messages": [AIMessage(content="Não há inimigos ativos.")], "combat_target": None}

    # --- 1. RULER (Interpretação da Ação do Jogador) ---
    ruling = None
    should_call_ruler = (last_user_intent and not isinstance(messages[-1], (ToolMessage, AIMessage)))
    
    if should_call_ruler:
        # Se for ação complexa, chama o Ruler
        if _is_complex_action(last_user_intent):
            print(f"\n\033[96m⚖️ [RULER] Analisando: '{last_user_intent}'...\033[0m")
            try:
                ruling = resolve_action(player, last_user_intent)
                print(f"\033[96m   → Fórmula: {ruling.get('dice_formula')}\033[0m")
            except Exception as e:
                print(f"Erro no Ruler: {e}")

    # --- 2. FORMATAÇÃO DOS INIMIGOS (Com Ataques Explícitos) ---
    enemy_desc_list = []
    for idx, e in enumerate(active_enemies):
        atk_str = "Ataque Básico (1d4)"
        if "attacks" in e and isinstance(e["attacks"], list):
            # Converte a lista de ataques (dict) em string legível para a LLM
            # Ex: [Espada: +5, 1d8+3 slashing]
            atks_fmt = []
            for a in e["attacks"]:
                # Suporte tanto para objeto Pydantic quanto Dict
                a_name = a.get('name') if isinstance(a, dict) else a.name
                a_bonus = a.get('bonus') if isinstance(a, dict) else getattr(a, 'bonus', 0)
                a_dmg = a.get('damage') if isinstance(a, dict) else getattr(a, 'damage', '1d4')
                a_save = a.get('save_dc') if isinstance(a, dict) else getattr(a, 'save_dc', None)
                
                mechanic = a_save if a_save else f"+{a_bonus}"
                atks_fmt.append(f"[{a_name}: {mechanic}, Dmg: {a_dmg}]")
            
            atk_str = " | ".join(atks_fmt)
        
        enemy_desc_list.append(
            f"{idx+1}. {e['name']} (HP:{e['hp']}/{e.get('max_hp','?')} | AC:{e.get('ac',10)})\n   Ataques Disponíveis: {atk_str}"
        )
    enemy_str = "\n".join(enemy_desc_list)

    # --- 3. INSTRUÇÕES ESPECÍFICAS ---
    ruling_instruction = ""
    if ruling and ruling.get('dice_formula'):
        ruling_instruction = f"""
        [PLAYER ACTION RULING]
        Target Formula: {ruling['dice_formula']}
        Effect: {ruling['mechanical_effect']}
        INSTRUCTION: Start by calling `roll_dice` with "{ruling['dice_formula']}".
        """
    else:
        ruling_instruction = f"INSTRUCTION: If physical attack, call `roll_dice` with '1d20+{total_atk}'."

    # --- 4. BOSS STRATEGY ---
    bosses = [e for e in active_enemies if e.get("type") == "BOSS"]
    boss_directive = ""
    if bosses:
        boss_directive = _tree_of_thoughts_strategy(player, bosses, "Standard Rules", last_user_intent, enemy_str)

    # --- 5. SYSTEM PROMPT (Protocolo de Turno Completo) ---
    system_msg = SystemMessage(content=f"""
    <role>Combat Engine (Fair Game Master)</role>
    
    <state>
    HERÓI: {player['name']} (HP {player['hp']} / AC {player['defense']})
    ATK BÔNUS FÍSICO: +{total_atk}
    
    INIMIGOS:
    {enemy_str}
    </state>

    {ruling_instruction}
    <boss_strategy>{boss_directive}</boss_strategy>

    <protocol>
    This engine executes a FULL ROUND (Player Action -> Enemy Reaction).
    
    STEP 1: PLAYER TURN
    1. Interpret Player Action. CALL `roll_dice` based on formula.
    2. Check Result vs Enemy AC (or Save DC).
    3. If HIT: CALL `update_hp` (Enemy).

    STEP 2: ENEMY TURN (MANDATORY if Enemy survives)
    1. Select an attack from "Ataques Disponíveis" based on <boss_strategy>.
    2. DO NOT INVENT STATS. Use the formulas provided (e.g., if list says '2d10+5', use it!).
    3. CALL `roll_dice` for the enemy's attack (Use the stats provided, e.g., "1d20+9").
    4. Check Result vs Player AC ({player.get('defense')}).
    5. If HIT (or Player fails Save): 
       - CALL `roll_dice` for damage (using the damage formula provided).
       - CALL `update_hp` (Target: "{player['name']}", Amount: negative damage).
    
    STEP 3: NARRATIVE
    - Narrate the entire exchange (Player's move + Enemy's reaction) vividly.
    </protocol>
    """)

    # Execução (Usando SMART para lidar com a complexidade do turno duplo)
    tier = ModelTier.SMART
    llm = get_llm(temperature=0.2, tier=tier)
    
    print(f"\n\033[93m🎲 [ENGINE] Iniciando Turno de Combate...\033[0m")
    
    return execute_engine(llm, system_msg, messages, state, node_name="Combate")