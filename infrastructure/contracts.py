"""Contratos síncronos entre o domínio e infraestrutura substituível.

Este módulo deliberadamente não importa psycopg, Supabase, S3 ou FAISS. As
dataclasses são os valores estáveis que adapters locais/hosted compartilham.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from io import BufferedIOBase
from typing import Any, BinaryIO, Literal, Mapping, Protocol
from uuid import UUID


class InfrastructureError(RuntimeError):
    """Erro sanitizável na fronteira de infraestrutura."""


class NotFound(InfrastructureError):
    pass


class Conflict(InfrastructureError):
    pass


class Unauthorized(InfrastructureError):
    pass


class Forbidden(InfrastructureError):
    pass


# SPEC-220 R3: única lista de códigos que uma resposta 401/403/503 de sessão
# pode carregar. Mensagens internas (str(exc)) nunca saem na resposta.
AUTH_ERROR_CODES = frozenset({
    "session_missing", "session_invalid", "csrf_invalid", "origin_denied",
    "captcha_required", "captcha_invalid", "recent_session_required",
    "account_delete_not_requested", "credentials_invalid", "link_invalid_or_expired",
    "signup_failed", "password_reset_failed", "account_deleted", "server_misconfigured",
    # Auth debug 2026-10-18: GoTrue says "e-mail não confirmado" só após a senha conferir
    # (sem enumeração); captcha recusado pelo GoTrue não é falha de credencial.
    "email_not_confirmed",
})
_AUTH_CODE_ALIASES = {
    "sessão ausente": "session_missing", "token ausente": "session_missing",
    "principal ausente": "session_missing",
    "credenciais inválidas": "credentials_invalid",
    "não foi possível criar a conta": "signup_failed",
    "account_deleted_or_invalid_blob_owner": "account_deleted",
    "Origin ausente": "origin_denied", "Origin não permitido": "origin_denied",
    "CSRF inválido": "csrf_invalid",
}


def public_auth_code(exc: BaseException) -> str:
    """Mapeia qualquer erro de sessão para um código público da lista fechada."""
    code = getattr(exc, "code", None) or (str(exc.args[0]) if exc.args else "")
    code = _AUTH_CODE_ALIASES.get(code, code)
    return code if code in AUTH_ERROR_CODES else "session_invalid"


class CsrfError(ValueError):
    """SPEC-220 R10: Origin/CSRF inválido => 403 (o cliente não deve tentar refresh)."""

    def __init__(self, code: str) -> None:
        self.code = code if code in {"csrf_invalid", "origin_denied"} else "csrf_invalid"
        super().__init__(self.code)


class SessionSecretError(ValueError):
    """Segredo de sessão ausente/curto: 503 server_misconfigured, sem mensagem interna."""


class StaleVersion(Conflict):
    pass


class LeaseHeld(Conflict):
    pass


class JobDeferred(InfrastructureError):
    """The handler refuses to run NOW (e.g. a kill switch is off) but the job stays valid:
    the worker re-queues it without consuming an attempt (SPEC-196 F5)."""

    def __init__(self, reason: str, delay_seconds: float = 60.0) -> None:
        super().__init__(reason)
        self.reason = reason
        self.delay_seconds = delay_seconds




@dataclass(frozen=True)
class Principal:
    user_id: UUID
    issuer: str
    subject: str
    local: bool = False


@dataclass(frozen=True)
class StoredGame:
    game_id: UUID
    owner_id: UUID
    schema_version: int
    version: int
    state: dict[str, Any]
    updated_at: datetime


@dataclass(frozen=True)
class MemoryDocument:
    document_id: str
    text: str
    scope: Literal["lore", "rules", "session", "npc", "chronicle"]
    metadata: dict[str, Any] = field(default_factory=dict)
    score: float | None = None


@dataclass(frozen=True)
class MemoryQuery:
    text: str
    scope: Literal["lore", "rules", "session", "npc", "chronicle"]
    principal: Principal | None = None
    game_id: UUID | None = None
    npc_id: str | None = None
    max_visibility: Literal["public", "hidden", "secret"] = "public"
    k: int = 3
    vector: tuple[float, ...] | None = None
    embedding_profile_id: str | None = None


@dataclass(frozen=True)
class MemoryWriteIntent:
    document: MemoryDocument
    principal: Principal | None = None
    game_id: UUID | None = None
    npc_id: str | None = None
    timeline_epoch: int = 0


@dataclass(frozen=True)
class BlobMetadata:
    owner_id: UUID
    game_id: UUID
    content_type: str
    sha256: str
    purpose: str
    size_bytes: int | None = None


@dataclass(frozen=True)
class BlobRef:
    key: str
    sha256: str
    size_bytes: int
    content_type: str


@dataclass(frozen=True)
class JobRequest:
    kind: str
    dedupe_key: str
    payload: dict[str, Any]
    owner_id: UUID | None = None
    game_id: UUID | None = None
    max_attempts: int = 3


@dataclass(frozen=True)
class LeasedJob:
    job_id: UUID
    lease_token: UUID
    request: JobRequest
    attempt: int


@dataclass(frozen=True)
class OperationClaim:
    operation_id: UUID
    lease_token: UUID
    game_id: UUID | None
    base_version: int | None
    request_hash: str


@dataclass(frozen=True)
class RateLimitDecision:
    allowed: bool
    remaining: int
    retry_after_seconds: int


class GameStore(Protocol):
    def create(self, principal: Principal, state: dict[str, Any]) -> StoredGame: ...

    def get(self, principal: Principal, game_id: UUID) -> StoredGame | None: ...

    def list(self, principal: Principal) -> list[StoredGame]: ...

    def save(
        self,
        principal: Principal,
        game_id: UUID,
        expected_version: int,
        state: dict[str, Any],
    ) -> StoredGame: ...

    def delete(self, principal: Principal, game_id: UUID) -> bool: ...


class RuntimeCatalogStore(Protocol):
    def get(
        self,
        namespace: str,
        key: str,
        *,
        owner_id: UUID | None,
        game_id: UUID | None,
    ) -> dict[str, Any] | None: ...

    def list(
        self,
        namespace: str,
        *,
        owner_id: UUID | None,
        game_id: UUID | None,
    ) -> dict[str, dict[str, Any]]: ...

    def put(
        self,
        namespace: str,
        key: str,
        value: dict[str, Any],
        *,
        scope: Literal["global", "user", "game"],
        owner_id: UUID | None,
        game_id: UUID | None,
    ) -> None: ...


class MemoryStore(Protocol):
    def query(self, request: MemoryQuery) -> list[MemoryDocument]: ...

    def stage(self, intent: MemoryWriteIntent) -> None: ...


class BlobStore(Protocol):
    def put(self, key: str, payload: BinaryIO, metadata: BlobMetadata) -> BlobRef: ...

    def open(self, key: str) -> BufferedIOBase: ...

    def signed_url(self, key: str, expires_seconds: int) -> str: ...

    def delete(self, key: str) -> bool: ...


class JobQueue(Protocol):
    def enqueue(self, job: JobRequest) -> UUID: ...

    def lease(self, worker_id: str, kinds: set[str], limit: int) -> list[LeasedJob]: ...

    def complete(self, job_id: UUID, lease_token: UUID, result: dict[str, Any]) -> None: ...

    def fail(self, job_id: UUID, lease_token: UUID, error_code: str) -> None: ...

    # Optional: ``defer(job_id, lease_token, delay_seconds, reason)`` re-queues without
    # consuming an attempt; JobWorker falls back to ``fail`` when an adapter lacks it.


class TurnCoordinator(Protocol):
    def claim(
        self,
        principal: Principal,
        operation_id: UUID,
        *,
        game_id: UUID | None,
        kind: str,
        request_hash: str,
        base_version: int | None,
    ) -> OperationClaim: ...

    def complete(
        self,
        claim: OperationClaim,
        *,
        committed_version: int | None,
        receipt: Mapping[str, Any],
    ) -> dict[str, Any]: ...

    def fail(self, claim: OperationClaim, error_code: str) -> None: ...


class RateLimiter(Protocol):
    def consume(self, key: str, *, limit: int, window_seconds: int) -> RateLimitDecision: ...
    # SPEC-220: adapters também expõem ``peek`` (sem consumir) e ``reset(key)``.


class IdentityVerifier(Protocol):
    def verify(self, credential: str | None) -> Principal: ...




def validate_scope(
    scope: Literal["global", "user", "game"],
    owner_id: UUID | None,
    game_id: UUID | None,
) -> None:
    valid = (
        (scope == "global" and owner_id is None and game_id is None)
        or (scope == "user" and owner_id is not None and game_id is None)
        or (scope == "game" and owner_id is not None and game_id is not None)
    )
    if not valid:
        raise ValueError("combinação inválida de scope/owner_id/game_id")


