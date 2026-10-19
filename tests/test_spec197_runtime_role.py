"""SPEC-197 R-05: helpers offline de scripts/staging/runtime_role.py."""

import pytest

from infrastructure.runtime import hosted_supabase_dsn_ref
from scripts.staging import common
from scripts.staging import runtime_role as rr


def test_dsn_uses_tenant_user_port_6543_and_passes_runtime_validation():
    dsn = rr.runtime_dsn(
        "postgresql://postgres.abcdefghij:p@aws-0-sa-east-1.pooler.supabase.com:5432/postgres",
        "abcdefghij",
        "pw/with+chars",
    )
    assert "rpg_runtime.abcdefghij:" in dsn and ":6543/" in dsn and "sslmode=require" in dsn
    assert "pw/with" not in dsn  # senha percent-encoded
    assert hosted_supabase_dsn_ref(dsn) == "abcdefghij"
    assert common.target_matches_ref("abcdefghij", dsn)


def test_refuses_non_pooler_host():
    with pytest.raises(common.GuardError):
        rr.runtime_dsn(
            "postgresql://postgres:p@db.abcdefghij.supabase.co:5432/postgres", "abcdefghij", "x"
        )


def test_password_is_48_alnum_and_env_upsert_replaces_in_place(tmp_path):
    pw = rr.new_password()
    assert len(pw) == 48 and pw.isalnum()
    f = tmp_path / ".env.staging"
    f.write_text("A=1\nRPG_RUNTIME_DB_PASSWORD=old\n", encoding="utf-8")
    rr.upsert_env(f, {"RPG_RUNTIME_DB_PASSWORD": "new", "B": "2"})
    assert f.read_text(encoding="utf-8").splitlines() == [
        "A=1",
        "RPG_RUNTIME_DB_PASSWORD=new",
        "B=2",
    ]
