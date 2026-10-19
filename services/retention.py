"""SPEC-222 R7: TTL/purge de metadados técnicos por owner (cron /internal/cron/operations).

Os prazos aqui (D-B, default da spec) são declarados na seção de retenção da política
(docs/spec222/retencao.md, validada por teste). Cada lote é limitado para caber no
orçamento do cron; o que sobrar sai no próximo ciclo. Saída: só contagens.
"""

from __future__ import annotations

from infrastructure.db_roles import admin_connection

BATCH = 1000
OPERATIONS_DAYS = 90
JOBS_DAYS = 30
USAGE_EVENTS_MONTHS = 13
FINOPS_EVALUATIONS_DAYS = 180
DAILY_COUNTERS_DAYS = 7
ACCOUNT_DELETION_COMPACT_DAYS = 30
ACCOUNT_DELETION_YEARS = 5

RETENTION_RULES: dict[str, str] = {
    "operations": f"{OPERATIONS_DAYS} dias após a conclusão (recibos de idempotência)",
    "jobs": f"{JOBS_DAYS} dias após estado terminal",
    "usage_events": f"{USAGE_EVENTS_MONTHS} meses (prazo fiscal/contábil do consumo)",
    "finops_evaluations": f"{FINOPS_EVALUATIONS_DAYS} dias",
    "owner_daily_counters": f"{DAILY_COUNTERS_DAYS} dias (contador técnico da cota diária, SPEC-219)",
    "account_deletions": (
        f"reduzida a owner_id e data após {ACCOUNT_DELETION_COMPACT_DAYS} dias; "
        f"apagada após {ACCOUNT_DELETION_YEARS} anos"
    ),
}

_STATEMENTS: tuple[tuple[str, str], ...] = (
    # Operations still referenced by turns (game history), usage events (13-month window)
    # or wallet reservations (financial) are kept; FK cascades must never erase them.
    (
        "operations",
        f"""delete from app.operations where id in (
        select o.id from app.operations o
        where o.status in ('completed','failed','abandoned')
          and o.finished_at < now() - interval '{OPERATIONS_DAYS} days'
          and not exists (select 1 from app.turns t where t.operation_id = o.id)
          and not exists (select 1 from app.usage_events u where u.operation_id = o.id)
          and not exists (select 1 from app.wallet_reservations r where r.usage_operation_id = o.id)
        limit {BATCH})""",
    ),
    (
        "jobs",
        f"""delete from app.jobs where id in (
        select id from app.jobs where status in ('succeeded','dead','cancelled')
          and updated_at < now() - interval '{JOBS_DAYS} days' limit {BATCH})""",
    ),
    (
        "usage_events",
        f"""delete from app.usage_events where event_id in (
        select event_id from app.usage_events
        where created_at < now() - interval '{USAGE_EVENTS_MONTHS} months' limit {BATCH})""",
    ),
    (
        "finops_evaluations",
        f"""delete from app.finops_evaluations where evaluation_id in (
        select evaluation_id from app.finops_evaluations
        where evaluated_at < now() - interval '{FINOPS_EVALUATIONS_DAYS} days' limit {BATCH})""",
    ),
    (
        "owner_daily_counters",
        f"""delete from app.owner_daily_counters
        where day < (now() at time zone 'utc')::date - {DAILY_COUNTERS_DAYS}""",
    ),
    (
        "account_deletions_compacted",
        f"""update app.account_deletions
        set blob_keys = '{{}}', recovery_attempted_at = null, sessions_revoked_at = null,
            requested_at = completed_at
        where owner_id in (select owner_id from app.account_deletions
          where status = 'deleted'
            and completed_at < now() - interval '{ACCOUNT_DELETION_COMPACT_DAYS} days'
            and (recovery_attempted_at is not null or sessions_revoked_at is not null
                 or requested_at <> completed_at or cardinality(blob_keys) > 0)
          limit {BATCH})""",
    ),
    (
        "account_deletions",
        f"""delete from app.account_deletions where owner_id in (
        select owner_id from app.account_deletions where status = 'deleted'
          and completed_at < now() - interval '{ACCOUNT_DELETION_YEARS} years' limit {BATCH})""",
    ),
)


def purge_expired(pool) -> dict[str, int]:
    """Apply every TTL once (bounded). Missing tables (older schema) are skipped."""
    result: dict[str, int] = {}
    with admin_connection(pool) as connection:
        for name, sql in _STATEMENTS:
            table = name.removesuffix("_compacted")
            if (
                connection.execute("select to_regclass(%s) as r", (f"app.{table}",)).fetchone()["r"]
                is None
            ):
                continue
            with connection.transaction():
                result[f"purged_{name}"] = connection.execute(sql).rowcount
    return result


def retention_markdown() -> str:
    """R10: tabela de retenção derivada do código (fonte da seção §5 da política)."""
    from infrastructure.account_lifecycle import PRIVATE_TABLES, RETAINED_WITH_REASON

    lines = [
        "# Retenção de dados — gerado de `infrastructure/account_lifecycle.py` e `services/retention.py`",
        "",
        "> Não editar à mão: `uv run python scripts/gen_retention_doc.py`. Teste:",
        "> `tests/test_spec222_transparency.py`. É a fonte da seção 5 da política de privacidade.",
        "",
        "## Apagado na exclusão de conta",
        "",
        ", ".join(f"`{table}`" for table in PRIVATE_TABLES) + ".",
        "",
        "## Retido após a exclusão (motivo legal e prazo)",
        "",
        "| Tabela | Motivo e prazo |",
        "|---|---|",
        *(f"| `{table}` | {reason} |" for table, reason in RETAINED_WITH_REASON.items()),
        "",
        "## TTL de metadados técnicos (cron `/internal/cron/operations`)",
        "",
        "| Tabela | Prazo |",
        "|---|---|",
        *(f"| `{table}` | {rule} |" for table, rule in RETENTION_RULES.items()),
        "",
    ]
    return "\n".join(lines)
