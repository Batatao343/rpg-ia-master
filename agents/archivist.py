"""
agents/archivist.py
Gerencia a Memória de Curto (Resumo) e Longo Prazo (RAG) da sessão.
"""
import re
import inspect
from typing import List
from langchain_core.messages import SystemMessage
from pydantic import BaseModel, Field, field_validator
from llm_setup import get_llm, ModelTier
from rag import add_memory_to_session, add_npc_memory
from services.chronicle import append_entry
from services import conflict_summary as conflict_summary_service
from services.event_processor import process_pending_events
from services.memory_retry import normalize_pending_npc_memory
from services.memory_provenance import (
    MAX_MEMORY_PROMOTIONS,
    MAX_MEMORY_REJECTIONS,
    bounded_audit_rows,
    commit_memory_facts,
    make_memory_fact,
    memory_metadata,
    normalize_memory_facts,
    validate_memory_fact,
)
from services.prose_guard import sanitize_meta_preamble
from services.context_builder import render_event
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


def _extract_summary_plain(llm, context_msgs: list, current_summary: str) -> str:
    """Fallback plain-text: pede só o resumo sem JSON schema. Retorna string ou ''."""
    try:
        res = llm.invoke([
            SystemMessage(content=(
                f"Resumo anterior: \"{current_summary}\"\n\n"
                "Com base nas mensagens abaixo, escreva UM parágrafo (máx. 5 frases) "
                "resumindo a situação atual do herói. Só o texto, sem JSON, sem títulos."
            ))
        ] + context_msgs)
        text = getattr(res, "content", "") or ""
        if isinstance(text, list):
            text = " ".join(p.get("text", "") if isinstance(p, dict) else str(p) for p in text)
        return text.strip()
    except Exception as e:
        print(f"⚠️ [ARCHIVIST] Fallback texto falhou: {e}")
        return ""


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
        print(f"⚠️ [ARCHIVIST] Persistência RAG falhou: {exc}")
        return False
    print(f"📚 [ARCHIVIST] Fatos: {texts}")
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
        or state.get("pending_memory_facts")
        or state.get("pending_npc_memory")
    ):
        return True
    last = int(state.get("archivist_last_run", 0) or 0)
    return (turn - last) >= _ARCHIVE_EVERY


def archive_node(state: GameState):
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
    event_updates = process_pending_events(state)

    turn = state.get("world", {}).get("turn_count", 0)
    prior_event_ids = {
        str(event.get("event_id"))
        for event in (state.get("event_log") or [])
        if isinstance(event, dict) and event.get("event_id")
    }
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
        if retry_records and not _persist_memory_records(game_id, retry_records):
            return {
                **event_updates,
                "archive_due": True,
                "memory_facts": memory_facts,
                "pending_memory_facts": retry_records,
                "memory_rejections": memory_rejections,
                "memory_promotions": memory_promotions,
                "rag_persistence_error": "Falha ao persistir memória de sessão pendente.",
            }
        memory_facts, promoted = commit_memory_facts(memory_facts, retry_records)
        if promoted:
            memory_promotions = bounded_audit_rows([
                *memory_promotions,
                {"turn": int(turn), "count": promoted, "reason": "canonical_source"},
            ], limit=MAX_MEMORY_PROMOTIONS)
        pending_memory_facts = []
        event_updates = {
            **event_updates,
            "memory_facts": memory_facts,
            "pending_memory_facts": [],
            "memory_rejections": memory_rejections,
            "memory_promotions": memory_promotions,
            "rag_persistence_error": None,
        }
        effective_state = {**state, **event_updates}

    # Retry operation-scoped da memória vetorial de NPC. Cada sucesso sai da
    # fila imediatamente; falhas permanecem sem que uma interação nova ou um
    # persist([]) global possa mascará-las.
    pending_npc_memory = normalize_pending_npc_memory(
        state.get("pending_npc_memory")
    )
    npc_retry_committed = False
    if pending_npc_memory:
        remaining_npc_memory = []
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
                print(f"⚠️ [ARCHIVIST] Retry de memória NPC falhou: {exc}")
                ok = False
            if not ok:
                remaining_npc_memory.append(write)
        event_updates = {
            **event_updates,
            "pending_npc_memory": remaining_npc_memory,
        }
        if remaining_npc_memory:
            waiting_ids = ", ".join(dict.fromkeys(
                write["npc_id"] for write in remaining_npc_memory
            ))
            return {
                **event_updates,
                "archive_due": True,
                "memory_fact_policy": (
                    state.get("memory_fact_policy") or "canonical_only"
                ),
                "memory_canonical_facts": list(
                    state.get("memory_canonical_facts") or []
                ),
                "rag_persistence_error": (
                    state.get("rag_persistence_error")
                    or f"Falha ao persistir memória de {waiting_ids}."
                ),
            }
        npc_retry_committed = True
        event_updates["rag_persistence_error"] = None

    from services.memory_summary import compact_summary
    current_summary = compact_summary(
        state.get("narrative_summary", "A aventura segue."))
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
    prior_rag_error = (
        None if npc_retry_committed else state.get("rag_persistence_error")
    )
    if canonical_only and prior_rag_error and not authoritative_records:
        # ``persist([])`` é no-op, não um commit. Em especial, uma falha prévia
        # do índice de NPC chega aqui com canonical_only e sem fatos globais:
        # não podemos apagar o erro nem confirmar o archive sem qualquer write.
        return {
            **event_updates,
            "archive_due": True,
            "memory_fact_policy": memory_fact_policy,
            "memory_canonical_facts": policy_facts,
            "rag_persistence_error": prior_rag_error,
        }
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
            pending_memory_facts = normalize_memory_facts(
                [*pending_memory_facts, *to_write], pending=True,
            )
            return False
        memory_facts = prospective
        pending_memory_facts = []
        if promoted:
            memory_promotions = bounded_audit_rows([
                *memory_promotions,
                {"turn": int(turn), "count": promoted, "reason": "canonical_source"},
            ], limit=MAX_MEMORY_PROMOTIONS)
        return True

    llm = get_llm(temperature=0.3, tier=ModelTier.SMART)

    sys_msg = SystemMessage(content=f"""
    <ROLE>Memory Manager do RPG</ROLE>

    <INPUTS>
    1. Resumo Anterior: "{current_summary}"
    2. Histórico Recente: (Ver mensagens abaixo)
    3. Fatos canônicos do último conflito: "{canonical_text or 'nenhum'}"
    </INPUTS>

    <TAREFA>
    1. ATUALIZAR O RESUMO: Escreva um novo parágrafo que combine o resumo anterior com os novos eventos recentes. Mantenha foco no "Aqui e Agora".
    2. EXTRAIR FATOS (LONG TERM): Identifique fatos cruciais que devem ser lembrados para sempre e salvos no banco de dados.
       Os fatos canônicos do conflito são AUTORIDADE: nunca os reverta, amplie ou contradiga.
    3. CRÔNICA DO MENESTREL: se um feito digno de canção ocorreu, escreva 'chronicle_entry' como um mini-parágrafo narrado por um bardo (3ª pessoa, evocativo). Caso contrário, deixe vazio ('').
       NÃO registre mortes, conquistas de locais ou missões concluídas como fato seco (o registro oficial já existe); escreva apenas a cor narrativa, ou deixe vazio.

    Se nada grandioso aconteceu, 'important_facts' deve ser [] (vazio).
    """)

    try:
        archivist_llm = llm.with_structured_output(MemoryUpdate)
        result = archivist_llm.invoke([sys_msg] + context_msgs)

        if not isinstance(result, MemoryUpdate):
            # Structured output falhou (Gemini retornou None ou tipo inesperado).
            # Fallback: plain-text para garantir ao menos o narrative_summary.
            print(f"⚠️ [ARCHIVIST] Structured output retornou {type(result).__name__}. "
                  "Ativando fallback de texto (fatos/crônica perdidos neste turno)...")
            summary = (current_summary if suppress_free_facts and not conflict_summary
                       else _extract_summary_plain(llm, context_msgs, current_summary))
            rag_ok = persist_records(authoritative_records)
            summary = merged_summary(summary)
            if summary or canonical_text:
                print("📝 [ARCHIVIST] narrative_summary salvo via fallback de texto.")
                updates = {
                    **memory_state_updates(),
                    "narrative_summary": summary,
                    "rag_persistence_error": None if rag_ok else "Falha ao persistir fatos canônicos.",
                }
                if not rag_ok and (conflict_summary or canonical_only):
                    # O contrato canônico só pode ser consumido depois que sua
                    # memória durável existe. Mantém a fila para retry.
                    updates["archive_due"] = True
                    if conflict_summary:
                        updates["conflict_summary"] = conflict_summary
                    elif duplicate_conflict:
                        updates["conflict_summary"] = None
                        updates["consumed_conflict_ids"] = consumed_conflict_ids
                    if canonical_only:
                        updates["memory_fact_policy"] = memory_fact_policy
                        updates["memory_canonical_facts"] = policy_facts
                    return {**event_updates, **updates}
                updates["archivist_last_run"] = turn
                updates["archive_due"] = bool(pending_memory_facts)
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
                if canonical_only:
                    updates["memory_fact_policy"] = None
                    updates["memory_canonical_facts"] = []
                return {**event_updates, **updates}
            # Plain-text também falhou — mantém estado atual (mas eventos já processados).
            print("⚠️ [ARCHIVIST] Ambos os caminhos falharam. Estado mantido.")
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
        rag_ok = persist_records(records)
        updates.update(memory_state_updates())
        updates["rag_persistence_error"] = (
            None if rag_ok else "Falha ao persistir memória de sessão.")

        # 2. Resumo (curto prazo)
        updates["narrative_summary"] = merged_summary(
            current_summary if suppress_free_facts and not conflict_summary
            else result.new_summary)

        if not rag_ok and (conflict_summary or canonical_only):
            # Não confirma o turno nem cria Crônica antes do commit durável.
            # `archive_due=True` e o resumo canônico preservado tornam o retry
            # explícito no próximo archivist.
            updates["archive_due"] = True
            if conflict_summary:
                updates["conflict_summary"] = conflict_summary
            elif duplicate_conflict:
                updates["conflict_summary"] = None
                updates["consumed_conflict_ids"] = consumed_conflict_ids
            if canonical_only:
                updates["memory_fact_policy"] = memory_fact_policy
                updates["memory_canonical_facts"] = policy_facts
            return {**event_updates, **updates}

        if narrative_rejections:
            updates["narrative_rejections"] = []
        if canonical_only:
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
        updates["archive_due"] = bool(pending_memory_facts)

        return {**event_updates, **updates}

    except Exception as e:
        print(f"⚠️ Erro no Arquivista: {e}")
        return dict(event_updates)
