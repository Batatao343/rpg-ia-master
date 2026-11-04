"""SPEC-397 R3: frase fixa que a abertura narrada de um combate ganha quando há emboscada.

Determinística (voz "você", sem número nem id); a mecânica (`_opening_initiator`) não muda."""

from __future__ import annotations

_LINES = {
    "ambush": "O inimigo se antecipa e ataca primeiro: você foi pego de surpresa.",
    "ambush_negated_vigilia": "Você percebe a emboscada a tempo e não é pego de surpresa.",
}


def line_for(reason: str | None) -> str:
    return _LINES.get(str(reason or ""), "")


def with_ambush(narrative: str, reason: str | None) -> str:
    """Anexa a frase da emboscada à narração de abertura (nada, se não houve emboscada)."""
    line = line_for(reason)
    if not line:
        return narrative
    return f"{narrative.rstrip()}\n\n{line}" if narrative.strip() else line
