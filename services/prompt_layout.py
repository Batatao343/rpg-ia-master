"""SPEC-317 R9 — ordem do prompt: instruções estáticas primeiro, estado dinâmico por último.

Provedores com cache de prefixo (DeepSeek, blocos de 64 tokens) só reaproveitam o início
IDÊNTICO do prompt. Os prompts do narrador, do NPC e do router começavam pelo cabeçalho
dinâmico (local, momento, NPCs...), então o prefixo nunca batia. Aqui cada prompt é
descrito como uma lista ordenada de pedaços ``(texto, estático)``:

- ``off`` (default): concatena na ordem original => byte a byte igual ao prompt de antes;
- ``on``: estáticos primeiro (na ordem relativa original), dinâmicos depois.

Só a ORDEM muda; nenhum texto é criado ou removido (testado por multiset de linhas).
"""

from __future__ import annotations

import os
from collections.abc import Sequence

Part = tuple[str, bool]

# Rotulo fixo que abre o bloco dinamico em static-first: separa "regras" de "estado do turno"
# (as clausulas dinamicas que antes viviam dentro das instrucoes vem depois dele).
DYNAMIC_LABEL = "[ESTADO E CONTEXTO DESTE TURNO - as regras acima continuam valendo]"


def static_first_enabled() -> bool:
    """``RPG_PROMPT_STATIC_FIRST=on|off`` (default ``off`` até medir ``cache_hit_ratio``)."""
    return os.environ.get("RPG_PROMPT_STATIC_FIRST", "off").strip().lower() == "on"


def compose(parts: Sequence[Part], *, static_first: bool | None = None) -> str:
    """Junta os pedaços; ``static_first=None`` lê a flag do ambiente."""
    if static_first is None:
        static_first = static_first_enabled()
    if not static_first:
        return "".join(text for text, _static in parts)
    statics = "".join(text for text, is_static in parts if is_static)
    dynamics = "".join(text for text, is_static in parts if not is_static)
    nl = chr(10)
    return nl.join([statics.strip(nl), "", DYNAMIC_LABEL, dynamics.strip(nl), ""])
