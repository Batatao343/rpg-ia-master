"""Context builder com orçamento de tokens (Fase 2.8).

Centraliza a montagem do contexto dos agentes: ranqueia fatos dinâmicos
(event_log, edges, entities, summaries) por relevância+recência, respeita um
orçamento de tokens por seção, e devolve um `ContextPack` com o bloco
`<ESTADO_ATUAL_DO_MUNDO>` pronto. Estado atual entra ANTES da lore base — a
verdade viva vence o canônico quando conflitam.

100% determinístico: zero chamada LLM extra (só o `query_rag` que os agentes já
faziam, agora aqui dentro e com try/except). Spec: specs/SPEC-005-fase-2.8-context-builder.md.
"""

from __future__ import annotations

import hashlib
import math
import os
import re
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from services import graph_resolver as gr
from services.memory_provenance import (
    find_strict_unrevealed,
    format_memory_fact,
    normalize_memory_facts,
)

try:  # RAG é opcional (offline / sem embeddings a busca falha graciosamente)
    import rag as _rag

    query_npc_memory = _rag.query_npc_memory
    query_rag = _rag.query_rag
    query_session_memory = getattr(_rag, "query_session_memory", lambda *_a, **_k: "")
    RAG_AVAILABLE = True
except Exception:  # pragma: no cover - defensivo
    RAG_AVAILABLE = False

    def query_rag(*_a, **_k) -> str:  # type: ignore
        return ""

    def query_npc_memory(*_a, **_k) -> str:  # type: ignore
        return ""

    def query_session_memory(*_a, **_k) -> str:  # type: ignore
        return ""


PURPOSES = ("story", "npc", "combat_narration", "planning")

# Seções do world_state_block (na ordem em que aparecem no prompt).
_WS_SECTIONS = ("current_state", "active_location", "relations", "entities")
_WRAPPER_TOKENS = 16  # custo fixo das tags <ESTADO_ATUAL_DO_MUNDO> etc.

_IMPACT_BY_TYPE = {
    "npc_killed": 1.0,
    "location_control_changed": 1.0,
    "secret_revealed": 0.8,
    "route_blocked": 0.8,  # Fase 6.1: rota fechada muda a cena (comércio/viagem)
    "route_cleared": 0.6,
    # SPEC-309 R5 [BALANCEAR]: o motor ganha voz
    "location_state_changed": 0.9,
    "world_crisis_warning": 0.6,
    "companion_left": 0.8,
    "companion_betrayed": 0.9,
    "companion_fate": 0.9,
    "crime_witnessed": 0.5,
    "law_resolved": 0.6,
    "quest_failed": 0.7,
    "unique_item_claimed": 0.5,
    "unique_item_lost": 0.5,
    "npc_fate_learned": 0.9,
}
_DEFAULT_IMPACT = 0.4

EVENT_TEMPLATES: dict[str, str] = {
    "npc_killed": "[turno {turn}] {target} foi morto (por: {actor}).",
    "location_control_changed": "[turno {turn}] {controller} assumiu o controle de {target}.",
    "faction_relation_changed": "[turno {turn}] Relação de {target} mudou ({relation}) com {other}.",
    "quest_completed": "[turno {turn}] Missão concluída: {target}.",
    "route_blocked": "[turno {turn}] A rota entre {target} e {other_loc} está BLOQUEADA (comércio cortado).",
    "route_cleared": "[turno {turn}] A rota entre {target} e {other_loc} foi reaberta.",
    "faction_deed": "[turno {turn}] O jogador {deed} {target}.",
}

# SPEC-309 §3.2: rotulos fechados (chave fora da tabela => frase descartada, nunca o id cru)
CRISIS_LABELS = {
    "guerra": "guerra",
    "fome": "fome",
    "praga": "praga",
    "abismo": "o Abismo inquieto",
}
CRIME_LABELS = {
    "furto": "um furto",
    "agressao": "uma agressão",
    "homicidio": "um homicídio",
    "dano_propriedade": "dano a propriedade",
    "magia_ilegal": "magia proibida",
    "resistencia": "resistência à guarda",
    "evasao": "uma fuga da guarda",
}
MODE_LABELS = {
    "fine": "multa paga",
    "sentence": "pena cumprida",
    "expulsao": "expulsão",
    "bribe": "acerto por fora",
}

_WORD = re.compile(r"[\wáàâãéêíóôõúüç]+", re.IGNORECASE)


# --------------------------------------------------------------------------- #
# Dataclasses
# --------------------------------------------------------------------------- #
@dataclass
class ContextBudget:
    max_tokens: int = 3500
    reserved: dict[str, float] = field(
        default_factory=lambda: {
            "current_state": 0.25,
            "active_location": 0.20,
            "relations": 0.15,
            "entities": 0.15,
            "lore": 0.15,
            "session_memory": 0.10,
        }
    )
    max_visibility: str = "public"


@dataclass
class ScoredFact:
    text: str
    score: float
    section: str
    source_id: str = ""
    visibility: str = "public"


@dataclass
class ContextPack:
    world_state_block: str
    lore_block: str
    memory_block: str
    total_tokens_est: int
    dropped: int
    evidence_ids: list[str] = field(default_factory=list)
    discarded_evidence: list[dict[str, str]] = field(default_factory=list)
    # SPEC-207 R7: refs SEM texto ({source_id, section, visibility} + selo SPEC-206).
    context_refs: list[dict[str, Any]] = field(default_factory=list)


# --------------------------------------------------------------------------- #
# Primitivos: tokens + score
# --------------------------------------------------------------------------- #
def estimate_tokens(text: str) -> int:
    """Heurística barata chars/4 (sem tokenizer real na v1)."""
    return math.ceil(len(text or "") / 4)


def _terms(s: str) -> set:
    return {w.lower() for w in _WORD.findall(s or "") if len(w) > 2}


def score_fact(
    fact_text: str,
    *,
    query: str,
    current_loc: str,
    scene_entities: list[str],
    impact: float,
    turns_ago: int,
) -> float:
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

    return (
        0.35 * relevance
        + 0.25 * location_match
        + 0.20 * entity_match
        + 0.10 * impact
        + 0.10 * recency
    )


# --------------------------------------------------------------------------- #
# Rendering determinístico de eventos/edges/entidades
# --------------------------------------------------------------------------- #
def _name(entity_id: str | None) -> str:
    if not entity_id:
        return entity_id or ""
    ent = gr.get_entity(entity_id)
    if ent and ent.get("name"):
        return ent["name"]
    return entity_id


def _loc_name(location_id: Any) -> str:
    import gamedata

    return str((gamedata.get_location(str(location_id or "")) or {}).get("name") or "")


def _state_label(state_id: str, festival_id: str = "") -> str:
    from services import location_states

    return location_states.public_label({"state": state_id, "festival_id": festival_id})


def _render_engine_voice(etype: str, event: dict, payload: dict) -> str | None:
    """SPEC-309 R1-R3: frases do motor, sem numeros e so com nomes conhecidos. `None` = tipo
    nao coberto aqui. Retorna o corpo SEM o prefixo `[turno N]`; "" descarta a frase."""
    target = event.get("target_id")
    if etype == "location_state_changed":
        local = _loc_name(payload.get("location_id") or target) or "um local"
        new = str(payload.get("state") or "")
        if not new:  # fim de estado
            prev = str(payload.get("previous") or "")
            fest = str(payload.get("festival_id") or "")
            prev_label = _state_label(prev, fest if prev == "festa" else "")
            return f"{local} não está mais {prev_label}." if prev_label else ""
        fest = str(payload.get("festival_id") or "")
        if new == "festa" and payload.get("cause") == "calendario":
            from services import world_calendar

            f = world_calendar._festival(fest) or {}
            if not f:
                return ""
            return f"{local} está {f.get('label', 'em festa')}: {f.get('name', '')}."
        label = _state_label(new)
        return f"{local} agora está {label}." if label else ""
    if etype == "world_crisis_warning":
        from services import world_pressures as wp

        kind = CRISIS_LABELS.get(str(payload.get("kind") or ""))
        region = wp.region_label(str(payload.get("region_id") or ""))
        return f"Há sinais de {kind} em {region or 'a região'}." if kind else ""
    if etype in ("companion_left", "companion_betrayed", "companion_fate"):
        name = str(payload.get("name") or "") or "um companheiro"
        if etype == "companion_left":
            return f"{name} deixou o grupo."
        if etype == "companion_betrayed":
            return f"{name} traiu o grupo e partiu."
        from services.chronicle import _FATE_TEXT

        fate = _FATE_TEXT.get(str(payload.get("fate") or ""), "teve um destino incerto")
        return f"{name} {fate}."
    if etype == "crime_witnessed":
        crime = CRIME_LABELS.get(str(payload.get("crime_type") or ""))
        if not crime:
            return ""
        local = _loc_name(payload.get("location_id")) or "um local"
        return f"Houve {crime} em {local}."
    if etype == "law_resolved":
        from services import law_codes

        mode_ = MODE_LABELS.get(str(payload.get("mode") or ""))
        name = str(
            (law_codes.get_code(str(payload.get("jurisdiction_id") or "")) or {}).get("name") or ""
        )
        if not mode_ or not name:
            return ""
        return f"A pendência do herói com {name} foi resolvida ({mode_})."
    if etype == "quest_failed":
        title = str(payload.get("quest_title") or "") or _name(target)
        return f"Missão fracassada: {title}." if title else ""
    if etype in ("unique_item_claimed", "unique_item_lost"):
        if etype == "unique_item_claimed" and payload.get("holder", "player") != "player":
            return ""
        from gamedata import ARTIFACTS_DB

        item = str((ARTIFACTS_DB.get(str(target or "")) or {}).get("name") or "")
        if not item:
            return ""
        if etype == "unique_item_claimed":
            return f"O herói obteve {item}, peça única no mundo."
        return f"O herói perdeu {item}."
    if etype == "npc_fate_learned":
        verb = {"morto": "morreu", "capturado": "foi capturado"}.get(str(payload.get("fate") or ""))
        if not verb:
            return ""
        who = str(payload.get("name") or "") or "alguém"
        where = _loc_name(payload.get("location_id"))
        return f"Chegou a notícia: {who} {verb}{' em ' + where if where else ''}."
    return None


_ENGINE_VOICE_TYPES = frozenset(
    {
        "location_state_changed",
        "world_crisis_warning",
        "companion_left",
        "companion_betrayed",
        "companion_fate",
        "crime_witnessed",
        "law_resolved",
        "quest_failed",
        "unique_item_claimed",
        "unique_item_lost",
        "npc_fate_learned",
    }
)


def render_event(event: dict, projection: dict | None = None) -> str:
    """1 frase determinística por GameEvent. `secret_revealed` NÃO passa por aqui
    (é renderizado de world_projection.revealed_facts). Tipo desconhecido → ""."""
    etype = event.get("type")
    if etype == "faction_membership_changed":  # SPEC-301: vazio p/ fação secreta não exposta
        from services.faction_membership import event_text

        return event_text(event)
    payload = event.get("payload", {}) or {}
    if etype in _ENGINE_VOICE_TYPES:  # SPEC-309 R1
        try:
            body = _render_engine_voice(str(etype), event, payload)
        except Exception as exc:  # payload legado/corrompido nunca derruba o pack (R21)
            from observability.telemetry import log_fallback

            log_fallback("context_builder", "render_event_failed", exc)
            return ""
        return f"[turno {event.get('turn', 0)}] {body}" if body else ""
    tmpl = EVENT_TEMPLATES.get(etype)
    if not tmpl:
        return ""
    return tmpl.format(
        turn=event.get("turn", 0),
        target=_name(event.get("target_id")),
        actor=_name(event.get("actor_id", "player")),
        controller=_name(payload.get("new_controller_id")),
        relation=payload.get("relation") or event.get("detail", "") or payload.get("detail", ""),
        other=_name(payload.get("other_faction_id") or event.get("actor_id")),
        other_loc=_name(payload.get("other_location_id")),
        deed="ajudou" if payload.get("direction") == "ajudou" else "prejudicou",
    )


# --------------------------------------------------------------------------- #
# Coleta de fatos dinâmicos
# --------------------------------------------------------------------------- #
def collect_dynamic_facts(
    state: dict,
    *,
    purpose: str,
    query: str,
    current_loc: str,
    scene_entities: list[str],
    knowledge_filter: set | None = None,
) -> list[ScoredFact]:
    """Renderiza event_log + revealed_facts + edges + entities + summaries em
    ScoredFacts (já pontuados). Não inclui lore/memória (essas vêm do RAG).

    SPEC-215 R6: `knowledge_filter` (só `purpose="npc"` com o flag `on`) = ids
    de assunto que o NPC sabe. Com filtro, eventos/segredos revelados saem do
    bloco neutro (entram rotulados pelo ledger) e "morto" só aparece para quem
    sabe da morte. `None` = comportamento anterior, byte a byte."""
    projection = state.get("world_projection", {}) or {}
    world = state.get("world", {}) or {}
    current_turn = int(world.get("turn_count", 0) or 0)
    include_hidden = purpose == "planning"

    facts: list[ScoredFact] = []

    def add(text: str, section: str, *, impact: float, turns_ago: int, sid: str = ""):
        if not text:
            return
        facts.append(
            ScoredFact(
                text=text,
                score=score_fact(
                    text,
                    query=query,
                    current_loc=current_loc,
                    scene_entities=scene_entities,
                    impact=impact,
                    turns_ago=turns_ago,
                ),
                section=section,
                source_id=sid,
            )
        )

    # --- current_state: quem controla o local + eventos ocorridos + segredos revelados ---
    # SPEC-234 R6: o grafo e indexado por ID; o nome so serve para scoring/texto.
    # Controlador `hidden` so aparece para o planner (include_hidden).
    loc_id = str(world.get("current_location_id") or "") or current_loc
    controller = (
        gr.get_current_controller(loc_id, projection, include_hidden=include_hidden)
        if loc_id
        else None
    )
    if controller:
        add(
            f"Quem controla {_name(loc_id)} agora: {_name(controller)}.",
            "current_state",
            impact=1.0,
            turns_ago=0,
            sid=f"ctrl:{loc_id}",
        )

    known_dead: set = set()
    if knowledge_filter is not None:
        known_dead = {
            ev.get("target_id")
            for ev in (state.get("event_log", []) or [])
            if isinstance(ev, dict)
            and ev.get("type") == "npc_killed"
            and ev.get("event_id") in knowledge_filter
        }

    from services import npc_world as _npc_world
    from services import world_perception

    for ev in (state.get("event_log", []) or [])[-100:]:
        if knowledge_filter is not None:
            break
        if not world_perception.event_perceived(state, ev):
            continue  # SPEC-308 R4: evento do motor que o heroi nao viu nem ouviu
        if _npc_world.event_hidden_from_player(state, ev):
            continue  # SPEC-304 R23: fato off-screen que o jogador ainda nao percebeu
        text = render_event(ev, projection)
        impact = _IMPACT_BY_TYPE.get(ev.get("type"), _DEFAULT_IMPACT)
        turns_ago = max(0, current_turn - int(ev.get("turn", 0) or 0))
        add(text, "current_state", impact=impact, turns_ago=turns_ago, sid=ev.get("event_id", ""))

    for eid, rf in (projection.get("revealed_facts", {}) or {}).items():
        if knowledge_filter is not None:
            break
        fact_txt = rf.get("fact", "")
        turn = int(rf.get("revealed_at_turn", 0) or 0)
        add(
            f"[turno {turn}] Revelado sobre {_name(rf.get('entity_id'))}: {fact_txt}",
            "current_state",
            impact=0.8,
            turns_ago=max(0, current_turn - turn),
            sid=eid,
        )

    # --- active_location: resumo dinâmico do local atual ---
    summaries = projection.get("location_summaries", {}) or {}
    summ = summaries.get(loc_id) or summaries.get(current_loc)
    if summ:
        add(
            f"Local {_name(loc_id)}: {summ}",
            "active_location",
            impact=0.6,
            turns_ago=0,
            sid=f"summ:{loc_id}",
        )

    # --- relations: edges efetivas relevantes ao local/cena ---
    seen_edges = set()
    # SPEC-308 P0-1: arestas escritas por evento do motor nao percebido nao chegam ao prompt
    for edge in gr.resolve_edges(
        world_perception.perceived_projection(state, projection), include_hidden=include_hidden
    ):
        eid = edge.get("id") or f"{edge.get('source')}:{edge.get('type')}:{edge.get('target')}"
        if eid in seen_edges:
            continue
        seen_edges.add(eid)
        # SPEC-215 R6/R3: aresta criada por evento só para quem sabe do evento.
        if (
            knowledge_filter is not None
            and edge.get("created_by_event")
            and edge.get("created_by_event") not in knowledge_filter
        ):
            continue
        rel = edge.get("type", "relação")
        add(
            f"{_name(edge.get('source'))} —{rel}→ {_name(edge.get('target'))}",
            "relations",
            impact=_DEFAULT_IMPACT,
            turns_ago=0,
            sid=eid,
        )

    # --- entities: EntityState notável (mortos, deslocados) ---
    for eid, est in (projection.get("entities", {}) or {}).items():
        alive = est.get("alive", True)
        if knowledge_filter is not None and not alive and eid not in known_dead:
            continue
        if not alive and _npc_world.entity_death_hidden(state, eid):
            continue  # SPEC-304 R23: a morte fora de cena ainda nao foi percebida
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
def _assemble(facts: list[ScoredFact], budget: ContextBudget):
    """Preenche cada seção na ordem de `budget.reserved` até a cota (em tokens);
    sobra de cota rola para a próxima seção. Corta no limite global (margem 5%)."""
    visibility_rank = {"public": 0, "hidden": 1, "secret": 2}
    maximum_visibility = visibility_rank.get(budget.max_visibility, -1)
    by_section: dict[str, list[ScoredFact]] = {}
    discarded_evidence: list[dict[str, str]] = []
    visibility_dropped = 0
    for f in facts:
        if visibility_rank.get(f.visibility, 3) > maximum_visibility:
            visibility_dropped += 1
            if f.source_id:
                discarded_evidence.append(
                    {
                        "id": f.source_id,
                        "section": f.section,
                        "reason": "visibility",
                    }
                )
            continue
        by_section.setdefault(f.section, []).append(f)
    for lst in by_section.values():
        lst.sort(key=lambda f: f.score, reverse=True)

    hard_cap = math.floor(budget.max_tokens * 1.05)
    used_total = _WRAPPER_TOKENS
    carry = 0.0
    dropped = visibility_dropped
    chosen: dict[str, list[ScoredFact]] = {}

    for section, pct in budget.reserved.items():
        quota = budget.max_tokens * pct + carry
        section_used = 0.0
        picked: list[ScoredFact] = []
        for fct in by_section.get(section, []):
            t = estimate_tokens(fct.text)
            if section_used + t <= quota and used_total + t <= hard_cap:
                picked.append(fct)
                section_used += t
                used_total += t
            else:
                dropped += 1
                if fct.source_id:
                    discarded_evidence.append(
                        {
                            "id": fct.source_id,
                            "section": section,
                            "reason": "section_or_global_budget",
                        }
                    )
        chosen[section] = picked
        carry = max(0.0, quota - section_used)

    known_sections = set(budget.reserved)
    for section, section_facts in by_section.items():
        if section in known_sections:
            continue
        dropped += len(section_facts)
        discarded_evidence.extend(
            {
                "id": fact.source_id,
                "section": section,
                "reason": "unknown_section",
            }
            for fact in section_facts
            if fact.source_id
        )

    return chosen, used_total, dropped, discarded_evidence


def _block(facts: list[ScoredFact]) -> str:
    return "\n".join(f.text for f in facts)


def assemble_pack(
    facts: list[ScoredFact], budget: ContextBudget, lore_text: str = "", memory_text: str = ""
) -> ContextPack:
    """Ranqueia + orça + renderiza os três blocos do ContextPack.

    Lore entra como bloco canônico. Memória é particionada para que um resumo ou
    resultado RAG grande não torne a seção inteira indivisível e descartável."""
    facts = list(facts)
    if lore_text:
        lore_id = "lore_content_" + hashlib.sha256(lore_text.encode("utf-8")).hexdigest()[:24]
        facts.append(
            ScoredFact(
                text=lore_text,
                score=1.0,
                section="lore",
                source_id=lore_id,
                visibility="public",
            )
        )
    if memory_text:
        chunks: list[str] = []
        for line in (part.strip() for part in memory_text.splitlines()):
            if not line:
                continue
            while len(line) > 600:
                cut = line.rfind(" ", 0, 601)
                if cut < 300:
                    cut = 600
                chunks.append(line[:cut].rstrip())
                line = line[cut:].lstrip()
            if line:
                chunks.append(line)
        for index, chunk in enumerate(chunks):
            memory_id = "memory_content_" + hashlib.sha256(chunk.encode("utf-8")).hexdigest()[:24]
            facts.append(
                ScoredFact(
                    text=chunk,
                    score=1.0 - min(index, 1000) * 0.0001,
                    section="session_memory",
                    source_id=memory_id,
                    visibility="public",
                )
            )

    chosen, used_total, dropped, discarded_evidence = _assemble(facts, budget)

    ws_body = (
        "\n".join(_block(chosen.get(sec, [])) for sec in _WS_SECTIONS if chosen.get(sec))
        or "Sem mudanças registradas no mundo (estado canônico vale)."
    )
    world_state_block = f"<ESTADO_ATUAL_DO_MUNDO>\n{ws_body}\n</ESTADO_ATUAL_DO_MUNDO>"
    lore_block = _block(chosen.get("lore", []))
    memory_block = _block(chosen.get("session_memory", []))
    evidence_ids = [
        fact.source_id
        for section in budget.reserved
        for fact in chosen.get(section, [])
        if fact.source_id
    ]

    from services.audit_trace import classify_fact

    context_refs = [
        classify_fact(
            section=fact.section,
            source_id=fact.source_id,
            visibility=fact.visibility,
            text=fact.text,
        )
        for section in budget.reserved
        for fact in chosen.get(section, [])
        if fact.source_id
    ]

    return ContextPack(
        world_state_block=world_state_block,
        lore_block=lore_block,
        memory_block=memory_block,
        total_tokens_est=used_total,
        dropped=dropped,
        evidence_ids=evidence_ids,
        discarded_evidence=discarded_evidence,
        context_refs=context_refs,
    )


# --------------------------------------------------------------------------- #
# Cartas utilitárias no contexto do narrador (cutover conflito-13)
# --------------------------------------------------------------------------- #
def utility_context_block(player: dict, *, abilities_db=None) -> str:
    """Capacidades FORA de combate que o herói conhece (`tipo=utilitaria`).

    O gate é determinístico (conhece/não conhece); a LLM só narra. Devolve ""
    se o herói não tem nenhuma — o storyteller omite o bloco."""
    if abilities_db is None:
        from services.cards import all_cards

        db = all_cards()
    else:
        # Nome do argumento preservado por compatibilidade de testes/callers; no
        # schema v4 ele representa um catálogo de Cartas.
        db = abilities_db
    lines = []
    for cid in player.get("known_cards") or []:
        card = db.get(cid) or {}
        if card.get("tipo") != "utilitaria":
            continue
        effect = card.get("efeito") or {}
        label = card.get("name", cid)
        hint = effect.get("prompt_hint", "")
        lines.append(f"- {label}: {hint}" if hint else f"- {label}")
    if not lines:
        return ""
    return (
        "<CAPACIDADES_DO_HEROI>\n"
        "O herói POSSUI estas capacidades fora de combate (narre o uso quando a "
        "ação do jogador as invocar; NÃO conceda capacidades fora desta lista):\n"
        + "\n".join(lines)
        + "\n</CAPACIDADES_DO_HEROI>"
    )


# --------------------------------------------------------------------------- #
# Entrada pública
# --------------------------------------------------------------------------- #
def build_context_pack(
    state: dict,
    query: str,
    purpose: str,
    token_budget: int = 3500,
    game_id: str | None = None,
    npc_id: str | None = None,
) -> ContextPack:
    """SPEC-200: mede a fase `context` (no-op sem timeline). Sem mudar comportamento."""
    from observability.latency import TurnPhase
    from observability.latency import phase as _phase

    with _phase(TurnPhase.CONTEXT):
        pack = _build_context_pack(state, query, purpose, token_budget, game_id, npc_id)
    # SPEC-207 R7: refs do contexto visto vão ao coletor do turno (no-op fora do turno).
    from services.audit_trace import note_context

    note_context(pack, purpose=purpose, npc_id=npc_id)
    return pack


def _build_context_pack(
    state: dict,
    query: str,
    purpose: str,
    token_budget: int = 3500,
    game_id: str | None = None,
    npc_id: str | None = None,
) -> ContextPack:
    """Monta o ContextPack. Lore canônico e memória de sessão são buscados e
    rotulados separadamente; `npc_id` inclui ainda a memória privada do NPC."""
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

    # SPEC-215: gate de conhecimento por NPC. `off` → gate None (byte a byte).
    gate = None
    if purpose == "npc" and npc_id:
        from services import npc_knowledge

        gate = npc_knowledge.context_gate(state, npc_id)
    gate_on = bool(gate) and gate["mode"] == "on"
    facts = collect_dynamic_facts(
        state,
        purpose=purpose,
        query=query,
        current_loc=current_loc,
        scene_entities=scene_entities,
        knowledge_filter=gate["filter"] if gate_on else None,
    )
    if gate_on:
        for index, (sid, line) in enumerate(gate["lines"]):
            facts.append(
                ScoredFact(
                    text=line, score=2.0 - index * 0.001, section="current_state", source_id=sid
                )
            )
    elif gate:  # shadow: mede o que seria filtrado, sem alterar o prompt
        gated = collect_dynamic_facts(
            state,
            purpose=purpose,
            query=query,
            current_loc=current_loc,
            scene_entities=scene_entities,
            knowledge_filter=gate["filter"],
        )
        npc_knowledge.log_shadow(
            npc_id,
            known=len(gate["lines"]),
            filtered=max(0, len(facts) - len(gated)),
            total=len(facts),
        )

    from services.context_sources import (
        EmbeddedContextQuery,
        acquire_context_sources,
        embed_context_query,
    )

    custom_readers = None
    if RAG_AVAILABLE and (
        query_rag is not getattr(_rag, "query_rag", None)
        or query_session_memory is not getattr(_rag, "query_session_memory", None)
        or query_npc_memory is not getattr(_rag, "query_npc_memory", None)
    ):
        custom_readers = {
            "lore": lambda: query_rag(
                query,
                index_name="lore",
                max_visibility="public",
            )
        }
        if game_id:
            custom_readers["session"] = lambda: query_session_memory(query, game_id)
        if game_id and npc_id:
            custom_readers["npc"] = lambda: query_npc_memory(game_id, npc_id, query)
    # Test doubles and compatibility adapters own their complete retrieval path.
    # Do not perform a real embedding before invoking those custom readers.
    embedded = (
        EmbeddedContextQuery(query, None, None, None)
        if custom_readers is not None
        else embed_context_query(query, game_id=game_id, npc_id=npc_id)
    )
    try:
        workers = max(1, min(3, int(os.getenv("RPG_CONTEXT_MAX_CONCURRENCY", "3"))))
    except ValueError:
        workers = 3
    acquired = acquire_context_sources(
        embedded,
        game_id=game_id,
        npc_id=npc_id,
        max_workers=workers,
        readers=custom_readers,
    )
    source_text = {result.source: result.text for result in acquired}
    lore_text = source_text.get("lore", "")

    # Memória de sessão nunca entra no bloco de lore canônico.
    memory_parts = []
    seen_memory_text: set[str] = set()

    def add_memory_part(text: str, *, legacy_if_unlabeled: bool = False) -> None:
        clean = str(text or "").strip()
        from services.narrative_evidence import build_evidence, validate_narrative

        clean = validate_narrative(clean, build_evidence(state), channel="context").text
        if not clean or clean in seen_memory_text or find_strict_unrevealed(clean, state):
            return
        # O índice pré-spec devolve texto cru; jamais lhe atribuímos autoridade.
        if legacy_if_unlabeled and not clean.startswith("["):
            clean = f"[NÃO VERIFICADO | legacy_unverified] {clean}"
        seen_memory_text.add(clean)
        memory_parts.append(clean)

    # O resumo curto é o primeiro candidato da quota; fatos duráveis ainda
    # concorrem individualmente em seguida.
    from services.memory_summary import compact_summary

    summary = compact_summary(state.get("narrative_summary", ""))
    # SPEC-215 D2: com `on`, resumo/ledger/memória de sessão do JOGADOR saem do
    # prompt do NPC; fica a memória privada do NPC + lore público.
    if summary and not gate_on and not find_strict_unrevealed(summary, state):
        add_memory_part(f"[RESUMO NARRATIVO | speculative] {summary}")

    if game_id and not gate_on:
        session_memory = source_text.get("session", "")
        if session_memory:
            add_memory_part(session_memory, legacy_if_unlabeled=True)
    if npc_id and game_id:
        npc_mem = source_text.get("npc", "")
        if npc_mem:
            add_memory_part(npc_mem, legacy_if_unlabeled=True)
    # SPEC-234 R8: ordem sob orcamento = resumo, RAG relevante, ledger do mais
    # NOVO para o mais antigo (o score decresce com a posicao).
    # O ledger auditável dá continuidade mesmo se o índice estiver temporariamente
    # indisponível. Conteúdo com assinatura secreta não revelada falha fechado.
    for record in (
        []
        if gate_on
        else active_memory_facts(
            state.get("memory_facts"),
            current_turn=int((state.get("world") or {}).get("turn_count", 0) or 0),
            state=state,
        )[-20:][::-1]
    ):
        if find_strict_unrevealed(record["text"], state):
            continue
        add_memory_part(format_memory_fact(record))
    memory_text = "\n".join(memory_parts)

    budget = ContextBudget(max_tokens=token_budget)
    return assemble_pack(facts, budget, lore_text=lore_text, memory_text=memory_text)


def active_memory_facts(rows, *, current_turn: int, state: dict | None = None) -> list[dict]:
    """Contexto ativo: especulação não confirmada expira após 20 turnos."""
    records = normalize_memory_facts(rows)
    from services.narrative_evidence import build_evidence, validate_narrative

    evidence = build_evidence(state or {})
    return [
        record
        for record in records
        if not (
            record.get("confidence") == "speculative"
            and record.get("source_turn") is not None
            and int(current_turn) - int(record.get("source_turn") or 0) >= 20
        )
        and not validate_narrative(record["text"], evidence, channel="context").rejections
    ]
