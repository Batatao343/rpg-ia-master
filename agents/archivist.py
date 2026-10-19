"""
agents/archivist.py
Gerencia a Memória de Curto (Resumo) e Longo Prazo (RAG) da sessão.
"""
import inspect
import re
from typing import List

from langchain_core.messages import SystemMessage
from pydantic import BaseModel, Field, field_validator

from llm_setup import ModelTier, get_llm
from observability.telemetry import log_event as _log_event
from rag import add_memory_to_session, add_npc_memory
from services import conflict_summary as conflict_summary_service
from services.chronicle import append_entry
from services.context_builder import render_event
from services.event_processor import process_pending_events
from services.memory_provenance import (
    MAX_MEMORY_PROMOTIONS,
    MAX_MEMORY_REJECTIONS,
    bounded_audit_rows,
    commit_memory_facts,
    make_memory_fact,
    memory_metadata,
    normalize_memory_facts,
    sanitize_inventory_grounding,
    sanitize_location_grounding,
    sanitize_npc_identity_grounding,
    set_vector_status,
    validate_memory_fact,
)
from services.memory_retry import normalize_pending_npc_memory
from services.prompt_guard import PLAYER_INPUT_RULE, guard_messages
from services.prose_guard import sanitize_meta_preamble
from state import GameState


class MemoryUpdate(BaseModel):
    new_summary: str = Field(description="Um parágrafo resumindo a situação ATUAL e imediata da história.")
    important_facts: List[str] = Field(description="Fatos PERMANENTES para o banco de dados. Lista vazia se nada importante.")
    chronicle_entry: str = Field(
        default="",
        description="Feito digno de canção: 1-3 frases em prosa de menestrel (3ª pessoa, épico-sombrio). Vazio se turno banal.",
    )

    @field_validator("important_facts", mode="before")
    @classmethod
    def _coerce_facts(cls, v):
        """Resiliência (achado dos smokes reais): o LLM às vezes devolve
        `important_facts` como lista de DICTS ({fato,type} / {role,content}) em
        vez de strings — isso derrubava o schema inteiro por validação e o turno
        perdia fatos/crônica no fallback de texto. Coage cada item para string
        ANTES da validação de tipo, preservando a memória do turno."""
        if not isinstance(v, list):
            return v
        out: List[str] = []
        allowed_keys = ("content", "fato", "fact", "text", "desc", "value", "description")
        for item in v:
            if isinstance(item, str):
                s = item.strip()
            elif isinstance(item, dict):
                s = str(next(
                    (item[key] for key in allowed_keys
                     if key in item and isinstance(item[key], (str, int, float))),
                    "",
                )).strip()
            else:
                s = str(item).strip()
            # Transcript/wrapper não é fato permanente.
            looks_like_transcript = bool(
                re.search(r"(?im)^\s*(human|assistant|system|user|ai)\s*:", s)
                or s.count("\n") > 2
            )
            if s and not looks_like_transcript and len(s) <= 320:
                out.append(s)
        return out


_ERROR_SUMMARY_PREFIXES = (
    "erro", "error", "⚠", "falha", "não foi possível", "nao foi possivel",
    "todos os provedores", "llm indisponível", "llm indisponivel",
)


def _extract_summary_plain(llm, context_msgs: list, current_summary: str) -> str:
    """Fallback plain-text: pede só o resumo sem JSON schema. Retorna string ou ''."""
    if getattr(llm, "is_fallback", False):
        from observability.telemetry import log_fallback
        log_fallback("archivist", "fallback_llm_no_summary")
        return ""  # SPEC-234 R5: a mensagem de erro do FallbackLLM nunca vira resumo
    try:
        res = llm.invoke([
            SystemMessage(content=(
                f"Resumo anterior: \"{current_summary}\"\n\n"
                "Com base nas mensagens abaixo, escreva UM parágrafo (máx. 5 frases) "
                "resumindo a situação atual do herói. Só o texto, sem JSON, sem títulos.\n"
                f"{PLAYER_INPUT_RULE}"
            ))
        ] + guard_messages(context_msgs))  # SPEC-223 R5
        text = getattr(res, "content", "") or ""
        if isinstance(text, list):
            text = " ".join(p.get("text", "") if isinstance(p, dict) else str(p) for p in text)
        text = text.strip()
        if text.lower().startswith(_ERROR_SUMMARY_PREFIXES):
            return ""
        return text
    except Exception as e:
        _log_event("archivist", "fallback_text_failed", level="warning", error=type(e).__name__)
        return ""


_VECTOR_RETRY_EVERY = 3  # SPEC-234 R1/D-B: no maximo 1 retry vetorial a cada 3 turnos
_ARCHIVE_EVERY = 10  # turnos sem evento relevante antes de forçar um arquivamento


def _persist_memory_records(game_id: str, records: List[dict]) -> bool:
    """Write único com metadata; aceita stubs antigos de dois argumentos."""
    records = normalize_memory_facts(records)
    if not records:
        return True
    texts = [record["text"] for record in records]
    metadatas = [memory_metadata(record) for record in records]
    try:
        parameters = inspect.signature(add_memory_to_session).parameters.values()
        accepts_metadata = any(
            parameter.name == "metadatas"
            or parameter.kind == inspect.Parameter.VAR_KEYWORD
            for parameter in parameters
        )
    except (TypeError, ValueError):
        accepts_metadata = True
    try:
        if accepts_metadata:
            ok = add_memory_to_session(
                game_id, texts, metadatas=metadatas,
            )
        else:  # compatibilidade de testes/callers que monkeypatcham a função
            ok = add_memory_to_session(game_id, texts)
    except Exception as exc:
        _log_event("archivist", "rag_persist_failed", level="warning", error=type(exc).__name__)
        return False
    _log_event("archivist", "facts_extracted", level="debug", count=len(texts))
    return ok is not False


def _validate_candidates(candidates: List[dict], state: dict) -> tuple[List[dict], List[dict]]:
    accepted: List[dict] = []
    rejected: List[dict] = []
    for candidate in normalize_memory_facts(candidates):
        record, reason = validate_memory_fact(candidate, state)
        if record is not None:
            accepted.append(record)
            continue
        rejected.append({
            "memory_id": candidate.get("memory_id"),
            "turn": candidate.get("source_turn"),
            "provenance": candidate.get("provenance"),
            "reason": reason or "invalid_memory_fact",
            "text_preview": candidate.get("text", "")[:120],
        })
    return accepted, rejected


def _event_memory_records(events: List[dict], state: dict) -> List[dict]:
    projection = state.get("world_projection") or {}
    records: List[dict] = []
    for event in events:
        if not isinstance(event, dict) or not event.get("event_id"):
            continue
        text = render_event(event, projection)
        if event.get("type") == "secret_revealed":
            detail = str((event.get("payload") or {}).get("detail") or "").strip()
            if detail:
                text = f"[turno {event.get('turn', 0)}] Segredo revelado: {detail}"
        if not text:
            continue
        records.append(make_memory_fact(
            text,
            provenance="canonical_event",
            source_id=str(event["event_id"]),
            source_turn=int(event.get("turn", 0) or 0),
            canonical_entity_ids=[
                item for item in (event.get("actor_id"), event.get("target_id"))
                if item
            ],
        ))
    return records


def _rejection_identity(row) -> tuple:
    """Identidade estável de uma rejeição, inclusive com o buffer já capado."""
    if not isinstance(row, dict):
        return ("", "", "", "")
    return (
        str(row.get("turn") or ""),
        str(row.get("type") or ""),
        str(row.get("target_id") or ""),
        str(row.get("reason") or "")[:240],
    )


def _should_archive(state: GameState, turn: int) -> bool:
    """
    Cadência do arquivista: só roda o LLM em EVENTO RELEVANTE (flag archive_due, setada por
    combate/viagem/descanso/NPC/loot) OU a cada ~10 turnos. Exploração trivial não dispara.
    """
    if (
        state.get("archive_due")
        or state.get("conflict_summary")
        or state.get("memory_fact_policy") == "canonical_only"
        or state.get("pending_npc_memory")
    ):
        return True
    # SPEC-234 §7: fatos pendentes (índice fora) só reabrem o arquivista na janela de
    # retry vetorial — não a cada turno, para não pagar um SMART por turno.
    if state.get("pending_memory_facts") and int(turn) % _VECTOR_RETRY_EVERY == 0:
        return True
    last = int(state.get("archivist_last_run", 0) or 0)
    return (turn - last) >= _ARCHIVE_EVERY


def _validate_derived(result: dict, state: GameState, evidence, audit: list, *,
                      deferred: bool = False) -> None:
    """Revalida resumo e prosa da crônica derivados contra a evidência canônica
    (SPEC-213 R7: sempre o estado canônico ATUAL, inclusive quando adiados)."""
    from observability.latency import accumulate as _timed  # SPEC-200 R4 (so mede)
    from services.narrative_evidence import validate_narrative
    from services.projections import strip_dead_npc_presence
    canonical = {**state, **evidence.state}
    if 'narrative_summary' in result:
        with _timed('archivist_validate_ms'):
            check = validate_narrative(result['narrative_summary'], evidence, channel='summary')
        from services.memory_summary import compact_summary as _compact
        text = check.text
        audit.extend(check.rejections)
        if text and deferred:
            text, dead = strip_dead_npc_presence(text, canonical)
            audit.extend(dead)
        result['narrative_summary'] = (
            text
            or _compact(state.get('narrative_summary', '') or '')
            or 'A aventura segue.'
        )
    if 'chronicle' in result:
        from copy import deepcopy
        chapters = deepcopy(result['chronicle'])
        for chapter in chapters:
            for entry in chapter.get('entries', []):
                if entry.get('kind') != 'prose' or entry.get('turn') != evidence.turn:
                    continue
                with _timed('archivist_validate_ms'):
                    check = validate_narrative(entry.get('text', ''), evidence, channel='chronicle')
                text = check.text
                audit.extend(check.rejections)
                if text and deferred:
                    text, dead = strip_dead_npc_presence(text, canonical)
                    audit.extend(dead)
                entry['text'] = text
            chapter['entries'] = [entry for entry in chapter.get('entries', []) if entry.get('text')]
        result['chronicle'] = chapters


def archive_node(state: GameState):
    from langgraph.types import Overwrite

    from services import projections
    from services.narrative_evidence import build_evidence, guard_current_messages

    # Validate after event processing, before feeding prose back to the model.
    event_updates = process_pending_events(state)
    effective = {**state, **event_updates}
    from observability.latency import accumulate as _timed  # SPEC-200 R4 (so mede)
    with _timed('archivist_validate_ms'):
        messages, audit = guard_current_messages(effective)
    effective['messages'] = messages
    turn = int((effective.get('world') or {}).get('turn_count', 0) or 0)
    if (
        projections.deferral_active()
        and effective.get('game_id')
        and _should_archive(effective, turn)
    ):
        # SPEC-213 modo A: canônico (eventos/guard da prosa) fica no turno; resumo,
        # fatos do LLM e prosa da crônica viram projeção drenada pelo dono do lock.
        prior_ids = {
            str(event.get('event_id'))
            for event in (state.get('event_log') or [])
            if isinstance(event, dict) and event.get('event_id')
        }
        new_ids = [
            str(event['event_id'])
            for event in (effective.get('event_log') or [])
            if isinstance(event, dict) and event.get('event_id')
            and str(event['event_id']) not in prior_ids
        ]
        prior_rejections = {
            _rejection_identity(row) for row in (state.get('event_rejections') or [])
        }
        new_rejections = any(
            _rejection_identity(row) not in prior_rejections
            for row in (event_updates.get('event_rejections', state.get('event_rejections')) or [])
        )
        epoch = int((effective.get('continuity') or {}).get('timeline_epoch', 0) or 0)
        # Revisão Astra: projeção anterior ainda pendente (falhou, aguarda retry)
        # não pode perder a linha de base dos eventos do seu turno ao ser sucedida.
        earlier = projections.normalize_plan(state.get('pending_derived'))
        if earlier is not None and earlier.get('epoch') == epoch:
            new_ids = [*earlier['new_event_ids'],
                       *[x for x in new_ids if x not in earlier['new_event_ids']]]
            new_rejections = new_rejections or earlier['new_rejections']
        result = dict(event_updates)
        result['pending_derived'] = projections.make_plan(
            new_event_ids=new_ids, new_rejections=new_rejections, turn=turn, epoch=epoch,
        )
        if audit:
            result['evidence_rejections'] = [*(state.get('evidence_rejections') or []), *audit][-64:]
        if messages != list(state.get('messages') or []):
            result['messages'] = Overwrite(messages)
        return result
    evidence = build_evidence(effective)
    # Keep the pre-event baseline for new-event memory detection. Processing the
    # same pending queue twice loses that baseline even if application is deduped.
    result = _archive_node({**state, 'messages': messages}, event_updates=event_updates)
    _validate_derived(result, state, evidence, audit)
    if audit:
        result['evidence_rejections'] = [*(state.get('evidence_rejections') or []), *audit][-64:]
    if messages != list(state.get('messages') or []):
        result['messages'] = Overwrite(messages)
    return result


def run_derived_projection(state: GameState, plan: dict) -> dict:
    """SPEC-213: executor da projeção adiada. Roda sobre o estado canônico JÁ
    commitado (eventos aplicados, prosa ao jogador guardada) usando a linha de base
    do plano para detectar os eventos novos daquele turno. Mesmo prompt/LLM."""
    from services.narrative_evidence import build_evidence
    evidence = build_evidence(state)
    audit: list = []
    result = _archive_node(state, event_updates={}, baseline=plan)
    _validate_derived(result, state, evidence, audit, deferred=True)
    if audit:
        result['evidence_rejections'] = [*(state.get('evidence_rejections') or []), *audit][-64:]
    return result


def _archive_node(state: GameState, *, event_updates: dict | None = None,
                  baseline: dict | None = None):
    """
    Compacta o histórico recente em um resumo e extrai fatos para o RAG.
    Roda com cadência (evento relevante OU a cada ~10 turnos) — não em todo turno.
    """
    messages = state.get("messages", [])
    game_id = state.get("game_id")

    if not game_id:
        return {}

    # Fase 2.6: valida/aplica a fila de eventos estruturados em TODO turno, ANTES da
    # guarda de cadência — turno trivial ainda precisa consolidar o mundo. No-op se
    # a fila está vazia (retorna {}).
    if event_updates is None:
        event_updates = process_pending_events(state)

    turn = state.get("world", {}).get("turn_count", 0)
    prior_event_ids = {
        str(event.get("event_id"))
        for event in (state.get("event_log") or [])
        if isinstance(event, dict) and event.get("event_id")
    }
    if baseline is not None:
        # SPEC-213: projeção adiada — o estado já contém os eventos do turno; a
        # linha de base do plano diz quais eram novos.
        prior_event_ids -= {str(x) for x in (baseline.get("new_event_ids") or [])}
    effective_state = {**state, **event_updates}
    new_events = [
        event for event in (effective_state.get("event_log") or [])
        if isinstance(event, dict)
        and event.get("event_id")
        and str(event["event_id"]) not in prior_event_ids
    ]
    if not _should_archive(effective_state, turn):
        if new_events:
            # O event_log já é durável e canônico. Não força uma chamada SMART
            # fora da cadência: agenda a cópia derivada para o índice no próximo
            # archivist, mantendo o turno trivial barato e compatível.
            deferred, rejected = _validate_candidates(
                _event_memory_records(new_events, effective_state),
                effective_state,
            )
            return {
                **event_updates,
                "archive_due": False,
                "memory_facts": normalize_memory_facts(
                    state.get("memory_facts")
                ),
                "pending_memory_facts": normalize_memory_facts([
                    *normalize_memory_facts(
                        state.get("pending_memory_facts"), pending=True,
                    ),
                    *deferred,
                ], pending=True),
                "memory_rejections": bounded_audit_rows([
                    *bounded_audit_rows(
                        state.get("memory_rejections"),
                        limit=MAX_MEMORY_REJECTIONS,
                    ),
                    *rejected,
                ], limit=MAX_MEMORY_REJECTIONS),
                "memory_promotions": bounded_audit_rows(
                    state.get("memory_promotions"),
                    limit=MAX_MEMORY_PROMOTIONS,
                ),
            }
        return {"archive_due": False, **event_updates}  # turno trivial: pula o LLM do arquivista

    # Retry global ocorre antes de produzir candidatos novos. O ledger só muda
    # depois do write físico; uma falha deixa exatamente os mesmos IDs pendentes.
    memory_facts = normalize_memory_facts(state.get("memory_facts"))
    pending_memory_facts = normalize_memory_facts(
        state.get("pending_memory_facts"), pending=True,
    )
    memory_rejections = bounded_audit_rows(
        state.get("memory_rejections"), limit=MAX_MEMORY_REJECTIONS,
    )
    memory_promotions = bounded_audit_rows(
        state.get("memory_promotions"), limit=MAX_MEMORY_PROMOTIONS,
    )
    if pending_memory_facts:
        retry_records, retry_rejections = _validate_candidates(
            pending_memory_facts, effective_state,
        )
        memory_rejections = bounded_audit_rows(
            [*memory_rejections, *retry_rejections], limit=MAX_MEMORY_REJECTIONS,
        )
        retry_due = int(turn) % _VECTOR_RETRY_EVERY == 0
        if retry_records and retry_due and _persist_memory_records(game_id, retry_records):
            memory_facts, promoted = commit_memory_facts(memory_facts, retry_records)
            memory_facts = set_vector_status(
                memory_facts, [item["memory_id"] for item in retry_records], "written",
            )
            if promoted:
                memory_promotions = bounded_audit_rows([
                    *memory_promotions,
                    {"turn": int(turn), "count": promoted, "reason": "canonical_source"},
                ], limit=MAX_MEMORY_PROMOTIONS)
            pending_memory_facts = []
        else:
            # Indice indisponivel (ou fora da janela de retry): o ledger e a
            # fonte primaria e ja contem os fatos; o turno segue (SPEC-234 R1).
            pending_memory_facts = retry_records
            if retry_records:
                memory_facts, _ = commit_memory_facts(memory_facts, retry_records)
                memory_facts = set_vector_status(
                    memory_facts, [item["memory_id"] for item in retry_records],
                    "pending",
                )
                _log_event("archivist", "vector_index_unavailable", level="warning")
        event_updates = {
            **event_updates,
            "memory_facts": memory_facts,
            "pending_memory_facts": pending_memory_facts,
            "memory_rejections": memory_rejections,
            "memory_promotions": memory_promotions,
            "rag_persistence_error": (
                "Falha ao persistir memória de sessão pendente."
                if pending_memory_facts else None
            ),
        }
        effective_state = {**state, **event_updates}

    # Retry operation-scoped da memória vetorial de NPC. Cada sucesso sai da
    # fila imediatamente; falhas permanecem sem que uma interação nova ou um
    # persist([]) global possa mascará-las.
    pending_npc_memory = normalize_pending_npc_memory(
        state.get("pending_npc_memory")
    )
    npc_retry_committed = False
    remaining_npc_memory: list = []
    if pending_npc_memory and int(turn) % _VECTOR_RETRY_EVERY != 0:
        remaining_npc_memory = list(pending_npc_memory)  # fora da janela de retry
    elif pending_npc_memory:
        remaining_npc_memory = []
        committed_npc_records = []
        for write in pending_npc_memory:
            try:
                npc_records = [
                    make_memory_fact(
                        fact,
                        provenance="npc_claim",
                        source_id=f"npc:{write['npc_id']}",
                        source_turn=int(turn),
                        canonical_entity_ids=[write["npc_id"]],
                    )
                    for fact in write["facts"]
                ]
                parameters = inspect.signature(add_npc_memory).parameters.values()
                accepts_metadata = any(
                    parameter.name == "metadatas"
                    or parameter.kind == inspect.Parameter.VAR_KEYWORD
                    for parameter in parameters
                )
                if accepts_metadata:
                    ok = add_npc_memory(
                        game_id,
                        write["npc_id"],
                        list(write["facts"]),
                        metadatas=[memory_metadata(record) for record in npc_records],
                    ) is not False
                else:
                    ok = add_npc_memory(
                        game_id,
                        write["npc_id"],
                        list(write["facts"]),
                    ) is not False
            except Exception as exc:
                _log_event("archivist", "npc_memory_retry_failed", level="warning", error=type(exc).__name__)
                ok = False
            if not ok:
                remaining_npc_memory.append(write)
            else:
                committed_npc_records.extend(npc_records)
        if committed_npc_records:
            memory_facts, promoted = commit_memory_facts(
                memory_facts, committed_npc_records,
            )
            if promoted:
                memory_promotions = bounded_audit_rows([
                    *memory_promotions,
                    {"turn": int(turn), "count": promoted,
                     "reason": "canonical_source"},
                ], limit=MAX_MEMORY_PROMOTIONS)
        event_updates = {
            **event_updates,
            "pending_npc_memory": remaining_npc_memory,
            "memory_facts": memory_facts,
            "memory_promotions": memory_promotions,
        }
        if remaining_npc_memory:
            waiting_ids = ", ".join(dict.fromkeys(
                write["npc_id"] for write in remaining_npc_memory
            ))
            event_updates["rag_persistence_error"] = (
                event_updates.get("rag_persistence_error")
                or state.get("rag_persistence_error")
                or f"Falha ao persistir memória de {waiting_ids}."
            )
        else:
            npc_retry_committed = True
            if not pending_memory_facts:
                event_updates["rag_persistence_error"] = None

    from services.memory_summary import compact_summary
    current_summary = compact_summary(
        state.get("narrative_summary", "A aventura segue."))
    current_summary, initial_location_rejections = sanitize_location_grounding(
        current_summary,
    )
    current_summary, initial_inventory_rejections = sanitize_inventory_grounding(
        current_summary, effective_state,
    )
    current_summary, initial_npc_rejections = sanitize_npc_identity_grounding(
        current_summary, effective_state,
    )
    if (
        initial_location_rejections
        or initial_inventory_rejections
        or initial_npc_rejections
    ):
        memory_rejections = bounded_audit_rows([
            *memory_rejections,
            *[
                {
                    "turn": int((state.get("world") or {}).get("turn_count", 0) or 0),
                    "provenance": "narrative_summary",
                    "reason": "location_region_contradiction",
                    **row,
                }
                for row in initial_location_rejections
            ],
            *[
                {
                    "turn": int((state.get("world") or {}).get("turn_count", 0) or 0),
                    "provenance": "narrative_summary",
                    "reason": "inventory_possession_contradiction",
                    **row,
                }
                for row in initial_inventory_rejections
            ],
            *[
                {
                    "turn": int((state.get("world") or {}).get("turn_count", 0) or 0),
                    "provenance": "narrative_summary",
                    "reason": "npc_identity_contradiction",
                    **row,
                }
                for row in initial_npc_rejections
            ],
        ], limit=MAX_MEMORY_REJECTIONS)
    current_summary = current_summary or "A aventura segue."
    context_msgs = messages[-6:] if len(messages) > 6 else messages
    pending_conflict_summary = dict(state.get("conflict_summary") or {})
    consumed_conflict_ids = (
        conflict_summary_service.normalize_consumed_conflict_ids(
            state.get("consumed_conflict_ids")
        )
    )
    conflict_id = ""
    if pending_conflict_summary:
        if (
            not pending_conflict_summary.get("conflict_id")
            and pending_conflict_summary.get("conflict_turn") is None
        ):
            pending_conflict_summary["conflict_turn"] = int(turn)
        conflict_id = conflict_summary_service.ensure_conflict_id(
            pending_conflict_summary,
            turn=pending_conflict_summary.get("conflict_turn"),
        )
        pending_conflict_summary["conflict_id"] = conflict_id
        effective_state = {
            **effective_state,
            "conflict_summary": pending_conflict_summary,
        }
    duplicate_conflict = bool(
        conflict_id and conflict_id in consumed_conflict_ids
    )
    memory_fact_policy = state.get("memory_fact_policy")
    canonical_only = memory_fact_policy == "canonical_only"
    raw_policy_facts = state.get("memory_canonical_facts") or []
    if isinstance(raw_policy_facts, str):
        raw_policy_facts = [raw_policy_facts]
    policy_facts = list(dict.fromkeys(
        fact.strip()
        for fact in raw_policy_facts
        if isinstance(fact, str) and fact.strip()
    ))
    prior_rejection_rows = list(state.get("event_rejections") or [])
    processed_rejection_rows = list(
        event_updates.get("event_rejections", prior_rejection_rows) or []
    )
    prior_rejection_ids = {
        _rejection_identity(row) for row in prior_rejection_rows
    }
    new_rejections = any(
        _rejection_identity(row) not in prior_rejection_ids
        for row in processed_rejection_rows
    )
    if baseline is not None:
        new_rejections = bool(baseline.get("new_rejections"))
    narrative_rejections = list(state.get("narrative_rejections") or [])

    # Summary já confirmado é lixo transitório repetido: limpa sem chamar LLM,
    # RAG ou Crônica. Políticas/rejeições independentes ainda seguem seu fluxo.
    if (
        duplicate_conflict
        and not canonical_only
        and not new_rejections
        and not narrative_rejections
        and not new_events
    ):
        return {
            **event_updates,
            "conflict_summary": None,
            "consumed_conflict_ids": consumed_conflict_ids,
            "archive_due": False,
            "rag_persistence_error": None,
        }

    conflict_summary = (
        {} if duplicate_conflict else pending_conflict_summary
    )
    canonical_facts = (
        conflict_summary_service.summary_facts(conflict_summary)
        if conflict_summary else []
    )
    authoritative_facts = list(dict.fromkeys(canonical_facts + policy_facts))
    event_records = _event_memory_records(new_events, effective_state)
    conflict_source = f"conflict:{conflict_id}" if conflict_id else f"engine_policy:{turn}"
    authoritative_records = [
        *event_records,
        *[
            make_memory_fact(
                fact,
                provenance="canonical_event",
                source_id=(conflict_source if fact in canonical_facts else f"engine_policy:{turn}"),
                source_turn=int(turn),
            )
            for fact in authoritative_facts
        ],
    ]
    canonical_text = (
        conflict_summary_service.canonical_summary_text(conflict_summary)
        if conflict_summary else ""
    )
    suppress_free_facts = bool(
        conflict_summary
        or duplicate_conflict
        or new_rejections
        or narrative_rejections
    )

    def merged_summary(proposed: str) -> str:
        base = sanitize_meta_preamble(proposed) or current_summary
        if conflict_summary:
            base = conflict_summary_service.narrative_or_fallback(
                conflict_summary, base,
            )
        if canonical_text and canonical_text.casefold() not in base.casefold():
            base = f"{base.rstrip()} {canonical_text}".strip()
        return compact_summary(base)

    def memory_state_updates() -> dict:
        return {
            "memory_facts": memory_facts,
            "pending_memory_facts": pending_memory_facts,
            "memory_rejections": memory_rejections,
            "memory_promotions": memory_promotions,
        }

    def persist_records(candidates: List[dict]) -> bool:
        nonlocal memory_facts, pending_memory_facts
        nonlocal memory_rejections, memory_promotions
        accepted, rejected = _validate_candidates(candidates, effective_state)
        memory_rejections = bounded_audit_rows(
            [*memory_rejections, *rejected], limit=MAX_MEMORY_REJECTIONS,
        )
        prospective, promoted = commit_memory_facts(memory_facts, accepted)
        current_ids = {item["memory_id"] for item in memory_facts}
        to_write = [
            item for item in prospective if item["memory_id"] not in current_ids
        ]
        if not to_write:
            return True
        if not _persist_memory_records(game_id, to_write):
            # SPEC-234 R1: o ledger e a fonte primaria; a copia vetorial fica
            # pendente para retry com backoff e o turno NAO congela.
            pending_memory_facts = normalize_memory_facts(
                [*pending_memory_facts, *to_write], pending=True,
            )
            memory_facts = set_vector_status(
                prospective, [item["memory_id"] for item in to_write], "pending",
            )
            from rag import _note_degraded
            _note_degraded("session_write")
            return False
        memory_facts = set_vector_status(
            prospective, [item["memory_id"] for item in to_write], "written",
        )
        if promoted:
            memory_promotions = bounded_audit_rows([
                *memory_promotions,
                {"turn": int(turn), "count": promoted, "reason": "canonical_source"},
            ], limit=MAX_MEMORY_PROMOTIONS)
        return True

    llm = get_llm(temperature=0.3, tier=ModelTier.SMART)

    from gamedata import get_location
    from inventory import item_display
    world = effective_state.get("world") or {}
    canonical_location = get_location(world.get("current_location_id", "")) or {}
    location_anchor = (
        f"{canonical_location.get('name', world.get('current_location', 'desconhecido'))} "
        f"pertence à região {canonical_location.get('region', 'desconhecida')}"
    )
    inventory_anchor = ", ".join(
        item_display(row)
        for row in ((effective_state.get("player") or {}).get("inventory") or [])
        if isinstance(row, dict)
    ) or "vazio"
    from services.entity_identity import coalesce_runtime_npcs
    npc_identity_lines = []
    for key, npc in coalesce_runtime_npcs(effective_state.get("npcs") or {}).items():
        if not isinstance(npc, dict) or not npc.get("in_scene", False):
            continue
        appearance = " ".join(str(npc.get("appearance") or "").split())[:240]
        if appearance:
            npc_identity_lines.append(
                f"- {npc.get('name') or key}: {appearance}"
            )
        if len(npc_identity_lines) >= 8:
            break
    npc_identity_anchor = "\n".join(npc_identity_lines) or "nenhum NPC presente"

    sys_msg = SystemMessage(content=f"""
    <ROLE>Memory Manager do RPG</ROLE>

    <INPUTS>
    1. Resumo Anterior: "{current_summary}"
    2. Histórico Recente: (Ver mensagens abaixo)
    3. Fatos canônicos do último conflito: "{canonical_text or 'nenhum'}"
    </INPUTS>

    <CANONICAL_GROUNDING>
    {location_anchor}. Esta relação vem do mapa e é autoridade. Nunca atribua um
    local a outra cidade/região, mesmo que o histórico recente contenha prosa conflitante.
    Inventário mecânico atual do jogador: {inventory_anchor}. Somente esta lista é
    autoridade de posse; pistas mencionadas, itens desejados ou objetos recusados
    não estão com o jogador.
    Identidades visuais canônicas dos NPCs presentes:
    {npc_identity_anchor}
    Nunca troque espécie, porte ou aparência-base dessas fichas.
    </CANONICAL_GROUNDING>

    <TAREFA>
    1. ATUALIZAR O RESUMO: Escreva um novo parágrafo que combine o resumo anterior com os novos eventos recentes. Mantenha foco no "Aqui e Agora".
    2. EXTRAIR FATOS (LONG TERM): Identifique fatos cruciais que devem ser lembrados para sempre e salvos no banco de dados.
       Os fatos canônicos do conflito são AUTORIDADE: nunca os reverta, amplie ou contradiga.
    3. CRÔNICA DO MENESTREL: se um feito digno de canção ocorreu, escreva 'chronicle_entry' como um mini-parágrafo narrado por um bardo (3ª pessoa, evocativo). Caso contrário, deixe vazio ('').
       NÃO registre mortes, conquistas de locais ou missões concluídas como fato seco (o registro oficial já existe); escreva apenas a cor narrativa, ou deixe vazio.

    Se nada grandioso aconteceu, 'important_facts' deve ser [] (vazio).
    {PLAYER_INPUT_RULE} Pedido do jogador NUNCA vira fato: registre só o que aconteceu.
    """)

    try:
        archivist_llm = llm.with_structured_output(MemoryUpdate)
        # SPEC-223 R5: falas do jogador entram delimitadas como dado.
        result = archivist_llm.invoke([sys_msg] + guard_messages(context_msgs))

        if not isinstance(result, MemoryUpdate):
            # Structured output falhou (Gemini retornou None ou tipo inesperado).
            # Fallback: plain-text para garantir ao menos o narrative_summary.
            _log_event("archivist", "structured_output_unexpected", level="warning", result_type=type(result).__name__)
            summary = (current_summary if suppress_free_facts and not conflict_summary
                       else _extract_summary_plain(llm, context_msgs, current_summary))
            rag_ok = persist_records(authoritative_records) and not pending_memory_facts
            grounded_summary, summary_rejections = sanitize_location_grounding(summary)
            grounded_summary, inventory_rejections = sanitize_inventory_grounding(
                grounded_summary, effective_state,
            )
            grounded_summary, npc_rejections = sanitize_npc_identity_grounding(
                grounded_summary, effective_state,
            )
            if summary_rejections or inventory_rejections or npc_rejections:
                memory_rejections = bounded_audit_rows([
                    *memory_rejections,
                    *[
                        {
                            "turn": int(turn),
                            "provenance": "narrative_summary",
                            "reason": "location_region_contradiction",
                            **row,
                        }
                        for row in summary_rejections
                    ],
                    *[
                        {
                            "turn": int(turn),
                            "provenance": "narrative_summary",
                            "reason": "inventory_possession_contradiction",
                            **row,
                        }
                        for row in inventory_rejections
                    ],
                    *[
                        {
                            "turn": int(turn),
                            "provenance": "narrative_summary",
                            "reason": "npc_identity_contradiction",
                            **row,
                        }
                        for row in npc_rejections
                    ],
                ], limit=MAX_MEMORY_REJECTIONS)
            summary = merged_summary(grounded_summary or current_summary)
            if summary or canonical_text:
                _log_event("archivist", "summary_saved_text_fallback", level="info")
                updates = {
                    **memory_state_updates(),
                    "narrative_summary": summary,
                    "rag_persistence_error": None if rag_ok else (
                        event_updates.get("rag_persistence_error")
                        or "Falha ao persistir fatos canônicos."
                    ),
                }
                updates["archivist_last_run"] = turn
                updates["archive_due"] = bool(pending_memory_facts or remaining_npc_memory)
                if conflict_summary:
                    updates["conflict_summary"] = None
                    updates["consumed_conflict_ids"] = (
                        conflict_summary_service.append_consumed_conflict_id(
                            consumed_conflict_ids, conflict_id,
                        )
                    )
                    updates["chronicle"] = append_entry(
                        event_updates.get("chronicle", state.get("chronicle") or []),
                        text=canonical_text, turn=turn, kind="conflict")
                elif duplicate_conflict:
                    updates["conflict_summary"] = None
                    updates["consumed_conflict_ids"] = consumed_conflict_ids
                if narrative_rejections:
                    updates["narrative_rejections"] = []
                if canonical_only and not remaining_npc_memory:
                    updates["memory_fact_policy"] = None
                    updates["memory_canonical_facts"] = []
                return {**event_updates, **updates}
            # Plain-text também falhou — mantém estado atual (mas eventos já processados).
            _log_event("archivist", "both_paths_failed", level="warning")
            return dict(event_updates)

        updates: dict = {}

        # 1. RAG (longo prazo). Em turno de conflito, só o contrato canônico é
        # persistido; a prosa livre não pode reintroduzir fato rejeitado.
        inference_records = [
            make_memory_fact(
                fact,
                provenance="inference",
                source_id=f"archivist:{turn}",
                source_turn=int(turn),
            )
            for fact in (
                [] if suppress_free_facts else result.important_facts
            )
        ]
        records = authoritative_records if (conflict_summary or canonical_only) else [
            *authoritative_records,
            *inference_records,
        ]
        rag_ok = persist_records(records) and not (
            pending_memory_facts or remaining_npc_memory
        )
        updates.update(memory_state_updates())
        updates["rag_persistence_error"] = (
            None if rag_ok else (
                event_updates.get("rag_persistence_error")
                or "Falha ao persistir memória de sessão."))

        # 2. Resumo (curto prazo)
        summary_candidate = (
            current_summary if suppress_free_facts and not conflict_summary
            else result.new_summary
        )
        grounded_summary, summary_rejections = sanitize_location_grounding(
            summary_candidate,
        )
        grounded_summary, inventory_rejections = sanitize_inventory_grounding(
            grounded_summary, effective_state,
        )
        grounded_summary, npc_rejections = sanitize_npc_identity_grounding(
            grounded_summary, effective_state,
        )
        if summary_rejections or inventory_rejections or npc_rejections:
            memory_rejections = bounded_audit_rows([
                *memory_rejections,
                *[
                    {
                        "turn": int(turn),
                        "provenance": "narrative_summary",
                        "reason": "location_region_contradiction",
                        **row,
                    }
                    for row in summary_rejections
                ],
                *[
                    {
                        "turn": int(turn),
                        "provenance": "narrative_summary",
                        "reason": "inventory_possession_contradiction",
                        **row,
                    }
                    for row in inventory_rejections
                ],
                *[
                    {
                        "turn": int(turn),
                        "provenance": "narrative_summary",
                        "reason": "npc_identity_contradiction",
                        **row,
                    }
                    for row in npc_rejections
                ],
            ], limit=MAX_MEMORY_REJECTIONS)
            updates.update(memory_state_updates())
        updates["narrative_summary"] = merged_summary(
            grounded_summary or current_summary,
        )

        if narrative_rejections:
            updates["narrative_rejections"] = []
        if canonical_only and not remaining_npc_memory:
            updates["memory_fact_policy"] = None
            updates["memory_canonical_facts"] = []

        # 3. Crônica do menestrel (prosa) — appenda SOBRE o chronicle já atualizado
        # pelos milestones do event_processor (mesma chave; updates vence no merge).
        base_chron = event_updates.get("chronicle", state.get("chronicle") or [])
        if conflict_summary:
            base_chron = append_entry(
                base_chron, text=canonical_text, turn=turn, kind="conflict")
            updates["conflict_summary"] = None
            updates["consumed_conflict_ids"] = (
                conflict_summary_service.append_consumed_conflict_id(
                    consumed_conflict_ids, conflict_id,
                )
            )
        elif duplicate_conflict:
            updates["conflict_summary"] = None
            updates["consumed_conflict_ids"] = consumed_conflict_ids
        entry = sanitize_meta_preamble(
            (getattr(result, "chronicle_entry", "") or "").strip())
        if entry and not suppress_free_facts and not canonical_only:
            base_chron = append_entry(base_chron, text=entry, turn=turn, kind="prose")
        if base_chron != (event_updates.get("chronicle", state.get("chronicle") or [])):
            updates["chronicle"] = base_chron

        updates["archivist_last_run"] = turn
        updates["archive_due"] = bool(pending_memory_facts or remaining_npc_memory)

        return {**event_updates, **updates}

    except Exception as e:
        _log_event("archivist", "node_failed", level="error", error=type(e).__name__)
        return dict(event_updates)
