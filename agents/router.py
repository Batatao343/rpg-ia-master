from typing import Literal, Optional, TypedDict
from langchain_core.messages import SystemMessage, AIMessage
from langgraph.graph import END

from llm_setup import get_llm
from state import GameState


class RouteDecision(TypedDict):
    destination: Literal["storyteller", "combat_agent", "rules_agent", "npc_actor"]
    npc_name: Optional[str]
    reasoning: str


def _needs_campaign_plan(state: GameState) -> bool:
    plan = state.get("campaign_plan")
    if not plan:
        return True
    turn = state.get("world", {}).get("turn_count", 0)
    last_plan_turn = plan.get("last_planned_turn", -10)
    timed_out = turn - last_plan_turn >= 10
    finished = plan.get("status") == "completed"
    blocked = plan.get("needs_replan")
    return timed_out or finished or blocked


def _get_active_plan_step(state: GameState):
    plan = state.get("campaign_plan")
    if not plan:
        return None
    beats = plan.get("beats", [])
    idx = plan.get("current_step", 0)
    if idx < len(beats):
        return beats[idx]
    return beats[-1] if beats else None


def dm_router_node(state: GameState):
    if _needs_campaign_plan(state):
        return {"next": "campaign_manager"}

    active_step = _get_active_plan_step(state)
    if active_step:
        state["active_plan_step"] = active_step

    messages = state["messages"]
    if not messages:
        return {"next": "storyteller", "active_plan_step": active_step}

    if isinstance(messages[-1], AIMessage) and not messages[-1].tool_calls:
        return {"next": END, "active_plan_step": active_step}

    loc = state['world']['current_location']
    visible_npcs = [
        n for n, d in state.get('npcs', {}).items()
        if d['location'] == loc or d['location'] == 'Party'
    ]

    llm = get_llm(temperature=0.1)

    sys = SystemMessage(content=f"""
    <role>Supervisor de Fluxo RPG.</role>
    <context>
    Local Atual: {loc}
    NPCs Visíveis/Existentes: {visible_npcs}
    Plano Atual: {active_step}
    </context>
    <rules>
    1. INTERAÇÃO SOCIAL ('npc_actor'):
       - O jogador SÓ pode falar com NPCs listados em 'NPCs Visíveis'.
       - Se ele tentar falar com alguém que NÃO está na lista (ex: "Falo com o Rei" e o Rei não está lá), envie para 'storyteller'.

    2. COMBATE ('combat_agent'):
       - Ataques, agressão física ou início de hostilidades.

    3. REGRAS/PERÍCIA ('rules_agent'):
       - Ações físicas (escalar, esconder), uso de itens ou magia utilitária.

    4. NARRATIVA ('storyteller'):
       - Exploração, perguntas sobre o ambiente, falar sozinho ou tentar falar com NPCs inexistentes.
    </rules>
    """)

    try:
        router = llm.with_structured_output(RouteDecision)
        decision = router.invoke([sys] + messages)

        dest = decision['destination']
        target = decision['npc_name']

        if dest == 'npc_actor' and target:
            visible_lower = [n.lower() for n in visible_npcs]

            if target.lower() not in visible_lower:
                return {"next": "storyteller", "active_plan_step": active_step}

            return {"next": "npc_actor", "active_npc_name": target, "active_plan_step": active_step}

        return {"next": dest, "active_plan_step": active_step}

    except Exception:
        return {"next": "storyteller", "active_plan_step": active_step}
