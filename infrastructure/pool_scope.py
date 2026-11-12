"""SPEC-410: decisao do checkout request-scoped quando falta principal.

Precedencia (aplicada por `PostgresPool.connection`): principal > marca de sistema > modo.
Este modulo so cuida do ultimo degrau: contar/logar (`shadow`) ou levantar (`on`)."""

from __future__ import annotations

import os
import sys

from infrastructure.contracts import RlsScopeError

STRICT_FLAG = "RPG_RLS_STRICT_PRINCIPAL"
MODES = ("off", "shadow", "on")
_PROFILES = {"hosted", "hosted-supabase"}


def strict_mode(profile: str, request_rls: bool, env: dict[str, str] | None = None) -> str:
    """Modo efetivo do pool: so perfil hosted com `request_rls`; valor invalido => `off`."""
    if profile not in _PROFILES or not request_rls:
        return "off"
    raw = (env if env is not None else os.environ).get(STRICT_FLAG, "off")
    mode = str(raw).strip().lower()
    return mode if mode in MODES else "off"


def boot_rls_mode(profile: str, request_rls: bool) -> str:
    """Modo do pool no boot do runtime + log (RLS desligado e modo estrito ativo)."""
    from observability.telemetry import log_event

    if not request_rls:
        log_event("runtime", "request_rls_disabled", level="warning", profile=profile)
    mode = strict_mode(profile, request_rls)
    if mode != "off":
        log_event("runtime", "rls_strict_principal", mode=mode)
    return mode


def caller_ref() -> str:
    """`modulo.funcao` do primeiro frame fora do pool; so no caminho raro (sem principal)."""
    frame = sys._getframe(1)
    while frame is not None:
        module = frame.f_globals.get("__name__", "?")
        if not module.startswith(("infrastructure.postgres", "infrastructure.pool_scope")) and (
            module not in {"infrastructure.db_roles", "contextlib"}
        ):
            return f"{module}.{frame.f_code.co_name}"[:120]
        frame = frame.f_back
    return "unknown"


def on_missing_principal(mode: str) -> None:
    """Checkout request-scoped sem principal e sem marca. `off` nao chega aqui com custo."""
    if mode == "off":
        return
    caller = caller_ref()
    try:
        from observability.metrics import metrics
        from observability.telemetry import log_event

        metrics.increment("rpg_pool_checkout_without_principal_total", {"mode": mode})
        log_event(
            "pool",
            "checkout_without_principal",
            level="warning" if mode == "shadow" else "error",
            caller=caller,
            mode=mode,
        )
    except Exception:  # noqa: BLE001  silent-ok: a medicao nunca derruba o checkout
        pass
    if mode == "on":
        raise RlsScopeError("checkout sem principal nem marca de sistema")
