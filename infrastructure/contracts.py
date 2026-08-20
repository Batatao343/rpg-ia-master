"""Contratos síncronos entre o domínio e infraestrutura substituível.

Este módulo deliberadamente não importa psycopg, Supabase, S3 ou FAISS. As
dataclasses são os valores estáveis que adapters locais/hosted compartilham.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from io import BufferedIOBase
from typing import Any, BinaryIO, Literal, Mapping, Protocol, Sequence
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


class StaleVersion(Conflict):
    pass


class LeaseHeld(Conflict):
    pass


class PersistenceUnavailable(InfrastructureError):
    pass


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


class IdentityVerifier(Protocol):
    def verify(self, credential: str | None) -> Principal: ...


def ensure_binary_stream(payload: BinaryIO) -> BinaryIO:
    if not hasattr(payload, "read"):
        raise TypeError("payload precisa ser um stream binário")
    return payload


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


def require_unique_document_ids(documents: Sequence[MemoryDocument]) -> None:
    ids = [document.document_id for document in documents]
    if len(ids) != len(set(ids)):
        raise Conflict("document_id duplicado")
