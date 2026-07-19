"""
agents/archivist.py
Gerencia a Memória de Curto (Resumo) e Longo Prazo (RAG) da sessão.
"""
from typing import List
from langchain_core.messages import SystemMessage
from pydantic import BaseModel, Field, field_validator
from llm_setup import get_llm, ModelTier
from rag import add_memory_to_session
from services.chronicle import append_entry
from services.event_processor import process_pending_events
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
        for item in v:
            if isinstance(item, str):
                s = item.strip()
            elif isinstance(item, dict):
                s = str(item.get("content") or item.get("fato") or item.get("fact")
                        or item.get("desc") or item.get("text")
                        or "; ".join(f"{k}: {val}" for k, val in item.items())).strip()
            else:
                s = str(item).strip()
            if s:
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


def _should_archive(state: GameState, turn: int) -> bool:
    """
    Cadência do arquivista: só roda o LLM em EVENTO RELEVANTE (flag archive_due, setada por
    combate/viagem/descanso/NPC/loot) OU a cada ~10 turnos. Exploração trivial não dispara.
    """
    if state.get("archive_due"):
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
    if not _should_archive(state, turn):
        return {"archive_due": False, **event_updates}  # turno trivial: pula o LLM do arquivista

    current_summary = state.get("narrative_summary", "A aventura segue.")
    context_msgs = messages[-6:] if len(messages) > 6 else messages

    llm = get_llm(temperature=0.3, tier=ModelTier.SMART)

    sys_msg = SystemMessage(content=f"""
    <ROLE>Memory Manager do RPG</ROLE>

    <INPUTS>
    1. Resumo Anterior: "{current_summary}"
    2. Histórico Recente: (Ver mensagens abaixo)
    </INPUTS>

    <TAREFA>
    1. ATUALIZAR O RESUMO: Escreva um novo parágrafo que combine o resumo anterior com os novos eventos recentes. Mantenha foco no "Aqui e Agora".
    2. EXTRAIR FATOS (LONG TERM): Identifique fatos cruciais que devem ser lembrados para sempre e salvos no banco de dados.
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
            summary = _extract_summary_plain(llm, context_msgs, current_summary)
            if summary:
                print("📝 [ARCHIVIST] narrative_summary salvo via fallback de texto.")
                return {"narrative_summary": summary, "archivist_last_run": turn,
                        "archive_due": False, **event_updates}
            # Plain-text também falhou — mantém estado atual (mas eventos já processados).
            print("⚠️ [ARCHIVIST] Ambos os caminhos falharam. Estado mantido.")
            return dict(event_updates)

        updates: dict = {}

        # 1. RAG (longo prazo)
        if result.important_facts:
            add_memory_to_session(game_id, result.important_facts)
            print(f"📚 [ARCHIVIST] Fatos: {result.important_facts}")

        # 2. Resumo (curto prazo)
        updates["narrative_summary"] = result.new_summary

        # 3. Crônica do menestrel (prosa) — appenda SOBRE o chronicle já atualizado
        # pelos milestones do event_processor (mesma chave; updates vence no merge).
        entry = (getattr(result, "chronicle_entry", "") or "").strip()
        if entry:
            base_chron = event_updates.get("chronicle", state.get("chronicle") or [])
            updates["chronicle"] = append_entry(base_chron, text=entry, turn=turn, kind="prose")

        updates["archivist_last_run"] = turn
        updates["archive_due"] = False

        return {**event_updates, **updates}

    except Exception as e:
        print(f"⚠️ Erro no Arquivista: {e}")
        return dict(event_updates)
