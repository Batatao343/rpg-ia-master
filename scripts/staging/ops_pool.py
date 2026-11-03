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

_COMMAND_FRAMES = {
    "execute", "executemany", "fetchone", "fetchall", "fetchmany", "copy",
    "commit", "rollback", "__exit__", "wait", "_commit_gen", "_exit_gen",
}  # fmt: skip
_CHECKOUT_FRAMES = {"getconn", "connection", "_connect", "connect"}


def open_ops_pool(dsn: str):
    from infrastructure.postgres import PostgresPool

    return PostgresPool(dsn, max_size=1, timeout=20.0, connect_timeout=10.0)


def _is_checkout_failure(exc: BaseException) -> bool:
    """PoolTimeout é sempre de checkout; OperationalError só se veio do checkout/connect (nunca de comando ou commit)."""
    try:
        from psycopg import OperationalError
        from psycopg_pool import PoolTimeout
    except ImportError:  # sem psycopg não há o que repetir
        return False
    if isinstance(exc, PoolTimeout):
        return True
    if not isinstance(exc, OperationalError):
        return False
    names: list[str] = []
    tb = exc.__traceback__
    while tb is not None:
        names.append(tb.tb_frame.f_code.co_name)
        tb = tb.tb_next
    # detecção POSITIVA: passou pelo checkout/connect e por nenhum comando nem commit
    return bool(_CHECKOUT_FRAMES & set(names)) and not (_COMMAND_FRAMES & set(names))


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
