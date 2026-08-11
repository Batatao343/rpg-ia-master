"""Normalização fechada para referências opcionais vindas de texto livre.

O identificador lógico não é alterado além de ``strip``. Somente valores que
representam ausência são convertidos em ``None``; isso evita materializar
sentinelas de provider (por exemplo, ``"null"``) como entidades reais.
"""

from typing import Optional


_EMPTY_ENTITY_REFS = frozenset({
    "null",
    "none",
    "nil",
    "n/a",
    "undefined",
    "nenhum",
    "ninguém",
    "ninguem",
})


def optional_entity_ref(value: object) -> Optional[str]:
    """Retorna uma referência aparada ou ``None`` para sentinelas de ausência."""
    if value is None:
        return None
    text = str(value).strip()
    if not text or text.casefold() in _EMPTY_ENTITY_REFS:
        return None
    return text
