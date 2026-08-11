"""
agents/router.py
Roteador de Intenções.
Agora com detecção explícita de início de combate para acionar o Spawner.
"""
from enum import Enum
from typing import Literal, Optional
from langchain_core.messages import AIMessage, SystemMessage, HumanMessage
from langgraph.graph import END
from pydantic import BaseModel, Field, field_validator

from llm_setup import ModelTier, get_llm
from services.input_normalization import optional_entity_ref
from state import GameState

class RouteType(str, Enum):
    STORY = "storyteller"
    COMBAT = "combat_agent"
    NPC = "npc_actor"
    LOOT = "loot"
    NONE = "none"

# spec combate-lifecycle (R3): combate ATIVO que não recebe rota de combate por
# N turnos seguidos é "órfão" — expira sozinho (rede de segurança; com R1+R2 quase
# nunca dispara).
COMBAT_IDLE_EXPIRE = 3


def _last_human_text(messages) -> str:
    """Texto da última fala do jogador (para detectar viagem no gate de combate)."""
    for m in reversed(messages or []):
        if getattr(m, "type", "") == "human":
            return str(getattr(m, "content", "") or "")
    return ""


def _combat_gate(state: GameState, world: dict, combat: dict):
    """Gate determinístico quando `combat.active` (spec combate-lifecycle):
    - R2: força `combat_agent` (bloqueia npc/loot; conversa segue pro combate que narra).
    - R1: ação de VIAGEM não teleporta — vira tentativa de fuga (flag + destino).
    - R3: combate órfão (idle_turns >= N) expira, limpando TUDO (R5)."""
    from world_utils import find_travel_destination

    idle = int(combat.get("idle_turns", 0)) + 1
    if idle >= COMBAT_IDLE_EXPIRE:
        print("🧟 [COMBAT] Combate órfão expirou (idle) — encerrando.")
        cleared = {"active": False, "round": combat.get("round", 1),
                   "order": combat.get("order", []), "idle_turns": 0}
        return {"next": RouteType.STORY.value, "combat": cleared,
                "enemies": [], "combat_target": None,
                "messages": [SystemMessage(content="SYSTEM: COMBAT EXPIRED — "
                             "os inimigos perdem seu rastro e o combate termina.")]}

    combat["idle_turns"] = idle
    payload = {"next": RouteType.COMBAT.value, "world": world, "combat": combat}
    intent = _last_human_text(state.get("messages", []))
    # Uma borda estruturada (API/harness) já resolveu o id exato do destino.
    # O parser textual é apenas fallback: nomes de interiores contêm o nome da
    # região e podem ser reduzidos indevidamente ao nó-pai se reprocessados.
    explicit_dest_id = state.get("combat_flee_destination")
    has_structured_action = state.get("combat_declaration") is not None
    dest = (
        find_travel_destination(world, intent)
        if intent and not explicit_dest_id and not has_structured_action
        else None
    )
    if state.get("combat_flee_attempt") and explicit_dest_id:
        payload["combat_flee_attempt"] = True
        payload["combat_flee_destination"] = explicit_dest_id
    elif dest is not None:
        payload["combat_flee_attempt"] = True
        payload["combat_flee_destination"] = dest["id"]
        print(f"🏃 [COMBAT] Viagem em combate → tentativa de FUGA para {dest['name']}.")
    return payload

class RouterDecision(BaseModel):
    route: RouteType
    loot_context: Optional[Literal["TREASURE", "SHOP", "CRAFT"]] = Field(
        description="Se for LOOT: 'TREASURE', 'SHOP' ou 'CRAFT'."
    )
    target: Optional[str] = Field(description="Se for COMBAT, quem é o inimigo? Ex: 'Goblin', 'Guarda', 'O Vulto'.")
    reasoning: str
    confidence: float

    @field_validator("loot_context", mode="before")
    @classmethod
    def _normalize_loot_context(cls, value):
        normalized = optional_entity_ref(value)
        return normalized.upper() if normalized is not None else None

    @field_validator("target", mode="before")
    @classmethod
    def _normalize_target(cls, value):
        return optional_entity_ref(value)

def dm_router_node(state: GameState):
    messages = state.get("messages", [])
    if not messages: return {"next": RouteType.STORY.value}
    
    last_msg = messages[-1]
    # Evita loop se a IA acabou de falar (exceto tool calls)
    if isinstance(last_msg, AIMessage) and not getattr(last_msg, "tool_calls", None):
        return {"next": END}

    world = state.get("world", {})
    loc = world.get("current_location", "Desconhecido")

    # spec combate-lifecycle: com combate ATIVO, o router não decide livremente —
    # gate determinístico (força combate, converte viagem em fuga, expira órfão).
    combat = dict(state.get("combat") or {})
    if combat.get("active"):
        return _combat_gate(state, world, combat)

    system_instruction = f"""
    Roteador de RPG. Classifique a intenção da ÚLTIMA mensagem do jogador.
    
    Local Atual: {loc}
    
    REGRAS:
    - COMBAT: Jogador ataca, saca armas ou reage a uma ameaça narrada. IMPORTANTE: Identifique o 'target' (inimigo).
    - NPC: Conversa social, diplomacia.
    - LOOT: "Vasculhar corpo", "Pegar item", "Abrir baú" (TREASURE) ou "Comprar/Vender/Criar" (SHOP/CRAFT).
    - STORY: Movimentação, exploração, observar cenário.
    """

    llm = get_llm(temperature=0.0, tier=ModelTier.CLASSIFY)

    try:
        router_llm = llm.with_structured_output(RouterDecision)
        decision = router_llm.invoke([SystemMessage(content=system_instruction)] + messages[-3:])
    except Exception as e:
        print(f"⚠️ Router Error: {e}")
        return {"next": RouteType.STORY.value}

    # Sem API key (FallbackLLM) o invoke devolve um AIMessage, não um
    # RouterDecision. Nesse caso seguimos para o storyteller (modo degradado).
    if not isinstance(decision, RouterDecision):
        return {"next": RouteType.STORY.value}

    # RouteType.NONE ("nenhuma intenção clara": input sem ação, lixo ou injeção)
    # NÃO é um nó do grafo — o mapping condicional de main.py só conhece
    # storyteller/combat/npc/loot/END. O LLM real ESCOLHE NONE para a entrada do
    # troll (emoji, SQL, "ignore as instruções") e o router devolvia next="none"
    # → KeyError('none') no grafo. O MockLLM nunca escolhe NONE, então o bug só
    # aparecia no LLM real (achado do playtest da Fase 5). Normaliza para STORY:
    # o narrador descreve o ambiente em vez de derrubar o turno.
    if decision.route == RouteType.NONE:
        decision.route = RouteType.STORY

    print(f"🚦 [ROUTER] {decision.route.value} -> Alvo: {decision.target}")

    response_payload = {
        "next": decision.route.value,
        "world": world,
        # LangGraph preserva o valor anterior quando a chave falta. Limpar os
        # campos não aplicáveis impede um alvo antigo de vazar para outra rota.
        "combat_target": None,
        "active_npc_name": None,
        "loot_source": None,
    }

    if decision.route == RouteType.LOOT:
        response_payload["loot_source"] = decision.loot_context or "TREASURE"

    # GATILHO DE NPC:
    # O ator de NPC exige 'active_npc_name'. Sem isso ele responde "Ninguém responde".
    # Tentamos casar o alvo identificado com um NPC já presente na cena.
    if decision.route == RouteType.NPC:
        from services import npc_layers

        chosen = None
        valid_npc_names = [
            normalized
            for npc_name in npc_layers.npcs_in_scene(state)
            if (normalized := optional_entity_ref(npc_name)) is not None
        ]
        if decision.target:
            tgt = decision.target.lower()
            for npc_name in valid_npc_names:
                if tgt in npc_name.lower() or npc_name.lower() in tgt:
                    chosen = npc_name
                    break
        # Fallback: se só há um NPC na cena, fala com ele.
        if not chosen and len(valid_npc_names) == 1:
            chosen = valid_npc_names[0]
        if not chosen and decision.target:
            chosen = decision.target  # deixa o ator tentar carregar do DB
        response_payload["active_npc_name"] = chosen

    # GATILHO DE COMBATE:
    # Se for combate, adicionamos uma flag no histórico (temporária) para o Combat Agent saber que é o turno 1
    if decision.route == RouteType.COMBAT:
        target = decision.target or "Inimigos"
        response_payload["combat_target"] = target
        if "messages" not in response_payload: response_payload["messages"] = []
        response_payload["messages"].append(
            SystemMessage(content=f"SYSTEM: COMBAT START. TARGET_HINT: {target}")
        )

    return response_payload
