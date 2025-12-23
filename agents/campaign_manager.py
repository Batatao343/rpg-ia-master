from typing import List
from pydantic import BaseModel, Field
from langchain_core.messages import SystemMessage

from llm_setup import get_llm
from state import GameState


class PlanStep(BaseModel):
    title: str = Field(description="Nome curto do passo narrativo")
    beat_type: str = Field(description="Tipo do passo: exploracao, social, combate, investigacao, clímax")
    goal: str = Field(description="Objetivo imediato a ser alcançado pelo grupo")
    complications: str = Field(description="Obstáculos ou riscos esperados")
    success_hint: str = Field(description="Como saber que este passo foi concluído")


class CampaignPlanDraft(BaseModel):
    location: str
    premise: str
    intended_climax: str
    beats: List[PlanStep]


def _hydrate_plan(draft: CampaignPlanDraft, turn_count: int) -> dict:
    beats = []
    for beat in draft.beats:
        beats.append(
            {
                "title": beat.title,
                "type": beat.beat_type,
                "goal": beat.goal,
                "complications": beat.complications,
                "success_hint": beat.success_hint,
                "status": "pending",
            }
        )
    if not beats:
        beats.append(
            {
                "title": "Enquadrar a cena",
                "type": "exploracao",
                "goal": "Descrever o local e oferecer escolhas iniciais",
                "complications": "curiosidade do grupo",
                "success_hint": "Jogador toma uma decisão clara",
                "status": "pending",
            }
        )

    return {
        "location": draft.location,
        "premise": draft.premise,
        "intended_climax": draft.intended_climax,
        "beats": beats,
        "current_step": 0,
        "last_planned_turn": turn_count,
        "needs_replan": False,
        "status": "active",
    }


def _fallback_plan(state: GameState) -> dict:
    loc = state.get("world", {}).get("current_location", "local misterioso")
    turn = state.get("world", {}).get("turn_count", 0)
    return {
        "location": loc,
        "premise": "Criar um arco rápido de descoberta e confronto.",
        "intended_climax": "Revelar um segredo e enfrentar seu guardião.",
        "beats": [
            {
                "title": "Mapa do terreno",
                "type": "exploracao",
                "goal": "Apresentar pontos de interesse do local",
                "complications": "neblina e ecos estranhos",
                "success_hint": "Jogador identifica um alvo para seguir",
                "status": "pending",
            },
            {
                "title": "Contato social",
                "type": "social",
                "goal": "Permitir diálogo com um guia ou informante",
                "complications": "segredos e meias verdades",
                "success_hint": "Jogador obtém pista clara",
                "status": "pending",
            },
            {
                "title": "Clímax",
                "type": "climax",
                "goal": "Enfrentar o guardião ou obstáculo final",
                "complications": "risco de combate",
                "success_hint": "Conflito resolvido ou acordo firmado",
                "status": "pending",
            },
        ],
        "current_step": 0,
        "last_planned_turn": turn,
        "needs_replan": False,
        "status": "active",
    }


def campaign_manager_node(state: GameState):
    turn_count = state.get("world", {}).get("turn_count", 0)
    loc = state.get("world", {}).get("current_location", "local desconhecido")
    last_messages = state.get("messages", [])
    recent_summary = " \n".join(m.content for m in last_messages[-3:] if hasattr(m, "content"))

    llm = get_llm(temperature=0.2)

    if getattr(llm, "is_fallback", False):
        plan = _fallback_plan(state)
        state["campaign_plan"] = plan
        state["active_plan_step"] = plan["beats"][plan["current_step"]]
        return {"campaign_plan": plan, "active_plan_step": state["active_plan_step"]}

    sys = SystemMessage(
        content=f"""
        <role>Planejador de campanha</role>
        <contexto>
        Local atual: {loc}
        Turno: {turn_count}
        Resumo recente: {recent_summary}
        Objetivo: Montar um arco com início, meio e clímax em até 5 passos curtos.
        </contexto>

        GERE UM PLANO ESTRUTURADO:
        - 'beats' deve ter de 3 a 5 passos encadeados.
        - Inclua pelo menos um passo social/investigativo e outro de risco (combate, armadilha ou dilema).
        - O clímax precisa ter um desfecho verificável.
        - Seja específico sobre objetivos e sinais de conclusão de cada passo.
        """
    )

    try:
        planner = llm.with_structured_output(CampaignPlanDraft)
        draft = planner.invoke([sys])
        plan = _hydrate_plan(draft, turn_count)
    except Exception as exc:  # pragma: no cover - fallback seguro
        print(f"[CAMPAIGN MANAGER ERROR] {exc}")
        plan = _fallback_plan(state)

    state["campaign_plan"] = plan
    state["active_plan_step"] = plan["beats"][plan["current_step"]]
    return {"campaign_plan": plan, "active_plan_step": state["active_plan_step"]}
