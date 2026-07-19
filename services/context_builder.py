"""Context builder com orçamento de tokens (Fase 2.8).

Centraliza a montagem do contexto dos agentes: ranqueia fatos dinâmicos
(event_log, edges, entities, summaries) por relevância+recência, respeita um
orçamento de tokens por seção, e devolve um `ContextPack` com o bloco
`<ESTADO_ATUAL_DO_MUNDO>` pronto. Estado atual entra ANTES da lore base — a
verdade viva vence o canônico quando conflitam.

100% determinístico: zero chamada LLM extra (só o `query_rag` que os agentes já
faziam, agora aqui dentro e com try/except). Spec: specs/fase-2.8-context-builder.md.
"""
from __future__ import annotations

import math
import re
from dataclasses import dataclass, field
from typing import Dict, List, Optional

from services import graph_resolver as gr

try:  # RAG é opcional (offline / sem embeddings a busca falha graciosamente)
    from rag import query_npc_memory, query_rag
    RAG_AVAILABLE = True
except Exception:  # pragma: no cover - defensivo
    RAG_AVAILABLE = False

    def query_rag(*_a, **_k) -> str:  # type: ignore
        return ""

    def query_npc_memory(*_a, **_k) -> str:  # type: ignore
        return ""


PURPOSES = ("story", "npc", "combat_narration", "planning")

# Seções do world_state_block (na ordem em que aparecem no prompt).
_WS_SECTIONS = ("current_state", "active_location", "relations", "entities")
_WRAPPER_TOKENS = 16  # custo fixo das tags <ESTADO_ATUAL_DO_MUNDO> etc.

_IMPACT_BY_TYPE = {
    "npc_killed": 1.0,
    "location_control_changed": 1.0,
    "secret_revealed": 0.8,
    "route_blocked": 0.8,   # Fase 6.1: rota fechada muda a cena (comércio/viagem)
    "route_cleared": 0.6,
}
_DEFAULT_IMPACT = 0.4

EVENT_TEMPLATES: Dict[str, str] = {
    "npc_killed": "[turno {turn}] {target} foi morto (por: {actor}).",
    "location_control_changed": "[turno {turn}] {controller} assumiu o controle de {target}.",
    "faction_relation_changed": "[turno {turn}] Relação de {target} mudou ({relation}) com {other}.",
    "quest_completed": "[turno {turn}] Missão concluída: {target}.",
    "route_blocked": "[turno {turn}] A rota entre {target} e {other_loc} está BLOQUEADA (comércio cortado).",
    "route_cleared": "[turno {turn}] A rota entre {target} e {other_loc} foi reaberta.",
}

_WORD = re.compile(r"[\wáàâãéêíóôõúüç]+", re.IGNORECASE)


# --------------------------------------------------------------------------- #
# Dataclasses
# --------------------------------------------------------------------------- #
@dataclass
class ContextBudget:
    max_tokens: int = 3500
    reserved: Dict[str, float] = field(default_factory=lambda: {
        "current_state": 0.25,
        "active_location": 0.20,
        "relations": 0.15,
        "entities": 0.15,
        "lore": 0.15,
        "session_memory": 0.10,
    })


@dataclass
class ScoredFact:
    text: str
    score: float
    section: str
    source_id: str = ""


@dataclass
class ContextPack:
    world_state_block: str
    lore_block: str
    memory_block: str
    total_tokens_est: int
    dropped: int


# --------------------------------------------------------------------------- #
# Primitivos: tokens + score
# --------------------------------------------------------------------------- #
def estimate_tokens(text: str) -> int:
    """Heurística barata chars/4 (sem tokenizer real na v1)."""
    return math.ceil(len(text or "") / 4)


def _terms(s: str) -> set:
    return {w.lower() for w in _WORD.findall(s or "") if len(w) > 2}


def score_fact(fact_text: str, *, query: str, current_loc: str,
               scene_entities: List[str], impact: float, turns_ago: int) -> float:
    """Score composto (0..~1) de um fato dinâmico. Sem embeddings — barato/offline."""
    fact_terms = _terms(fact_text)
    q_terms = _terms(query)
    relevance = (len(q_terms & fact_terms) / len(q_terms)) if q_terms else 0.0

    loc_terms = _terms(current_loc)
    location_match = 1.0 if (loc_terms and (loc_terms & fact_terms)) else 0.0

    entities = [e for e in (scene_entities or []) if e]
    if entities:
        hits = sum(1 for e in entities if _terms(e) & fact_terms)
        entity_match = hits / len(entities)
    else:
        entity_match = 0.0

    recency = max(0.0, 1.0 - turns_ago / 50.0)

    return (0.35 * relevance + 0.25 * location_match + 0.20 * entity_match
            + 0.10 * impact + 0.10 * recency)


# --------------------------------------------------------------------------- #
# Rendering determinístico de eventos/edges/entidades
# --------------------------------------------------------------------------- #
def _name(entity_id: Optional[str]) -> str:
    if not entity_id:
        return entity_id or ""
    ent = gr.get_entity(entity_id)
    if ent and ent.get("name"):
        return ent["name"]
    return entity_id


def render_event(event: Dict, projection: Optional[Dict] = None) -> str:
    """1 frase determinística por GameEvent. `secret_revealed` NÃO passa por aqui
    (é renderizado de world_projection.revealed_facts). Tipo desconhecido → ""."""
    etype = event.get("type")
    tmpl = EVENT_TEMPLATES.get(etype)
    if not tmpl:
        return ""
    payload = event.get("payload", {}) or {}
    return tmpl.format(
        turn=event.get("turn", 0),
        target=_name(event.get("target_id")),
        actor=_name(event.get("actor_id", "player")),
        controller=_name(payload.get("new_controller_id")),
        relation=payload.get("relation") or event.get("detail", "") or payload.get("detail", ""),
        other=_name(payload.get("other_faction_id") or event.get("actor_id")),
        other_loc=_name(payload.get("other_location_id")),
    )


# --------------------------------------------------------------------------- #
# Coleta de fatos dinâmicos
# --------------------------------------------------------------------------- #
def collect_dynamic_facts(state: Dict, *, purpose: str, query: str,
                          current_loc: str, scene_entities: List[str]) -> List[ScoredFact]:
    """Renderiza event_log + revealed_facts + edges + entities + summaries em
    ScoredFacts (já pontuados). Não inclui lore/memória (essas vêm do RAG)."""
    projection = state.get("world_projection", {}) or {}
    world = state.get("world", {}) or {}
    current_turn = int(world.get("turn_count", 0) or 0)
    include_hidden = purpose == "planning"

    facts: List[ScoredFact] = []

    def add(text: str, section: str, *, impact: float, turns_ago: int, sid: str = ""):
        if not text:
            return
        facts.append(ScoredFact(
            text=text,
            score=score_fact(text, query=query, current_loc=current_loc,
                             scene_entities=scene_entities, impact=impact, turns_ago=turns_ago),
            section=section,
            source_id=sid,
        ))

    # --- current_state: quem controla o local + eventos ocorridos + segredos revelados ---
    controller = gr.get_current_controller(current_loc, projection) if current_loc else None
    if controller:
        add(f"Quem controla {_name(current_loc)} agora: {_name(controller)}.",
            "current_state", impact=1.0, turns_ago=0, sid=f"ctrl:{current_loc}")

    for ev in (state.get("event_log", []) or [])[-100:]:
        text = render_event(ev, projection)
        impact = _IMPACT_BY_TYPE.get(ev.get("type"), _DEFAULT_IMPACT)
        turns_ago = max(0, current_turn - int(ev.get("turn", 0) or 0))
        add(text, "current_state", impact=impact, turns_ago=turns_ago,
            sid=ev.get("event_id", ""))

    for eid, rf in (projection.get("revealed_facts", {}) or {}).items():
        fact_txt = rf.get("fact", "")
        turn = int(rf.get("revealed_at_turn", 0) or 0)
        add(f"[turno {turn}] Revelado sobre {_name(rf.get('entity_id'))}: {fact_txt}",
            "current_state", impact=0.8, turns_ago=max(0, current_turn - turn), sid=eid)

    # --- active_location: resumo dinâmico do local atual ---
    summ = (projection.get("location_summaries", {}) or {}).get(current_loc)
    if summ:
        add(f"Local {_name(current_loc)}: {summ}", "active_location",
            impact=0.6, turns_ago=0, sid=f"summ:{current_loc}")

    # --- relations: edges efetivas relevantes ao local/cena ---
    seen_edges = set()
    for edge in gr.resolve_edges(projection, include_hidden=include_hidden):
        eid = edge.get("id") or f"{edge.get('source')}:{edge.get('type')}:{edge.get('target')}"
        if eid in seen_edges:
            continue
        seen_edges.add(eid)
        rel = edge.get("type", "relação")
        add(f"{_name(edge.get('source'))} —{rel}→ {_name(edge.get('target'))}",
            "relations", impact=_DEFAULT_IMPACT, turns_ago=0, sid=eid)

    # --- entities: EntityState notável (mortos, deslocados) ---
    for eid, est in (projection.get("entities", {}) or {}).items():
        alive = est.get("alive", True)
        loc = est.get("location_id")
        status = "vivo" if alive else "morto"
        text = f"{_name(eid)}: {status}"
        if loc:
            text += f", em {_name(loc)}"
        add(text + ".", "entities", impact=(0.4 if alive else 1.0), turns_ago=0, sid=eid)

    return facts


# --------------------------------------------------------------------------- #
# Montador de seções + budget
# --------------------------------------------------------------------------- #
def _assemble(facts: List[ScoredFact], budget: ContextBudget):
    """Preenche cada seção na ordem de `budget.reserved` até a cota (em tokens);
    sobra de cota rola para a próxima seção. Corta no limite global (margem 5%)."""
    by_section: Dict[str, List[ScoredFact]] = {}
    for f in facts:
        by_section.setdefault(f.section, []).append(f)
    for lst in by_section.values():
        lst.sort(key=lambda f: f.score, reverse=True)

    hard_cap = math.floor(budget.max_tokens * 1.05)
    used_total = _WRAPPER_TOKENS
    carry = 0.0
    dropped = 0
    chosen: Dict[str, List[ScoredFact]] = {}

    for section, pct in budget.reserved.items():
        quota = budget.max_tokens * pct + carry
        section_used = 0.0
        picked: List[ScoredFact] = []
        for fct in by_section.get(section, []):
            t = estimate_tokens(fct.text)
            if section_used + t <= quota and used_total + t <= hard_cap:
                picked.append(fct)
                section_used += t
                used_total += t
            else:
                dropped += 1
        chosen[section] = picked
        carry = max(0.0, quota - section_used)

    return chosen, used_total, dropped


def _block(facts: List[ScoredFact]) -> str:
    return "\n".join(f.text for f in facts)


def assemble_pack(facts: List[ScoredFact], budget: ContextBudget,
                  lore_text: str = "", memory_text: str = "") -> ContextPack:
    """Ranqueia + orça + renderiza os três blocos do ContextPack.

    `lore_text`/`memory_text` são blobs de RAG/resumo; entram como fatos únicos nas
    seções `lore`/`session_memory` (concorrem só com a própria cota)."""
    facts = list(facts)
    if lore_text:
        facts.append(ScoredFact(text=lore_text, score=1.0, section="lore", source_id="lore"))
    if memory_text:
        facts.append(ScoredFact(text=memory_text, score=1.0, section="session_memory",
                                source_id="memory"))

    chosen, used_total, dropped = _assemble(facts, budget)

    ws_body = "\n".join(
        _block(chosen.get(sec, [])) for sec in _WS_SECTIONS if chosen.get(sec)
    ) or "Sem mudanças registradas no mundo (estado canônico vale)."
    world_state_block = f"<ESTADO_ATUAL_DO_MUNDO>\n{ws_body}\n</ESTADO_ATUAL_DO_MUNDO>"
    lore_block = _block(chosen.get("lore", []))
    memory_block = _block(chosen.get("session_memory", []))

    return ContextPack(
        world_state_block=world_state_block,
        lore_block=lore_block,
        memory_block=memory_block,
        total_tokens_est=used_total,
        dropped=dropped,
    )


# --------------------------------------------------------------------------- #
# spec arvores-habilidade-classes (§3.3): utilitárias no contexto do narrador
# --------------------------------------------------------------------------- #
def utility_context_block(player: Dict, *, abilities_db=None) -> str:
    """Capacidades FORA de combate que o herói conhece (ability_kind='utility').

    O gate é determinístico (conhece/não conhece); a LLM só narra. Devolve ""
    se o herói não tem nenhuma — o storyteller omite o bloco."""
    db = abilities_db
    if db is None:
        try:
            from gamedata import ABILITIES as db
        except Exception:  # pragma: no cover - defensivo
            return ""
    lines = []
    for aid in player.get("known_abilities") or []:
        a = db.get(aid) or {}
        if a.get("ability_kind") != "utility":
            continue
        ooc = a.get("out_of_combat") or {}
        label = ooc.get("label") or a.get("name", aid)
        hint = ooc.get("prompt_hint", "")
        lines.append(f"- {label}: {hint}" if hint else f"- {label}")
    if not lines:
        return ""
    return ("<CAPACIDADES_DO_HEROI>\n"
            "O herói POSSUI estas capacidades fora de combate (narre o uso quando a "
            "ação do jogador as invocar; NÃO conceda capacidades fora desta lista):\n"
            + "\n".join(lines) + "\n</CAPACIDADES_DO_HEROI>")


# --------------------------------------------------------------------------- #
# Entrada pública
# --------------------------------------------------------------------------- #
def build_context_pack(state: Dict, query: str, purpose: str,
                       token_budget: int = 3500, game_id: Optional[str] = None,
                       npc_id: Optional[str] = None) -> ContextPack:
    """Monta o ContextPack para um agente. `game_id` → busca híbrida lore+sessão
    (só o storyteller passa). `npc_id` → inclui memória vetorizada do NPC."""
    if purpose not in PURPOSES:
        raise ValueError(f"purpose inválido: {purpose!r} (use um de {PURPOSES})")

    world = state.get("world", {}) or {}
    current_loc = world.get("current_location", "") or ""
    # spec encontros-dedupe (R1): NPCs vinculados ao local/em cena/party — não
    # arrasta NPC gerado de outra cena para os fatos deste contexto.
    from services.npc_layers import npcs_for_context
    scene_entities = npcs_for_context(state)
    if current_loc:
        scene_entities.append(current_loc)

    facts = collect_dynamic_facts(state, purpose=purpose, query=query,
                                  current_loc=current_loc, scene_entities=scene_entities)

    # Lore global (respeita visibility; segredo não vaza). Falha de rede → "".
    lore_text = ""
    try:
        lore_text = query_rag(query, index_name="lore", game_id=game_id,
                              max_visibility="public") or ""
    except Exception:
        lore_text = ""

    # Memória de sessão: resumo + (npc) memória vetorizada do NPC.
    memory_parts = []
    summary = state.get("narrative_summary", "")
    if summary:
        memory_parts.append(summary)
    if npc_id and game_id:
        try:
            npc_mem = query_npc_memory(game_id, npc_id, query)
            if npc_mem:
                memory_parts.append(npc_mem)
        except Exception:
            pass
    memory_text = "\n".join(memory_parts)

    budget = ContextBudget(max_tokens=token_budget)
    return assemble_pack(facts, budget, lore_text=lore_text, memory_text=memory_text)
