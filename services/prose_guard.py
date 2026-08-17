"""services/prose_guard.py — anti-repetição de prosa (spec polish-prosa).

Funções PURAS (sem LLM) para o narrador: extrair a "abertura" de uma narração,
pegar as últimas aberturas do histórico (injetadas no prompt, R1), detectar
repetição (telemetria R4) e alimentar a invariante R5. Zero mecânica de jogo.
"""
from __future__ import annotations

import logging
import hashlib
import re
from typing import List

_LOG = logging.getLogger("rpg.prose")

_META_NOUN = (
    r"(?:a\s+|o\s+|uma\s+|um\s+)?"
    r"(?:narrativa|resposta|descrição|texto|trecho|versão|cena)"
)

_META_PREAMBLE = re.compile(
    r"^\s*(?:#{1,6}\s*)?"
    rf"(?:aqui (?:está|vai|segue)\s+{_META_NOUN}[^:\n.!?]{{0,90}}[:.!?\n-]+|"
    rf"abaixo (?:você encontra|segue|está)\s+{_META_NOUN}[^:\n.!?]{{0,90}}[:.!?\n-]+|"
    r"como solicitado[^:\n.!?]{0,90}[:.!?\n-]+|"
    r"(?:narrativa|resposta|descrição)\s*[:\n-]+)",
    flags=re.IGNORECASE,
)

_ENGINE_MARKERS = re.compile(
    r"(?:\[\s*ECOS\s+DO\s+MUNDO\s*\]|\bContexto\s+do\s+local\s*:)",
    flags=re.IGNORECASE,
)

_ECHOED_IMPERATIVE = re.compile(
    r"(?:^|(?<=[.!?])\s+)(?:Descreva|Narre)\b[^.!?]*(?:[.!?]|$)\s*",
    flags=re.IGNORECASE,
)

_NEUTRAL_TRANSITIONS = (
    "A cena encontra outro compasso. ",
    "O momento avança sob nova tensão. ",
    "Por outro ângulo, a situação persiste. ",
    "A paisagem permanece, mas o instante muda. ",
    "O silêncio se rearranja ao seu redor. ",
    "Desta vez, o gesto ganha outro peso. ",
)


def opening(text: str, words: int = 6) -> str:
    """Primeiras `words` palavras normalizadas (minúsculas, sem pontuação) —
    a 'assinatura' de abertura de uma narração."""
    toks = re.findall(r"\w+", (text or "").lower())
    return " ".join(toks[:words])


def sanitize_meta_preamble(text: str) -> str:
    """Remove moldura de assistente no início, preservando a prosa do jogo."""
    cleaned = str(text or "").strip()
    previous = None
    while cleaned and cleaned != previous:
        previous = cleaned
        cleaned = _META_PREAMBLE.sub("", cleaned, count=1).lstrip(" \t\r\n—-:")
    return cleaned.strip()


def sanitize_player_facing(text: str) -> str:
    """Fecha a fronteira motor→jogador sem reescrever conteúdo livre.

    Remove somente o vocabulário fechado usado nas notas internas do motor e
    imperativos de prompt que alguns providers ecoam literalmente.
    """
    cleaned = sanitize_meta_preamble(text)
    cleaned = _ENGINE_MARKERS.sub("", cleaned)
    cleaned = _ECHOED_IMPERATIVE.sub(" ", cleaned)
    cleaned = re.sub(r"[ \t]+", " ", cleaned)
    cleaned = re.sub(r" *\n *", "\n", cleaned)
    cleaned = re.sub(r"\s+([,.;!?])", r"\1", cleaned)
    return cleaned.strip()


_PROTAGONIST_THIRD_PERSON = re.compile(
    r"\b(?:O jogador|O personagem|O herói)\b",
    flags=re.IGNORECASE,
)


def normalize_protagonist_voice(text: str) -> str:
    """Converte somente o sujeito fechado do protagonista para segunda pessoa."""
    return _PROTAGONIST_THIRD_PERSON.sub("Você", str(text or ""))


def contains_engine_marker(text: str) -> bool:
    """True quando uma narração visível ainda contém marcador interno."""
    return bool(_ENGINE_MARKERS.search(str(text or "")))


def vary_repeated_opening(text: str, recent_openings: List[str], *,
                          salt: str = "") -> str:
    """Quebra abertura literalmente repetida com transição neutra e estável.

    A transformação é conservadora: só atua quando seis palavras iniciais são
    iguais às de uma abertura recente, e nunca chama o LLM novamente.
    """
    value = str(text or "").strip()
    recent = [str(item or "").strip() for item in recent_openings if str(item or "").strip()]
    if not value or not any(repeats(value, item) for item in recent):
        return value
    digest = hashlib.sha256(f"{salt}|{value}".encode("utf-8")).digest()
    start = int.from_bytes(digest[:2], "big") % len(_NEUTRAL_TRANSITIONS)
    for offset in range(len(_NEUTRAL_TRANSITIONS)):
        prefix = _NEUTRAL_TRANSITIONS[(start + offset) % len(_NEUTRAL_TRANSITIONS)]
        candidate = prefix + value
        if not any(repeats(candidate, item) for item in recent):
            return candidate
    return _NEUTRAL_TRANSITIONS[start] + value


def remove_rejected_claims(text: str, rejected_terms: List[str]) -> str:
    """Remove frases que afirmam um item/evento rejeitado pelo motor.

    A comparação é literal e case-insensitive; não tenta inferir semântica.
    """
    terms = [str(term).strip().casefold() for term in rejected_terms
             if str(term).strip()]
    if not terms:
        return str(text or "")
    value = str(text or "")
    # Quantias aparecem com frequência em algarismo no structured output e por
    # extenso na prosa ("15" vs. "quinze"). Se o motor rejeitou uma aquisição
    # monetária, descarta o parágrafo inteiro que menciona ouro/moedas para não
    # deixar frases anafóricas como "você guarda a bolsa" sobreviverem.
    if any("ouro" in term or "moeda" in term for term in terms):
        paragraphs = re.split(r"\n\s*\n", value)
        value = "\n\n".join(
            paragraph for paragraph in paragraphs
            if not re.search(r"\b(?:ouro|moedas?)\b", paragraph, re.IGNORECASE)
        )
    chunks = re.split(r"(?<=[.!?])(\s+)", value)
    kept: List[str] = []
    for index in range(0, len(chunks), 2):
        sentence = chunks[index]
        separator = chunks[index + 1] if index + 1 < len(chunks) else ""
        lowered = sentence.casefold()
        if not any(term in lowered for term in terms):
            kept.extend((sentence, separator))
    return "".join(kept).strip()


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
