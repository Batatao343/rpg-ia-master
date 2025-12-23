"""
agents/router.py

Este módulo é o 'Cérebro de Tráfego' da Engine.
Ele não gera a história, apenas decide QUEM deve gerar a próxima resposta.
Usa 'Structured Output' para garantir que a decisão seja sempre um JSON válido.
"""

from enum import Enum
from typing import Optional, List

# Imports do LangChain para manipulação de mensagens e fluxo
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
from langgraph.graph import END
from pydantic import BaseModel, Field

# Imports internos do seu projeto
from llm_setup import ModelTier, get_llm
from state import GameState

# --- 1. DEFINIÇÕES DE TIPOS ---

class RouteType(str, Enum):
    """
    Define os destinos possíveis no grafo.
    Isso garante que o LLM não invente um destino inexistente (ex: 'inventory_manager').
    """
    STORY = "storyteller"    # Narrativa geral, exploração, descrição de cenário
    COMBAT = "combat_agent"  # Início de briga, sacar armas, ataques
    RULES = "rules_agent"    # Perguntas sobre mecânicas ("Quanto de XP tenho?", "Como funciona x?")
    NPC = "npc_actor"        # Conversa direta com um personagem específico
    NONE = "none"            # Fallback (raramente usado)


class RouterDecision(BaseModel):
    """
    A estrutura RÍGIDA que o LLM é obrigado a retornar.
    Substitui a necessidade de fazer parsing de strings ou regex.
    """
    route: RouteType = Field(
        description="O próximo módulo a ser executado com base na intenção do usuário."
    )
    target: Optional[str] = Field(
        default=None,
        description="Se a rota for NPC ou COMBAT, quem é o alvo? Ex: 'Goblin', 'Valerius'. Se não houver alvo específico, use null."
    )
    reasoning: str = Field(
        description="Uma breve explicação do porquê desta decisão (útil para debug)."
    )
    confidence: float = Field(
        ge=0.0, le=1.0,
        description="Nível de certeza da decisão, de 0.0 a 1.0."
    )

# --- 2. LÓGICA DO NÓ ---

def dm_router_node(state: GameState):
    """
    Analisa o histórico de mensagens e o estado do mundo para decidir o próximo passo.
    
    Args:
        state (GameState): O estado atual contendo mensagens, mundo, npcs, etc.
        
    Returns:
        dict: Um update de estado contendo a chave 'next' (próximo nó) e metadados.
    """
    
    messages = state["messages"]

    # --- CHECK 1: ESTADO VAZIO ---
    # Se não há mensagens, é o início do jogo. Manda pro Storyteller iniciar.
    if not messages:
        return {"next": RouteType.STORY.value}

    # --- CHECK 2: PROTEÇÃO CONTRA LOOP INFINITO ---
    # Se a última mensagem foi da IA e não chamou nenhuma ferramenta (tool_calls),
    # significa que a IA acabou de falar. O jogo deve PARAR (END) e esperar o usuário.
    # Sem isso, a IA poderia ficar respondendo a si mesma eternamente.
    last_msg = messages[-1]
    if isinstance(last_msg, AIMessage) and not getattr(last_msg, "tool_calls", None):
        return {"next": END}

    # --- PREPARAÇÃO DO CONTEXTO ---
    # O Roteador precisa saber onde estamos e quem está perto para não alucinar.
    world = state.get("world", {})
    loc = world.get("current_location", "Desconhecido")
    
    # Extrai apenas os nomes dos NPCs visíveis para economizar tokens
    # Assume que state['npcs'] é um dict { "Nome": {dados...}, ... }
    visible_npcs = list(state.get("npcs", {}).keys())

    # --- PROMPT DO SISTEMA ---
    # Aqui definimos as regras do jogo para o LLM Roteador.
    # Note que explicamos EXATAMENTE o que cada rota significa.
    system_instruction = f"""
    <PERSONA>
    Você é o Roteador de Decisão (Dungeon Master) de uma Engine de RPG.
    Sua única função é analisar a última mensagem do JOGADOR e classificar a intenção.

    <CONTEXTO ATUAL>
    - Local: {loc}
    - Personagens Visíveis (NPCs): {visible_npcs}

    <DEFINIÇÕES DE ROTA>
    1. STORY (storyteller): O jogador quer explorar, observar, viajar ou fazer ações gerais. Padrão para dúvidas ambíguas.
    2. NPC (npc_actor): O jogador fala DIRETAMENTE com um personagem específico presente na lista acima.
    3. COMBAT (combat_agent): O jogador ataca alguém, saca uma arma ou assume postura agressiva.
    4. RULES (rules_agent): O jogador pergunta sobre fichas, XP, regras ou inventário (fora da narrativa).

    <INSTRUÇÕES>
    - Se o jogador falar com alguém que NÃO está na lista de NPCs Visíveis, escolha 'STORY' para que o narrador diga que a pessoa não está lá.
    - Se a confiança for baixa, marque confidence < 0.5.
    """

    # Configuramos o modelo FAST (barato e rápido) com temperatura 0 (máxima precisão)
    llm = get_llm(temperature=0.0, tier=ModelTier.FAST)
    
    try:
        # --- A MÁGICA DO STRUCTURED OUTPUT ---
        # Forçamos o LLM a retornar a classe RouterDecision, não texto livre.
        router_llm = llm.with_structured_output(RouterDecision)
        
        # Invocamos passando o sistema + as últimas 5 mensagens (histórico recente é suficiente)
        # Isso economiza tokens e mantém o foco no presente.
        decision = router_llm.invoke([SystemMessage(content=system_instruction)] + messages[-5:])
        
    except Exception as e:
        # --- FALLBACK DE SEGURANÇA ---
        # Se a API cair ou der erro de JSON, não crashe o jogo.
        # Mande para o Storyteller (o destino mais seguro) e logue o erro.
        print(f"⚠️ [ROUTER ERROR]: {e}")
        return {"next": RouteType.STORY.value}

    # --- LOG DE DEBUG (Opcional, mas útil) ---
    print(f"🚦 [ROUTER] Rota: {decision.route.value} | Alvo: {decision.target} | Conf: {decision.confidence}")

    # --- LÓGICA DE DECISÃO ---

    # 1. CONFIANÇA BAIXA: Se a IA não entendeu, pergunte ao usuário.
    # IMPORTANTE: Retorna END para parar a execução e esperar input.
    if decision.confidence < 0.6:
        clarification_msg = AIMessage(
            content="Não entendi muito bem. Você quer conversar com alguém, atacar ou apenas explorar o local?"
        )
        return {
            "messages": [clarification_msg],
            "next": END 
        }

    # 2. ROTA DE NPC: Validação de Alvo
    if decision.route == RouteType.NPC:
        # O LLM extraiu um alvo (ex: "o guarda"). Vamos ver se bate com algum NPC real.
        # Usamos uma busca simples (case insensitive) na lista de NPCs visíveis.
        target_name = decision.target if decision.target else ""
        
        # Procura se algum nome da lista está contido no alvo ou vice-versa
        real_target = next(
            (n for n in visible_npcs if n.lower() in target_name.lower() or target_name.lower() in n.lower()), 
            None
        )
        
        if not real_target:
            # O jogador tentou falar com alguém que não existe ou não está aqui.
            # Mandamos para o Storyteller narrar: "Não há ninguém com esse nome aqui."
            # Injetamos uma 'dica' oculta no estado para o Storyteller saber o que houve.
            return {
                "next": RouteType.STORY.value,
                # Opcional: Você pode adicionar um campo temporário de erro se quiser
            }
        
        # Se achou, manda pro Agente de NPC com o nome correto
        return {
            "next": RouteType.NPC.value,
            "active_npc_name": real_target,
            "router_confidence": decision.confidence
        }

    # 3. ROTAS PADRÃO (Story, Combat, Rules)
    return {
        "next": decision.route.value,
        "world": world, # Repassa o mundo (embora o StateGraph já faça merge, é bom garantir)
        "router_confidence": decision.confidence
    }