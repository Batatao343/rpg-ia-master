"""SPEC-317 R7 — leitura de arquivo de dados com cache de texto por (mtime, tamanho).

O cache guarda o TEXTO, nunca o objeto parseado: cada chamador recebe uma estrutura
nova (``json.loads``), então mutação do resultado não vaza entre turnos nem entre
sessões. Arquivo reescrito (mtime/tamanho mudam) invalida sozinho, inclusive quando
outra instância serverless o gravou. ``RPG_INDEX_CACHE=off`` desliga.
"""

from __future__ import annotations

import json
import os
import threading
from typing import Any

_CACHE: dict[str, tuple[tuple[int, int], str]] = {}
_LOCK = threading.Lock()
_MAX = 32


def _enabled() -> bool:
    return os.environ.get("RPG_INDEX_CACHE", "on").strip().lower() != "off"


def read_text_cached(path: str) -> str:
    """Texto UTF-8 do arquivo; ``OSError`` se não existir/ilegível (como ``open``)."""
    if not _enabled():
        with open(path, encoding="utf-8") as handle:
            return handle.read()
    key = os.path.abspath(path)
    st = os.stat(path)
    stamp = (st.st_mtime_ns, st.st_size)
    with _LOCK:
        hit = _CACHE.get(key)
    if hit is not None and hit[0] == stamp:
        return hit[1]
    with open(path, encoding="utf-8") as handle:
        text = handle.read()
    with _LOCK:
        if len(_CACHE) >= _MAX:
            _CACHE.pop(next(iter(_CACHE)), None)
        _CACHE[key] = (stamp, text)
    return text


def read_json_cached(path: str) -> Any:
    """``json.load`` equivalente, com o texto em cache (objeto novo a cada chamada)."""
    return json.loads(read_text_cached(path))


def clear() -> None:
    with _LOCK:
        _CACHE.clear()
