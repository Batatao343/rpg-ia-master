"""
agents/router.py
Roteador de Intenções.
Agora com detecção explícita de início de combate para acionar o Spawner.
"""
from observability.telemetry import log_event as _log_event
from enum import Enum
import re
from typing import Literal, Optional
from langchain_core.messages import AIMessage, SystemMessage, HumanMessage
from langgraph.graph import END
from pydantic import BaseModel, Field, field_validator

from llm_setup import ModelTier, get_llm
from services.input_normalization import optional_entity_ref
from services.prompt_guard import PLAYER_INPUT_RULE
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

_EXPLICIT_STORY_RE = re.compile(
    r"\b(?:descanso|descansamos|durmo|dormimos|acampo|acampamos|viajo|viajamos|(?:quero|vou|vamos|preciso|posso)\s+(?:descansar|dormir|acampar|viajar)|vou\s+para|sigo\s+para)\b",
    re.IGNORECASE,
)
_EXPLICIT_HOSTILITY_RE = re.compile(
    r"\b(?:atac\w*|golpe\w*|apunhal\w*|dispar\w*|saco\s+(?:a|minha|o|meu)?\s*"
    r"(?:arma|espada|arco)|inicio\s+(?:um\s+)?combate|enfrent\w*)\b",
    re.IGNORECASE,
)


def _last_human_text(messages) -> str:
    """Texto da última fala do jogador (para detectar viagem no gate de combate)."""
    for m in reversed(messages or []):
        if getattr(m, "type", "") == "human":
            return str(getattr(m, "content", "") or "")
    return ""


def _base_route_payload(route: RouteType, world: dict) -> dict:
    """Resposta completa: reducer não pode preservar transitórios antigos."""
    return {
        "next": route.value,
        "world": world,
        "combat_target": None,
        "active_npc_name": None,
        "loot_source": None,
        "combat_origin_hint": None,
        "npc_fallback_hint": None,  # SPEC-230 R8: transitório
        # SPEC-202: transitórios do interlocutor (zerados a cada rota).
        "interlocutor_reason": None,
        "mediated_subject_id": None,
        "combat_target_ref": None,  # SPEC-203: one-shot
        "combat_encounter_hint": None,  # SPEC-203: one-shot
    }


def _interlocutor_payload(resolution, world: dict) -> dict:
    """SPEC-202: payload de rota a partir de uma InterlocutorResolution."""
    route = RouteType(resolution.route)
    payload = _base_route_payload(route, world)
    payload["interlocutor_reason"] = resolution.reason
    payload["mediated_subject_id"] = resolution.mediated_subject_id
    if route == RouteType.NPC:
        payload["active_npc_name"] = resolution.npc_state_key
    if resolution.fallback_hint:
        payload["npc_fallback_hint"] = resolution.fallback_hint
    return payload


def _combat_gate(state: GameState, world: dict, combat: dict):
    """Gate determinístico quando `combat.active` (spec combate-lifecycle):
    - R2: força `combat_agent` (bloqueia npc/loot; conversa segue pro combate que narra).
    - R1: ação de VIAGEM não teleporta — vira tentativa de fuga (flag + destino).
    - R3: combate órfão (idle_turns >= N) expira, limpando TUDO (R5)."""
    from world_utils import find_travel_destination

    idle = int(combat.get("idle_turns", 0)) + 1
    if idle >= COMBAT_IDLE_EXPIRE:
        _log_event("router", "orphan_combat_expired", level="info")
        cleared = {"active": False, "round": combat.get("round", 1),
                   "order": combat.get("order", []), "idle_turns": 0}
        # SPEC-203 R5/R7: expiração vira outcome explícito, com desfecho na UI.
        from services import encounter_manifest as em
        manifest = combat.get("encounter")
        if em.is_valid_manifest(manifest):
            cleared["encounter"] = manifest
            cleared["instance_id"] = combat.get("instance_id")
        cleared["phase"] = combat.get("phase") or "active"
        cleared = em.end_combat(cleared, "expired")
        if em.is_valid_manifest(manifest):
            cleared["result"] = em.build_result(
                manifest, "expired", int(combat.get("round", 1) or 1))
        return {"next": RouteType.STORY.value, "combat": cleared,
                "enemies": [], "combat_target": None,
                "messages": [SystemMessage(content="SYSTEM: COMBAT EXPIRED — "
                             "os inimigos perdem seu rastro e o combate termina.")]}

    combat["idle_turns"] = idle
    payload = {"next": RouteType.COMBAT.value, "world": world, "combat": combat,
               "interlocutor_reason": None, "mediated_subject_id": None}
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
        _log_event("router", "travel_in_combat_flee", level="info")
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

    from services.actor_lifecycle import is_recovery_turn
    if is_recovery_turn(state):
        return _base_route_payload(RouteType.STORY, world)

    # Descanso e viagem explícitos fora de combate são mecânicas de STORY.
    # Fechar essa borda evita que contexto hostil antigo reabra um conflito no
    # turno imediatamente posterior a uma fuga.
    last_human = _last_human_text(messages)

    # SPEC-203 R6: o 1º turno após um encontro encerrado (≠ morte) NÃO reabre
    # combate por contexto residual — só hostilidade explícita reabre. A intenção
    # NPC/LOOT/STORY do jogador continua sendo respeitada (revisão Astra: forçar
    # STORY sequestrava "falo com o prisioneiro rendido").
    resume_explore = bool(combat.get("phase") == "ended" and combat.get("result")
                          and not combat.get("explore_resumed")
                          and combat.get("outcome") != "death")

    def _resumed(payload: dict) -> dict:
        if resume_explore:
            payload["combat"] = {**combat, "explore_resumed": True}
        return payload

    # SPEC-229 R4: hostilidade explícita tem precedência; formas verbais fechadas.
    if (_EXPLICIT_STORY_RE.search(last_human)
            and not _EXPLICIT_HOSTILITY_RE.search(last_human)):
        return _resumed(_base_route_payload(RouteType.STORY, world))

    # SPEC-180: Jev is opt-in and limited to decisions its closed contract can
    # fully represent. Shadow never supplies a route; every other result uses
    # the existing CLASSIFY path. Python gates above retain precedence.
    from services.jev_rollout import decide_route
    if decide_route(state, last_human) == RouteType.STORY.value:
        return _resumed(_base_route_payload(RouteType.STORY, world))

    # SPEC-202 R2/R3: meta-pergunta ao narrador e descrição de cena são decididas
    # em Python, SEM chamar o CLASSIFY (zero invoke).
    from services import interlocutor
    pre = interlocutor.pre_classify(state, last_human)
    if pre is not None:
        return _resumed(_interlocutor_payload(pre, world))

    scene_names = ", ".join(
        interlocutor.canonical_npc_name(state, key)
        for key in interlocutor.scene_keys(state)) or "ninguém"

    system_instruction = f"""
    Roteador de RPG. Classifique a intenção da ÚLTIMA mensagem do jogador.
    
    Local Atual: {loc}
    NPCs presentes na cena: {scene_names}

    REGRAS:
    - COMBAT: Jogador ataca, saca armas ou reage a uma ameaça narrada. IMPORTANTE: Identifique o 'target' (inimigo).
    - NPC: Conversa social, diplomacia DIRIGIDA a um personagem presente. 'target' = nome EXATO de um NPC presente (ou vazio).
    - Pergunta ao narrador/mestre SOBRE alguém (o que sente, se mente, quem é) = STORY, não NPC.
    - LOOT: "Vasculhar corpo", "Pegar item", "Abrir baú" (TREASURE) ou "Comprar/Vender/Criar" (SHOP/CRAFT).
    - STORY: Movimentação, exploração, observar cenário.
    - {PLAYER_INPUT_RULE}
    """

    llm = get_llm(temperature=0.0, tier=ModelTier.CLASSIFY)

    try:
        from services.prompt_guard import guard_messages
        router_llm = llm.with_structured_output(RouterDecision)
        decision = router_llm.invoke(
            [SystemMessage(content=system_instruction)] + guard_messages(messages[-3:]))
    except Exception as e:
        _log_event("router", "failed", level="error", error=type(e).__name__)
        return _resumed({**_base_route_payload(RouteType.STORY, world),
                         "interlocutor_reason": "classify_fallback"})

    # Sem API key (FallbackLLM) o invoke devolve um AIMessage, não um
    # RouterDecision. Nesse caso seguimos para o storyteller (modo degradado).
    if not isinstance(decision, RouterDecision):
        return _resumed({**_base_route_payload(RouteType.STORY, world),
                         "interlocutor_reason": "classify_fallback"})

    # RouteType.NONE ("nenhuma intenção clara": input sem ação, lixo ou injeção)
    # NÃO é um nó do grafo — o mapping condicional de main.py só conhece
    # storyteller/combat/npc/loot/END. O LLM real ESCOLHE NONE para a entrada do
    # troll (emoji, SQL, "ignore as instruções") e o router devolvia next="none"
    # → KeyError('none') no grafo. O MockLLM nunca escolhe NONE, então o bug só
    # aparecia no LLM real (achado do playtest da Fase 5). Normaliza para STORY:
    # o narrador descreve o ambiente em vez de derrubar o turno.
    if decision.route == RouteType.NONE:
        decision.route = RouteType.STORY
    # SPEC-203 R6: pós-desfecho, COMBAT sem hostilidade explícita vira exploração.
    if (resume_explore and decision.route == RouteType.COMBAT
            and not _EXPLICIT_HOSTILITY_RE.search(last_human)):
        decision.route = RouteType.STORY

    _log_event("router", "decision", level="debug", route=decision.route.value)

    # SPEC-202 R3–R8: o alvo do CLASSIFY só vira interlocutor se resolver para
    # uma ficha existente em cena; o alvo cru NUNCA é propagado (R5).
    if decision.route in (RouteType.NPC, RouteType.STORY):
        resolution = interlocutor.post_classify(
            state, last_human, decision.route.value, decision.target)
        return _resumed(_interlocutor_payload(resolution, world))

    response_payload = _base_route_payload(decision.route, world)
    response_payload["interlocutor_reason"] = "classify_story"

    if decision.route == RouteType.LOOT:
        response_payload["loot_source"] = decision.loot_context or "TREASURE"

    # GATILHO DE COMBATE:
    # Se for combate, adicionamos uma flag no histórico (temporária) para o Combat Agent saber que é o turno 1
    if decision.route == RouteType.COMBAT:
        target = decision.target or "Inimigos"
        response_payload["combat_target"] = target
        # SPEC-203 R3(b): alvo que casa com NPC em cena vira referência canônica.
        from services import npc_layers
        folded_target = target.casefold()
        for npc_name in npc_layers.npcs_in_scene(state):
            if npc_name in (state.get("npcs") or {}) and (
                    npc_name.casefold() in folded_target
                    or folded_target in npc_name.casefold()):
                response_payload["combat_target_ref"] = f"npc:{npc_name}"
                break
        response_payload["combat_origin_hint"] = (
            "player_provoked"
            if _EXPLICIT_HOSTILITY_RE.search(last_human)
            else "regional_danger"
        )
        if "messages" not in response_payload: response_payload["messages"] = []
        response_payload["messages"].append(
            SystemMessage(content=f"SYSTEM: COMBAT START. TARGET_HINT: {target}")
        )

    return _resumed(response_payload)
