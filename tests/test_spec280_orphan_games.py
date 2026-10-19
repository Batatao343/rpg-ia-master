"""SPEC-280 (offline): Auth deletion erases the owner's games; orphan cleanup is dry-run by default."""
from __future__ import annotations

import re
from pathlib import Path

import pytest

MIGRATION = Path(__file__).resolve().parents[1] / "supabase" / "migrations" / \
    "20261019151000_auth_user_delete_erases_games.sql"


def _sql() -> str:
    return re.sub(r"\s+", " ", MIGRATION.read_text(encoding="utf-8").lower())


def test_trigger_after_delete_on_auth_users_is_definer_and_portable():
    sql = _sql()
    assert "after delete on auth.users" in sql
    assert "security definer set search_path = ''" in sql
    assert "delete from app.games where owner_id = old.id" in sql
    assert "to_regclass('auth.users')" in sql
    assert "if exists (select 1 from app.account_deletions where owner_id = old.id) then return old" in sql
    assert "rolbypassrls" in sql


def test_migration_is_idempotent_and_locked_down():
    sql = _sql()
    assert "create or replace function app.erase_games_of_deleted_auth_user" in sql
    assert "drop trigger if exists rpg_erase_games_on_auth_delete on auth.users" in sql
    assert "revoke all on function app.erase_games_of_deleted_auth_user() from public, anon, authenticated, rpg_api" in sql
    assert sql.rstrip().endswith("select app.grant_runtime_access();")


def test_cli_is_dry_run_by_default(monkeypatch):
    import scripts.admin_orphan_games as m
    calls = []
    monkeypatch.setattr(m, "_connect", lambda dsn: _FakeConn())
    monkeypatch.setattr(m, "plan", lambda conn: calls.append("plan") or {"orphan_games": 3})
    monkeypatch.setattr(m, "apply", lambda conn, expect: calls.append("apply") or {})
    monkeypatch.setenv("X_DSN", "postgresql://u@h/db")
    assert m.main(["--dsn-env", "X_DSN"]) == 0
    assert calls == ["plan"]


def test_cli_apply_requires_expect(monkeypatch):
    import scripts.admin_orphan_games as m
    monkeypatch.setenv("X_DSN", "postgresql://u@h/db")
    with pytest.raises(SystemExit):
        m.main(["--dsn-env", "X_DSN", "--apply"])


class _FakeConn:
    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False

    def transaction(self):
        return self

    def rollback(self):
        pass
