"""Narration agent that advances the story and campaign plan."""

from typing import Dict, List

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
from pydantic import BaseModel, Field

from agents.archivist import archive_narrative
from agents.npc import generate_new_npc
from llm_setup import get_llm
from rag import query_rag
from state import GameState


class StoryUpdate(BaseModel):
    """Structured storyteller response containing narration and spawned NPCs."""

    narrative: str = Field(description="O texto narrativo da resposta.")
    introduced_npcs: List[str] = Field(
        default_factory=list, description="Lista de nomes de NOVOS personagens que entraram na cena nesta rodada."
    )


def _with_new_npc(npcs: Dict[str, Dict], new_name: str, loc: str, narrative_text: str) -> Dict[str, Dict]:
    """Return a new NPC mapping with a generated NPC added if possible."""

    existing_lower = {name.lower(): name for name in npcs.keys()}
    if new_name.lower() in existing_lower:
        return npcs

    tpl = generate_new_npc(new_name, context=f"Local: {loc}. Cena: {narrative_text}")
    if not tpl:
        return npcs

    new_npcs = dict(npcs)
    new_npcs[new_name] = {
        "name": tpl["name"],
        "role": tpl["role"],
        "persona": tpl["persona"],
        "location": loc,
        "relationship": tpl["initial_relationship"],
        "memory": [],
        "last_interaction": "",
    }
    return new_npcs


def storyteller_node(state: GameState):
    """Narrate the next scene beat, updating campaign progress and NPCs immutably."""

    messages = state.get("messages", [])
    if not messages:
        return {"messages": [AIMessage(content="Conte sua ação inicial para começarmos a história.")]}
    if not isinstance(messages[-1], HumanMessage):
        return {"messages": [AIMessage(content="Preciso da sua próxima ação para narrar o que acontece em seguida.")]}

    last_user_input = messages[-1].content
    world = dict(state.get("world", {}))
    loc = world.get("current_location", "")
    existing_npcs = list(state.get("npcs", {}).keys())

    try:
        lore_context = query_rag(f"{loc} {last_user_input}", index_name="lore")
    except Exception as exc:  # noqa: BLE001
        print(f"[STORYTELLER RAG ERROR] {exc}")
        lore_context = ""
    if not lore_context:
        lore_context = "Nenhuma lore específica encontrada. Use criatividade Dark Fantasy."

    campaign_plan = state.get("campaign_plan") or {}
    beats = [dict(beat) for beat in campaign_plan.get("beats", [])]
    current_step = campaign_plan.get("current_step", 0)
    active_step = None
    plan_finished = False
    if current_step < len(beats):
        active_step = beats[current_step].get("description")
    elif campaign_plan.get("climax"):
        active_step = campaign_plan.get("climax")
        plan_finished = True
    else:
        active_step = "Descreva o próximo acontecimento coerente com a cena."

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

        updated_plan = None
        needs_replan = state.get("needs_replan", False)
        if campaign_plan:
            updated_plan = dict(campaign_plan)
            updated_beats = beats
            if current_step < len(updated_beats):
                updated_beats[current_step]["status"] = "done"
                updated_plan["current_step"] = current_step + 1
            else:
                plan_finished = True
            updated_plan["beats"] = updated_beats
        if plan_finished:
            needs_replan = True

        npcs = state.get("npcs", {})
        new_npcs = npcs
        for new_name in update.introduced_npcs:
            new_npcs = _with_new_npc(new_npcs, new_name, loc, narrative_text)

        archive_narrative(narrative_text)

        return {
            "messages": [AIMessage(content=narrative_text)],
            "npcs": new_npcs,
            "world": world,
            "campaign_plan": updated_plan if updated_plan else campaign_plan if campaign_plan else None,
            "needs_replan": needs_replan,
        }

    except Exception as e:  # noqa: BLE001
        print(f"[STORYTELLER ERROR] {e}")
        fallback_llm = get_llm(temperature=0.7)
        fallback_response = fallback_llm.invoke([sys] + messages)
        if isinstance(fallback_response, str):
            fallback_text = fallback_response
        else:
            fallback_text = getattr(fallback_response, "content", "O vento sopra... (Erro técnico na narrativa).")

        needs_replan = state.get("needs_replan", False) or plan_finished

        return {
            "messages": [AIMessage(content=fallback_text)],
            "world": world,
            "npcs": state.get("npcs", {}),
            "campaign_plan": campaign_plan if campaign_plan else None,
            "needs_replan": needs_replan,
        }
