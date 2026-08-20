import pytest

from infrastructure.runtime import RuntimeConfig


def test_legacy_default_e_loopback():
    config = RuntimeConfig.from_env({})
    assert config.profile == "legacy"
    assert config.game_store == "file"


def test_legacy_recusa_exposicao_publica():
    with pytest.raises(ValueError, match="loopback"):
        RuntimeConfig.from_env({"RPG_BIND_HOST": "0.0.0.0"})


def test_hosted_falha_fechado_com_filesystem_auth_ou_sem_db():
    base = {"RPG_RUNTIME_PROFILE": "hosted", "RPG_BIND_HOST": "0.0.0.0"}
    with pytest.raises(ValueError, match="DATABASE_URL"):
        RuntimeConfig.from_env(base)
    with pytest.raises(ValueError, match="autenticação"):
        RuntimeConfig.from_env({**base, "DATABASE_URL": "postgresql://local", "RPG_AUTH_MODE": "disabled"})
    with pytest.raises(ValueError, match="filesystem"):
        RuntimeConfig.from_env({**base, "DATABASE_URL": "postgresql://local", "RPG_BLOB_STORE": "file"})


def test_local_aceita_stack_completa():
    config = RuntimeConfig.from_env(
        {"RPG_RUNTIME_PROFILE": "local", "DATABASE_URL": "postgresql://localhost/postgres"}
    )
    assert config.memory_store == "pgvector"
    assert config.auth_mode == "supabase"


def test_portable_exige_oidc_e_s3_sem_supabase():
    base = {
        "RPG_RUNTIME_PROFILE": "portable",
        "DATABASE_URL": "postgresql://localhost/postgres",
    }
    with pytest.raises(ValueError, match="RPG_OIDC_USERINFO_URL"):
        RuntimeConfig.from_env(base)
    config = RuntimeConfig.from_env({
        **base,
        "RPG_OIDC_USERINFO_URL": "https://identity.example/userinfo",
        "RPG_OIDC_ISSUER": "https://identity.example",
    })
    assert config.blob_store == "s3"
    assert config.auth_mode == "oidc"
    assert config.supabase_url == ""
