"""
agents/world_simulator.py
Fase 2 — "respiração" do mundo: ao descansar/viajar, simula 1 evento off-screen NARRADO
(rumor/sinal que o jogador percebe), grava o fato no RAG da sessão e pode empurrar levemente
o perigo local.

Arquitetura: a IA NARRA/identifica (WorldPulse); Python resolve (clampa o perigo, persiste no RAG).
Não-onisciência: o prompt só lista fações que o jogador conhece (intel.known); forças desconhecidas
aparecem como sinais sem nome. Guard de FallbackLLM (isinstance). Inerte sem chave.
"""
from typing import Tuple
from langchain_core.messages import SystemMessage
from pydantic import BaseModel, Field

from llm_setup import ModelTier, get_llm
from services.prose_guard import sanitize_meta_preamble
from world_utils import clock_label, ensure_faction_intel, ensure_factions

try:
    from rag import add_memory_to_session
    RAG_AVAILABLE = True
except ImportError:  # pragma: no cover
    RAG_AVAILABLE = False
    def add_memory_to_session(*args, **kwargs): return None

import gamedata


class WorldPulse(BaseModel):
    rumor: str = Field(description="1-2 frases que o JOGADOR percebe (rumor de taverna, sinal na estrada, "
                                   "eco distante). NÃO nomeie fações/poderes que ele não conhece.")
    fact: str = Field(
        default="",
        description="Justificativa narrativa opcional. Não vira memória por si só; "
                    "somente a consequência aplicada pelo motor é persistida.")
    danger_shift: int = Field(default=0, description="-1, 0 ou +1: o mundo ficou mais ou menos perigoso aqui?")


def _effective_danger(world: dict, loc_id: str) -> int:
    overrides = world.get("danger_overrides") or {}
    if loc_id in overrides:
        return int(overrides[loc_id])
    loc = gamedata.get_location(loc_id) or {}
    return int(loc.get("danger", world.get("danger_level", 1)))


def _known_factions_ctx(factions, intel) -> str:
    intel = ensure_faction_intel(intel)
    linhas = [
        f"- {f.get('name')} ({f.get('region','')}) · disposição={f.get('disposition','neutro')}"
        for f in ensure_factions(factions)
        if intel.get(f.get("id"), {}).get("known") and not f.get("defeated")
    ]
    return "\n".join(linhas) or "Nenhuma facção conhecida pelo jogador (use só sinais sem nome)."


def _apply_danger_shift(world: dict, loc_id: str, shift: int) -> dict:
    """Empurra o perigo do local em [-1,+1], clampado a [1,4]. Determinístico."""
    shift = max(-1, min(1, int(shift)))
    if shift == 0 or not loc_id:
        return world
    cur = _effective_danger(world, loc_id)
    new = max(1, min(4, cur + shift))
    overrides = dict(world.get("danger_overrides") or {})
    overrides[loc_id] = new
    world["danger_overrides"] = overrides
    if world.get("current_location_id") == loc_id:
        world["danger_level"] = new
    return world


def simulate_world(state: dict, world: dict, factions, intel, periods: int = 1) -> Tuple[dict, str]:
    """
    Gera 1 evento off-screen narrado. Retorna (world, nota). Nota = "[ECOS DO MUNDO] ..." ou "".
    Não levanta: qualquer falha → (world, "").
    """
    world = dict(world or {})
    loc_id = world.get("current_location_id", "")
    loc_name = world.get("current_location", "a região")
    threat = world.get("looming_threat") or "—"
    danger = _effective_danger(world, loc_id)

    sys = SystemMessage(content=f"""
    Você é o SIMULADOR DO MUNDO de um RPG dark fantasy. O tempo passou ({periods} período(s))
    enquanto o jogador descansava/viajava. Gere UM evento off-screen plausível.

    Local: {loc_name}. Momento: {clock_label(world)}. Perigo atual: {danger}/4.
    Ameaça pairando: {threat}.
    Fações que o JOGADOR conhece:
    {_known_factions_ctx(factions, intel)}

    REGRAS:
    - 'rumor': o que o jogador PERCEBE (ouve/vê) — 1-2 frases. NÃO revele nomes/planos de poderes
      que ele não conhece; forças desconhecidas são "sinais sem nome".
    - 'fact': registro interno objetivo (pode nomear), curto.
    - 'danger_shift': -1, 0 ou +1 conforme o mundo ficou mais/menos perigoso AQUI.
    """)

    llm = get_llm(temperature=0.8, tier=ModelTier.FAST)
    try:
        pulse = llm.with_structured_output(WorldPulse).invoke([sys])
    except Exception:
        return world, ""

    if not isinstance(pulse, WorldPulse):  # FallbackLLM devolve AIMessage
        return world, ""

    before_danger = _effective_danger(world, loc_id)
    world = _apply_danger_shift(world, loc_id, getattr(pulse, "danger_shift", 0))
    after_danger = _effective_danger(world, loc_id)

    # Apenas a consequência que Python realmente aplicou vira memória. `pulse.fact`
    # é prosa não verificada e não pode promover cânone novo.
    applied_fact = (
        f"[mundo] O perigo de {loc_name} mudou de {before_danger} para {after_danger}."
        if after_danger != before_danger else "")
    if RAG_AVAILABLE and state.get("game_id") and applied_fact:
        try:
            add_memory_to_session(state["game_id"], [applied_fact])
        except Exception:
            pass

    rumor = sanitize_meta_preamble(pulse.rumor or "")
    return world, (f"[ECOS DO MUNDO] {rumor}" if rumor else "")
