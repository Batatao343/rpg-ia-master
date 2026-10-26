"""services/combat_intents.py - intencoes de combate por regex fechada (SPEC-325).

Funcoes puras, sem LLM: a intencao vem de regex ou nome canonico. Fase A expoe o
golpe nao-letal; Fase B (fuga) a abordagem, o abandono de companheiro e o aceite
do sacrificio. Objeto e ordem a aliado entram nas fases C-D.
"""

from __future__ import annotations

import re
import unicodedata

from services.death_flow import NONLETHAL_RE, nonlethal_declared  # noqa: F401

__all__ = [
    "NONLETHAL_RE",
    "abandon_target",
    "accepts_sacrifice",
    "chase_approach",
    "nonlethal_declared",
]

_NEGATION = re.compile(r"\b(?:nao|nunca|jamais|sem|ninguem)\b")


def _fold(text: object) -> str:
    raw = unicodedata.normalize("NFKD", str(text or ""))
    return "".join(c for c in raw if not unicodedata.combining(c)).lower()


def _negated(folded: str, start: int) -> bool:
    """Negacao na mesma oracao, antes do trecho (janela curta, sem cruzar `,`/`;`/`.`)."""
    before = folded[max(0, start - 24) : start]
    clause = re.split(r"[,;.!?]", before)[-1]
    return bool(_NEGATION.search(clause))


# SPEC-325 R10: palavras-chave FECHADAS -> chave de `chase.APPROACH_VIRTUDE`.
_APPROACH_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("correr", re.compile(r"\bcorr(?:o|er|endo|emos)\b")),
    ("desviar", re.compile(r"\bdesvi(?:o|ar|ando|amos)\b")),
    ("rotas", re.compile(r"\brotas?\b")),
    ("atalhos", re.compile(r"\batalhos?\b")),
    ("romper", re.compile(r"\b(?:rompo|romper|rompendo|rompemos)\b")),
    ("obstaculos", re.compile(r"\bobstaculos?\b")),
    ("resistencia", re.compile(r"\b(?:resistencia|resisto|resistir)\b")),
    ("prolongada", re.compile(r"\bprolongad[ao]\b")),
    ("coordenar", re.compile(r"\bcoorden(?:o|ar|amos)\b")),
    ("mobilizar", re.compile(r"\bmobiliz(?:o|ar|amos)\b")),
)


def chase_approach(text: str) -> str | None:
    """Abordagem da fuga declarada no texto (primeira palavra-chave nao negada), ou None."""
    folded = _fold(text)
    best: tuple[int, str] | None = None
    for key, rx in _APPROACH_PATTERNS:
        for m in rx.finditer(folded):
            if _negated(folded, m.start()):
                continue
            if best is None or m.start() < best[0]:
                best = (m.start(), key)
            break
    return best[1] if best else None


# SPEC-325 R12: "deixo/abandono <nome>" (so casa com candidatos reais).
_ABANDON_RE = re.compile(
    r"\b(?:deixo|deixamos|deixar|abandono|abandonamos|abandonar)\b\s+(?:(?:a|o|as|os)\s+)?"
    r"(?P<rest>[^.,;!?]*)"
)


def abandon_target(text: str, candidates: dict[str, str]) -> str | None:
    """Id do candidato abandonado pelo texto (`candidates` = id -> nome), ou None.

    Casa o nome inteiro ou o primeiro nome; negacao e falso positivo ("abandono o
    plano") nao casam porque so os candidatos existem no mapa."""
    if not candidates:
        return None
    folded = _fold(text)
    for m in _ABANDON_RE.finditer(folded):
        if _negated(folded, m.start()):
            continue
        rest = m.group("rest").strip()
        first_pass: list[tuple[str, str]] = [
            (cid, _fold(name).strip()) for cid, name in candidates.items()
        ]
        for cid, name in first_pass:  # nome inteiro primeiro
            if name and re.match(rf"{re.escape(name)}\b", rest):
                return cid
        for cid, name in first_pass:  # depois o primeiro nome
            token = name.split()[0] if name else ""
            if len(token) >= 3 and re.match(rf"{re.escape(token)}\b", rest):
                return cid
    return None


_ACCEPT_RE = re.compile(r"\baceit(?:o|ar|amos)\b")


def accepts_sacrifice(text: str) -> bool:
    """Aceite da oferta de sacrificio (so e consultado com oferta pendente)."""
    folded = _fold(text)
    return any(not _negated(folded, m.start()) for m in _ACCEPT_RE.finditer(folded))
