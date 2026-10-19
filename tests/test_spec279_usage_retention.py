"""SPEC-279 (offline): usage facts survive a campaign delete; readers keep counting them."""
from __future__ import annotations

import inspect
import re
from pathlib import Path

MIGRATION = Path(__file__).resolve().parents[1] / "supabase" / "migrations" / \
    "20261019150000_usage_events_survive_game_delete.sql"


def _sql() -> str:
    return re.sub(r"\s+", " ", MIGRATION.read_text(encoding="utf-8").lower())


def test_game_link_is_set_null_and_operation_link_no_longer_cascades():
    sql = _sql()
    assert "references app.games(id) on delete set null" in sql
    assert "drop constraint if exists usage_events_operation_id_fkey" in sql
    assert "references app.operations" not in sql      # opaque id, like wallet_settled_usage
    assert "drop not null" not in sql
    assert "on delete cascade" not in sql


def test_migration_is_idempotent_and_regrants_runtime():
    sql = _sql()
    assert "add column if not exists operation_kind" in sql
    assert "drop constraint if exists usage_events_operation_id_fkey" in sql
    assert "drop constraint if exists usage_events_game_id_fkey" in sql
    assert "create or replace function app.validate_usage_attribution" in sql
    assert sql.rstrip().endswith("select app.grant_runtime_access();")


def test_attribution_trigger_snapshots_kind_from_operations_and_still_fails_closed():
    sql = _sql()
    assert "new.operation_kind := canonical_kind" in sql
    assert "usage attribution mismatch" in sql
    # backfill never touches owners under account erasure (their write fence would reject it)
    assert "not exists (select 1 from app.account_deletions" in sql


def test_readers_keep_events_whose_operation_was_deleted():
    from infrastructure.account_read_model import PostgresAccountReader
    from infrastructure.finops_reader import PostgresFinopsReader
    for fn in (PostgresFinopsReader.ops_counts, PostgresAccountReader.usage):
        src = re.sub(r"\s+", " ", inspect.getsource(fn))
        assert "left join app.operations o" in src
        assert "coalesce(" in src and "operation_kind" in src
