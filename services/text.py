"""Texto sem acento/caixa: o unico ``fold`` do produto (SPEC-378 E1)."""

from __future__ import annotations

import unicodedata
from typing import Literal


def fold(
    text: object,
    *,
    case: Literal["casefold", "lower"] = "casefold",
    strip: bool = False,
    collapse: bool = False,
) -> str:
    """NFKD, sem marcas combinantes, caixa dobrada; ``collapse`` = ``" ".join(s.split())``."""
    nfkd = unicodedata.normalize("NFKD", str(text or ""))
    plain = "".join(c for c in nfkd if not unicodedata.combining(c))
    out = plain.casefold() if case == "casefold" else plain.lower()
    if strip:
        out = out.strip()
    if collapse:
        out = " ".join(out.split())
    return out
