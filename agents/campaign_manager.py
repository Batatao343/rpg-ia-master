"""Campaign planning node used to keep multi-step story arcs coherent."""

from typing import List

from langchain_core.messages import HumanMessage, SystemMessage
from pydantic import BaseModel, Field, field_validator

from llm_setup import ModelTier, get_llm
from state import CampaignBeat, CampaignPlan, GameState

# --- INTEGRAÇÃO RAG ---
from rag import query_rag  # <--- Importação necessária
from services.chronicle import default_chapter_title, open_chapter
from services.context_builder import build_context_pack


class CampaignPlanModel(BaseModel):
    """Structured response format for the campaign planner LLM."""

    location: str = Field(description="Scene location the plan is for")
    beats: List[str] = Field(
        min_length=3, max_length=5,
        description="Ordered story beats leading to the climax — SEMPRE em português do Brasil (pt-BR), NUNCA em inglês",
    )
    climax: str = Field(description="The intended climactic moment — SEMPRE em português do Brasil (pt-BR)")
    arc_title: str = Field(
        default="",
        description=(
            "Short evocative arc title (3-6 words, PT-BR). "
            "KEEP the previous title if the story arc continues; "
            "change it ONLY when a truly new arc begins."
        ),
    )

    @field_validator("beats")
    @classmethod
    def validate_beats(cls, beats: List[str]) -> List[str]:
        """Trim whitespace and drop empty beats returned by the model."""
        return [b.strip() for b in beats if b.strip()]


# spec balanceamento-early-game (R4): replan periódico espaçado (era 10 — plot
# twists demais; needs_replan explícito continua imediato).
REPLAN_INTERVAL = 15


def _region_of(loc_ref: str):
    """Região de um local por id OU nome exibível; None se não está no mapa
    (ex.: local inventado pelo LLM)."""
    from gamedata import find_location_by_name, get_location
    loc = get_location(loc_ref) or find_location_by_name(loc_ref)
    return (loc or {}).get("region")


def _same_region(loc_id_a: str, loc_id_b: str) -> bool:
    """True se os dois locais RESOLVEM no mapa e são da mesma região.
    Irresolvível → True (não dá pra provar que a região mudou — não replaneja
    por viagem; o intervalo/beats cuidam do resto). Spec balanceamento R4."""
    ra, rb = _region_of(loc_id_a), _region_of(loc_id_b)
    if ra is None or rb is None:
        return True
    return ra == rb


def _should_replan(state: GameState) -> bool:
    """Determine if the campaign plan needs to be regenerated.

    R4 (spec balanceamento-early-game): viagem SÓ replaneja quando o ARCO muda
    de fato — região nova E (≥ 1 beat concluído OU arco sem beats). Mover-se
    entre sublocais/interiores do mesmo hub não joga fora o arco (era a causa
    dos "plot twists por viagem")."""

    world = state.get("world", {})
    plan = state.get("campaign_plan")
    turn_count = world.get("turn_count", 0)

    if state.get("needs_replan"):
        return True

    if not plan:
        return True

    beats = plan.get("beats") or []
    location_moved = plan.get("location") and plan["location"] != world.get("current_location")
    if location_moved and not _same_region(plan["location"], world.get("current_location", "")):
        beat_done = any(b.get("status") != "pending" for b in beats if isinstance(b, dict))
        orphan = not beats  # arco órfão de contexto: plano sem beat nenhum
        if beat_done or orphan:
            return True

    last_turn = plan.get("last_planned_turn", -REPLAN_INTERVAL)
    if turn_count - last_turn >= REPLAN_INTERVAL:
        return True

    current_step = plan.get("current_step", 0)
    finished = current_step >= len(beats)
    return finished


def _build_plan(state: GameState) -> CampaignPlan:
    """Generate a structured campaign plan for the current scene using RAG context."""

    world = state.get("world", {})
    messages = state.get("messages", [])
    current_loc = world.get("current_location", "Unknown")
    current_arc = (state.get("campaign_plan") or {}).get("arc_title", "")

    last_human = next((m for m in reversed(messages) if isinstance(m, HumanMessage)), None)
    last_intent = last_human.content if last_human else ""

    # --- 1. CONTEXTO (Fase 2.8: pack centraliza lore + estado atual do mundo) ---
    # purpose="planning" → o arquiteto pode ver edges hidden/secret (visão de mundo).
    search_query = f"{current_loc} {last_intent}"
    pack = build_context_pack(state, query=search_query, purpose="planning")
    lore_context = pack.lore_block or "No specific lore available for this location."
    world_state_context = pack.world_state_block

    # --- 2. CONFIGURAÇÃO DO LLM ---
    planner_llm = get_llm(temperature=0.4, tier=ModelTier.SMART) # Aumentei levemente a temp para criatividade
    
    system_msg = SystemMessage(
        content=(
            "<PERSONA>\n"
            "You are the Campaign Architect for a rich, immersive tabletop RPG.\n"
            
            "<CONTEXT>\n"
            f"Location: {current_loc}\n"
            f"Weather/Time: {world.get('weather', 'unknown')} / {world.get('time_of_day', 'unknown')}\n"
            
            f"{world_state_context}\n"
            "(Se o estado atual do mundo contradisser o lore, o estado atual VENCE.)\n"

            "<LORE_CONTEXT>\n"
            f"{lore_context}\n"
            "</LORE_CONTEXT>\n"

            "<INSTRUCTIONS>\n"
            "Design a concise plot roadmap (3-5 beats) for the current scene.\n"
            "0. IDIOMA (OBRIGATÓRIO): escreva os beats, o climax e o arc_title SEMPRE "
            "em PORTUGUÊS DO BRASIL (pt-BR). NUNCA em inglês, mesmo que estas instruções "
            "estejam em inglês.\n"
            "1. USE THE LORE: If the lore mentions specific dangers, factions, or secrets, weave them into the beats.\n"
            "2. PACING: Start with atmosphere/hook, rise tension, and lead to a climax.\n"
            "3. ACTIONABLE: Beats must be clear instructions for the Storyteller AI (em pt-BR, ex.: 'Revele a inscrição antiga na parede').\n"
            "4. ARC TITLE: current arc title is "
            f"'{current_arc or '(none yet)'}'. KEEP it if the story arc continues; "
            "change it ONLY when a truly new arc begins (3-6 words, pt-BR).\n"

            "<EXEMPLO>\n"
            "Lore: 'As Cavernas Sussurrantes são assombradas por ecos do passado.'\n"
            "Beats: ['Descreva os ecos perturbadores imitando o grupo', 'O jogador acha um esqueleto com um bilhete de aviso', 'Os ecos se fundem num guardião espectral']\n"
            "Climax: 'Confronto com o Espectro ou a solução de seu enigma.'"
        )
    )

    prefix = "Recent player intent: " if last_human else "Initial setup: "
    human_msg = HumanMessage(
        content=prefix + (last_intent if last_intent else "Start the scene with strong hooks.")
    )

    try:
        structured = planner_llm.with_structured_output(CampaignPlanModel)
        # Passamos o histórico recente para ele entender o fluxo imediato
        plan = structured.invoke([system_msg, human_msg])
        
        beats: List[CampaignBeat] = [
            {"description": beat, "status": "pending"} for beat in plan.beats
        ]
        return {
            "location": plan.location,
            "beats": beats,
            "climax": plan.climax,
            "current_step": 0,
            "last_planned_turn": world.get("turn_count", 0),
            "arc_title": (plan.arc_title or "").strip() or current_arc,
        }
    except Exception as exc:  # noqa: BLE001
        print(f"[CAMPAIGN MANAGER ERROR] {exc}")
        fallback_beats: List[CampaignBeat] = [
            {"description": f"Explore the mysteries of {current_loc}.", "status": "pending"},
            {"description": "Encounter a challenge related to the local environment.", "status": "pending"},
            {"description": "Make a significant discovery or face a threat.", "status": "pending"},
        ]
        return {
            "location": current_loc,
            "beats": fallback_beats,
            "climax": "Resolve the immediate conflict.",
            "current_step": 0,
            "last_planned_turn": world.get("turn_count", 0),
            # Fallback: mantém o arco atual (não fragmenta a crônica por erro de LLM)
            "arc_title": current_arc or default_chapter_title(current_loc),
        }


def _downed_recente(state: GameState) -> bool:
    return any(c.get("name") == "downed_recente"
               for c in (state.get("player") or {}).get("active_conditions", []) or [])


def _prefix_recovery_beat(plan, world) -> dict:
    """spec pos-saque-recuperacao (R3): injeta um beat de recuperação
    DETERMINÍSTICO no topo do plano após o Saque (o LLM não escreve este beat).
    Idempotente — não duplica se já está no topo."""
    plan = dict(plan or {})
    beats = list(plan.get("beats") or [])
    if beats and beats[0].get("recovery"):
        return plan
    local = world.get("current_location", "um lugar seguro")
    beats.insert(0, {"description": f"Recupere forças em {local} antes de voltar à estrada.",
                     "status": "pending", "recovery": True})
    plan["beats"] = beats
    return plan


def campaign_manager_node(state: GameState):
    """Ensure a coherent multi-step campaign plan exists and is refreshed periodically."""

    world = dict(state.get("world", {}))
    if world.get("turn_count") is None:
        world["turn_count"] = 0

    # Cada invocação do grafo equivale a um turno do jogador.
    # Incrementamos aqui (primeiro nó do fluxo) para que replanejamento,
    # arquivista e memórias de NPC tenham noção real de tempo.
    world["turn_count"] = world.get("turn_count", 0) + 1

    if not _should_replan(state):
        plan = state.get("campaign_plan")
        if _downed_recente(state) and plan:
            plan = _prefix_recovery_beat(plan, world)  # R3 (sem replan)
        return {
            "next": "dm_router",
            "world": world,
            "campaign_plan": plan,
            "needs_replan": False,
        }

    print(f"🗺️ [CAMPAIGN] Generating new plot for: {world.get('current_location')}")
    new_plan = _build_plan(state)
    if _downed_recente(state):
        new_plan = _prefix_recovery_beat(new_plan, world)  # R3 (com replan)

    updated_state = {
        "campaign_plan": new_plan,
        "needs_replan": False,
        "world": world,
        # Importante: Não sobrescrevemos 'messages' aqui para não perder histórico
        "next": "dm_router",
    }

    # Fase 3.1: arco novo → capítulo novo na crônica (mesmo título → no-op).
    new_title = (new_plan.get("arc_title") or "").strip()
    old_title = (state.get("campaign_plan") or {}).get("arc_title", "")
    if new_title and new_title != old_title:
        updated_state["chronicle"] = open_chapter(
            state.get("chronicle") or [],
            title=new_title,
            turn=world["turn_count"],
            location=world.get("current_location", ""),
        )
    return updated_state