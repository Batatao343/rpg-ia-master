"""SPEC-367 R18: abertura tolerante do pool dos scripts de operação (kill switch, preflight).

`open_ops_pool` abre um pool de 1 conexão com timeouts folgados (handshake TLS lento do pooler);
`with_checkout_retry` repete SÓ falha de checkout (nenhum comando chegou ao banco), então uma
escrita nunca é duplicada. Nada aqui imprime DSN nem mensagem de erro.
"""

from __future__ import annotations

import sys
import time
from collections.abc import Callable, Sequence
from typing import Any

from services.checkout_retry import is_checkout_failure as _is_checkout_failure


def open_ops_pool(dsn: str):
    from infrastructure.postgres import PostgresPool

    return PostgresPool(dsn, max_size=1, timeout=20.0, connect_timeout=10.0)


class DbUnavailable(RuntimeError):
    """Todas as tentativas de checkout falharam."""


def with_checkout_retry[T](
    fn: Callable[[], T],
    *,
    attempts: int = 3,
    delays: Sequence[float] = (1.0, 3.0),
    sleep: Callable[[float], Any] | None = None,
) -> T:
    for attempt in range(1, attempts + 1):
        try:
            return fn()
        except Exception as exc:
            if not _is_checkout_failure(exc):
                raise
            print(
                f"ops.db_retry attempt={attempt} error_class={type(exc).__name__}",
                file=sys.stderr,
            )
            if attempt >= attempts:
                raise DbUnavailable("db_unavailable") from None
            (sleep or time.sleep)(delays[min(attempt - 1, len(delays) - 1)])
    raise DbUnavailable("db_unavailable")  # pragma: no cover
