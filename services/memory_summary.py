"""Limites determinísticos do resumo de curto prazo.

Detalhes duráveis pertencem ao ledger/RAG; o resumo existe para manter o aqui e
agora dentro de um budget previsível, sem nova chamada de LLM.
"""
from __future__ import annotations

import re

NARRATIVE_SUMMARY_MAX_CHARS = 1200


def compact_summary(value: object,
                    max_chars: int = NARRATIVE_SUMMARY_MAX_CHARS) -> str:
    """Mantém o final (mais recente) e tenta iniciar numa fronteira de frase."""
    text = str(value or "")
    if len(text) <= max_chars:
        return text
    tail = text[-(max_chars - 2):]
    boundary = re.search(r"(?<=[.!?])\s+", tail[: max_chars // 4])
    if boundary:
        tail = tail[boundary.end():]
    return f"… {tail}"[-max_chars:]
