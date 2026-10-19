"""SPEC-280: find and (optionally) delete games whose owner no longer exists in Supabase Auth.

Dry-run by default; prints counts only (no ids/PII). Deleting needs ``--apply --expect N`` where N is the
orphan count seen in the dry-run. Refuses when auth.users is missing/empty (OIDC profile: everything would
look orphaned) or when usage_events still cascades from games (SPEC-279 not applied: spend would vanish).
Owners with any SPEC-190 tombstone (deleting/deleted) are left to that flow. Only for databases of the
``hosted-supabase`` profile: in a mixed database (OIDC owners + some Auth users) OIDC games would look
orphaned — the ``--expect`` count from the dry-run is the last barrier, so read it before applying.

  uv run --frozen python scripts/admin_orphan_games.py --dsn-env RPG_STAGING_DB_URL --env-file .env.staging
  uv run --frozen python scripts/admin_orphan_games.py --dsn-env RPG_STAGING_DB_URL --env-file .env.staging \
      --apply --expect 13 --out docs/staging-wave-2026-10-17/evidence/spec280_orphans_apply.json
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from decimal import Decimal
from pathlib import Path
from typing import Any
from collections.abc import Sequence

FINANCIAL_TABLES = (
    "wallet_accounts",
    "wallet_entries",
    "wallet_reservations",
    "wallet_attempt_tickets",
    "wallet_settled_usage",
    "payment_orders",
    "wallet_debt_entries",
    "purchase_reconciliation_state",
    "google_play_purchases",
)

_ORPHANS = """select g.id, g.owner_id from app.games g
    where not exists (select 1 from auth.users u where u.id = g.owner_id)
      and not exists (select 1 from app.account_deletions d where d.owner_id = g.owner_id)"""


class OrphanCleanupRefused(RuntimeError):
    pass


def _one(conn, sql: str, params: Sequence[Any] = ()) -> Any:
    row = conn.execute(sql, params).fetchone()
    return next(iter(row.values())) if isinstance(row, dict) else row[0]


def _guards(conn) -> None:
    if _one(conn, "select to_regclass('auth.users') is not null") is not True:
        raise OrphanCleanupRefused("auth.users ausente: perfil sem Supabase Auth")
    if not _one(conn, "select exists(select 1 from auth.users)"):
        raise OrphanCleanupRefused("auth.users vazio: todo jogo pareceria órfão")
    cascade = _one(
        conn,
        """select count(*) from pg_constraint
        where conrelid = 'app.usage_events'::regclass and contype = 'f'
          and confrelid in ('app.games'::regclass, 'app.operations'::regclass) and confdeltype = 'c'""",
    )
    if cascade:
        raise OrphanCleanupRefused(
            "usage_events ainda cascateia de games/operations (aplique a SPEC-279)"
        )


def _snapshot(conn, owners: list) -> dict:
    spend = _one(
        conn,
        """select coalesce(sum(cost_usd), 0) from app.usage_events
        where owner_id = any(%s) and counts_as_spend""",
        (owners,),
    )
    usage = _one(conn, "select count(*) from app.usage_events where owner_id = any(%s)", (owners,))
    financial = {}
    for table in FINANCIAL_TABLES:
        if _one(conn, "select to_regclass(%s) is not null", (f"app.{table}",)):
            financial[table] = _one(
                conn, f"select count(*) from app.{table} where owner_id = any(%s)", (owners,)
            )
    return {"spend_usd": Decimal(spend), "usage_events": int(usage), "financial_rows": financial}


def _col(row, name: str, index: int):
    return row[name] if isinstance(row, dict) else row[index]


def plan(conn) -> dict:
    _guards(conn)
    rows = conn.execute(_ORPHANS).fetchall()
    owners = sorted({_col(r, "owner_id", 1) for r in rows})
    snap = _snapshot(conn, owners)
    skipped = _one(
        conn,
        """select count(*) from app.games g join app.account_deletions d
        on d.owner_id = g.owner_id
        where not exists (select 1 from auth.users u where u.id = g.owner_id)""",
    )
    return {
        "orphan_games": len(rows),
        "orphan_owners": len(owners),
        "orphan_usage_events": snap["usage_events"],
        "orphan_usage_spend_usd": snap["spend_usd"],
        "skipped_account_deletion_tombstone": int(skipped),
    }


def apply(conn, expect: int) -> dict:
    """Delete the orphans inside the caller's transaction; raise (caller rolls back) on any mismatch."""
    _guards(conn)
    rows = conn.execute(_ORPHANS + " for update of g").fetchall()
    ids = [_col(r, "id", 0) for r in rows]
    owners = sorted({_col(r, "owner_id", 1) for r in rows})
    if len(ids) != expect:
        raise OrphanCleanupRefused(f"esperado {expect} órfãos, medido {len(ids)}")
    before = _snapshot(conn, owners)
    deleted = conn.execute("delete from app.games where id = any(%s)", (ids,)).rowcount
    after = _snapshot(conn, owners)
    if deleted != expect or before != after:
        raise OrphanCleanupRefused("gasto/dados financeiros mudariam: rollback")
    return {
        "deleted_games": deleted,
        "owners": len(owners),
        "spend_before_usd": before["spend_usd"],
        "spend_after_usd": after["spend_usd"],
        "usage_events_before": before["usage_events"],
        "usage_events_after": after["usage_events"],
        "financial_rows_before": before["financial_rows"],
        "financial_rows_after": after["financial_rows"],
    }


def _connect(dsn: str):
    import psycopg
    from psycopg.rows import dict_row

    return psycopg.connect(dsn, row_factory=dict_row)


def _dsn(name: str, env_file: str | None) -> str:
    if env_file:
        from dotenv import dotenv_values

        value = dotenv_values(env_file).get(name)
    else:
        value = os.environ.get(name)
    if not value:
        raise SystemExit(f"{name} ausente")
    return value


def main(argv: Sequence[str] | None = None) -> int:
    p = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    p.add_argument(
        "--dsn-env", required=True, help="nome da variável com o DSN (o valor nunca é impresso)"
    )
    p.add_argument("--env-file", help="dotenv de onde ler --dsn-env (não exporta para o processo)")
    p.add_argument("--apply", action="store_true", help="apaga (padrão: só conta)")
    p.add_argument("--expect", type=int, help="com --apply: número de órfãos visto no dry-run")
    p.add_argument("--out", help="grava o resultado (só contagens) neste JSON")
    a = p.parse_args(argv)
    if a.apply and a.expect is None:
        p.error("--apply exige --expect N (o número do dry-run)")
    result: dict[str, Any] = {"mode": "apply" if a.apply else "dry-run"}
    with _connect(_dsn(a.dsn_env, a.env_file)) as conn:
        if a.apply:
            with conn.transaction():
                result["apply"] = apply(conn, a.expect)
        result["plan"] = plan(conn)
        conn.rollback()
    result["ok"] = not (a.apply and result["plan"]["orphan_games"])  # after apply: must be 0
    text = json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True, default=str)
    if a.out:
        Path(a.out).parent.mkdir(parents=True, exist_ok=True)
        Path(a.out).write_text(text + "\n", encoding="utf-8")
    print(text)
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    sys.exit(main())
