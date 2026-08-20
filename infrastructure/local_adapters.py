"""Adapters locais determinísticos usados por legacy e pela suíte offline."""

from __future__ import annotations

import hashlib
import io
import json
import os
import tempfile
import threading
import time
from collections import deque
from copy import deepcopy
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path, PurePosixPath
from typing import Any, Callable
from urllib.parse import quote
from uuid import UUID, uuid4

from infrastructure.contracts import (
    BlobMetadata,
    BlobRef,
    Conflict,
    Forbidden,
    JobRequest,
    LeaseHeld,
    LeasedJob,
    MemoryDocument,
    MemoryQuery,
    MemoryWriteIntent,
    NotFound,
    OperationClaim,
    Principal,
    RateLimitDecision,
    StaleVersion,
    StoredGame,
    Unauthorized,
    validate_scope,
)


def _replace_with_retry(source: str | Path, destination: str | Path,
                        *, attempts: int = 6) -> None:
    """Tolera locks efêmeros de antivírus/OneDrive sem perder atomicidade."""
    last_error: PermissionError | None = None
    for attempt in range(attempts):
        try:
            os.replace(source, destination)
            return
        except PermissionError as exc:
            last_error = exc
            if attempt + 1 < attempts:
                time.sleep(0.01 * (2 ** attempt))
    assert last_error is not None
    raise last_error


def _atomic_json(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump(value, handle, ensure_ascii=False, sort_keys=True)
            handle.flush()
            os.fsync(handle.fileno())
        _replace_with_retry(temporary, path)
    except BaseException:
        try:
            os.unlink(temporary)
        except OSError:
            pass
        raise


class FileGameStore:
    """Store de contrato em diretório isolado.

    O adapter de compatibilidade dos saves históricos continua em
    ``persistence.py``; este formato envelopado é usado somente por runtimes
    explicitamente configurados e testes de porta.
    """

    def __init__(
        self,
        root: str | Path,
        *,
        schema_version: int = 1,
        encode: Callable[[dict[str, Any]], dict[str, Any]] = deepcopy,
        decode: Callable[[dict[str, Any]], dict[str, Any]] = deepcopy,
    ) -> None:
        self.root = Path(root).resolve()
        self.schema_version = schema_version
        self._encode = encode
        self._decode = decode
        self._lock = threading.RLock()

    def _path(self, game_id: UUID) -> Path:
        return self.root / f"{game_id}.json"

    def _read(self, game_id: UUID) -> dict[str, Any] | None:
        path = self._path(game_id)
        if not path.exists():
            return None
        return json.loads(path.read_text(encoding="utf-8"))

    def _stored(self, row: dict[str, Any]) -> StoredGame:
        return StoredGame(
            game_id=UUID(row["game_id"]),
            owner_id=UUID(row["owner_id"]),
            schema_version=int(row["schema_version"]),
            version=int(row["version"]),
            state=self._decode(row["state"]),
            updated_at=datetime.fromisoformat(row["updated_at"]),
        )

    def create(self, principal: Principal, state: dict[str, Any]) -> StoredGame:
        game_id = UUID(str(state["game_id"]))
        with self._lock:
            if self._path(game_id).exists():
                raise Conflict("game_id já existe")
            now = datetime.now(UTC)
            row = {
                "game_id": str(game_id),
                "owner_id": str(principal.user_id),
                "schema_version": self.schema_version,
                "version": 1,
                "updated_at": now.isoformat(),
                "state": self._encode(state),
            }
            _atomic_json(self._path(game_id), row)
            return self._stored(row)

    def get(self, principal: Principal, game_id: UUID) -> StoredGame | None:
        with self._lock:
            row = self._read(game_id)
            if not row or row["owner_id"] != str(principal.user_id):
                return None
            return self._stored(row)

    def list(self, principal: Principal) -> list[StoredGame]:
        with self._lock:
            rows: list[StoredGame] = []
            for path in self.root.glob("*.json") if self.root.exists() else ():
                try:
                    row = json.loads(path.read_text(encoding="utf-8"))
                except (OSError, ValueError):
                    continue
                if row.get("owner_id") == str(principal.user_id):
                    rows.append(self._stored(row))
            return sorted(rows, key=lambda item: item.updated_at, reverse=True)

    def save(
        self,
        principal: Principal,
        game_id: UUID,
        expected_version: int,
        state: dict[str, Any],
    ) -> StoredGame:
        with self._lock:
            row = self._read(game_id)
            if not row or row["owner_id"] != str(principal.user_id):
                raise NotFound("campanha não encontrada")
            if int(row["version"]) != expected_version:
                raise StaleVersion("versão confirmada divergiu")
            row["version"] = expected_version + 1
            row["updated_at"] = datetime.now(UTC).isoformat()
            row["state"] = self._encode(state)
            _atomic_json(self._path(game_id), row)
            return self._stored(row)

    def delete(self, principal: Principal, game_id: UUID) -> bool:
        with self._lock:
            row = self._read(game_id)
            if not row or row["owner_id"] != str(principal.user_id):
                return False
            self._path(game_id).unlink(missing_ok=True)
            return True


class JsonRuntimeCatalogStore:
    def __init__(self, path: str | Path) -> None:
        self.path = Path(path).resolve()
        self._lock = threading.RLock()

    def _load(self) -> dict[str, dict[str, Any]]:
        if not self.path.exists():
            return {}
        try:
            value = json.loads(self.path.read_text(encoding="utf-8"))
            return value if isinstance(value, dict) else {}
        except (OSError, ValueError):
            return {}

    @staticmethod
    def _scope_key(owner_id: UUID | None, game_id: UUID | None) -> str:
        if game_id is not None:
            return f"game:{owner_id}:{game_id}"
        if owner_id is not None:
            return f"user:{owner_id}"
        return "global"

    def get(
        self,
        namespace: str,
        key: str,
        *,
        owner_id: UUID | None,
        game_id: UUID | None,
    ) -> dict[str, Any] | None:
        with self._lock:
            row = self._load().get(self._scope_key(owner_id, game_id), {})
            value = row.get(namespace, {}).get(key)
            return deepcopy(value) if isinstance(value, dict) else None

    def list(
        self,
        namespace: str,
        *,
        owner_id: UUID | None,
        game_id: UUID | None,
    ) -> dict[str, dict[str, Any]]:
        with self._lock:
            values = self._load().get(self._scope_key(owner_id, game_id), {}).get(namespace, {})
            return deepcopy(values) if isinstance(values, dict) else {}

    def put(
        self,
        namespace: str,
        key: str,
        value: dict[str, Any],
        *,
        scope: str,
        owner_id: UUID | None,
        game_id: UUID | None,
    ) -> None:
        validate_scope(scope, owner_id, game_id)  # type: ignore[arg-type]
        with self._lock:
            data = self._load()
            scoped = data.setdefault(self._scope_key(owner_id, game_id), {})
            scoped.setdefault(namespace, {})[key] = deepcopy(value)
            _atomic_json(self.path, data)


class LegacyRuntimeCatalogStore:
    """Adapter compatível com os quatro overlays históricos.

    Os três catálogos globais preservam seus nomes de arquivo para não quebrar
    ferramentas existentes. Escopos user/game usam um envelope separado e nunca
    são promovidos ao namespace global.
    """

    _GLOBAL_FILES = {
        "npc_template": "npc_database.json",
        "bestiary_template": "bestiary_runtime.json",
        "custom_artifact": "custom_artifacts.json",
    }

    def __init__(self, root_provider: Callable[[], Path]) -> None:
        self._root_provider = root_provider
        self._lock = threading.RLock()

    def _global_path(self, namespace: str) -> Path | None:
        filename = self._GLOBAL_FILES.get(namespace)
        return self._root_provider().resolve() / filename if filename else None

    def _scoped_store(self) -> JsonRuntimeCatalogStore:
        return JsonRuntimeCatalogStore(self._root_provider().resolve() / "runtime_catalog.json")

    @staticmethod
    def _load_path(path: Path) -> dict[str, dict[str, Any]]:
        if not path.exists():
            return {}
        try:
            value = json.loads(path.read_text(encoding="utf-8"))
            return value if isinstance(value, dict) else {}
        except (OSError, ValueError):
            return {}

    def get(
        self,
        namespace: str,
        key: str,
        *,
        owner_id: UUID | None,
        game_id: UUID | None,
    ) -> dict[str, Any] | None:
        path = self._global_path(namespace)
        if path is not None and owner_id is None and game_id is None:
            value = self._load_path(path).get(key)
            return deepcopy(value) if isinstance(value, dict) else None
        return self._scoped_store().get(
            namespace, key, owner_id=owner_id, game_id=game_id
        )

    def list(
        self,
        namespace: str,
        *,
        owner_id: UUID | None,
        game_id: UUID | None,
    ) -> dict[str, dict[str, Any]]:
        path = self._global_path(namespace)
        if path is not None and owner_id is None and game_id is None:
            return deepcopy(self._load_path(path))
        return self._scoped_store().list(namespace, owner_id=owner_id, game_id=game_id)

    def put(
        self,
        namespace: str,
        key: str,
        value: dict[str, Any],
        *,
        scope: str,
        owner_id: UUID | None,
        game_id: UUID | None,
    ) -> None:
        validate_scope(scope, owner_id, game_id)  # type: ignore[arg-type]
        path = self._global_path(namespace)
        if path is not None and scope == "global":
            with self._lock:
                data = self._load_path(path)
                data[key] = deepcopy(value)
                _atomic_json(path, data)
            return
        self._scoped_store().put(
            namespace,
            key,
            value,
            scope=scope,
            owner_id=owner_id,
            game_id=game_id,
        )


class InMemoryMemoryStore:
    def __init__(self) -> None:
        self._documents: dict[str, MemoryDocument] = {}

    def stage(self, intent: MemoryWriteIntent) -> None:
        current = self._documents.get(intent.document.document_id)
        if current and current != intent.document:
            raise Conflict("memory_id divergente")
        self._documents[intent.document.document_id] = intent.document

    def query(self, request: MemoryQuery) -> list[MemoryDocument]:
        words = set(request.text.casefold().split())
        candidates = [doc for doc in self._documents.values() if doc.scope == request.scope]
        ranked = sorted(
            candidates,
            key=lambda doc: len(words.intersection(doc.text.casefold().split())),
            reverse=True,
        )
        return ranked[: request.k]


def _safe_blob_key(key: str) -> PurePosixPath:
    candidate = PurePosixPath(key)
    if candidate.is_absolute() or not candidate.parts or any(part in ("", ".", "..") for part in candidate.parts):
        raise ValueError("object key inválida")
    if "\\" in key:
        raise ValueError("object key deve usar separador POSIX")
    return candidate


class FileBlobStore:
    def __init__(self, root: str | Path) -> None:
        self.root = Path(root).resolve()

    def _path(self, key: str) -> Path:
        candidate = self.root.joinpath(*_safe_blob_key(key).parts).resolve()
        if self.root != candidate and self.root not in candidate.parents:
            raise ValueError("object key escapou da raiz")
        return candidate

    def put(self, key: str, payload: Any, metadata: BlobMetadata) -> BlobRef:
        data = payload.read()
        if not isinstance(data, bytes):
            raise TypeError("payload precisa produzir bytes")
        digest = hashlib.sha256(data).hexdigest()
        if digest != metadata.sha256:
            raise Conflict("sha256 do blob divergiu")
        if metadata.size_bytes is not None and metadata.size_bytes != len(data):
            raise Conflict("tamanho do blob divergiu")
        path = self._path(key)
        path.parent.mkdir(parents=True, exist_ok=True)
        if path.exists() and path.read_bytes() != data:
            raise Conflict("object key já contém outro conteúdo")
        if not path.exists():
            # Prefixar com o nome inteiro do objeto estourava MAX_PATH no Windows
            # justamente para keys canônicas de assets (owner/game/UUID/hash).
            fd, temporary = tempfile.mkstemp(prefix=".blob.", suffix=".tmp", dir=path.parent)
            try:
                with os.fdopen(fd, "wb") as handle:
                    handle.write(data)
                    handle.flush()
                    os.fsync(handle.fileno())
                _replace_with_retry(temporary, path)
            except BaseException:
                try:
                    os.unlink(temporary)
                except OSError:
                    pass
                raise
        return BlobRef(key=key, sha256=digest, size_bytes=len(data), content_type=metadata.content_type)

    def open(self, key: str) -> io.BufferedReader:
        return self._path(key).open("rb")

    def signed_url(self, key: str, expires_seconds: int) -> str:
        if expires_seconds <= 0:
            raise ValueError("expiração precisa ser positiva")
        if not self._path(key).exists():
            raise NotFound("blob não encontrado")
        expires = int(time.time()) + expires_seconds
        return f"file:///{quote(key)}?expires={expires}"

    def delete(self, key: str) -> bool:
        path = self._path(key)
        if not path.exists():
            return False
        path.unlink()
        return True


@dataclass
class _Queued:
    job_id: UUID
    request: JobRequest
    attempt: int = 0
    lease_token: UUID | None = None
    status: str = "queued"
    result: dict[str, Any] | None = None
    error_code: str | None = None


class InlineJobQueue:
    def __init__(self) -> None:
        self._jobs: dict[UUID, _Queued] = {}
        self._dedupe: dict[tuple[str, str], UUID] = {}
        self._order: deque[UUID] = deque()
        self._lock = threading.RLock()

    def enqueue(self, job: JobRequest) -> UUID:
        with self._lock:
            dedupe = (job.kind, job.dedupe_key)
            if dedupe in self._dedupe:
                return self._dedupe[dedupe]
            job_id = uuid4()
            self._jobs[job_id] = _Queued(job_id=job_id, request=job)
            self._dedupe[dedupe] = job_id
            self._order.append(job_id)
            return job_id

    def lease(self, worker_id: str, kinds: set[str], limit: int) -> list[LeasedJob]:
        del worker_id
        leased: list[LeasedJob] = []
        with self._lock:
            for job_id in list(self._order):
                row = self._jobs[job_id]
                if len(leased) >= limit:
                    break
                if row.status != "queued" or row.request.kind not in kinds:
                    continue
                row.status = "running"
                row.attempt += 1
                row.lease_token = uuid4()
                leased.append(LeasedJob(job_id, row.lease_token, row.request, row.attempt))
        return leased

    def _leased(self, job_id: UUID, lease_token: UUID) -> _Queued:
        row = self._jobs.get(job_id)
        if not row:
            raise NotFound("job não encontrado")
        if row.status != "running" or row.lease_token != lease_token:
            raise LeaseHeld("lease inválida")
        return row

    def complete(self, job_id: UUID, lease_token: UUID, result: dict[str, Any]) -> None:
        with self._lock:
            row = self._leased(job_id, lease_token)
            row.status = "succeeded"
            row.result = deepcopy(result)

    def fail(self, job_id: UUID, lease_token: UUID, error_code: str) -> None:
        with self._lock:
            row = self._leased(job_id, lease_token)
            row.error_code = error_code
            row.lease_token = None
            if row.attempt >= row.request.max_attempts:
                row.status = "dead"
            else:
                row.status = "queued"


class MemoryRateLimiter:
    def __init__(self, clock: Callable[[], float] = time.monotonic) -> None:
        self._clock = clock
        self._buckets: dict[str, tuple[float, int]] = {}
        self._lock = threading.Lock()

    def consume(self, key: str, *, limit: int, window_seconds: int) -> RateLimitDecision:
        if limit <= 0 or window_seconds <= 0:
            raise ValueError("limit e window_seconds precisam ser positivos")
        now = self._clock()
        with self._lock:
            started, count = self._buckets.get(key, (now, 0))
            if now - started >= window_seconds:
                started, count = now, 0
            if count >= limit:
                retry = max(1, int(window_seconds - (now - started)))
                return RateLimitDecision(False, 0, retry)
            count += 1
            self._buckets[key] = (started, count)
            return RateLimitDecision(True, limit - count, 0)


class FixedIdentityVerifier:
    def __init__(self, principal: Principal) -> None:
        self.principal = principal

    def verify(self, credential: str | None) -> Principal:
        if credential not in (None, "", "local"):
            raise Unauthorized("credential não suportada no perfil local")
        return self.principal


class InProcessTurnCoordinator:
    def __init__(self) -> None:
        self._active_games: dict[UUID, OperationClaim] = {}
        self._claims: dict[UUID, tuple[Principal, OperationClaim, str, dict[str, Any] | None]] = {}
        self._lock = threading.RLock()

    def claim(
        self,
        principal: Principal,
        operation_id: UUID,
        *,
        game_id: UUID | None,
        kind: str,
        request_hash: str,
        base_version: int | None,
    ) -> OperationClaim:
        with self._lock:
            existing = self._claims.get(operation_id)
            if existing:
                if existing[0] != principal or existing[1].request_hash != request_hash:
                    raise Conflict("idempotency key reutilizada com outro request")
                return existing[1]
            if game_id is not None and game_id in self._active_games:
                raise LeaseHeld("campanha já possui mutação ativa")
            claim = OperationClaim(operation_id, uuid4(), game_id, base_version, request_hash)
            self._claims[operation_id] = (principal, claim, kind, None)
            if game_id is not None:
                self._active_games[game_id] = claim
            return claim

    def complete(
        self,
        claim: OperationClaim,
        *,
        committed_version: int | None,
        receipt: Any,
    ) -> dict[str, Any]:
        with self._lock:
            row = self._claims.get(claim.operation_id)
            if not row or row[1].lease_token != claim.lease_token:
                raise LeaseHeld("fencing token inválido")
            value = deepcopy(dict(receipt))
            value.setdefault("committed_version", committed_version)
            self._claims[claim.operation_id] = (row[0], row[1], row[2], value)
            if claim.game_id is not None:
                self._active_games.pop(claim.game_id, None)
            return value

    def fail(self, claim: OperationClaim, error_code: str) -> None:
        with self._lock:
            row = self._claims.get(claim.operation_id)
            if not row or row[1].lease_token != claim.lease_token:
                raise LeaseHeld("fencing token inválido")
            self._claims[claim.operation_id] = (row[0], row[1], row[2], {"error": error_code})
            if claim.game_id is not None:
                self._active_games.pop(claim.game_id, None)
