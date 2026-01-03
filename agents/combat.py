"""
agents/combat.py
Agente de Combate Inteligente.
Integração: Router -> Identify Enemies -> Bestiary Fetch -> Combat Loop.
"""
from typing import List, Dict, Optional
from langchain_core.messages import SystemMessage, AIMessage, HumanMessage, ToolMessage
from pydantic import BaseModel, Field

# Imports do Projeto
from state import GameState, EnemyStats
from llm_setup import ModelTier, get_llm
from gamedata import ARTIFACTS_DB
from engine_utils import execute_engine
from agents.ruler_completo import resolve_action

# --- IMPORTAÇÃO CRÍTICA DO BESTIÁRIO ---
# Isso garante que usaremos o cache/DB existente
from agents.bestiary import generate_new_enemy 

# --- MODELOS DE IDENTIFICAÇÃO ---
class EnemyIdentification(BaseModel):
    name: str = Field(description="Nome singular do inimigo. Ex: 'Goblin', 'Rato da Peste'")
    count: int = Field(description="Quantidade destes inimigos na cena.")

class EncounterScanner(BaseModel):
    detected_enemies: List[EnemyIdentification]
    flavor_text: str = Field(description="Descrição curta da entrada dos inimigos em combate.")

# --- FUNÇÃO DE SPAWN INTEGRADA ---
def _spawn_enemies_integrated(messages: List, target_hint: str) -> List[EnemyStats]:
    """
    1. Lê o contexto narrativo.
    2. Identifica nomes e quantidades.
    3. Busca/Gera as fichas usando o Bestiary Agent (mantendo consistência do DB).
    """
    print(f"⚡ [COMBAT] Escaneando cena por inimigos. Dica: '{target_hint}'...")
    
    llm = get_llm(temperature=0.0, tier=ModelTier.FAST)
    
    # Prompt focado apenas em IDENTIFICAR, não em criar stats
    sys_prompt = f"""
    Analise a narrativa recente. O combate começou.
    Identifique QUAIS inimigos estão presentes e QUANTOS.
    Use a dica do alvo se ajudar: "{target_hint}".
    
    Exemplo: Se o texto diz "Três orcs surgem", retorne: [{{name: "Orc", count: 3}}].
    """
    
    try:
        scanner = llm.with_structured_output(EncounterScanner)
        scan_result = scanner.invoke([SystemMessage(content=sys_prompt)] + messages[-4:])
        
        final_enemies_list = []
        
        for identified in scan_result.detected_enemies:
            # AQUI ESTÁ A INTEGRAÇÃO COM O SEU BANCO DE DADOS
            # Chamamos o bestiary.py. Se o monstro já existir no JSON, ele retorna na hora.
            # Se não, ele cria, SALVA NO JSON, e retorna.
            template = generate_new_enemy(identified.name, context=target_hint)
            
            # Agora instanciamos (criamos cópias únicas para o combate)
            for i in range(identified.count):
                # Criamos uma cópia profunda para não alterar o template original
                instance = template.copy()
                
                # ID único para o combate (ex: enemy_goblin_1, enemy_goblin_2)
                instance["id"] = f"{template['id']}_{i+1}"
                instance["name"] = f"{template['name']} {i+1}" if identified.count > 1 else template["name"]
                
                # Garante campos obrigatórios do EnemyStats
                if "stamina" not in instance: instance["stamina"] = 10
                if "mana" not in instance: instance["mana"] = 0
                if "defense" not in instance: instance["defense"] = instance.get("ac", 10)
                if "attack_mod" not in instance: instance["attack_mod"] = 0 # Usado se não tiver attacks listados
                
                final_enemies_list.append(instance)
                
        return final_enemies_list, scan_result.flavor_text

    except Exception as e:
        print(f"⚠️ Erro no Spawn Integrado: {e}")
        # Fallback genérico se tudo falhar
        return [{
            "id": "fallback_enemy", "name": "Inimigo Sombrio", "hp": 15, "max_hp": 15, 
            "defense": 12, "status": "ativo", "active_conditions": [], 
            "attributes": {}, "abilities": ["Ataque 1d6"], "stamina": 0, "mana": 0
        }], "Algo hostil emerge das sombras!"

# --- UTILS DE COMBATE ---
def get_mod(score: int) -> int: return (score - 10) // 2
def _normalize_attr_name(attr: str) -> str:
    mapping = {"strength": "str", "força": "str", "dexterity": "dex", "destreza": "dex", "constitution": "con", "constituição": "con", "intelligence": "int", "wisdom": "wis", "charisma": "cha"}
    return mapping.get(attr.lower(), attr.lower())

# --- NÓ PRINCIPAL ---
def combat_node(state: GameState):
    messages = state.get("messages", [])
    if not messages: return {"next": "dm_router"}

    player = state["player"]
    party = state.get("party", []) 
    enemies = state.get("enemies", []) or []
    
    # 1. VERIFICAÇÃO DE INÍCIO (HANDOFF)
    last_msg = messages[-1]
    is_combat_start = False
    if isinstance(last_msg, SystemMessage) and "COMBAT START" in str(last_msg.content):
        is_combat_start = True
    
    combat_target = state.get("combat_target", "Inimigos")

    # 2. LOGICA DE SPAWN (SE NECESSÁRIO)
    # Se começou agora e não tem ninguém na lista de inimigos...
    spawned_flavor = None
    active_enemies = [e for e in enemies if e["status"] == "ativo"]
    
    if is_combat_start and not active_enemies:
        # Chama a função que usa o BESTIÁRIO
        generated_enemies, spawned_flavor = _spawn_enemies_integrated(messages, combat_target)
        enemies = generated_enemies
        active_enemies = enemies # Atualiza localmente
        print(f"⚔️ Combate Configurado: {[e['name'] for e in active_enemies]}")

    # 3. CONDIÇÃO DE VITÓRIA (Só verifica se NÃO acabou de spawnar)
    if not active_enemies:
        return {
            "messages": [AIMessage(content="O silêncio retorna ao campo de batalha. Vitória.")],
            "next": "loot",
            "combat_target": None,
            "enemies": []
        }

    # --- PREPARAÇÃO DO PROMPT DE ENGINE (Mantido idêntico, apenas montagem de strings) ---
    attrs = player.get("attributes", {"str": 10})
    normalized_attrs = {_normalize_attr_name(k): v for k, v in attrs.items()}
    mods = {k: get_mod(v) for k, v in normalized_attrs.items()}
    
    # Inventário e Mecânicas
    inventory_ids = player.get("inventory", [])
    best_atk_bonus = 0
    total_ac_bonus = 0
    active_attr_key = "str"
    mechanics_log = []

    for item_id in inventory_ids:
        item_data = ARTIFACTS_DB.get(item_id)
        if item_data:
            stats = item_data.get("combat_stats", {})
            if item_data.get("type") == "weapon":
                b = stats.get("attack_bonus", 0)
                if b > best_atk_bonus:
                    best_atk_bonus = b
                    if "attribute" in stats: active_attr_key = _normalize_attr_name(stats["attribute"])
            total_ac_bonus += stats.get("ac_bonus", 0)

            mech = item_data.get("mechanics", {})
            for p in mech.get("passive_effects", []): mechanics_log.append(f"[PASSIVE] {item_data['name']}: {p}")
            active = mech.get("active_ability")
            if active: mechanics_log.append(f"[SPELL] {active.get('name')}: {active.get('effect')}")

    total_atk = mods.get(active_attr_key, 0) + best_atk_bonus
    current_ac = 10 + mods.get("dex", 0) + total_ac_bonus

    # Formatação dos Inimigos
    enemy_desc_list = []
    for idx, e in enumerate(active_enemies):
        atk_str = "Ataque Básico"
        # Tenta pegar ataques da estrutura do bestiário
        attacks = e.get("attacks", [])
        if attacks and isinstance(attacks, list) and len(attacks) > 0:
            # Pega o primeiro ataque como exemplo
            atk = attacks[0]
            if isinstance(atk, dict):
                atk_str = f"{atk.get('name')} (+{atk.get('bonus')}) {atk.get('damage')}"
            else:
                atk_str = str(atk)
        
        enemy_desc_list.append(f"{idx+1}. {e['name']} (HP:{e['hp']}/{e['max_hp']} | AC:{e.get('defense', 10)}) | {atk_str}")
    
    mechanics_str = "\n".join(mechanics_log) if mechanics_log else "Nenhum."
    enemy_str = "\n".join(enemy_desc_list)
    party_str = ", ".join([p['name'] for p in party if p['hp'] > 0]) or "Sozinho"

    # Ruler Logic
    ruling_instruction = ""
    if is_combat_start and spawned_flavor:
        ruling_instruction = f"EVENTO INICIAL: {spawned_flavor} O combate começa agora."
    elif last_msg and not isinstance(last_msg, (ToolMessage, AIMessage, SystemMessage)):
        try:
            ruling = resolve_action(player, last_msg.content)
            ruling_instruction = f"[RULER]: Formula '{ruling.get('dice_formula')}', Effect: {ruling.get('mechanical_effect')}"
        except: pass

    # 4. EXECUÇÃO
    system_msg = SystemMessage(content=f"""
    <role>Combat Engine</role>
    <hero>
    {player['name']} | HP: {player['hp']} | AC: {current_ac}
    ATK: +{total_atk} ({active_attr_key.upper()})
    </hero>
    <mechanics>{mechanics_str}</mechanics>
    <enemies>\n{enemy_str}\n</enemies>
    <party>{party_str}</party>
    {ruling_instruction}
    
    <instructions>
    1. Resolve Hero Action based on [RULER] or description.
    2. Resolve Enemy Counter-Actions (Roll vs AC).
    3. Narrate broadly.
    </instructions>
    """)

    tier = ModelTier.SMART
    llm = get_llm(temperature=0.2, tier=tier)
    
    result = execute_engine(llm, system_msg, messages, state, node_name="Combate")
    
    # IMPORTANTE: Se spawnam inimigos, precisamos garantir que o state de retorno tenha eles
    if is_combat_start and enemies:
        # Se a engine não retornou enemies (pq não houve dano ainda), injetamos a lista inicial
        if "enemies" not in result or not result["enemies"]:
            result["enemies"] = enemies
            
    return result