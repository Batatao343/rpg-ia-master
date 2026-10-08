"""SPEC-181: fail-closed hosted topology and redacted, read-only diagnostics."""

from __future__ import annotations

from dataclasses import replace
import base64
import json

import pytest

from infrastructure.runtime import RuntimeConfig


def hosted_env() -> dict[str, str]:
    return {
        "RPG_RUNTIME_PROFILE": "hosted-supabase",
        "RPG_BIND_HOST": "0.0.0.0",
        "DATABASE_URL": (
            "postgresql://postgres.projectref:DB_PASSWORD_SENTINEL@"
            "aws-0-us-east-1.pooler.supabase.com:6543/postgres?sslmode=require"
        ),
        "SUPABASE_URL": "https://projectref.supabase.co",
        "SUPABASE_PUBLISHABLE_KEY": "sb_publishable_PUBLIC_SENTINEL",
        "SUPABASE_SERVICE_ROLE_KEY": "sb_secret_PRIVATE_SENTINEL",
    }


def legacy_service_role_jwt(role: str, ref: str = "projectref") -> str:
    payload = base64.urlsafe_b64encode(json.dumps({"role": role, "ref": ref}).encode()).decode().rstrip("=")
    return f"header.{payload}.signature"


def test_new_profile_and_legacy_contracts() -> None:
    new = RuntimeConfig.from_env(hosted_env())
    assert (new.auth_mode, new.blob_store, new.game_store) == (
        "supabase", "supabase", "postgres",
    )
    assert (new.db_pool_min_size, new.db_pool_max_size, new.db_pool_timeout) == (0, 1, 5.0)
    assert "SENTINEL" not in repr(new)

    assert RuntimeConfig.from_env({}).profile == "legacy"
    local = RuntimeConfig.from_env({
        "RPG_RUNTIME_PROFILE": "local", "DATABASE_URL": "postgresql://localhost/postgres",
    })
    assert (local.auth_mode, local.blob_store, local.db_pool_max_size) == (
        "supabase", "supabase", 4,
    )
    portable = RuntimeConfig.from_env({
        "RPG_RUNTIME_PROFILE": "portable", "DATABASE_URL": "postgresql://localhost/postgres",
        "RPG_OIDC_USERINFO_URL": "https://identity.example/userinfo",
        "RPG_OIDC_ISSUER": "https://identity.example",
    })
    assert (portable.auth_mode, portable.blob_store) == ("oidc", "s3")
    legacy_hosted = RuntimeConfig.from_env({
        "RPG_RUNTIME_PROFILE": "hosted", "RPG_BIND_HOST": "0.0.0.0",
        "DATABASE_URL": "postgresql://user:fake@db.example.com:5432/postgres",
        "RPG_OIDC_USERINFO_URL": "https://identity.example/userinfo",
        "RPG_OIDC_ISSUER": "https://identity.example",
    })
    assert (legacy_hosted.auth_mode, legacy_hosted.blob_store) == ("oidc", "s3")
    with pytest.raises(ValueError, match="OIDC"):
        RuntimeConfig.from_env({
            **hosted_env(), "RPG_RUNTIME_PROFILE": "hosted",
            "RPG_BLOB_STORE": "s3",
        })
    assert RuntimeConfig.from_env({
        **hosted_env(), "SUPABASE_SERVICE_ROLE_KEY": legacy_service_role_jwt("service_role"),
    }).profile == "hosted-supabase"


@pytest.mark.parametrize("key", [
    legacy_service_role_jwt("anon"),
    legacy_service_role_jwt("authenticated"),
    legacy_service_role_jwt("service_role", "otherref"),
    "header.payload.signature",
])
def test_hosted_rejects_non_service_role_jwt(key: str) -> None:
    with pytest.raises(ValueError):
        RuntimeConfig.from_env({**hosted_env(), "SUPABASE_SERVICE_ROLE_KEY": key})


def test_legacy_bind_and_hosted_dsn_are_fail_closed() -> None:
    with pytest.raises(ValueError, match="loopback"):
        RuntimeConfig.from_env({"RPG_BIND_HOST": "127.public.example"})
    base = {
        "RPG_RUNTIME_PROFILE": "hosted", "RPG_BIND_HOST": "0.0.0.0",
        "DATABASE_URL": "postgresql://user:fake@db.example.com:5432/postgres",
        "RPG_OIDC_USERINFO_URL": "https://identity.example/userinfo",
        "RPG_OIDC_ISSUER": "https://identity.example",
    }
    for dsn in (
        "host=127.0.0.1 dbname=postgres",
        base["DATABASE_URL"] + "?hostaddr=127.0.0.1",
        base["DATABASE_URL"] + "?host=outside.example&port=5432",
        "postgresql://user:fake@localhost,db.example.com:5432/postgres",
        "postgresql://user:fake@localhost%2Cdb.example.com:5432/postgres",
        "postgresql://user:fake@%2Ftmp%2Fdb.example.com:5432/postgres",
    ):
        with pytest.raises(ValueError):
            RuntimeConfig.from_env({**base, "DATABASE_URL": dsn})


@pytest.mark.parametrize("override", [
    {"RPG_BIND_HOST": "127.0.0.1"},
    {"RPG_BIND_HOST": "127.0.0.2"},
    {"DATABASE_URL": "postgresql://postgres:fake@127.0.0.1:6543/postgres"},
    {"DATABASE_URL": "postgresql://postgres:fake@127.0.0.2:6543/postgres"},
    {"SUPABASE_URL": "http://127.0.0.1:54321"},
    {"RPG_AUTH_MODE": "disabled"},
    {"RPG_AUTH_MODE": "oidc"},
    {"RPG_BLOB_STORE": "file"},
    {"RPG_BLOB_STORE": "s3"},
    {"SUPABASE_URL": ""},
    {"SUPABASE_PUBLISHABLE_KEY": ""},
    {"SUPABASE_SERVICE_ROLE_KEY": ""},
    {"SUPABASE_SERVICE_ROLE_KEY": "sb_publishable_PUBLIC_SENTINEL"},
    {"SUPABASE_SERVICE_ROLE_KEY": "opaque_wrong_key"},
    {"DATABASE_URL": "postgresql://postgres.projectref:fake@db.projectref.supabase.co:5432/postgres"},
    {"DATABASE_URL": "postgresql://postgres.projectref:fake@aws-0-us-east-1.pooler.supabase.com:5432/postgres"},
    {"DATABASE_URL": "postgresql://postgres.otherref:fake@aws-0-us-east-1.pooler.supabase.com:6543/postgres"},
    {"DATABASE_URL": "postgresql://postgres.projectref:fake@aws-0-us-east-1.pooler.supabase.com:6543/postgres?sslmode=disable"},
    {"DATABASE_URL": hosted_env()["DATABASE_URL"] + "&host=127.0.0.1"},
    {"DATABASE_URL": hosted_env()["DATABASE_URL"] + "&hostaddr=127.0.0.1"},
    {"DATABASE_URL": hosted_env()["DATABASE_URL"] + "&host=outside.example&port=5432"},
    {"DATABASE_URL": hosted_env()["DATABASE_URL"] + "&user=attacker.otherproject"},
    {"DATABASE_URL": hosted_env()["DATABASE_URL"] + "&service=outside"},
    {"DATABASE_URL": hosted_env()["DATABASE_URL"] + "&options=-c%20search_path%3Doutside"},
    {"DATABASE_URL": hosted_env()["DATABASE_URL"] + "&sslmode=disable"},
    {"DATABASE_URL": hosted_env()["DATABASE_URL"] + "&host%61ddr=127.0.0.1"},
    {"DATABASE_URL": hosted_env()["DATABASE_URL"] + "#host=127.0.0.1"},
    {"DATABASE_URL": "postgresql://postgres.projectref:fake@localhost,aws-0-us-east-1.pooler.supabase.com:6543/postgres?sslmode=require"},
    {"DATABASE_URL": "postgresql://postgres.projectref:fake@localhost%2Caws-0-us-east-1.pooler.supabase.com:6543/postgres?sslmode=require"},
    {"DATABASE_URL": "postgresql://postgres.projectref:fake@outside.example,aws-0-us-east-1.pooler.supabase.com:6543/postgres?sslmode=require"},
    {"DATABASE_URL": "postgresql://postgres.projectref:fake@%2Ftmp%2Faws-0-us-east-1.pooler.supabase.com:6543/postgres?sslmode=require"},
    {"RPG_DB_POOL_MAX_SIZE": "0"},
    {"RPG_DB_POOL_MIN_SIZE": "2"},
    {"RPG_DB_POOL_TIMEOUT_SECONDS": "0"},
])
def test_hosted_rejects_unsafe_config(override: dict[str, str]) -> None:
    with pytest.raises(ValueError):
        RuntimeConfig.from_env({**hosted_env(), **override})


def test_hosted_pool_settings_and_backend_validation_before_pool(monkeypatch: pytest.MonkeyPatch) -> None:
    from infrastructure import postgres, runtime

    env = {**hosted_env(), "RPG_DB_POOL_MIN_SIZE": "0", "RPG_DB_POOL_MAX_SIZE": "2",
           "RPG_DB_POOL_TIMEOUT_SECONDS": "2.5"}
    config = RuntimeConfig.from_env(env)
    assert (config.db_pool_min_size, config.db_pool_max_size, config.db_pool_timeout) == (0, 2, 2.5)

    called = []
    monkeypatch.setattr(postgres, "PostgresPool", lambda *_args, **_kwargs: called.append(True))
    with pytest.raises(ValueError):
        runtime.build_database_runtime(replace(config, supabase_service_role_key=""))
    assert not called


def test_pool_uses_transaction_safe_psycopg_settings(monkeypatch: pytest.MonkeyPatch) -> None:
    from infrastructure import postgres

    seen = []

    class FakePool:
        def __init__(self, **kwargs):
            seen.append(kwargs)

        def close(self):
            pass

    monkeypatch.setattr(postgres, "ConnectionPool", FakePool)
    pool = postgres.PostgresPool(
        hosted_env()["DATABASE_URL"], min_size=0, max_size=1, timeout=2.5,
        transaction_pooler=True,
    )
    pool.close()
    assert seen[0]["min_size"] == 0
    assert seen[0]["max_size"] == 1
    assert seen[0]["timeout"] == 2.5
    assert seen[0]["kwargs"]["prepare_threshold"] is None
    assert seen[0]["kwargs"]["sslmode"] == "require"
    assert "options" not in seen[0]["kwargs"]
    stronger = hosted_env()["DATABASE_URL"].replace("sslmode=require", "sslmode=verify-full")
    postgres.PostgresPool(stronger, transaction_pooler=True).close()
    assert seen[1]["kwargs"]["sslmode"] == "verify-full"
    postgres.PostgresPool("postgresql://localhost/postgres").close()
    assert "options" in seen[2]["kwargs"]
    assert "prepare_threshold" not in seen[2]["kwargs"]


def test_transaction_pool_reestablishes_local_query_timeouts(monkeypatch: pytest.MonkeyPatch) -> None:
    from infrastructure import postgres

    commands: list[str] = []

    class FakeConnection:
        def execute(self, statement: str) -> None:
            commands.append(statement)

    class ConnectionContext:
        def __enter__(self) -> FakeConnection:
            return FakeConnection()

        def __exit__(self, *_args: object) -> None:
            pass

    class FakePool:
        def __init__(self, **_kwargs: object):
            pass

        def connection(self) -> ConnectionContext:
            return ConnectionContext()

        def close(self) -> None:
            pass

    monkeypatch.setattr(postgres, "ConnectionPool", FakePool)
    with postgres.PostgresPool(hosted_env()["DATABASE_URL"], transaction_pooler=True).connection():
        pass
    assert commands == [
        "SET LOCAL statement_timeout = 15000", "SET LOCAL lock_timeout = 5000",
    ]
    commands.clear()
    with postgres.PostgresPool("postgresql://localhost/postgres").connection():
        pass
    assert commands == []


def test_hosted_runtime_wires_supabase_auth_storage_and_single_pool(monkeypatch: pytest.MonkeyPatch) -> None:
    from infrastructure import postgres, runtime
    from infrastructure.supabase_blob import SupabaseBlobStore
    from infrastructure.supabase_identity import SupabaseIdentityProvider

    seen = []

    class FakePool:
        def __init__(self, dsn, **kwargs):
            seen.append((dsn, kwargs))

        def close(self):
            pass

    monkeypatch.setattr(postgres, "PostgresPool", FakePool)
    built = runtime.build_database_runtime(RuntimeConfig.from_env(hosted_env()))
    assert len(seen) == 1
    assert seen[0][1] == {
        "min_size": 0, "max_size": 1, "timeout": 5.0, "transaction_pooler": True,
    }
    assert isinstance(built.identity_verifier, SupabaseIdentityProvider)
    assert isinstance(built.blob_store, SupabaseBlobStore)
    assert built.identity_verifier._key == hosted_env()["SUPABASE_PUBLISHABLE_KEY"]
    assert built.blob_store._key == hosted_env()["SUPABASE_SERVICE_ROLE_KEY"]
    assert built.resources == (built.game_store.pool,)


def test_blob_headers_distinguish_secret_api_key_from_legacy_jwt() -> None:
    from infrastructure.supabase_blob import SupabaseBlobStore

    modern = SupabaseBlobStore("https://projectref.supabase.co", "sb_secret_PRIVATE_SENTINEL")
    assert modern._headers() == {"apikey": "sb_secret_PRIVATE_SENTINEL"}

    legacy = SupabaseBlobStore("https://projectref.supabase.co", "header.payload.signature")
    assert legacy._headers() == {
        "apikey": "header.payload.signature",
        "Authorization": "Bearer header.payload.signature",
    }


def test_cloud_doctor_is_read_only_and_redacts_secrets(capsys: pytest.CaptureFixture) -> None:
    from scripts.cloud_doctor import diagnose, main

    values = hosted_env()
    report = diagnose(values)
    assert report["status"] == "ok"
    assert report["profile"] == "hosted-supabase"
    assert report["checks"]["DATABASE_URL"] == "present"
    assert report["checks"]["dsn_shape"] == "valid"
    assert "SENTINEL" not in json.dumps(report)
    assert main(values) == 0
    stdout = capsys.readouterr().out
    assert "SENTINEL" not in stdout
    assert "pooler.supabase.com" not in stdout

    missing = diagnose({**values, "SUPABASE_SERVICE_ROLE_KEY": ""})
    assert missing["status"] == "invalid"
    assert missing["checks"]["SUPABASE_SERVICE_ROLE_KEY"] == "missing"
    inherited_legacy = diagnose({**values, "RPG_BLOB_STORE": "file"})
    assert inherited_legacy["status"] == "invalid"
    assert inherited_legacy["checks"]["RPG_BLOB_STORE"] == "invalid"
    query_override = diagnose({
        **values, "DATABASE_URL": values["DATABASE_URL"] + "&hostaddr=127.0.0.1",
    })
    assert query_override["status"] == "invalid"
    assert query_override["checks"]["dsn_shape"] == "invalid"
    multi_host = diagnose({
        **values,
        "DATABASE_URL": values["DATABASE_URL"].replace(
            "@aws-0-us-east-1", "@localhost,aws-0-us-east-1",
        ),
    })
    assert multi_host["status"] == "invalid"
    assert multi_host["checks"]["dsn_shape"] == "invalid"
