"""services/prologue_token.py — selo HMAC do cenário do prólogo (SPEC-351 R15).

O cenário vai ao cliente e volta no `/game/new`. Para que o servidor saiba que
o NPC pessoal (e as âncoras de trama) que voltam são os que ELE gerou, o
`/game/prologue` devolve um token = HMAC (`RPG_SESSION_SECRET`) sobre o JSON
canônico do payload + dono + instante. Token ausente, vencido, de outro dono ou
que não confere → o chamador trata o NPC pessoal como só local; nunca levanta.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import os
import time

TOKEN_MAX_AGE = 3600
_VERSION = "v1"
_MIN_SECRET = 32


def _secret() -> bytes | None:
    value = os.getenv("RPG_SESSION_SECRET", "")
    return value.encode() if len(value) >= _MIN_SECRET else None


def _canonical(payload: dict) -> str:
    return json.dumps(
        payload, sort_keys=True, ensure_ascii=False, separators=(",", ":"), default=str
    )


def _digest(secret: bytes, payload: dict, owner: str, issued_at: int) -> str:
    message = f"{_VERSION}\n{owner}\n{issued_at}\n{_canonical(payload)}".encode()
    return hmac.new(secret, message, hashlib.sha256).hexdigest()


def sign_scenario(payload: dict, owner: str, *, now: int | None = None) -> str:
    """Token `v1.<epoch>.<hmac>`; `""` se não há `RPG_SESSION_SECRET` utilizável (D8)."""
    secret = _secret()
    if secret is None:
        return ""
    issued_at = int(time.time()) if now is None else int(now)
    return f"{_VERSION}.{issued_at}.{_digest(secret, payload, str(owner), issued_at)}"


def verify_scenario(
    token: str | None,
    payload: dict,
    owner: str,
    *,
    max_age: int = TOKEN_MAX_AGE,
    now: int | None = None,
) -> bool:
    secret = _secret()
    if secret is None or not token or len(token) > 1024:
        return False
    try:
        version, raw_at, signature = token.split(".")
        issued_at = int(raw_at)
    except ValueError:
        return False
    if version != _VERSION:
        return False
    current = int(time.time()) if now is None else int(now)
    if not 0 <= current - issued_at <= max_age:
        return False
    expected = _digest(secret, payload, str(owner), issued_at)
    return hmac.compare_digest(expected, signature)
