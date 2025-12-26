"""
agents/combat.py
(Versão Full AI: Sem heurísticas. O Ruler julga TUDO.)
"""
from typing import List, Dict, Optional
from langchain_core.messages import SystemMessage, AIMessage, HumanMessage, ToolMessage
from pydantic import BaseModel, Field

# Imports do Projeto
from state import GameState
from llm_setup import ModelTier, get_llm
from gamedata import ITEMS_DB
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

# --- FUNÇÕES AUXILIARES ---
def get_mod(score: int) -> int: return (score - 10) // 2

def _normalize_attr_name(attr: str) -> str:
    attr = attr.lower()
    mapping = {"strength": "str", "força": "str", "dexterity": "dex", "destreza": "dex", "constitution": "con", "constituição": "con", "intelligence": "int", "wisdom": "wis", "charisma": "cha"}
    return mapping.get(attr, attr)

# --- TREE OF THOUGHTS ---
def _tree_of_thoughts_strategy(player, party, bosses, last_user_intent, enemy_str) -> str:
    print(f"\n\033[95m🧠 [BOSS AI] Analisando Ameaças (ToT)...\033[0m")
    llm = get_llm(temperature=0.4, tier=ModelTier.SMART)
    
    party_count = len([p for p in party if p.get("hp", 0) > 0])
    party_context = f"Allies Active: {party_count}"
    
    system_msg = SystemMessage(content=f"""
    You are a Tactical AI for a Boss in a Fictional RPG Game Simulation.
    Context: Player HP {player['hp']}, {party_context}, Bosses Active.
    
    TASK: Generate 3 distinct tactical strategies (Aggressive, Defensive, Control).
    For each strategy, provide a 'win_rate' (0.0 to 1.0) and an 'action_script'.
    """)
    human_msg = HumanMessage(content=f"Player Action: {last_user_intent}")

    try:
        planner = llm.with_structured_output(BossStrategySet).with_retry(stop_after_attempt=3)
        plan = planner.invoke([system_msg, human_msg])
        
        if not plan or not plan.strategies:
            raise ValueError("IA retornou plano vazio.")

        best = max(plan.strategies, key=lambda s: s.win_rate)
        print(f"\033[95m✅ [BOSS AI] Estratégia: {best.name.upper()}\033[0m")
        return f"Boss Strategy: {best.name}. Tactic: {best.action_script}"
        
    except Exception as e:
        print(f"⚠️ [BOSS AI] Fallback: {e}")
        return "Boss Strategy: Brutal Force. Tactic: Attack the closest target."

# --- NÓ PRINCIPAL ---
def combat_node(state: GameState):
    messages = state.get("messages", [])
    if not messages: return {"next": "dm_router"}

    player = state["player"]
    party = state.get("party", []) 
    enemies = state.get("enemies", [])
    
    # 1. Filtra Ativos
    active_enemies = [e for e in enemies if e["status"] == "ativo"]
    active_party = [p for p in party if p.get("hp", 0) > 0]

    if not active_enemies:
        return {"messages": [AIMessage(content="O combate terminou.")], "combat_target": None}

    # 2. Stats Básicos (Apenas para referência no Prompt, o Ruler decide a fórmula real)
    attrs = player.get("attributes", {"str": 10})
    normalized_attrs = {_normalize_attr_name(k): v for k, v in attrs.items()}
    mods = {k: get_mod(v) for k, v in normalized_attrs.items()}
    
    best_bonus = 0
    active_attr_key = "str"
    for item_name in player.get("inventory", []):
        d = ITEMS_DB.get(item_name)
        if d and d.get("type") == "weapon":
            b = d.get("bonus", 0)
            if b > best_bonus:
                best_bonus = b
                active_attr_key = _normalize_attr_name(d.get("attr", "str"))
    total_atk = mods.get(active_attr_key, 0) + best_bonus

    # 3. Party String
    party_str = ""
    if active_party:
        p_lines = []
        for p in active_party:
            stats = p.get("stats", {})
            atk_info = stats.get("attack", "Ataque Básico +3 (1d6)")
            ac_info = stats.get("AC", 10)
            role = p.get("role", "Aliado")
            persona = p.get("persona", "Leal")
            
            p_lines.append(
                f"- {p['name']} ({role}) | HP: {p['hp']}/{p['max_hp']} | AC: {ac_info}\n"
                f"  PERSONALIDADE: {persona}\n"
                f"  HABILIDADE: {atk_info}"
            )
        party_str = "ALIADOS ATIVOS (PARTY AI):\n" + "\n".join(p_lines)
    else:
        party_str = "ALIADOS: Nenhum."

    # 4. Enemy String
    enemy_desc_list = []
    for idx, e in enumerate(active_enemies):
        atk_str = "Ataque Básico (1d4)"
        if "attacks" in e: atk_str = str(e['attacks']) 
        elif "attack" in e: atk_str = e['attack']
        enemy_desc_list.append(f"{idx+1}. {e['name']} (HP:{e['hp']} | AC:{e.get('defense', 10)}) | {atk_str}")
    enemy_str = "\n".join(enemy_desc_list)

    # 5. RULER & BOSS AI (FULL AI)
    last_msg = messages[-1]
    last_intent = last_msg.content if isinstance(last_msg, HumanMessage) else ""
    
    ruling_instruction = ""
    
    # SE for turno do jogador (mensagem humana), SEMPRE chama o Ruler.
    # Não importa se é "Ataco" ou "Invoco um Meteoro". O Ruler valida tudo.
    if last_intent and not isinstance(last_msg, (ToolMessage, AIMessage)):
        print(f"\n\033[96m⚖️ [RULER] Validando Regras para: '{last_intent}'...\033[0m")
        try:
            ruling = resolve_action(player, last_intent)
            ruling_instruction = (
                f"[RULER INTERVENTION - MANDATORY]\n"
                f"The Rules Judge has decided:\n"
                f"- ALLOWED: {ruling.get('is_allowed', True)}\n"
                f"- DICE FORMULA: '{ruling.get('dice_formula', '0')}'\n"
                f"- EFFECT: {ruling.get('mechanical_effect', 'None')}\n"
                f"- FLAVOR: {ruling.get('flavor_text', '')}\n"
                f"INSTRUCTION: Execute EXACTLY this formula for the player. Do not invent another one."
            )
        except Exception as e:
            print(f"Erro no Ruler: {e}")

    # Boss Strategy
    bosses = [e for e in active_enemies if e.get("type") == "BOSS"]
    boss_directive = ""
    if bosses:
        boss_directive = _tree_of_thoughts_strategy(player, active_party, bosses, last_intent, enemy_str)

    # 6. SYSTEM PROMPT
    system_msg = SystemMessage(content=f"""
    <role>Combat Engine (Party System)</role>
    
    <state>
    HERÓI: {player['name']} (HP {player['hp']} / AC {player['defense']})
    ATK BÔNUS FÍSICO (Ref): +{total_atk}
    
    {party_str}
    
    INIMIGOS:
    {enemy_str}
    </state>

    {ruling_instruction}
    <boss_strategy>{boss_directive}</boss_strategy>

    <protocol>
    Execute a FULL ROUND of combat.
    
    STEP 1: HERO ACTION
    - READ the [RULER INTERVENTION] above carefully.
    - If DICE FORMULA is not '0', CALL `roll_dice` with that exact formula.
    - If DICE FORMULA is '0', just apply the EFFECT (e.g., auto-damage or buff).
    - Call `update_hp` if applicable.

    STEP 2: ALLY ACTIONS (AUTO-PLAY)
    - For each ally, choose an action fitting their PERSONALITY.
    - Call `roll_dice` using their stats.
    - Call `update_hp` if they hit.

    STEP 3: ENEMY REACTION
    - Enemies attack Hero OR Allies.
    - Call `roll_dice` vs Target AC.
    - Call `update_hp` if hit.

    STEP 4: NARRATIVE
    - Describe the scene cinematically.
    </protocol>
    """)

    tier = ModelTier.SMART
    llm = get_llm(temperature=0.2, tier=tier)
    
    print(f"\n\033[93m⚔️ [PARTY COMBAT] Iniciando Rodada (Full AI Control)...\033[0m")
    
    return execute_engine(llm, system_msg, messages, state, node_name="Combate")