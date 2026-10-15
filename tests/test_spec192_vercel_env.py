"""SPEC-192: montagem de env Vercel (offline, sem rede)."""
import pytest

from scripts.staging import vercel_env as ve

FILES = {k: f"v-{k}" for k in ve.SECRET_FROM_FILE}


def test_production_has_runtime_contract_and_no_literal_leak_in_preview():
    prod, prev = ve.build_env(FILES)
    assert prod["RPG_RUNTIME_PROFILE"] == "hosted-supabase"
    assert prod["RPG_CORS_ORIGINS"] == f"https://{ve.PUBLIC_HOST}"
    assert prod["RPG_COOKIE_SECURE"] == "1" and prod["RPG_FORCE_MOCK"] == "1"
    assert not ve.FORBIDDEN_IN_PREVIEW & prev.keys()
    assert not {"DATABASE_URL", "SUPABASE_SERVICE_ROLE_KEY", "RPG_CRON_SECRET"} & prev.keys()


def test_missing_secret_names_reported_without_values():
    files = dict(FILES)
    del files["DATABASE_URL"]
    with pytest.raises(KeyError) as e:
        ve.build_env(files)
    assert "DATABASE_URL" in str(e.value) and "v-" not in str(e.value)


def test_bind_host_accepted_by_runtime_validation(monkeypatch):
    from infrastructure.runtime import RuntimeConfig
    env = {"RPG_RUNTIME_PROFILE": "hosted-supabase", "RPG_BIND_HOST": "0.0.0.0",
           "DATABASE_URL": "postgresql://postgres.abcdefghij:p@aws-0-sa-east-1.pooler.supabase.com:6543/postgres",
           "SUPABASE_URL": "https://abcdefghij.supabase.co",
           "SUPABASE_PUBLISHABLE_KEY": "sb_publishable_x", "SUPABASE_SERVICE_ROLE_KEY": "sb_secret_y"}
    assert RuntimeConfig.from_env(env).bind_host == "0.0.0.0"


def test_refuses_other_project(capsys):
    assert ve.main(["--project-name", "outro", "--dry-run"]) == 2
