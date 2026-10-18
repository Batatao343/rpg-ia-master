"""SPEC-192: montagem de env Vercel (offline, sem rede)."""
import pytest

from scripts.staging import vercel_env as ve

FILES = {k: f"v-{k}" for k in ve.SECRET_FROM_FILE}


def test_production_has_runtime_contract_and_no_literal_leak_in_preview():
    prod, prev = ve.build_env(FILES)
    assert prod["RPG_RUNTIME_PROFILE"] == "hosted-supabase"
    assert prod["RPG_CORS_ORIGINS"] == f"https://{ve.PUBLIC_HOST}"
    assert prod["RPG_COOKIE_SECURE"] == "1"
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
           "SUPABASE_PUBLISHABLE_KEY": "sb_publishable_x", "SUPABASE_SERVICE_ROLE_KEY": "sb_secret_y",
           "RPG_REQUEST_RLS": "off",  # SPEC-224: DSN unico postgres (rollback); o foco aqui e so o bind
           "RPG_ALLOW_INSECURE_HOSTED": "1"}  # só o bind é o foco; hardening: tests/test_boot_policy.py
    assert RuntimeConfig.from_env(env).bind_host == "0.0.0.0"


def test_refuses_other_project(capsys):
    assert ve.main(["--project-name", "outro", "--dry-run"]) == 2


def test_runtime_dsn_replaces_admin_dsn_unless_rollback_requested():
    files = {**FILES, "RPG_RUNTIME_DATABASE_URL": "postgresql://rpg_runtime.ref:x@h.pooler.supabase.com:6543/postgres",
             "RPG_ADMIN_DATABASE_URL": "postgresql://rpg_admin.ref:y@h.pooler.supabase.com:6543/postgres"}
    prod = ve.build_env(files)[0]
    assert prod["DATABASE_URL"] == files["RPG_RUNTIME_DATABASE_URL"]
    assert prod["RPG_ADMIN_DATABASE_URL"] == files["RPG_ADMIN_DATABASE_URL"] and "RPG_REQUEST_RLS" not in prod
    rollback = ve.build_env(files, use_admin_dsn=True)[0]  # SPEC-224: DSN unico + RLS por request desligado
    assert rollback["DATABASE_URL"] == FILES["DATABASE_URL"] and rollback["RPG_REQUEST_RLS"] == "off"
    assert "RPG_ADMIN_DATABASE_URL" not in rollback
    unprovisioned = ve.build_env(FILES)[0]
    assert unprovisioned["DATABASE_URL"] == FILES["DATABASE_URL"] and unprovisioned["RPG_REQUEST_RLS"] == "off"


def test_runtime_dsn_without_admin_dsn_refuses_to_deploy_a_boot_that_would_fail():
    files = {**FILES, "RPG_RUNTIME_DATABASE_URL": "postgresql://rpg_runtime.ref:x@h.pooler.supabase.com:6543/postgres"}
    with pytest.raises(KeyError, match="RPG_ADMIN_DATABASE_URL"):
        ve.build_env(files)


def test_staging_runs_real_llm_with_a_daily_cap_and_never_mock():
    """2026-10-17: staging sai do MockLLM (proibido em hosted, SPEC-218) para Groq real com teto diario."""
    from infrastructure.runtime import FORBIDDEN_IN_HOSTED
    prod, prev = ve.build_env(FILES)
    assert not set(FORBIDDEN_IN_HOSTED) & (prod.keys() | prev.keys())
    assert "RPG_FORCE_MOCK" in ve.REMOVED_NAMES and "LLM_PROVIDER" not in prod
    assert prod["GROQ_API_KEY"] == "v-GROQ_API_KEY" and len(prod["RPG_TELEMETRY_SECRET"]) > 0
    assert float(prod["RPG_DAILY_SPEND_CAP_BRL"]) > 0
    # SPEC-237: Jina precificado por token => cap de texto ligado por padrao; --no-text-cap o apaga
    assert prod["RPG_DAILY_SPEND_CAP_TEXT"] == "1" and "RPG_DAILY_SPEND_CAP_TEXT" not in prev
    assert "RPG_DAILY_SPEND_CAP_TEXT" not in ve.stale_names(prod)
    rollback = ve.build_env(FILES, text_cap=False)[0]
    assert "RPG_DAILY_SPEND_CAP_TEXT" not in rollback and "RPG_DAILY_SPEND_CAP_TEXT" in ve.stale_names(rollback)
    assert {"GROQ_API_KEY", "RPG_TELEMETRY_SECRET"} <= ve.FORBIDDEN_IN_PREVIEW


def test_switching_rls_mode_deletes_the_other_mode_variable():
    """Rollback (--use-admin-dsn) e volta ao RLS: o upsert nao apaga, entao o par do outro modo sai."""
    files = {**FILES, "RPG_RUNTIME_DATABASE_URL": "postgresql://rpg_runtime.ref:x@h.pooler.supabase.com:6543/postgres",
             "RPG_ADMIN_DATABASE_URL": "postgresql://rpg_admin.ref:y@h.pooler.supabase.com:6543/postgres"}
    rls = ve.build_env(files)[0]
    assert "RPG_REQUEST_RLS" in ve.stale_names(rls) and "RPG_ADMIN_DATABASE_URL" not in ve.stale_names(rls)
    rollback = ve.build_env(files, use_admin_dsn=True)[0]
    assert "RPG_ADMIN_DATABASE_URL" in ve.stale_names(rollback) and "RPG_REQUEST_RLS" not in ve.stale_names(rollback)


def test_deepseek_key_is_pushed_as_primary_secret_and_never_to_preview():
    """2026-10-17: dono autorizou DeepSeek no staging (primario de ROUTES); Groq continua como fallback."""
    prod, prev = ve.build_env({**FILES, "DEEPSEEK_API_KEY": "v-ds"})
    assert prod["DEEPSEEK_API_KEY"] == "v-ds" and prod["GROQ_API_KEY"] == "v-GROQ_API_KEY"
    assert "DEEPSEEK_API_KEY" in ve.FORBIDDEN_IN_PREVIEW and "DEEPSEEK_API_KEY" not in prev
    assert "DEEPSEEK_API_KEY" not in ve.build_env(FILES)[0]  # opcional: sem a chave o Groq assume
    # SPEC-236 §6.1: chave invalida temporaria (literal publico) forca a falha do primario
    broken = ve.build_env({**FILES, "DEEPSEEK_API_KEY": "v-ds"}, invalid_deepseek_key=True)[0]
    assert broken["DEEPSEEK_API_KEY"] == ve.INVALID_DEEPSEEK_KEY != "v-ds"


def test_projection_mode_flag_sets_post_response_and_inline_deletes_it():
    """SPEC-213 rollout no staging: post_response e opt-in; inline (default) apaga a variavel."""
    from services import projections
    inline = ve.build_env(FILES)[0]
    assert "RPG_PROJECTION_MODE" not in inline and "RPG_PROJECTION_MODE" in ve.stale_names(inline)
    on, prev = ve.build_env(FILES, projection_mode="post_response")
    assert on[projections.MODE_ENV] == "post_response" and "RPG_PROJECTION_MODE" not in prev
    assert "RPG_PROJECTION_MODE" not in ve.stale_names(on)
    with pytest.raises(ValueError):
        ve.build_env(FILES, projection_mode="job")
