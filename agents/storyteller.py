"""Narration agent that advances the story and campaign plan."""
from typing import Dict, List
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
from pydantic import BaseModel, Field

from agents.npc import generate_new_npc
from agents.ruler_completo import resolve_action
from llm_setup import get_llm
from rag import query_rag
from state import GameState
from world_utils import (
    apply_rest,
    apply_travel,
    clock_label,
    ensure_world,
    find_travel_destination,
    is_rest,
)

class StoryUpdate(BaseModel):
    narrative: str = Field(description="O texto narrativo da resposta.")
    introduced_npcs: List[str] = Field(default_factory=list, description="Lista de nomes de NOVOS personagens.")
    beat_completed: bool = Field(
        default=False,
        description=(
            "True SOMENTE se a ação deste turno cumpriu de forma clara o Objetivo Atual "
            "da cena (o beat ativo). Caso contrário False. Não marque True por progresso vago."
        ),
    )

def _with_new_npc(npcs: Dict[str, Dict], new_name: str, loc: str, narrative_text: str) -> Dict[str, Dict]:
    existing_lower = {name.lower(): name for name in npcs.keys()}
    if new_name.lower() in existing_lower: return npcs
    tpl = generate_new_npc(new_name, context=f"Local: {loc}. Cena: {narrative_text}")
    if not tpl: return npcs
    new_npcs = dict(npcs)
    new_npcs[new_name] = {
        "name": tpl["name"], "role": tpl["role"], "persona": tpl["persona"],
        "location": loc, "relationship": tpl.get("initial_relationship", 5),
        "memory": [], "last_interaction": "",
        "attributes": tpl.get("attributes", {}), "combat_stats": tpl.get("combat_stats", {})
    }
    return new_npcs

def storyteller_node(state: GameState):
    messages = state.get("messages", [])
    if not messages: return {"messages": [AIMessage(content="Comece a história.")]}
    
    last_user_input = messages[-1].content if isinstance(messages[-1], HumanMessage) else ""
    world = ensure_world(state.get("world", {}))

    # --- Fase 0: viagem / descanso / juízo de ação (determinístico + Ruler) ---
    travel_note = rest_note = ruling_note = ""
    rested_player = None
    dest = find_travel_destination(world, last_user_input) if last_user_input else None
    if dest:
        world = apply_travel(world, dest)
        travel_note = (
            f"O jogador VIAJOU para {dest['name']}. "
            f"Contexto do local: {dest.get('lore_seed', '')} Descreva a chegada e o que ele vê agora."
        )
    elif last_user_input and is_rest(last_user_input):
        rested_player, world = apply_rest(dict(state.get("player", {})), world)
        rest_note = (
            f"O jogador DESCANSOU. O tempo avançou para {clock_label(world)} e ele recuperou parte das forças. "
            "Narre a passagem do tempo e o estado do mundo ao acordar."
        )
    elif last_user_input:
        try:
            ruling = resolve_action(state.get("player", {}), last_user_input)
            if isinstance(ruling, dict):
                allowed = ruling.get("is_allowed", True)
                ruling_note = (
                    f"[JUÍZO DA AÇÃO] permitido={allowed} | "
                    f"efeito={ruling.get('mechanical_effect', '')} | {ruling.get('flavor_text', '')}. "
                    "Respeite este juízo: se permitido=False, o personagem FALHA de forma plausível."
                )
        except Exception:
            ruling_note = ""

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
    eventos_turno = "\n".join(n for n in (travel_note, rest_note, ruling_note) if n) or "Nenhum evento especial."

    sys = SystemMessage(content=f"""
    <PERSONA>
    Você é o Narrador (Mestre) de um RPG.
    Local Atual: {loc}.
    Momento: {clock_label(world)}.
    NPCs na cena: {existing_npcs}.
    Objetivo Atual: {active_step}
    </PERSONA>

    <EVENTOS_DESTE_TURNO>
    {eventos_turno}
    </EVENTOS_DESTE_TURNO>

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

        # --- Avanço de beat: o narrador sinaliza quando o objetivo da cena foi cumprido ---
        needs_replan = state.get("needs_replan", False)
        updated_plan = campaign_plan
        beat_done = bool(getattr(update, "beat_completed", False))
        if campaign_plan and beats and beat_done and current_step < len(beats):
            beats[current_step] = {**beats[current_step], "status": "done"}
            new_step = current_step + 1
            updated_plan = {**campaign_plan, "beats": beats, "current_step": new_step}
            # Esgotou os beats → próximo turno o campaign_manager replaneja (vê _should_replan).
            if new_step >= len(beats):
                needs_replan = True

        npcs = state.get("npcs", {})
        new_npcs = npcs
        for new_name in update.introduced_npcs:
            new_npcs = _with_new_npc(new_npcs, new_name, loc, narrative_text)

        updates = {
            "messages": [AIMessage(content=narrative_text)],
            "npcs": new_npcs,
            "world": world,
            "campaign_plan": updated_plan,
            "needs_replan": needs_replan,
        }
        if rested_player is not None:
            updates["player"] = rested_player
        return updates

    except Exception as e:
        print(f"[STORYTELLER ERROR] {e}")
        return {"messages": [AIMessage(content="O destino é incerto... (Erro AI).")]}