"""Seleção central e fail-closed dos adapters de infraestrutura."""

from __future__ import annotations

import os
import threading
from dataclasses import dataclass
from pathlib import Path
from typing import Mapping
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
    database_url: str = ""
    supabase_url: str = ""
    supabase_publishable_key: str = ""
    supabase_service_role_key: str = ""
    oidc_userinfo_url: str = ""
    oidc_issuer: str = ""

    @classmethod
    def from_env(cls, env: Mapping[str, str] | None = None) -> "RuntimeConfig":
        values = os.environ if env is None else env
        profile = values.get("RPG_RUNTIME_PROFILE", "legacy").strip().lower()
        defaults = {
            "legacy": ("file", "faiss", "file", "file", "inline", "memory", "disabled"),
            "local": ("postgres", "pgvector", "postgres", "supabase", "postgres", "postgres", "supabase"),
            "portable": ("postgres", "pgvector", "postgres", "s3", "postgres", "postgres", "oidc"),
            "hosted": ("postgres", "pgvector", "postgres", "s3", "postgres", "postgres", "oidc"),
        }
        if profile not in defaults:
            raise ValueError(f"RPG_RUNTIME_PROFILE inválido: {profile}")
        selected = defaults[profile]
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
        )
        config.validate()
        return config

    def validate(self) -> None:
        loopback = {"127.0.0.1", "localhost", "::1"}
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
            if self.bind_host not in loopback:
                raise ValueError("perfil legacy só pode escutar em loopback")
        if self.profile in {"local", "portable", "hosted"}:
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
        if self.profile == "hosted" and self.bind_host in loopback:
            raise ValueError("perfil hosted exige bind de serviço explícito")
        if self.profile in {"portable", "hosted"}:
            if self.auth_mode != "oidc":
                raise ValueError(f"perfil {self.profile} exige auth OIDC")
            if not self.oidc_userinfo_url or not self.oidc_issuer:
                raise ValueError(
                    f"perfil {self.profile} exige RPG_OIDC_USERINFO_URL e RPG_OIDC_ISSUER"
                )
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
    from infrastructure.pgvector_memory import PgVectorMemoryStore
    from infrastructure.postgres import PostgresGameStore, PostgresPool
    from infrastructure.postgres_catalog import PostgresRuntimeCatalogStore
    from infrastructure.postgres_jobs import PostgresJobQueue
    from infrastructure.postgres_turns import PostgresRateLimiter, PostgresTurnCoordinator
    from infrastructure.supabase_blob import SupabaseBlobStore
    from infrastructure.supabase_identity import SupabaseIdentityProvider

    pool = PostgresPool(config.database_url)
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
