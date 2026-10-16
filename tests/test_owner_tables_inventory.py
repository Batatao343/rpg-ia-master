"""SPEC-222 R3: toda tabela app.* com owner_id tem destino declarado na exclusão de conta.

Read-only contra o Postgres local: nenhuma tabela nova por owner pode nascer fora de
PRIVATE_TABLES (apagada) ∪ FINANCIAL_TABLES/RETAINED_WITH_REASON (retida com motivo).
"""
from __future__ import annotations

import os

import pytest

from infrastructure.account_lifecycle import (
    EXPORT_COLUMNS, EXPORT_TABLES, FINANCIAL_TABLES, PRIVATE_TABLES, RETAINED_WITH_REASON,
)


def test_lists_are_disjoint_and_financial_tables_have_a_reason():
    assert not set(PRIVATE_TABLES) & set(RETAINED_WITH_REASON)
    assert set(FINANCIAL_TABLES) <= set(RETAINED_WITH_REASON)
    assert all(reason.strip() for reason in RETAINED_WITH_REASON.values())
    assert set(EXPORT_TABLES) == set(EXPORT_COLUMNS)
    assert all("purchase_token" not in cols for cols in EXPORT_COLUMNS.values())


@pytest.mark.infra_local
def test_every_owner_table_is_covered_by_account_lifecycle():
    psycopg = pytest.importorskip("psycopg")
    dsn = os.getenv("RPG_TEST_DATABASE_URL")
    if not dsn:
        pytest.skip("RPG_TEST_DATABASE_URL ausente")
    with psycopg.connect(dsn) as db:
        owner_tables = {row[0] for row in db.execute(
            """select c.table_name from information_schema.columns c
               join information_schema.tables t
                 on t.table_schema=c.table_schema and t.table_name=c.table_name
               where c.table_schema='app' and c.column_name='owner_id'
                 and t.table_type='BASE TABLE'""").fetchall()}
        columns = {}
        for table in EXPORT_COLUMNS:
            columns[table] = {row[0] for row in db.execute(
                "select column_name from information_schema.columns where table_schema='app' "
                "and table_name=%s", (table,)).fetchall()}
    covered = set(PRIVATE_TABLES) | set(FINANCIAL_TABLES) | set(RETAINED_WITH_REASON)
    assert owner_tables - covered == set(), "tabela por owner sem destino na exclusão/retenção"
    # Every exported table must exist and every listed column must be real.
    for table, cols in EXPORT_COLUMNS.items():
        assert set(cols) <= columns[table], (table, set(cols) - columns[table])
