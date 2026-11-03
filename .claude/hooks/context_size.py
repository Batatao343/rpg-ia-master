"""UserPromptSubmit — SPEC-386 R8: lembra de /compact quando a sessão principal fica grande.

Lê só a cauda do transcrito (último `usage` de assistant). Contexto = input +
cache_read + cache_creation. Acima de LIMIT avisa uma vez a cada STEP tokens de
crescimento (estado em arquivo temporário por sessão). Subagente: não faz nada.
"""

from __future__ import annotations

import json
import os
import sys
import tempfile

LIMIT = 350_000
STEP = 100_000
TAIL_BYTES = 512_000


def last_context_tokens(transcript: str) -> int:
    with open(transcript, "rb") as fh:
        fh.seek(0, os.SEEK_END)
        size = fh.tell()
        fh.seek(max(0, size - TAIL_BYTES))
        tail = fh.read().decode("utf-8", errors="ignore").splitlines()
    for line in reversed(tail):
        if '"usage"' not in line:
            continue
        try:
            usage = json.loads(line).get("message", {}).get("usage") or {}
        except ValueError:
            continue
        total = sum(
            int(usage.get(k) or 0)
            for k in ("input_tokens", "cache_read_input_tokens", "cache_creation_input_tokens")
        )
        if total:
            return total
    return 0


def main() -> None:
    data = json.loads(sys.stdin.buffer.read().decode("utf-8"))
    if data.get("agent_id"):
        return
    transcript = data.get("transcript_path") or ""
    if not transcript or not os.path.isfile(transcript):
        return
    tokens = last_context_tokens(transcript)
    if tokens < LIMIT:
        return
    state = os.path.join(tempfile.gettempdir(), f"rpg-ctx-{data.get('session_id', 'x')}.txt")
    try:
        with open(state, encoding="utf-8") as fh:
            warned = int(fh.read().strip() or 0)
    except (OSError, ValueError):
        warned = 0
    if tokens < warned + STEP and warned:
        return
    with open(state, "w", encoding="utf-8") as fh:
        fh.write(str(tokens))
    k = tokens // 1000
    msg = (
        f"Sessão com ~{k} K tokens de contexto por turno. Regra do CLAUDE.md: /compact <estado> "
        "no próximo marco (spec pousada, onda fechada) ou handoff em arquivo + /clear."
    )
    print(
        json.dumps(
            {
                "systemMessage": msg,
                "hookSpecificOutput": {
                    "hookEventName": "UserPromptSubmit",
                    "additionalContext": msg,
                },
            }
        )
    )


if __name__ == "__main__":
    try:
        main()
    except Exception:  # silent-ok: hook nunca derruba a sessão
        pass
