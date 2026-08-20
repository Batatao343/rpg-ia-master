"""Sessões backend-only, proteção CSRF/Origin e principal autenticado.

O browser nunca recebe responsabilidade de persistir bearer tokens: access e
refresh ficam em cookies HttpOnly e o CSRF é um token opaco separado.
"""

from __future__ import annotations

import hashlib
import hmac
import secrets
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Protocol
from urllib.parse import urlsplit
from uuid import UUID

from infrastructure.contracts import Principal, Unauthorized


ACCESS_COOKIE = "rpg_access"
REFRESH_COOKIE = "rpg_refresh"
CSRF_COOKIE = "rpg_csrf"


@dataclass(frozen=True)
class SessionTokens:
    access_token: str
    refresh_token: str
    expires_at: datetime
    user_id: UUID


class IdentityProvider(Protocol):
    def login(self, email: str, password: str) -> SessionTokens: ...
    def refresh(self, refresh_token: str) -> SessionTokens: ...
    def logout(self, access_token: str) -> None: ...
    def verify(self, access_token: str) -> Principal: ...


class CsrfSigner:
    def __init__(self, secret: str) -> None:
        if len(secret) < 32:
            raise ValueError("RPG_SESSION_SECRET precisa ter ao menos 32 caracteres")
        self._secret = secret.encode("utf-8")

    def issue(self) -> str:
        nonce = secrets.token_urlsafe(24)
        signature = hmac.new(self._secret, nonce.encode(), hashlib.sha256).hexdigest()
        return f"{nonce}.{signature}"

    def verify(self, token: str | None) -> bool:
        if not token or "." not in token:
            return False
        nonce, signature = token.rsplit(".", 1)
        expected = hmac.new(self._secret, nonce.encode(), hashlib.sha256).hexdigest()
        return hmac.compare_digest(signature, expected)


def validate_mutation_request(
    *,
    cookie_token: str | None,
    header_token: str | None,
    origin: str | None,
    allowed_origins: set[str],
    signer: CsrfSigner,
) -> None:
    if not origin:
        raise Unauthorized("Origin ausente")
    normalized = f"{urlsplit(origin).scheme}://{urlsplit(origin).netloc}"
    if normalized not in allowed_origins:
        raise Unauthorized("Origin não permitido")
    if not cookie_token or not header_token or not hmac.compare_digest(cookie_token, header_token):
        raise Unauthorized("CSRF inválido")
    if not signer.verify(cookie_token):
        raise Unauthorized("CSRF inválido")


def cookie_settings(*, secure: bool, refresh: bool = False) -> dict[str, object]:
    return {
        "httponly": True,
        "secure": secure,
        "samesite": "strict" if refresh else "lax",
        "path": "/auth/refresh" if refresh else "/",
    }


def principal_from_session(provider: IdentityProvider, access_token: str | None) -> Principal:
    if not access_token:
        raise Unauthorized("sessão ausente")
    principal = provider.verify(access_token)
    if not principal.subject or principal.user_id != UUID(principal.subject):
        raise Unauthorized("subject inválido")
    return principal


def utc_now() -> datetime:
    return datetime.now(UTC)
