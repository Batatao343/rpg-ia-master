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

    env = {
        "RPG_RUNTIME_PROFILE": "hosted-supabase",
        "RPG_BIND_HOST": "0.0.0.0",
        "DATABASE_URL": "postgresql://postgres.abcdefghij:p@aws-0-sa-east-1.pooler.supabase.com:6543/postgres",
        "SUPABASE_URL": "https://abcdefghij.supabase.co",
        "SUPABASE_PUBLISHABLE_KEY": "sb_publishable_x",
        "SUPABASE_SERVICE_ROLE_KEY": "sb_secret_y",
        "RPG_REQUEST_RLS": "off",  # SPEC-224: DSN unico postgres (rollback); o foco aqui e so o bind
        "RPG_ALLOW_INSECURE_HOSTED": "1",
    }  # só o bind é o foco; hardening: tests/test_boot_policy.py
    assert RuntimeConfig.from_env(env).bind_host == "0.0.0.0"


def test_refuses_other_project(capsys):
    assert ve.main(["--project-name", "outro", "--dry-run"]) == 2


def test_runtime_dsn_replaces_admin_dsn_unless_rollback_requested():
    files = {
        **FILES,
        "RPG_RUNTIME_DATABASE_URL": "postgresql://rpg_runtime.ref:x@h.pooler.supabase.com:6543/postgres",
        "RPG_ADMIN_DATABASE_URL": "postgresql://rpg_admin.ref:y@h.pooler.supabase.com:6543/postgres",
    }
    prod = ve.build_env(files)[0]
    assert prod["DATABASE_URL"] == files["RPG_RUNTIME_DATABASE_URL"]
    assert (
        prod["RPG_ADMIN_DATABASE_URL"] == files["RPG_ADMIN_DATABASE_URL"]
        and "RPG_REQUEST_RLS" not in prod
    )
    rollback = ve.build_env(files, use_admin_dsn=True)[
        0
    ]  # SPEC-224: DSN unico + RLS por request desligado
    assert (
        rollback["DATABASE_URL"] == FILES["DATABASE_URL"] and rollback["RPG_REQUEST_RLS"] == "off"
    )
    assert "RPG_ADMIN_DATABASE_URL" not in rollback
    unprovisioned = ve.build_env(FILES)[0]
    assert (
        unprovisioned["DATABASE_URL"] == FILES["DATABASE_URL"]
        and unprovisioned["RPG_REQUEST_RLS"] == "off"
    )


def test_runtime_dsn_without_admin_dsn_refuses_to_deploy_a_boot_that_would_fail():
    files = {
        **FILES,
        "RPG_RUNTIME_DATABASE_URL": "postgresql://rpg_runtime.ref:x@h.pooler.supabase.com:6543/postgres",
    }
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
    assert (
        "RPG_DAILY_SPEND_CAP_TEXT" not in rollback
        and "RPG_DAILY_SPEND_CAP_TEXT" in ve.stale_names(rollback)
    )
    assert {"GROQ_API_KEY", "RPG_TELEMETRY_SECRET"} <= ve.FORBIDDEN_IN_PREVIEW


def test_switching_rls_mode_deletes_the_other_mode_variable():
    """Rollback (--use-admin-dsn) e volta ao RLS: o upsert nao apaga, entao o par do outro modo sai."""
    files = {
        **FILES,
        "RPG_RUNTIME_DATABASE_URL": "postgresql://rpg_runtime.ref:x@h.pooler.supabase.com:6543/postgres",
        "RPG_ADMIN_DATABASE_URL": "postgresql://rpg_admin.ref:y@h.pooler.supabase.com:6543/postgres",
    }
    rls = ve.build_env(files)[0]
    assert "RPG_REQUEST_RLS" in ve.stale_names(
        rls
    ) and "RPG_ADMIN_DATABASE_URL" not in ve.stale_names(rls)
    rollback = ve.build_env(files, use_admin_dsn=True)[0]
    assert "RPG_ADMIN_DATABASE_URL" in ve.stale_names(
        rollback
    ) and "RPG_REQUEST_RLS" not in ve.stale_names(rollback)


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


def test_jev_router_shadow_flag_and_off_deletes_it():
    """SPEC-217 R15: shadow envia modo + chave TypeSafe (secreta); off apaga; primary nunca."""
    off = ve.build_env(FILES)[0]
    assert "RPG_JEV_ROUTER_MODE" not in off and "TYPESAFE_API_KEY" not in off
    assert {"RPG_JEV_ROUTER_MODE", "TYPESAFE_API_KEY", "RPG_JEV_ROUTER_PRIMARY_APPROVED"} <= set(
        ve.stale_names(off)
    )
    with pytest.raises(KeyError) as e:
        ve.build_env(FILES, jev_router_mode="shadow")
    assert "TYPESAFE_API_KEY" in str(e.value)
    on, prev = ve.build_env({**FILES, "JEVMODEL_API_KEY": "v-jev"}, jev_router_mode="shadow")
    assert on["RPG_JEV_ROUTER_MODE"] == "shadow" and on["TYPESAFE_API_KEY"] == "v-jev"
    assert (
        "TYPESAFE_API_KEY" in ve.FORBIDDEN_IN_PREVIEW and not ve.FORBIDDEN_IN_PREVIEW & prev.keys()
    )
    assert "RPG_JEV_ROUTER_PRIMARY_APPROVED" not in on
    assert "RPG_JEV_ROUTER_MODE" not in ve.stale_names(on)
    with pytest.raises(ValueError):
        ve.build_env(FILES, jev_router_mode="primary")


def test_real_turnstile_site_key_and_optional_openai_key_stay_out_of_preview():
    from scripts.staging import vercel_env

    files = {k: "v" for k in vercel_env.SECRET_FROM_FILE}
    prod, _ = vercel_env.build_env(files)
    assert (
        prod["RPG_TURNSTILE_SITE_KEY"] == vercel_env.TURNSTILE_TEST_SITE_KEY
        and "OPENAI_API_KEY" not in prod
    )
    prod, preview = vercel_env.build_env(
        {**files, "TURNSTILE_SITE_KEY": "0x4real", "OPENAI_API_KEY": "sk-x"}
    )
    assert prod["RPG_TURNSTILE_SITE_KEY"] == "0x4real" and prod["OPENAI_API_KEY"] == "sk-x"
    assert "OPENAI_API_KEY" not in preview and "OPENAI_API_KEY" in vercel_env.FORBIDDEN_IN_PREVIEW


def test_jev_router_primary_requires_owner_flag_and_stays_out_of_preview():
    """SPEC-217: primary so com aprovacao explicita do dono; off/shadow apagam a aprovacao."""
    files = {**FILES, "TYPESAFE_API_KEY": "v-ts"}
    with pytest.raises(ValueError):
        ve.build_env(files, jev_router_mode="primary")
    on, prev = ve.build_env(files, jev_router_mode="primary", owner_approved_primary=True)
    assert on["RPG_JEV_ROUTER_MODE"] == "primary" and on["TYPESAFE_API_KEY"] == "v-ts"
    assert on["RPG_JEV_ROUTER_PRIMARY_APPROVED"] == "1"
    assert (
        not {"RPG_JEV_ROUTER_MODE", "TYPESAFE_API_KEY", "RPG_JEV_ROUTER_PRIMARY_APPROVED"}
        & prev.keys()
    )
    assert "RPG_JEV_ROUTER_PRIMARY_APPROVED" not in ve.stale_names(on)
    shadow = ve.build_env(files, jev_router_mode="shadow", owner_approved_primary=True)[0]
    assert "RPG_JEV_ROUTER_PRIMARY_APPROVED" not in shadow
    assert "RPG_JEV_ROUTER_PRIMARY_APPROVED" in ve.stale_names(shadow)
    assert "o primary no staging" in ve.OWNER_PRIMARY_APPROVAL


def test_daily_cap_override_for_spec236_trip_and_default_restores_five():
    """SPEC-236 §6.2: teto baixo temporario provoca trip real; push sem a flag volta a 5."""
    assert ve.build_env(FILES)[0]["RPG_DAILY_SPEND_CAP_BRL"] == "5"
    low, prev = ve.build_env(FILES, daily_cap_brl="0.01")
    assert low["RPG_DAILY_SPEND_CAP_BRL"] == "0.01" and "RPG_DAILY_SPEND_CAP_BRL" not in prev
    for bad in ("0", "-1", "abc"):
        with pytest.raises(ValueError):
            ve.build_env(FILES, daily_cap_brl=bad)


def test_npc_knowledge_flag_sets_mode_and_off_deletes_it():
    import pytest

    on, prev = ve.build_env(FILES, npc_knowledge="on")
    assert on["RPG_NPC_KNOWLEDGE"] == "on" and "RPG_NPC_KNOWLEDGE" not in prev
    off, _ = ve.build_env(FILES)
    assert "RPG_NPC_KNOWLEDGE" not in off
    assert "RPG_NPC_KNOWLEDGE" in ve.stale_names(off)
    with pytest.raises(ValueError):
        ve.build_env(FILES, npc_knowledge="maybe")


def test_world_engine_defaults_to_shadow_on_staging():
    env, prev = ve.build_env(FILES)
    assert env["RPG_WORLD_ENGINE"] == "shadow" and "RPG_WORLD_ENGINE" not in prev
    on, _ = ve.build_env(FILES, world_engine="on")
    assert on["RPG_WORLD_ENGINE"] == "on"
    with pytest.raises(ValueError):
        ve.build_env(FILES, world_engine="maybe")


def test_shared_pool_flag_sets_mode_and_off_deletes_it():
    on, prev = ve.build_env(FILES, shared_pool="shadow")
    assert on["RPG_SHARED_POOL"] == "shadow" and "RPG_SHARED_POOL" not in prev
    off, _ = ve.build_env(FILES)
    assert "RPG_SHARED_POOL" not in off and "RPG_SHARED_POOL" in ve.stale_names(off)
    with pytest.raises(ValueError):
        ve.build_env(FILES, shared_pool="maybe")


def test_world_flags_are_allowlisted():
    env, _ = ve.build_env(FILES, world_flags={"RPG_LAW": "shadow", "RPG_NPC_WORLD": "shadow"})
    env2, _ = ve.build_env(FILES, world_flags={"RPG_RUMORS": "shadow", "RPG_LORE_QUESTS": "shadow"})
    assert env2["RPG_RUMORS"] == "shadow" and env2["RPG_LORE_QUESTS"] == "shadow"
    assert env["RPG_LAW"] == "shadow" and env["RPG_NPC_WORLD"] == "shadow"
    plain, _ = ve.build_env(FILES)
    assert "RPG_LAW" not in plain and "RPG_LAW" in ve.stale_names(plain)
    with pytest.raises(ValueError):
        ve.build_env(FILES, world_flags={"RPG_FORCE_MOCK": "on"})
    with pytest.raises(ValueError):
        ve.build_env(FILES, world_flags={"RPG_LAW": "maybe"})


def test_preset_aprovado_e_o_default_do_staging():
    """25/10: rodar sem flags reproduz o estado aprovado (não apaga mundo vivo nem Jev primary)."""
    preset = ve.load_preset(ve.STAGING_PRESET_PATH)
    assert preset["jev_router_mode"] == "primary" and preset["owner_approved_primary"] is True
    assert preset["world_engine"] == "on" and preset["npc_knowledge"] == "on"
    assert set(preset["flags"]) <= set(ve.WORLD_FLAGS)
    assert all(not k.startswith("_") for k in preset)
    assert ve.load_preset(None) == {}


def test_dynamic_art_liga_a_variavel():
    env, _ = ve.build_env(FILES, dynamic_art=True)
    assert env["RPG_DYNAMIC_ART_ENABLED"] == "1"
    off, _ = ve.build_env(FILES)
    assert "RPG_DYNAMIC_ART_ENABLED" not in off
    assert "RPG_DYNAMIC_ART_ENABLED" in ve.stale_names(off)


def test_spec318_latency_flags_are_allowlisted_and_not_dropped():
    flags = {
        "RPG_NPC_TWO_PHASE": "on",
        "RPG_REPLAN_AFTER": "off",
        "RPG_DAY_DIGEST": "llm",
        "RPG_ARCHIVE_POLICY": "lean",
        "RPG_ARCHIVE_POLICY_SHADOW": "1",
    }
    env, _ = ve.build_env(FILES, world_flags=flags)
    for name, value in flags.items():
        assert env[name] == value
        assert name in ve.OPTIONAL_FLAGS and name in ve.WORLD_FLAGS
    plain, _ = ve.build_env(FILES)
    assert "RPG_ARCHIVE_POLICY" in ve.stale_names(plain)  # ausente => o script apaga a antiga
    with pytest.raises(ValueError):
        ve.build_env(FILES, world_flags={"RPG_ARCHIVE_POLICY": "on"})
    with pytest.raises(ValueError):
        ve.build_env(FILES, world_flags={"RPG_DAY_DIGEST": "shadow"})


@pytest.mark.parametrize("name", ["RPG_NPC_TWO_PHASE", "RPG_REPLAN_AFTER"])
def test_spec318_boolean_flags_reject_shadow(name):
    with pytest.raises(ValueError):
        ve.build_env(FILES, world_flags={name: "shadow"})
