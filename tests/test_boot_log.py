"""SPEC-249: linha de boot, avisos de config e falha de construção do runtime."""

import json

import pytest

from observability import boot, logging_setup

SENTINELS = {
    "DEEPSEEK_API_KEY": "sk-SENTINEL-deepseek-key",
    "RPG_DATABASE_URL": "postgresql://user:pw-SENTINEL@db-SENTINEL.host:5432/x",
    "RPG_TELEMETRY_SECRET": "telemetry-secret-SENTINEL-0123456789",
    "SUPABASE_SERVICE_ROLE_KEY": "service-SENTINEL",
}


def _lines(capsys):
    return [json.loads(x) for x in capsys.readouterr().out.splitlines() if x.strip()]


@pytest.fixture(autouse=True)
def _cfg(monkeypatch):
    monkeypatch.delenv("RPG_FORCE_MOCK", raising=False)
    logging_setup.configure_logging({"RPG_LOG_LEVEL": "info"})
    monkeypatch.setattr(boot, "_logged", False)


def test_boot_logged_once(capsys, monkeypatch):
    for k, v in SENTINELS.items():
        monkeypatch.setenv(k, v)
    monkeypatch.setenv("GIT_SHA", "abcdef0123456789")
    assert boot.log_boot_once() is True
    assert boot.log_boot_once() is False
    lines = [x for x in _lines(capsys) if x["event"] == "runtime.boot"]
    assert len(lines) == 1
    line = lines[0]
    assert line["git_sha"] == "abcdef012345" and line["llm_mode"] == "routes"
    assert "deepseek" in line["llm_providers_with_key"]
    assert line["instance_ref"] == boot.INSTANCE_REF
    for key in (
        "profile",
        "hardened",
        "embedding_provider",
        "jev_mode",
        "projection_mode",
        "log_level",
        "cold_start_ms",
    ):
        assert key in line


def test_boot_has_no_secrets(capsys, monkeypatch):
    for k, v in SENTINELS.items():
        monkeypatch.setenv(k, v)
    boot.log_boot_once()
    out = capsys.readouterr().out
    assert out
    for v in SENTINELS.values():
        assert v not in out
    assert "SENTINEL" not in out


def test_missing_telemetry_secret_warns(capsys, monkeypatch):
    monkeypatch.delenv("RPG_TELEMETRY_SECRET", raising=False)
    monkeypatch.delenv("GIT_SHA", raising=False)
    monkeypatch.delenv("VERCEL_GIT_COMMIT_SHA", raising=False)
    boot.log_boot_once()
    codes = {x.get("code") for x in _lines(capsys) if x["event"] == "runtime.config_warning"}
    assert {"telemetry_secret_weak", "git_sha_missing"} <= codes


def test_every_line_has_instance_ref(capsys):
    from observability.telemetry import log_event

    log_event("x", "y")
    assert _lines(capsys)[0]["instance_ref"] == boot.INSTANCE_REF


def test_pool_failure_logged(capsys, monkeypatch):
    from infrastructure import postgres
    from infrastructure.runtime import RuntimeConfig, build_database_runtime

    def boom(*a, **k):
        raise ConnectionError("postgresql://user:pw-SENTINEL@db-SENTINEL.host")

    monkeypatch.setattr(RuntimeConfig, "validate", lambda self: None)
    monkeypatch.setattr(postgres, "PostgresPool", boom)
    cfg = (
        RuntimeConfig.from_env({"RPG_RUNTIME_PROFILE": "local"})
        if hasattr(RuntimeConfig, "from_env")
        else None
    )
    with pytest.raises(ConnectionError):
        build_database_runtime(cfg)
    out = capsys.readouterr().out
    line = next(json.loads(x) for x in out.splitlines() if "runtime.build_failed" in x)
    assert line["component"] == "db_pool" and line["error_type"] == "ConnectionError"
    assert "SENTINEL" not in out
