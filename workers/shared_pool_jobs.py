"""shared_pool_jobs.py — job de promoção do pool compartilhado (SPEC-297 R18/R20).

`promote_due_job` é chamado pelo cron interno (hosted) e por `scripts/pool_promote.py`
(legacy, manual). Roda fora do turno; nunca dentro de uma request de jogador.

Com `pool` (conexões Postgres) o job liga:
- R20: cada avaliação grava `usage_events` sob um dono de SISTEMA (`SYSTEM_OWNER_ID`, operação
  `pool_evaluation`) — a FinOps vê o custo e nenhuma carteira/teto de jogador é tocado;
- R14 `pii`: e-mail e nome de exibição do dono de origem entram como `owner_values`.
Sem `pool` (legacy) não há contas: o uso vira só um log `pool.eval_usage` (contagens).
"""

from __future__ import annotations

from collections.abc import Callable, Sequence
from datetime import datetime
from hashlib import sha256
from uuid import UUID, uuid4

from observability.telemetry import log_event
from services.shared_pool import promote_due

# Dono técnico das linhas de custo do sistema (não é uma conta; sem FK em usage_events).
SYSTEM_OWNER_ID = UUID("00000000-0000-0000-0000-000000000297")


def log_usage_sink(entry, attempts: list[dict]) -> None:
    """Legacy: sem tabela de uso; só contagem (sem conteúdo)."""
    log_event("pool", "eval_usage", entry_id=entry.entry_id, attempts=len(attempts))


def make_usage_sink(pool) -> Callable[[object, list[dict]], None]:
    """Grava as tentativas de avaliação em `app.usage_events` (dono de sistema)."""

    def sink(entry, attempts: list[dict]) -> None:
        from infrastructure.db_roles import admin_connection
        from infrastructure.usage_events import append_usage_events
        from services.usage_metering import normalize_attempts

        operation_id = uuid4()
        request_hash = sha256(f"pool_evaluation:{entry.entry_id}".encode()).hexdigest()
        events = normalize_attempts(
            attempts, operation_id=operation_id, component="pool_eval", category="llm"
        )
        if not events:  # nada chegou a um provider (mock/build_error): sem custo a registrar
            return
        with admin_connection(pool) as connection, connection.transaction():
            connection.execute(
                """insert into app.operations
                  (id,owner_id,game_id,kind,status,request_sha256,finished_at)
                values (%s,%s,null,'pool_evaluation','completed',%s,now())""",
                (operation_id, SYSTEM_OWNER_ID, request_hash),
            )
            append_usage_events(
                connection,
                owner_id=SYSTEM_OWNER_ID,
                operation_id=operation_id,
                game_id=None,
                events=events,
            )

    return sink


def make_owner_values(pool) -> Callable[[object], Sequence[str]]:
    """E-mail e nomes de exibição do dono de origem (fail-closed: erro propaga)."""

    def lookup(entry) -> Sequence[str]:
        owner = getattr(entry, "origin_owner_id", None)
        if owner is None:
            return ()
        from infrastructure.db_roles import admin_connection

        with admin_connection(pool) as connection:
            # `rpg_runtime` não lê o schema auth: só as funções SECURITY DEFINER (R-1).
            row = connection.execute(
                "select app.runtime_auth_email(%s) as email, "
                "app.runtime_auth_display_names(%s) as names",
                (owner, owner),
            ).fetchone()
        if not row:
            return ()
        values = [row["email"]] if row.get("email") else []
        values += [str(n) for n in (row.get("names") or [])]
        return tuple(v for v in values if len(v.strip()) >= 3)

    return lookup


def promote_due_job(
    pool_store, llm=None, now: datetime | None = None, *, pool=None, **kwargs
) -> dict[str, int]:
    """Promove/rejeita entradas vencidas. Devolve só contagens.

    `pool` = pool Postgres do runtime (hosted/local): liga o custo (R20) e o PII do dono (R14)."""
    if pool is not None:
        kwargs.setdefault("usage_sink", make_usage_sink(pool))
        kwargs.setdefault("owner_values", make_owner_values(pool))
    else:
        kwargs.setdefault("usage_sink", log_usage_sink)
    return promote_due(pool_store, now=now, llm=llm, **kwargs)
