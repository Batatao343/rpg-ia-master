"""SPEC-387 R6: nova tentativa SO de falha de checkout do pool (nenhum comando chegou ao banco).

Critério único (SPEC-367 R18 `scripts/staging/ops_pool.py` importa daqui): `PoolTimeout` é sempre
de checkout; `OperationalError` só se passou por checkout/connect e por nenhum comando nem commit.
Uma escrita nunca é duplicada. Nada aqui registra DSN nem mensagem de erro.
"""

from __future__ import annotations

from collections.abc import Callable

_COMMAND_FRAMES = {
    "execute", "executemany", "fetchone", "fetchall", "fetchmany", "copy",
    "commit", "rollback", "__exit__", "wait", "_commit_gen", "_exit_gen",
}  # fmt: skip
_CHECKOUT_FRAMES = {"getconn", "connection", "_connect", "connect"}


def is_checkout_failure(exc: BaseException) -> bool:
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


def retry_once[T](fn: Callable[[], T]) -> T:
    """Chama `fn`; se falhar no checkout, tenta 1 vez mais. Outro erro (ou 2ª falha) sobe."""
    try:
        return fn()
    except Exception as exc:
        if not is_checkout_failure(exc):
            raise
    return fn()
