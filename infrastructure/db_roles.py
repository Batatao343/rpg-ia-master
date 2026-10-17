"""SPEC-224: escolha da credencial de banco por tipo de acesso (sem imports pesados).

- `pool.connection()`  -> acesso DE REQUEST: com RLS efetivo, assume `rpg_api` e o owner do principal.
- `admin_connection(pool)` -> acesso DE SISTEMA (worker, cron, wallet, rate limit, ciclo de conta,
  agregados cross-owner): usa o pool admin quando configurado e nunca troca de role.
- `system_scope(connection)` -> efeito DE SISTEMA dentro de uma transacao de request ja aberta
  (confirm de quote / liberacao de reserva da wallet no commit do turno ou no restore): devolve a
  transacao ao login de sessao so durante o bloco e volta para `rpg_api` ao sair, preservando a
  atomicidade com o commit canonico.
"""

from __future__ import annotations

from contextlib import contextmanager
from typing import Any, ContextManager, Iterator

REQUEST_DB_ROLE = "rpg_api"


def admin_connection(pool: Any) -> ContextManager[Any]:
    """Conexao de sistema; fakes de teste sem `admin_connection` caem em `connection()`."""
    opener = getattr(pool, "admin_connection", None)
    return opener() if opener is not None else pool.connection()


@contextmanager
def system_scope(connection: Any) -> Iterator[Any]:
    """Eleva (`SET LOCAL ROLE NONE`) uma transacao que esta em `rpg_api` e restaura ao sair.

    So age em conexoes psycopg reais que estao de fato em `rpg_api`; fakes, pool admin e
    `RPG_REQUEST_RLS=off` passam direto. O codigo que roda aqui ja filtra por owner em Python
    (mesmo nivel de confianca do pool admin)."""
    elevated = False
    if type(connection).__module__.startswith("psycopg"):
        row = connection.execute("select current_user = %s as scoped", (REQUEST_DB_ROLE,)).fetchone()
        scoped = row["scoped"] if isinstance(row, dict) else row[0]
        if scoped:
            connection.execute("SET LOCAL ROLE NONE")
            elevated = True
    try:
        yield connection
        if elevated:
            # Os gatilhos de conciliacao da wallet sao DEFERRABLE INITIALLY DEFERRED e rodariam no
            # COMMIT como `rpg_api` (sem acesso a wallet). Checa-os agora, ainda elevado; os unicos
            # deferrable do schema `app` sao os da wallet (todos initially deferred).
            connection.execute("SET CONSTRAINTS ALL IMMEDIATE")
            connection.execute("SET CONSTRAINTS ALL DEFERRED")
    finally:
        if elevated:
            from psycopg import pq

            # Transacao abortada sera desfeita inteira (e o SET LOCAL junto); so restaura se viva.
            if connection.info.transaction_status == pq.TransactionStatus.INTRANS:
                connection.execute(f"SET LOCAL ROLE {REQUEST_DB_ROLE}")
