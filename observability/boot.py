"""SPEC-249: linha de boot ``runtime.boot`` (1x por processo) + avisos de configuração.

Só nomes de provider/modo e flags — nunca valores de chave, DSN, host de banco ou e-mail.
"""

from __future__ import annotations

import os
import threading
import time
from uuid import uuid4

from observability.telemetry import log_event

_T0 = time.monotonic()
INSTANCE_REF = uuid4().hex[:8]
_lock = threading.Lock()
_logged = False


def _git_sha(env) -> str:
    return (env.get("GIT_SHA") or env.get("VERCEL_GIT_COMMIT_SHA") or "")[:12]


def _safe(fn, default="unknown"):
    try:
        return fn()
    except Exception:
        return default


def log_boot_once(env=None, *, force: bool = False) -> bool:
    """Emite ``runtime.boot`` (+ ``runtime.config_warning``) uma vez por processo. Nunca levanta."""
    global _logged
    env = os.environ if env is None else env
    with _lock:
        if _logged and not force:
            return False
        _logged = True
    try:
        import logging

        import llm_setup
        from infrastructure.runtime import HOSTED_PROFILES, is_hardened
        from observability.logging_setup import _parse_level
        profile = str(env.get("RPG_RUNTIME_PROFILE", "legacy")).strip().lower() or "legacy"
        level_name = logging.getLevelName(_parse_level(env.get("RPG_LOG_LEVEL"))[0]).lower()

        def _embedding():
            import rag
            return rag._resolve_provider() or "none"

        def _jev():
            from services.jev_rollout import rollout_mode
            return rollout_mode()

        def _projection():
            from services.projections import projection_mode
            return projection_mode()

        log_event(
            "runtime", "boot",
            git_sha=_git_sha(env), profile=profile, hardened=bool(_safe(lambda: is_hardened(env), False)),
            region=str(env.get("VERCEL_REGION", ""))[:16],
            llm_mode=_safe(llm_setup.llm_mode), llm_providers_with_key=_safe(llm_setup.providers_with_key, []),
            embedding_provider=_safe(_embedding), jev_mode=_safe(_jev),
            projection_mode=_safe(_projection), log_level=level_name,
            cold_start_ms=int((time.monotonic() - _T0) * 1000), instance_ref=INSTANCE_REF,
        )
        hosted = profile in HOSTED_PROFILES
        secret = str(env.get("RPG_TELEMETRY_SECRET", ""))
        if len(secret) < 16:
            log_event("runtime", "config_warning", level="warning", code="telemetry_secret_weak",
                      present=bool(secret))
        if not _git_sha(env):
            log_event("runtime", "config_warning", level="warning", code="git_sha_missing")
        if hosted and not str(env.get("RPG_CORS_ORIGINS", "")).strip():
            log_event("runtime", "config_warning", level="warning", code="cors_default_in_hosted")
    except Exception:
        return False
    return True


def log_build_failed(component: str, exc: BaseException) -> None:
    """SPEC-249 R3: ``component`` fechado + ``error_type``; nunca a mensagem (pode ter DSN)."""
    log_event("runtime", "build_failed", level="error", component=component,
              error_type=type(exc).__name__)
