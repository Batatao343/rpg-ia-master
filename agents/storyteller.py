from typing import List
from pydantic import BaseModel, Field
from langchain_core.messages import SystemMessage, HumanMessage, AIMessage

from agents.npc import generate_new_npc
from llm_setup import get_llm
from rag import query_rag
from state import GameState


class StoryUpdate(BaseModel):
    narrative: str = Field(description="O texto narrativo da resposta.")
    introduced_npcs: List[str] = Field(default_factory=list, description="Lista de nomes de NOVOS personagens que entraram na cena nesta rodada.")
    plan_step_completed: bool = Field(default=False, description="Marcar se o passo atual do plano foi concluído")
    plan_step_blocked: bool = Field(default=False, description="Marcar se o passo atual travou e precisa de replanejamento")
    plan_note: str = Field(default="", description="Observação resumida sobre o progresso do plano")


def _build_plan_context(state: GameState):
    plan = state.get("campaign_plan")
    active_step = state.get("active_plan_step") or (plan.get("beats", [None])[plan.get("current_step", 0)] if plan else None)
    if not plan or not active_step:
        return None, None
    summary = (
        f"Local alvo: {plan.get('location')} | Clímax: {plan.get('intended_climax')}\n"
        f"Passo atual: {active_step.get('title')} ({active_step.get('type')})\n"
        f"Objetivo: {active_step.get('goal')} | Obstáculos: {active_step.get('complications')}\n"
        f"Sinal de sucesso: {active_step.get('success_hint')}"
    )
    return plan, summary


def _update_plan_progress(state: GameState, update: StoryUpdate):
    plan = state.get("campaign_plan")
    if not plan:
        return

    beats = plan.get("beats", [])
    idx = plan.get("current_step", 0)
    if idx < len(beats):
        active_step = beats[idx]
        state["active_plan_step"] = active_step
    else:
        state["active_plan_step"] = beats[-1] if beats else None
        return

    if update.plan_step_completed:
        active_step["status"] = "completed"
        plan["current_step"] = min(idx + 1, len(beats))
        if plan["current_step"] >= len(beats):
            plan["status"] = "completed"
            plan["needs_replan"] = True
        else:
            state["active_plan_step"] = beats[plan["current_step"]]

    if update.plan_step_blocked:
        plan["needs_replan"] = True
        plan["status"] = "blocked"


def storyteller_node(state: GameState):
    messages = state["messages"]
    if not messages:
        return {"messages": [AIMessage(content="Conte sua ação inicial para começarmos a história.")]}
    if not isinstance(messages[-1], HumanMessage):
        return {"messages": [AIMessage(content="Preciso da sua próxima ação para narrar o que acontece em seguida.")]}

    last_user_input = messages[-1].content
    loc = state['world']['current_location']
    existing_npcs = list(state.get('npcs', {}).keys())

    lore_context = query_rag(f"{loc} {last_user_input}", index_name="lore")
    if not lore_context:
        lore_context = "Nenhuma lore específica encontrada. Use criatividade Dark Fantasy."

    plan, plan_summary = _build_plan_context(state)

    llm = get_llm(temperature=0.7)

    if getattr(llm, "is_fallback", False):
        return {"messages": [llm.invoke(None)]}

    plan_instructions = ""
    if plan_summary:
        plan_instructions = (
            "\nALINHE A NARRATIVA AO PLANO:\n"
            f"{plan_summary}\n"
            "- Incentive ações que aproximem do objetivo atual.\n"
            "- Encaminhe para o próximo passo quando o sucesso ficar claro.\n"
        )

    sys = SystemMessage(content=f"""
    Você é o Narrador (Mestre) de um RPG.
    Local Atual: {loc}.
    NPCs já na cena: {existing_npcs}.
    {plan_instructions}

    === CONTEXTO DO MUNDO (LORE) ===
    {lore_context}
    ================================

    INSTRUÇÕES DE ESTILO:
    - Responda em 2 a 3 parágrafos curtos, claros e objetivos.
    - Termine SEMPRE oferecendo 1 a 3 opções numeradas OU uma pergunta direta que convide ação imediata.
    - Destaque ganchos relevantes (NPCs, objetos, saídas) para orientar a próxima decisão.
    - Evite cliffhangers longos ou respostas prolixas.

    REGRAS:
    1. Narre a cena com imersão, INTEGRANDO a Lore consultada acima.
       (Ex: Se a lore diz que as ruínas brilham verde, descreva o brilho verde).
    2. Se o jogador tentou falar com alguém que não existe, narre que a pessoa não está lá.
    3. Se a SUA narrativa introduzir um novo personagem (ex: "Um guarda entra"), adicione o nome em 'introduced_npcs'.
    4. NÃO adicione NPCs inventados pelo jogador na lista.
    5. Se o passo do plano estiver bloqueado ou concluído, sinalize usando os campos de saída apropriados.
    """)

    try:
        story_engine = llm.with_structured_output(StoryUpdate)
        update = story_engine.invoke([sys] + messages)

        narrative_text = update.narrative

        if update.introduced_npcs:
            if 'npcs' not in state:
                state['npcs'] = {}

            for new_name in update.introduced_npcs:
                if new_name not in state['npcs']:
                    print(f"✨ [STORYTELLER] Invocando novo NPC: {new_name}")

                    tpl = generate_new_npc(new_name, context=f"Local: {loc}. Cena: {narrative_text}")

                    if tpl:
                        state['npcs'][new_name] = {
                            "name": tpl['name'],
                            "role": tpl['role'],
                            "persona": tpl['persona'],
                            "location": loc,
                            "relationship": tpl['initial_relationship'],
                            "memory": [],
                            "last_interaction": "",
                        }

        _update_plan_progress(state, update)

        if plan and plan.get("needs_replan"):
            state["next"] = "campaign_manager"

        return {
            "messages": [AIMessage(content=narrative_text)],
            "npcs": state.get('npcs', {}),
            "campaign_plan": state.get("campaign_plan"),
            "active_plan_step": state.get("active_plan_step"),
            "next": state.get("next"),
        }

    except Exception as e:  # pragma: no cover - segurança
        print(f"[STORYTELLER ERROR] {e}")
        return {"messages": [AIMessage(content="O vento sopra... (Erro técnico na narrativa).")]} 
