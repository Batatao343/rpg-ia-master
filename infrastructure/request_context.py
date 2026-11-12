"""Principal da request sem acoplar domínio a FastAPI."""

from __future__ import annotations

import contextvars
from contextlib import contextmanager
from collections.abc import Iterator

from infrastructure.contracts import Principal, Unauthorized

_principal: contextvars.ContextVar[Principal | None] = contextvars.ContextVar(
    "rpg_principal",
    default=None,
)


def active_principal() -> Principal | None:
    """Principal do request ou None (sem levantar); usado pelo pool para escopar o RLS."""
    return _principal.get()


def current_principal(*, required: bool = True) -> Principal | None:
    principal = _principal.get()
    if required and principal is None:
        raise Unauthorized("principal ausente")
    return principal


@contextmanager
def principal_scope(principal: Principal) -> Iterator[None]:
    token = _principal.set(principal)
    try:
        yield
    finally:
        _principal.reset(token)


def set_current_principal(principal: Principal | None):
    return _principal.set(principal)


def reset_current_principal(token) -> None:
    _principal.reset(token)


# SPEC-410: marca de chamador de sistema (cron/worker/drain/script). Declarada UMA vez no ponto de
# entrada; roteia `pool.connection()` ao pool admin (sem trocar de role) e PERDE para um principal.
_system_caller: contextvars.ContextVar[str | None] = contextvars.ContextVar(
    "rpg_system_caller",
    default=None,
)


def active_system_caller() -> str | None:
    """`reason` da marca de sistema ativa ou None."""
    return _system_caller.get()


@contextmanager
def system_caller(reason: str) -> Iterator[None]:
    """Fixa a marca de sistema (ex.: `cron:jobs`, `worker`, `script:admin_wallet_adjust`)."""
    if not reason or not reason.strip():
        raise ValueError("system_caller exige um reason")
    token = _system_caller.set(reason.strip())
    try:
        yield
    finally:
        _system_caller.reset(token)
