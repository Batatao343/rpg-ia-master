"""Seleção central e fail-closed dos adapters de infraestrutura."""

from __future__ import annotations

import os
import ipaddress
import base64
import binascii
import json
import threading
from dataclasses import dataclass, field
from pathlib import Path
from typing import Mapping
from urllib.parse import parse_qsl, urlsplit
from uuid import UUID

from infrastructure.contracts import (
    BlobStore,
    GameStore,
    IdentityVerifier,
    JobQueue,
    MemoryStore,
    Principal,
    RateLimiter,
    RuntimeCatalogStore,
    TurnCoordinator,
)
from infrastructure.local_adapters import (
    FileBlobStore,
    FileGameStore,
    FixedIdentityVerifier,
    InMemoryMemoryStore,
    InProcessTurnCoordinator,
    InlineJobQueue,
    LegacyRuntimeCatalogStore,
    MemoryRateLimiter,
)

LOCAL_PRINCIPAL_ID = UUID("00000000-0000-0000-0000-000000000001")


def _loopback_host(host: str) -> bool:
    normalized = host.strip("[]").rstrip(".").lower()
    if normalized == "localhost" or normalized.endswith(".localhost"):
        return True
    try:
        return ipaddress.ip_address(normalized).is_loopback
    except ValueError:
        return False


def _unsafe_hosted_host(host: str) -> bool:
    return _loopback_host(host) or host.lower().startswith("127.")


def _legacy_service_role_ref(key: str) -> str | None:
    """Check legacy JWT claims structurally; Supabase verifies its signature."""
    parts = key.split(".")
    if len(parts) != 3 or not all(parts):
        raise ValueError("SUPABASE_SERVICE_ROLE_KEY exige service_role JWT")
    try:
        payload = base64.urlsafe_b64decode(parts[1] + "=" * (-len(parts[1]) % 4))
        claims = json.loads(payload)
    except (ValueError, UnicodeDecodeError, binascii.Error):
        raise ValueError("SUPABASE_SERVICE_ROLE_KEY exige service_role JWT") from None
    if not isinstance(claims, dict) or claims.get("role") != "service_role":
        raise ValueError("SUPABASE_SERVICE_ROLE_KEY exige role service_role")
    ref = claims.get("ref")
    if ref is not None and not isinstance(ref, str):
        raise ValueError("SUPABASE_SERVICE_ROLE_KEY contém project_ref inválida")
    return ref


def hosted_supabase_dsn_ref(dsn: str) -> str:
    """Validate serverless transaction-pooler DSN without exposing its secret."""
    try:
        parsed = urlsplit(dsn)
        host = (parsed.hostname or "").lower()
        port = parsed.port
        user = parsed.username or ""
        query = parse_qsl(parsed.query, keep_blank_values=True, strict_parsing=True)
        # libpq treats URL query parameters as effective connection settings.
        # A second host/port/user here would bypass the authority checks below.
        if len(query) > 1 or any(key != "sslmode" for key, _ in query):
            raise ValueError("DATABASE_URL contém parâmetros não permitidos")
        sslmodes = [value for _, value in query]
    except ValueError:
        raise ValueError("DATABASE_URL inválida para hosted-supabase") from None
    if (parsed.scheme not in {"postgres", "postgresql"} or port != 6543
            or not parsed.password or not parsed.path.strip("/")
            or parsed.fragment or any(mode not in {"require", "verify-full"} for mode in sslmodes)):
        raise ValueError("DATABASE_URL exige pooler transacional Supabase em 6543")
    if host.endswith(".pooler.supabase.com"):
        # Shared Supavisor requires the project ref in the username.
        ref = user.rpartition(".")[2]
        if not ref or ref == user:
            raise ValueError("DATABASE_URL do pooler exige user.project_ref")
    elif host.startswith("db.") and host.endswith(".supabase.co"):
        # Dedicated paid-plan pooler is also transaction mode on 6543.
        ref = host[len("db."):-len(".supabase.co")]
        if user != "postgres":
            raise ValueError("DATABASE_URL do pooler dedicado exige postgres")
    else:
        raise ValueError("DATABASE_URL exige host de pooler Supabase")
    if not ref or not all(ch.isascii() and (ch.islower() or ch.isdigit()) for ch in ref):
        raise ValueError("DATABASE_URL contém project_ref inválida")
    return ref


def _supabase_api_ref(url: str) -> str:
    try:
        parsed = urlsplit(url)
        host = (parsed.hostname or "").lower()
        port = parsed.port
    except ValueError:
        raise ValueError("SUPABASE_URL inválida") from None
    suffix = ".supabase.co"
    if (parsed.scheme != "https" or not host.endswith(suffix)
            or host.startswith("db.") or port not in (None, 443)
            or parsed.username or parsed.password or parsed.path not in ("", "/")
            or parsed.query or parsed.fragment):
        raise ValueError("SUPABASE_URL exige API HTTPS do projeto")
    ref = host[:-len(suffix)]
    if not ref or "." in ref or not all(
        ch.isascii() and (ch.islower() or ch.isdigit()) for ch in ref
    ):
        raise ValueError("SUPABASE_URL contém project_ref inválida")
    return ref


@dataclass(frozen=True)
class RuntimeConfig:
    profile: str
    game_store: str
    memory_store: str
    runtime_catalog: str
    blob_store: str
    job_queue: str
    rate_limit_store: str
    auth_mode: str
    bind_host: str
    database_url: str = field(default="", repr=False)
    supabase_url: str = ""
    supabase_publishable_key: str = field(default="", repr=False)
    supabase_service_role_key: str = field(default="", repr=False)
    oidc_userinfo_url: str = ""
    oidc_issuer: str = ""
    db_pool_min_size: int = 0
    db_pool_max_size: int = 4
    db_pool_timeout: float = 5.0

    @classmethod
    def from_env(cls, env: Mapping[str, str] | None = None) -> "RuntimeConfig":
        values = os.environ if env is None else env
        profile = values.get("RPG_RUNTIME_PROFILE", "legacy").strip().lower()
        defaults = {
            "legacy": ("file", "faiss", "file", "file", "inline", "memory", "disabled"),
            "local": ("postgres", "pgvector", "postgres", "supabase", "postgres", "postgres", "supabase"),
            "portable": ("postgres", "pgvector", "postgres", "s3", "postgres", "postgres", "oidc"),
            "hosted": ("postgres", "pgvector", "postgres", "s3", "postgres", "postgres", "oidc"),
            "hosted-supabase": ("postgres", "pgvector", "postgres", "supabase", "postgres", "postgres", "supabase"),
        }
        if profile not in defaults:
            raise ValueError(f"RPG_RUNTIME_PROFILE inválido: {profile}")
        selected = defaults[profile]
        try:
            pool_min = int(values.get("RPG_DB_POOL_MIN_SIZE", "0"))
            pool_max = int(values.get(
                "RPG_DB_POOL_MAX_SIZE", "1" if profile == "hosted-supabase" else "4",
            ))
            pool_timeout = float(values.get("RPG_DB_POOL_TIMEOUT_SECONDS", "5"))
        except ValueError:
            raise ValueError("RPG_DB_POOL_* exige limites numéricos válidos") from None
        config = cls(
            profile=profile,
            game_store=values.get("RPG_GAME_STORE", selected[0]).strip().lower(),
            memory_store=values.get("RPG_MEMORY_STORE", selected[1]).strip().lower(),
            runtime_catalog=values.get("RPG_RUNTIME_CATALOG", selected[2]).strip().lower(),
            blob_store=values.get("RPG_BLOB_STORE", selected[3]).strip().lower(),
            job_queue=values.get("RPG_JOB_QUEUE", selected[4]).strip().lower(),
            rate_limit_store=values.get("RPG_RATE_LIMIT_STORE", selected[5]).strip().lower(),
            auth_mode=values.get("RPG_AUTH_MODE", selected[6]).strip().lower(),
            bind_host=values.get("RPG_BIND_HOST", "127.0.0.1").strip().lower(),
            database_url=values.get("DATABASE_URL", "").strip(),
            supabase_url=values.get("SUPABASE_URL", "").strip(),
            supabase_publishable_key=values.get("SUPABASE_PUBLISHABLE_KEY", "").strip(),
            supabase_service_role_key=values.get("SUPABASE_SERVICE_ROLE_KEY", "").strip(),
            oidc_userinfo_url=values.get("RPG_OIDC_USERINFO_URL", "").strip(),
            oidc_issuer=values.get("RPG_OIDC_ISSUER", "").strip(),
            db_pool_min_size=pool_min,
            db_pool_max_size=pool_max,
            db_pool_timeout=pool_timeout,
        )
        config.validate()
        return config

    def validate(self) -> None:
        if self.profile == "legacy":
            expected = ("file", "faiss", "file", "file", "inline", "memory", "disabled")
            actual = (
                self.game_store,
                self.memory_store,
                self.runtime_catalog,
                self.blob_store,
                self.job_queue,
                self.rate_limit_store,
                self.auth_mode,
            )
            if actual != expected:
                raise ValueError("perfil legacy exige apenas adapters legados")
            if not _loopback_host(self.bind_host):
                raise ValueError("perfil legacy só pode escutar em loopback")
        if self.profile in {"local", "portable", "hosted", "hosted-supabase"}:
            if self.game_store != "postgres" or self.memory_store != "pgvector":
                raise ValueError(f"perfil {self.profile} exige Postgres + pgvector")
            if self.runtime_catalog != "postgres" or self.job_queue != "postgres":
                raise ValueError(f"perfil {self.profile} exige catálogo/fila Postgres")
            if self.rate_limit_store != "postgres":
                raise ValueError(f"perfil {self.profile} exige rate limit Postgres")
            if self.auth_mode == "disabled":
                raise ValueError(f"perfil {self.profile} exige autenticação")
            if self.blob_store == "file":
                raise ValueError(f"perfil {self.profile} recusa BlobStore em filesystem")
            if not self.database_url:
                raise ValueError(f"perfil {self.profile} exige DATABASE_URL")
            if (not 0 <= self.db_pool_min_size <= self.db_pool_max_size <= 4
                    or self.db_pool_max_size < 1
                    or not 0.1 <= self.db_pool_timeout <= 30):
                raise ValueError("RPG_DB_POOL_* fora dos limites seguros")
        if self.profile in {"hosted", "hosted-supabase"}:
            if _unsafe_hosted_host(self.bind_host):
                raise ValueError(f"perfil {self.profile} exige bind de serviço explícito")
            try:
                db_url = urlsplit(self.database_url)
                db_host = (db_url.hostname or "").lower()
            except ValueError:
                raise ValueError("DATABASE_URL inválida") from None
            if _unsafe_hosted_host(db_host) or db_host == "0.0.0.0":
                raise ValueError("perfil hosted recusa DATABASE_URL loopback")
            if self.profile == "hosted":
                try:
                    query = parse_qsl(db_url.query, keep_blank_values=True, strict_parsing=True)
                    if (db_url.scheme not in {"postgres", "postgresql"} or not db_host
                            or db_url.fragment or len(query) > 1
                            or any(key != "sslmode" or value not in {"require", "verify-ca", "verify-full"}
                                   for key, value in query)):
                        raise ValueError
                except ValueError:
                    raise ValueError("DATABASE_URL hosted exige URL Postgres sem override de destino") from None
        if self.profile in {"portable", "hosted"}:
            if self.auth_mode != "oidc":
                raise ValueError(f"perfil {self.profile} exige auth OIDC")
            if self.blob_store != "s3":
                raise ValueError(f"perfil {self.profile} exige BlobStore S3")
            if not self.oidc_userinfo_url or not self.oidc_issuer:
                raise ValueError(
                    f"perfil {self.profile} exige RPG_OIDC_USERINFO_URL e RPG_OIDC_ISSUER"
                )
        if self.profile == "hosted-supabase":
            if self.auth_mode != "supabase" or self.blob_store != "supabase":
                raise ValueError("perfil hosted-supabase exige auth/storage Supabase")
            if not self.supabase_url or not self.supabase_publishable_key or not self.supabase_service_role_key:
                raise ValueError(
                    "perfil hosted-supabase exige SUPABASE_URL, SUPABASE_PUBLISHABLE_KEY e "
                    "SUPABASE_SERVICE_ROLE_KEY"
                )
            if not self.supabase_publishable_key.startswith("sb_publishable_"):
                raise ValueError("SUPABASE_PUBLISHABLE_KEY deve ser publishable")
            if self.supabase_publishable_key == self.supabase_service_role_key:
                raise ValueError("publishable e service role devem ser credenciais distintas")
            db_ref = hosted_supabase_dsn_ref(self.database_url)
            api_ref = _supabase_api_ref(self.supabase_url)
            if db_ref != api_ref:
                raise ValueError("DATABASE_URL e SUPABASE_URL apontam a projetos diferentes")
            if not self.supabase_service_role_key.startswith("sb_secret_"):
                key_ref = _legacy_service_role_ref(self.supabase_service_role_key)
                if key_ref is not None and key_ref != api_ref:
                    raise ValueError("service_role JWT aponta a projeto diferente")
        if self.supabase_service_role_key and self.supabase_service_role_key.startswith("VITE_"):
            raise ValueError("service role nunca pode usar namespace Vite")


@dataclass
class InfrastructureRuntime:
    config: RuntimeConfig
    game_store: GameStore
    memory_store: MemoryStore
    runtime_catalog: RuntimeCatalogStore
    blob_store: BlobStore
    turn_coordinator: TurnCoordinator
    job_queue: JobQueue
    rate_limiter: RateLimiter
    identity_verifier: IdentityVerifier
    resources: tuple[object, ...] = ()


def build_legacy_runtime(config: RuntimeConfig | None = None) -> InfrastructureRuntime:
    config = config or RuntimeConfig.from_env({})
    root = Path(os.getenv("RPG_RUNTIME_CACHE_DIR", "data/runtime"))
    principal = Principal(LOCAL_PRINCIPAL_ID, "local", str(LOCAL_PRINCIPAL_ID), local=True)
    return InfrastructureRuntime(
        config=config,
        game_store=FileGameStore(root / "contract_games"),
        memory_store=InMemoryMemoryStore(),
        runtime_catalog=LegacyRuntimeCatalogStore(
            lambda: Path(os.getenv("RPG_RUNTIME_CACHE_DIR", "data/runtime"))
        ),
        blob_store=FileBlobStore(root / "blobs"),
        turn_coordinator=InProcessTurnCoordinator(),
        job_queue=InlineJobQueue(),
        rate_limiter=MemoryRateLimiter(),
        identity_verifier=FixedIdentityVerifier(principal),
    )


def build_database_runtime(config: RuntimeConfig) -> InfrastructureRuntime:
    """Compõe adapters compartilhando um único pool; falha antes de servir."""
    config.validate()
    from infrastructure.pgvector_memory import PgVectorMemoryStore
    from infrastructure.postgres import PostgresGameStore, PostgresPool
    from infrastructure.postgres_catalog import PostgresRuntimeCatalogStore
    from infrastructure.postgres_jobs import PostgresJobQueue
    from infrastructure.postgres_turns import PostgresRateLimiter, PostgresTurnCoordinator
    from infrastructure.supabase_blob import SupabaseBlobStore
    from infrastructure.supabase_identity import SupabaseIdentityProvider

    pool = PostgresPool(
        config.database_url,
        min_size=config.db_pool_min_size,
        max_size=config.db_pool_max_size,
        timeout=config.db_pool_timeout,
        transaction_pooler=config.profile == "hosted-supabase",
    )
    try:
        if config.blob_store == "supabase":
            if not config.supabase_url or not config.supabase_service_role_key:
                raise ValueError("BlobStore Supabase exige SUPABASE_URL e service role no backend")
            blob_store: BlobStore = SupabaseBlobStore(
                config.supabase_url, config.supabase_service_role_key,
            )
        elif config.blob_store == "s3":
            try:
                import boto3
            except ImportError as exc:  # pragma: no cover - extra opcional
                raise RuntimeError("BlobStore S3 exige boto3") from exc
            from infrastructure.s3_blob import S3BlobStore
            bucket = os.getenv("RPG_S3_BUCKET", "").strip()
            if not bucket:
                raise ValueError("BlobStore S3 exige RPG_S3_BUCKET")
            blob_store = S3BlobStore(
                boto3.client(
                    "s3", endpoint_url=os.getenv("RPG_S3_ENDPOINT") or None,
                    region_name=os.getenv("RPG_S3_REGION") or None,
                ),
                bucket,
            )
        else:
            raise ValueError(f"BlobStore não suportado: {config.blob_store}")
        if config.auth_mode == "supabase":
            if not config.supabase_url or not config.supabase_publishable_key:
                raise ValueError("auth Supabase exige SUPABASE_URL e SUPABASE_PUBLISHABLE_KEY")
            identity: IdentityVerifier = SupabaseIdentityProvider(
                config.supabase_url, config.supabase_publishable_key,
            )
        elif config.auth_mode == "oidc":
            from infrastructure.oidc_identity import OidcIdentityProvider
            identity = OidcIdentityProvider(config.oidc_userinfo_url, config.oidc_issuer)
        else:
            raise ValueError(f"auth não suportada: {config.auth_mode}")
        def embed_query(text: str):
            import rag
            embeddings = rag.get_embeddings()
            if embeddings is None:
                raise RuntimeError("provider de embedding indisponível")
            values = embeddings.embed_query(text)
            if len(values) != 1024:
                raise ValueError(f"embedding incompatível: {len(values)} dimensões")
            return values

        memory_store = PgVectorMemoryStore(pool, embedder=embed_query)
        return InfrastructureRuntime(
            config=config,
            game_store=PostgresGameStore(pool),
            memory_store=memory_store,
            runtime_catalog=PostgresRuntimeCatalogStore(pool),
            blob_store=blob_store,
            turn_coordinator=PostgresTurnCoordinator(pool),
            job_queue=PostgresJobQueue(pool),
            rate_limiter=PostgresRateLimiter(pool),
            identity_verifier=identity,
            resources=(pool,),
        )
    except Exception:
        pool.close()
        raise


def build_runtime(config: RuntimeConfig | None = None) -> InfrastructureRuntime:
    config = config or RuntimeConfig.from_env()
    if config.profile == "legacy":
        return build_legacy_runtime(config)
    return build_database_runtime(config)


_runtime: InfrastructureRuntime | None = None
_runtime_lock = threading.RLock()


def get_runtime() -> InfrastructureRuntime:
    global _runtime
    with _runtime_lock:
        if _runtime is None:
            config = RuntimeConfig.from_env()
            _runtime = build_runtime(config)
        return _runtime


def set_runtime(runtime: InfrastructureRuntime) -> None:
    global _runtime
    with _runtime_lock:
        _runtime = runtime


def reset_runtime() -> None:
    global _runtime
    with _runtime_lock:
        if _runtime is not None:
            for resource in _runtime.resources:
                close = getattr(resource, "close", None)
                if callable(close):
                    close()
        _runtime = None
