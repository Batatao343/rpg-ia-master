"""Principal da request sem acoplar domínio a FastAPI."""

from __future__ import annotations

import contextvars
from contextlib import contextmanager
from typing import Iterator

from infrastructure.contracts import Principal, Unauthorized


_principal: contextvars.ContextVar[Principal | None] = contextvars.ContextVar(
    "rpg_principal", default=None,
)


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
