"""
agents/router.py

Este módulo é o 'Guarda de Trânsito' da Engine.
Ele decide para qual agente (Narrador, Combate, NPC, Regras) a intenção do jogador deve ir.
"""

from enum import Enum
from typing import Optional, List

# Imports do LangChain e Pydantic
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
from langgraph.graph import END
from pydantic import BaseModel, Field

# Imports internos do projeto
from llm_setup import ModelTier, get_llm
from state import GameState


# --- 1. DEFINIÇÕES DE DADOS ESTRUTURADOS ---

class RouteType(str, Enum):
    """
    Destinos válidos no grafo.
    Usar Enum impede que o LLM invente rotas que não existem no código.
    """
    STORY = "storyteller"    # Exploração, descrição de cenário, viagem
    COMBAT = "combat_agent"  # Início de hostilidade, ataques, sacar armas
    NPC = "npc_actor"        # Conversa direta com um NPC específico
    NONE = "none"            # Fallback


class RouterDecision(BaseModel):
    """
    O formato rígido que o LLM deve preencher.
    Isso elimina a necessidade de fazer parsing de texto (Regex).
    """
    route: RouteType = Field(
        description="O módulo que deve lidar com a intenção do jogador."
    )
    target: Optional[str] = Field(
        default=None,
        description="Se for NPC ou COMBAT, quem é o alvo da ação? Ex: 'Goblin', 'Valerius'. Se não houver, null."
    )
    reasoning: str = Field(
        description="Explicação breve do motivo da escolha (para debug)."
    )
    confidence: float = Field(
        ge=0.0, le=1.0,
        description="Nível de certeza de 0.0 a 1.0."
    )


# --- 2. LÓGICA DO NÓ (ROUTER) ---

def dm_router_node(state: GameState):
    """
    Analisa o input do jogador e direciona para o nó correto.
    """
    messages = state.get("messages", [])
    
    # Check 1: Início do Jogo
    if not messages:
        return {"next": RouteType.STORY.value}

    # Check 2: Proteção contra Loop de IA
    # Se a última mensagem foi da IA e não foi uma chamada de ferramenta, paramos.
    last_msg = messages[-1]
    if isinstance(last_msg, AIMessage) and not getattr(last_msg, "tool_calls", None):
        return {"next": END}

    # --- PREPARAÇÃO DO CONTEXTO ---
    world = state.get("world", {})
    loc = world.get("current_location", "Desconhecido")
    
    # Lista de NPCs presentes na cena (apenas nomes para economizar tokens)
    visible_npcs = list(state.get("npcs", {}).keys())

    # --- PROMPT DO SISTEMA ---
    # Define claramente o que é cada rota para evitar confusão
    system_instruction = f"""
    Você é o Roteador de Decisão (Dungeon Master) de uma Engine de RPG.
    Analise a última mensagem do JOGADOR e classifique a intenção.

    CONTEXTO:
    - Local: {loc}
    - NPCs Visíveis: {visible_npcs}

    DEFINIÇÕES DE ROTA:
    1. STORY (storyteller): O jogador quer explorar, observar, viajar ou fazer ações gerais. (Padrão).
    2. NPC (npc_actor): O jogador fala DIRETAMENTE com um personagem da lista acima.
    3. COMBAT (combat_agent): O jogador ataca, saca armas, prepara emboscada ou mostra hostilidade agressiva.

    INSTRUÇÕES:
    - Se o jogador falar com alguém que NÃO está na lista, escolha 'STORY' (o narrador dirá que não está lá).
    - Extraia o 'target' se houver um alvo claro (ex: "Ataco o *Goblin*", "Falo com *Valerius*").
    """

    # Configura LLM Rápido e Preciso
    llm = get_llm(temperature=0.0, tier=ModelTier.FAST)

    try:
        # Structured Output: A mágica que força o JSON válido
        router_llm = llm.with_structured_output(RouterDecision)
        
        # Envia as últimas 5 mensagens para manter o contexto recente
        decision = router_llm.invoke([SystemMessage(content=system_instruction)] + messages[-5:])
        
    except Exception as e:
        print(f"⚠️ [ROUTER ERROR]: {e}")
        # Fallback seguro: Manda para a História
        return {"next": RouteType.STORY.value}

    print(f"🚦 [ROUTER] Rota: {decision.route.value} | Alvo: {decision.target} | Conf: {decision.confidence}")

    # --- LÓGICA DE DECISÃO E FILTRAGEM ---

    # 1. Confiança Baixa: Pede clarificação ao usuário
    if decision.confidence < 0.6:
        clarification = AIMessage(
            content="🤔 Não entendi muito bem. Você quer conversar, atacar ou apenas explorar?"
        )
        return {
            "messages": [clarification],
            "next": END  # Importante: Para aqui e espera o usuário digitar de novo
        }

    # 2. Rota de NPC: Validação de Presença
    if decision.route == RouteType.NPC:
        target_name = decision.target if decision.target else ""
        
        # Busca Fuzzy: Vê se o alvo citado está na lista de NPCs reais
        real_target = next(
            (n for n in visible_npcs if n.lower() in target_name.lower() or target_name.lower() in n.lower()), 
            None
        )
        
        if not real_target:
            # Jogador quer falar com fantasma -> Narrador resolve
            return {"next": RouteType.STORY.value}
        
        return {
            "next": RouteType.NPC.value,
            "active_npc_name": real_target
        }

    # --- MONTAGEM DO RETORNO PADRÃO ---
    response_payload = {
        "next": decision.route.value,
        "world": world,
        "router_confidence": decision.confidence,
        # Passa o alvo para o combate saber quem atacar (evita que o Combat Agent tenha que adivinhar)
        "combat_target": decision.target if decision.route == RouteType.COMBAT else None
    }

    # === 3. INJEÇÃO DE CONTEXTO DE COMBATE (HANDSHAKE) ===
    # Se o roteador decidiu que é HORA DO COMBATE, avisa o próximo agente.
    if decision.route == RouteType.COMBAT:
        print(f"⚔️ [ROUTER] Iniciando Sequência de Combate contra: {decision.target}")
        
        # Cria uma mensagem de sistema INVISÍVEL para o jogador, mas instrutiva para a IA
        # Isso corrige o "engasgo" onde o combate começava sem contexto
        combat_trigger = SystemMessage(content=(
            "SYSTEM EVENT: COMBAT SCENE START.\n"
            "INSTRUCTION FOR COMBAT AGENT:\n"
            "1. This is the transition from narrative to combat.\n"
            "2. Describe the enemies drawing weapons or reacting to the player's hostility.\n"
            "3. If the player attacked first, resolve that surprise attack immediately.\n"
            "4. Ask for Initiative roll if the situation is neutral."
        ))
        
        # Garante que a lista de mensagens existe no payload
        if "messages" not in response_payload:
            response_payload["messages"] = []
            
        # Anexa o gatilho ao final do histórico que o Combat Agent vai receber
        response_payload["messages"].append(combat_trigger)

    return response_payload