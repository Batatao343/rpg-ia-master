"""Narration agent that advances the story and campaign plan."""
from typing import Dict, List
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
from pydantic import BaseModel, Field

from agents.npc import generate_new_npc
from llm_setup import get_llm
from rag import query_rag
from state import GameState

class StoryUpdate(BaseModel):
    narrative: str = Field(description="O texto narrativo da resposta.")
    introduced_npcs: List[str] = Field(default_factory=list, description="Lista de nomes de NOVOS personagens.")

def _with_new_npc(npcs: Dict[str, Dict], new_name: str, loc: str, narrative_text: str) -> Dict[str, Dict]:
    existing_lower = {name.lower(): name for name in npcs.keys()}
    if new_name.lower() in existing_lower: return npcs
    tpl = generate_new_npc(new_name, context=f"Local: {loc}. Cena: {narrative_text}")
    if not tpl: return npcs
    new_npcs = dict(npcs)
    new_npcs[new_name] = {
        "name": tpl["name"], "role": tpl["role"], "persona": tpl["persona"],
        "location": loc, "relationship": tpl["initial_relationship"],
        "memory": [], "last_interaction": "",
        "attributes": tpl.get("attributes", {}), "combat_stats": tpl.get("combat_stats", {})
    }
    return new_npcs

def storyteller_node(state: GameState):
    messages = state.get("messages", [])
    if not messages: return {"messages": [AIMessage(content="Comece a história.")]}
    
    last_user_input = messages[-1].content if isinstance(messages[-1], HumanMessage) else ""
    world = dict(state.get("world", {}))
    loc = world.get("current_location", "")
    existing_npcs = list(state.get("npcs", {}).keys())
    
    # --- Contexto Híbrido ---
    game_id = state.get("game_id")
    narrative_summary = state.get("narrative_summary", "")
    
    try:
        # Busca Lore Global + Memória da Sessão
        lore_context = query_rag(f"{loc} {last_user_input}", index_name="lore", game_id=game_id)
    except Exception:
        lore_context = ""

    if not lore_context: lore_context = "Dark Fantasy Genérica."

    campaign_plan = state.get("campaign_plan") or {}
    beats = [dict(beat) for beat in campaign_plan.get("beats", [])]
    current_step = campaign_plan.get("current_step", 0)
    active_step = beats[current_step].get("description") if current_step < len(beats) else "Clímax ou Ação Livre."

    llm = get_llm(temperature=0.7)
    
    # PROMPT ATUALIZADO
    sys = SystemMessage(content=f"""
    <PERSONA>
    Você é o Narrador (Mestre) de um RPG.
    Local Atual: {loc}.
    NPCs na cena: {existing_npcs}.
    Objetivo Atual: {active_step}
    </PERSONA>

    <MEMORIA_RECENTE>
    Resumo dos fatos anteriores: {narrative_summary}
    </MEMORIA_RECENTE>

    <LORE_E_FATOS_PASSADOS>
    {lore_context}
    </LORE_E_FATOS_PASSADOS>

    <INSTRUÇÕES>
    - Responda em 2 a 3 parágrafos.
    - Termine com opções ou pergunta para ação.
    - Se introduzir NPC novo, adicione em 'introduced_npcs'.
    """)

    try:
        story_engine = llm.with_structured_output(StoryUpdate).with_retry(stop_after_attempt=3)
        update = story_engine.invoke([sys] + messages[-6:]) # Contexto reduzido

        narrative_text = update.narrative
        
        updated_plan = None
        needs_replan = state.get("needs_replan", False)
        if campaign_plan and current_step < len(beats):
             # Lógica simplificada de avanço de beat
             pass

        npcs = state.get("npcs", {})
        new_npcs = npcs
        for new_name in update.introduced_npcs:
            new_npcs = _with_new_npc(new_npcs, new_name, loc, narrative_text)

        return {
            "messages": [AIMessage(content=narrative_text)],
            "npcs": new_npcs,
            "world": world,
            "campaign_plan": campaign_plan,
            "needs_replan": needs_replan,
        }

    except Exception as e:
        print(f"[STORYTELLER ERROR] {e}")
        return {"messages": [AIMessage(content="O destino é incerto... (Erro AI).")]}