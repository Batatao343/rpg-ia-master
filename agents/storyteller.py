from typing import List
from pydantic import BaseModel, Field
from langchain_core.messages import SystemMessage, HumanMessage, AIMessage
from state import GameState
from llm_setup import ModelTier, get_llm

# Importa a função de criação (já integrada com RAG no npc.py)
from agents.npc import generate_new_npc

# --- INTEGRAÇÃO RAG ---
from rag import query_rag

# Schema de Saída
class StoryUpdate(BaseModel):
    narrative: str = Field(description="O texto narrativo da resposta.")
    introduced_npcs: List[str] = Field(default_factory=list, description="Lista de nomes de NOVOS personagens que entraram na cena nesta rodada.")


class QuestPlan(BaseModel):
    steps: List[str] = Field(min_length=3, max_length=3, description="Sequência de 3 batidas narrativas")


def storyteller_node(state: GameState):
    messages = state["messages"]
    if not messages:
        return {"messages": [AIMessage(content="Conte sua ação inicial para começarmos a história.")]}
    if not isinstance(messages[-1], HumanMessage):
        return {"messages": [AIMessage(content="Preciso da sua próxima ação para narrar o que acontece em seguida.")]}

    last_user_input = messages[-1].content
    loc = state['world']['current_location']
    existing_npcs = list(state.get('npcs', {}).keys())

    # 1. CONSULTA A LORE (RAG)
    lore_context = query_rag(f"{loc} {last_user_input}", index_name="lore")
    if not lore_context:
        lore_context = "Nenhuma lore específica encontrada. Use criatividade Dark Fantasy."

    world = state["world"]
    quest_plan = world.get("quest_plan", []) or []
    plan_origin = world.get("quest_plan_origin")
    location_changed = plan_origin is not None and plan_origin != loc

    if location_changed or not quest_plan:
        quest_plan = _generate_campaign_plan(loc, last_user_input, lore_context)
        world["quest_plan"] = quest_plan
        world["quest_plan_origin"] = loc

    active_step = quest_plan[0] if quest_plan else "Descreva o próximo acontecimento coerente com a cena."

    llm = get_llm(temperature=0.7)

    if getattr(llm, "is_fallback", False):
        return {"messages": [llm.invoke(None)]}

    sys = SystemMessage(content=f"""
    Você é o Narrador (Mestre) de um RPG.
    Local Atual: {loc}.
    NPCs já na cena: {existing_npcs}.
    Passo Atual do Plano de Campanha: {active_step}

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
    """)

    try:
        story_engine = llm.with_structured_output(StoryUpdate).with_retry(stop_after_attempt=3)
        update = story_engine.invoke([sys] + messages)

        narrative_text = update.narrative

        if world.get("quest_plan"):
            world["quest_plan"] = world["quest_plan"][1:]

        if update.introduced_npcs:
            if 'npcs' not in state:
                state['npcs'] = {}

            existing_lower = {name.lower(): name for name in state['npcs'].keys()}
            for new_name in update.introduced_npcs:
                if new_name.lower() in existing_lower:
                    continue
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

        return {
            "messages": [AIMessage(content=narrative_text)],
            "npcs": state.get('npcs', {}),
            "world": world,
        }

    except Exception as e:  # noqa: BLE001
        print(f"[STORYTELLER ERROR] {e}")
        fallback_llm = get_llm(temperature=0.7)
        fallback_response = fallback_llm.invoke([sys] + messages)
        if isinstance(fallback_response, str):
            fallback_text = fallback_response
        else:
            fallback_text = getattr(fallback_response, "content", "O vento sopra... (Erro técnico na narrativa).")

        return {
            "messages": [AIMessage(content=fallback_text)],
            "world": world,
            "npcs": state.get('npcs', {}),
        }


def _generate_campaign_plan(location: str, last_user_input: str, lore_context: str) -> List[str]:
    """Cria um arco de 3 passos para a cena atual usando o modelo SMART."""
    planner_llm = get_llm(temperature=0.3, tier=ModelTier.SMART)
    system_msg = SystemMessage(content=f"""
    You are the Campaign Director for a tabletop RPG session.
    Location: {location}
    Lore Context: {lore_context}

    Produce exactly 3 sequential plot beats that guide the scene from setup to climax.
    Keep each beat concise (max 20 words) and actionable for the storyteller.
    """)

    human_msg = HumanMessage(content=f"Player intent or recent action: {last_user_input}")

    try:
        planner = planner_llm.with_structured_output(QuestPlan)
        plan = planner.invoke([system_msg, human_msg])
        return plan.steps
    except Exception as exc:  # noqa: BLE001
        print(f"[STORYTELLER PLAN ERROR] {exc}")
        return [
            "Estabeleça o perigo imediato do local.",
            "Revele uma pista ou aliado improvável.",
            "Conduza a um confronto ou decisão dramática.",
        ]
