"""services/prose_guard.py — anti-repetição de prosa (spec polish-prosa).

Funções PURAS (sem LLM) para o narrador: extrair a "abertura" de uma narração,
pegar as últimas aberturas do histórico (injetadas no prompt, R1), detectar
repetição (telemetria R4) e alimentar a invariante R5. Zero mecânica de jogo.
"""
from __future__ import annotations

import logging
import re
from typing import List

_LOG = logging.getLogger("rpg.prose")


def opening(text: str, words: int = 6) -> str:
    """Primeiras `words` palavras normalizadas (minúsculas, sem pontuação) —
    a 'assinatura' de abertura de uma narração."""
    toks = re.findall(r"\w+", (text or "").lower())
    return " ".join(toks[:words])


def ultimas_aberturas(messages, n: int = 2, words: int = 12) -> List[str]:
    """As `n` últimas aberturas de narração (mensagens não-humanas) do histórico,
    com ~`words` palavras cada — para o prompt pedir variação (R1)."""
    out: List[str] = []
    for m in reversed(messages or []):
        content = getattr(m, "content", "")
        if content and getattr(m, "type", "") != "human":
            ab = opening(str(content), words)
            if ab:
                out.append(ab)
            if len(out) >= n:
                break
    return out


def repeats(a: str, b: str, words: int = 6) -> bool:
    """True se `a` e `b` começam com as mesmas `words` palavras (não-vazias)."""
    oa = opening(a, words)
    return bool(oa) and oa == opening(b, words)


def openings_clause(aberturas: List[str]) -> str:
    """Cláusula de prompt (R1): pede para NÃO repetir a estrutura/imagem das
    aberturas recentes. Vazio se não há histórico."""
    if not aberturas:
        return ""
    listadas = " | ".join(f'"{a}…"' for a in aberturas)
    return ("\n    - VARIE A ABERTURA: as últimas narrações começaram assim: "
            f"{listadas}. NÃO comece com estrutura ou imagem parecida; abra diferente.")


def log_if_repeats(new_text: str, prev_text: str, *, where: str = "prose") -> bool:
    """R4: telemetria (não pune) — loga warning se a abertura repete a anterior."""
    if repeats(new_text, prev_text):
        _LOG.warning("Abertura repetida (%s): “%s…”", where, opening(new_text))
        return True
    return False
