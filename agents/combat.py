from typing import List, Optional
from pydantic import BaseModel, Field
from langchain_core.messages import SystemMessage, AIMessage, HumanMessage
from state import GameState
from llm_setup import ModelTier, get_llm
from gamedata import ITEMS_DB
from engine_utils import execute_engine

# Importa gerador de inimigos para conversão de NPCs hostis
from agents.bestiary import generate_new_enemy

# --- INTEGRAÇÃO RAG ---
from rag import query_rag


class BossStrategy(BaseModel):
    name: str
    description: str
    win_rate: float = Field(ge=0, le=10, description="0-10 win probability")
    action_script: str = Field(description="Tactical actions to execute this turn")


class BossStrategySet(BaseModel):
    strategies: List[BossStrategy]


def get_mod(score: int) -> int:
    return (score - 10) // 2


def combat_node(state: GameState):
    messages = state.get("messages", [])
    if not messages:
        return {
            "messages": [
                AIMessage(
                    content="Nenhuma ação recente. Descreva o que deseja fazer para iniciar o combate."
                )
            ],
            "world": state.get("world", {}),
        }

    player = state["player"]

    # Cálculos Básicos
    attrs = player["attributes"]
    mods = {k: get_mod(v) for k, v in attrs.items()}

    best_bonus = 0
    active_attr = "strength"
    for i in player.get("inventory", []):
        d = ITEMS_DB.get(i)
        if d and d["type"] == "weapon" and d["bonus"] > best_bonus:
            best_bonus = d["bonus"]
            active_attr = d["attr"]
    total_atk = mods[active_attr] + best_bonus

    # Inimigos Ativos
    enemies = state.get("enemies", [])
    active_enemies = [e for e in enemies if e["status"] == "ativo"]

    # Verifica última intenção do jogador para buscar regra
    last_msg = messages[-1]
    player_already_acted = isinstance(last_msg, AIMessage) and not last_msg.tool_calls

    last_user_intent = ""
    if isinstance(last_msg, HumanMessage):
        last_user_intent = last_msg.content

    # --- PRE-CHECK: converte agressão a NPC em inimigo ativo ---
    if not active_enemies:
        target_npc = None
        
        # 1. TENTA PEGAR DO ROUTER (Prioridade Máxima)
        # O Router já resolveu pronomes ("atacá-lo" -> "Valerius")
        router_target = state.get("combat_target") 
        
        found_by_router = False

        if router_target:
            print(f"🎯 [COMBAT] Router indicou alvo: {router_target}")
            # Busca fuzzy no dicionário de NPCs
            for name, npc in state.get("npcs", {}).items():
                # Verifica se o nome do NPC está dentro do alvo do router ou vice-versa
                if name.lower() in router_target.lower() or router_target.lower() in name.lower():
                    target_npc = (name, npc)
                    found_by_router = True
                    break
        
        # 2. FALLBACK: BUSCA NO TEXTO (Se o Router falhou ou não enviou nada)
        if not target_npc and last_user_intent:
            lowered_intent = last_user_intent.lower()
            for name, npc in state.get("npcs", {}).items():
                if name.lower() in lowered_intent:
                    target_npc = (name, npc)
                    break

        # SE ACHOU UM ALVO VÁLIDO (Pelo Router ou Texto)
        if target_npc:
            npc_name, npc_data = target_npc
            print(
                f"⚔️ [COMBAT] Jogador iniciou agressão contra NPC '{npc_name}'. Convertendo para inimigo..."
            )
            
            # Gera a ficha técnica do monstro baseada na persona do NPC
            enemy_template = generate_new_enemy(npc_name, context=npc_data.get("persona", ""))
            
            if enemy_template:
                if "enemies" not in state:
                    state["enemies"] = []
                
                new_id = f"{npc_name.lower().replace(' ', '_')}_{len(state['enemies'])}"
                hostile = enemy_template.copy()
                hostile["id"] = hostile.get("id", new_id)
                hostile["status"] = hostile.get("status", "ativo")
                hostile.setdefault("active_conditions", [])
                hostile.setdefault("type", enemy_template.get("type", "NPC"))
                
                # Salva quem ele era antes de virar monstro (para memória póstuma)
                hostile["origin_npc"] = {
                    "name": npc_name,
                    "persona": npc_data.get("persona"),
                    "relationship": npc_data.get("relationship"),
                    "memory": npc_data.get("memory", [])[-5:],
                }
                
                # Adiciona à lista de inimigos
                state["enemies"].append(hostile)
                
                # Opcional: Remove da lista de NPCs sociais para ele não aparecer duplicado
                state.get("npcs", {}).pop(npc_name, None)
                
                # Atualiza a lista local de inimigos ativos para o combate começar AGORA
                active_enemies = [hostile]
                
                # Limpa o combat_target do estado para não causar loops futuros
                state["combat_target"] = None

        # Se depois de tudo isso ainda não tiver inimigos...
        if not active_enemies:
            return {
                "messages": [
                    AIMessage(
                        content="There is no one here to fight. The tension fades as the scene shifts."
                    )
                ],
                "world": state.get("world", {}),
            }

    # ✅ CORREÇÃO AQUI: join com generator (sem vírgula sobrando)
    enemy_str = "\n".join(
        f"{idx+1}. {e['name']} (ID:{e['id']} | HP:{e['hp']} | Cond:{e.get('active_conditions', [])})"
        for idx, e in enumerate(active_enemies)
    )

    boss_enemies = [e for e in active_enemies if e.get("type", "").upper() == "BOSS"]

    # 1. CONSULTA O RAG (REGRAS DE COMBATE)
    combat_rules = ""
    if last_user_intent:
        try:
            combat_rules = query_rag(last_user_intent, index_name="rules")
        except Exception as exc:  # noqa: BLE001
            print(f"[COMBAT RAG ERROR] {exc}")
            combat_rules = ""
        if not combat_rules:
            combat_rules = "Regras Padrão: Ataque x AC. Dano reduz HP."

    boss_directive = None
    if boss_enemies:
        boss_directive = _tree_of_thoughts_strategy(
            player, boss_enemies, combat_rules, last_user_intent, enemy_str
        )

    system_msg = SystemMessage(
        content=f"""
    <role>General de Combate (Game Engine).</role>

    <state>
    Player: HP {player['hp']} | ATK +{total_atk} | AC {player['defense']}
    Condições Atuais: {player.get('active_conditions',[])}
    Inimigos Visíveis:
    {enemy_str}

    Player Já Agiu Neste Turno? {player_already_acted}
    </state>

    <boss_strategy>
    {boss_directive if boss_directive else "Nenhum chefe presente ou estratégia padrão para lacaios."}
    </boss_strategy>

    <consulted_rules>
    {combat_rules}
    </consulted_rules>

    <protocol>
    1. AÇÃO JOGADOR (Se não agiu):
       - Analise a intenção. Se for Ataque, requer Tool 'Ataque Jogador'.
       - Se for Manobra (Desarmar, Empurrar), siga a regra em <consulted_rules>.
       
       IMPORTANTE: O Jogador acabou de iniciar hostilidade contra um novo inimigo ({active_enemies[0]['name']}).
       Descreva o início do combate e processe o primeiro ataque se a intenção foi clara.

    2. REAÇÃO INIMIGA (Se Player já agiu ou sobrou ação):
       - Inimigos vivos contra-atacam.
       - Se Inimigo tem condição 'Cego/Caído', aplique penalidade (Desvantagem).
    </protocol>
    """
    )

    tier = ModelTier.SMART if boss_enemies else ModelTier.FAST
    llm = get_llm(temperature=0.1, tier=tier)
    
    # Retornamos o combat_target como None para limpar o estado global
    result = execute_engine(llm, system_msg, state["messages"], state, "Combate")
    if "combat_target" not in result:
        result["combat_target"] = None # Garante a limpeza
        
    return result


def _tree_of_thoughts_strategy(
    player, bosses, combat_rules: str, last_user_intent: str, enemy_str: str
) -> str:
    """Gera 3 ramos táticos e escolhe o de maior win rate para chefes."""
    llm = get_llm(temperature=0.4, tier=ModelTier.SMART)
    system_msg = SystemMessage(
        content=f"""
    You are a tactical AI assisting boss monsters in a tabletop RPG.
    Player status: HP {player['hp']}, AC {player['defense']}, Conditions: {player.get('active_conditions',[])}
    Active bosses and enemies:
    {enemy_str}

    Combat rules in play:
    {combat_rules}

    Generate exactly three distinct strategies (aggressive burst, evasive/defensive-heal, tactical/AoE or control), each with:
    - name
    - 1-2 sentence description
    - win_rate score from 0-10 (higher means better odds this round)
    - action_script describing concrete moves for this turn
    """
    )

    human_msg = HumanMessage(content=f"Player last intent: {last_user_intent}")

    try:
        planner = llm.with_structured_output(BossStrategySet)
        plan = planner.invoke([system_msg, human_msg])
        strategies = plan.strategies
    except Exception as exc:  # noqa: BLE001
        print(f"[BOSS STRATEGY ERROR] {exc}")
        strategies = [
            BossStrategy(
                name="Aggressive Claws",
                description="Investida brutal",
                win_rate=5.0,
                action_script="Avançar com golpes consecutivos",
            ),
            BossStrategy(
                name="Soaring Breath",
                description="Ataque aéreo de fôlego",
                win_rate=7.0,
                action_script="Alçar voo e usar sopro em área",
            ),
            BossStrategy(
                name="Retreat and Mend",
                description="Recuo para curar",
                win_rate=4.5,
                action_script="Recuar, usar cobertura e curar feridas",
            ),
        ]

    best = max(strategies, key=lambda s: s.win_rate)
    return f"Estratégia vencedora: {best.name} ({best.win_rate}/10). Roteiro: {best.action_script}."