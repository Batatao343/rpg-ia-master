from pathlib import Path


def test_claim_insert_handles_every_unique_arbiter_before_validating_existing():
    source = Path("infrastructure/postgres_turns.py").read_text(encoding="utf-8")
    claim_insert = source.split("insert into app.operations", 1)[1].split(
        "returning id", 1,
    )[0]
    assert "on conflict do nothing" in claim_insert.lower()
    assert "on conflict (id)" not in claim_insert.lower()


def test_migration_removes_only_redundant_owner_operation_unique():
    migration = Path(
        "supabase/migrations/20260828163000_drop_redundant_operations_unique.sql"
    ).read_text(encoding="utf-8").lower()
    assert "drop constraint if exists operations_owner_id_id_key" in migration
    assert "drop constraint" in migration
    assert "primary key" not in migration.split("alter table", 1)[1]
