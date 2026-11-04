"""services/leak_phrases.py — frases que nunca aparecem em texto público (SPEC-348/350).

Fonte: `data/world/leak_phrases.json` (dobradas: minúsculas, sem acento) + as
assinaturas de `secret_signatures` para os grupos `arauto` e `pacto`. Consumido
pelo lint de tramas (produção) e por `tests/test_spec348_leaks.py`.
"""

from __future__ import annotations

import json
import os
from functools import lru_cache

from services import text as _text

LEAK_PHRASES_PATH = os.path.join("data", "world", "leak_phrases.json")
_DERIVED = {"arauto": "arauto_identidade", "pacto": "pacto_valerius"}


def fold(text: object) -> str:
    return _text.fold(text)


@lru_cache(maxsize=1)
def leak_phrases() -> dict[str, list[str]]:
    from services.secret_signatures import SECRET_SIGNATURES

    try:
        with open(LEAK_PHRASES_PATH, encoding="utf-8") as f:
            raw = json.load(f)
    except (OSError, ValueError):
        raw = {}
    out = {k: [fold(p) for p in v] for k, v in raw.items() if not k.startswith("_")}
    for group, sig in _DERIVED.items():
        out.setdefault(group, [])
        out[group] += [fold(s) for s in SECRET_SIGNATURES.get(sig, [])]
    return out


def all_phrases() -> list[str]:
    return [p for ph in leak_phrases().values() for p in ph]
