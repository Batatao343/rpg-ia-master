"""SPEC-218: fail-closed de perfil e configuração de segurança em deploy exposto."""
from __future__ import annotations

import importlib

import pytest

from infrastructure import runtime as rt
from infrastructure.runtime import (
    HOSTED_REQUIRED_ENV,
    HOSTED_SECURITY_REQUIREMENTS,
    RuntimeConfig,
    assert_boot_policy,
    docs_enabled,
    exposure_markers,
    hosted_security_problems,
    is_hardened,
    kill_switch_fail_closed_default,
)

SECRET = "s" * 40


def secure_env(**over: str) -> dict[str, str]:
    env = {
        "RPG_RUNTIME_PROFILE": "hosted-supabase",
        "RPG_BIND_HOST": "0.0.0.0",
        "DATABASE_URL": (
            "postgresql://postgres.projectref:SEGREDO_DB@"
            "aws-0-us-east-1.pooler.supabase.com:6543/postgres?sslmode=require"
        ),
        "SUPABASE_URL": "https://projectref.supabase.co",
        "SUPABASE_PUBLISHABLE_KEY": "sb_publishable_PUBLIC",
        "SUPABASE_SERVICE_ROLE_KEY": "sb_secret_PRIVATE",
        "RPG_COOKIE_SECURE": "1",
        "RPG_SESSION_SECRET": SECRET,
        "RPG_TELEMETRY_SECRET": SECRET,
        "RPG_CORS_ORIGINS": "https://app.example.com",
        "RPG_AUTH_CAPTCHA_REQUIRED": "1",
        "RPG_AUTH_CAPTCHA_MODE": "gotrue",
        "RPG_TURNSTILE_SITE_KEY": "site",
        "RPG_AUTH_EMAIL_CONFIRMATION_REQUIRED": "1",
        "RPG_NO_MOCK": "1",
    }
    env.update(over)
    return {k: v for k, v in env.items() if v is not None}


def without(name: str) -> dict[str, str]:
    env = secure_env()
    env.pop(name)
    return env


# --- R1/R2: exposição e boot ------------------------------------------------
@pytest.mark.parametrize("marker", ["VERCEL", "RAILWAY_ENVIRONMENT", "RENDER", "K_SERVICE", "FLY_APP_NAME", "PORT"])
def test_legacy_exposed_boot_fails(marker: str) -> None:
    with pytest.raises(RuntimeError, match="legacy_profile_exposed") as exc:
        assert_boot_policy({marker: "x"})
    assert marker in str(exc.value)


def test_legacy_exposed_by_non_loopback_bind() -> None:
    with pytest.raises(RuntimeError, match="RPG_BIND_HOST"):
        assert_boot_policy({"RPG_BIND_HOST": "0.0.0.0"})


def test_explicit_empty_or_unknown_profile_is_not_a_bypass() -> None:
    with pytest.raises(RuntimeError, match="legacy_profile_exposed"):
        assert_boot_policy({"PORT": "8000", "RPG_RUNTIME_PROFILE": ""})
    with pytest.raises(RuntimeError, match="legacy_profile_exposed"):
        assert_boot_policy({"PORT": "8000", "RPG_RUNTIME_PROFILE": " LEGACY "})
    with pytest.raises(ValueError):  # perfil desconhecido nunca sobe
        assert_boot_policy({"PORT": "8000", "RPG_RUNTIME_PROFILE": "prod"})


def test_legacy_loopback_without_markers_ok() -> None:
    assert_boot_policy({})
    assert_boot_policy({"RPG_BIND_HOST": "127.0.0.1", "PORT": "8000"})  # loopback explícito remove PORT
    assert exposure_markers({"RPG_BIND_HOST": "127.0.0.1", "PORT": "8000"}) == set()


def test_loopback_bind_does_not_hide_platform_marker() -> None:
    """Tentativa de contornar R2: RPG_BIND_HOST loopback + marcador de plataforma."""
    env = {"RPG_BIND_HOST": "127.0.0.1", "PORT": "8000", "RAILWAY_ENVIRONMENT": "production"}
    assert exposure_markers(env) == {"RAILWAY_ENVIRONMENT"}
    with pytest.raises(RuntimeError, match="legacy_profile_exposed"):
        assert_boot_policy(env)


def test_allow_legacy_exposed_override() -> None:
    assert_boot_policy({"PORT": "8000", "RPG_ALLOW_LEGACY_EXPOSED": "1"})
    with pytest.raises(RuntimeError):
        assert_boot_policy({"PORT": "8000", "RPG_ALLOW_LEGACY_EXPOSED": "true"})  # só "1"


def test_boot_error_has_no_env_values() -> None:
    env = {"PORT": "8000", "DATABASE_URL": "postgres://u:SEGREDO@h/db", "RPG_SESSION_SECRET": "SEGREDO"}
    with pytest.raises(RuntimeError) as exc:
        assert_boot_policy(env)
    assert "SEGREDO" not in str(exc.value) and "8000" not in str(exc.value)
    bad = secure_env(RPG_COOKIE_SECURE="0", RPG_SESSION_SECRET="SEGREDO_CURTO")
    with pytest.raises(ValueError) as exc2:
        assert_boot_policy(bad)
    assert "SEGREDO" not in str(exc2.value)


def test_db_profile_validates_config_at_boot() -> None:
    assert_boot_policy(secure_env())
    with pytest.raises(ValueError, match="hosted_config_insecure"):
        assert_boot_policy(without("RPG_COOKIE_SECURE"))


def test_api_module_import_fails_closed_when_exposed(monkeypatch: pytest.MonkeyPatch) -> None:
    import api

    monkeypatch.setenv("PORT", "8000")
    monkeypatch.delenv("RPG_RUNTIME_PROFILE", raising=False)
    with pytest.raises(RuntimeError, match="legacy_profile_exposed"):
        importlib.reload(api)
    monkeypatch.delenv("PORT")
    importlib.reload(api)  # volta ao estado normal para os demais testes


# --- R3/R11: requisitos hosted ---------------------------------------------
def test_secure_env_is_valid_and_hardened() -> None:
    RuntimeConfig.from_env(secure_env())
    assert hosted_security_problems(secure_env()) == []
    assert is_hardened(secure_env())
    assert not is_hardened({})  # legacy nunca "hardened"


@pytest.mark.parametrize("name", [
    "RPG_COOKIE_SECURE", "RPG_SESSION_SECRET", "RPG_TELEMETRY_SECRET", "RPG_CORS_ORIGINS",
    "RPG_AUTH_CAPTCHA_REQUIRED", "RPG_AUTH_EMAIL_CONFIRMATION_REQUIRED", "RPG_NO_MOCK",
])
def test_hosted_missing_requirement_fails(name: str) -> None:
    with pytest.raises(ValueError, match="hosted_config_insecure") as exc:
        RuntimeConfig.from_env(without(name))
    assert name in str(exc.value)


@pytest.mark.parametrize("override,needle", [
    ({"RPG_COOKIE_SECURE": "0"}, "RPG_COOKIE_SECURE"),
    ({"RPG_SESSION_SECRET": "curto"}, "RPG_SESSION_SECRET"),
    ({"RPG_TELEMETRY_SECRET": "x" * 31}, "RPG_TELEMETRY_SECRET"),
    ({"RPG_CORS_ORIGINS": "*"}, "RPG_CORS_ORIGINS"),
    ({"RPG_CORS_ORIGINS": "https://a.example.com,http://b.example.com"}, "RPG_CORS_ORIGINS"),
    ({"RPG_CORS_ORIGINS": "https://localhost"}, "RPG_CORS_ORIGINS"),
    ({"RPG_CORS_ORIGINS": "https://127.0.0.1:8000"}, "RPG_CORS_ORIGINS"),
    ({"RPG_CORS_ORIGINS": "https://a.example.com/path"}, "RPG_CORS_ORIGINS"),
    ({"RPG_AUTH_CAPTCHA_REQUIRED": "0"}, "RPG_AUTH_CAPTCHA_REQUIRED"),
    ({"RPG_TURNSTILE_SITE_KEY": ""}, "RPG_AUTH_CAPTCHA_REQUIRED"),
    ({"RPG_AUTH_CAPTCHA_MODE": "app"}, "RPG_AUTH_CAPTCHA_REQUIRED"),  # sem RPG_TURNSTILE_SECRET
    ({"RPG_RATE_LIMIT": "0"}, "RPG_RATE_LIMIT"),
    ({"RPG_RATE_LIMIT": "-5"}, "RPG_RATE_LIMIT"),
    ({"RPG_RATE_LIMIT": "abc"}, "RPG_RATE_LIMIT"),
    ({"LLM_PROVIDER": "ollama"}, "LLM_PROVIDER"),
    ({"RPG_FORCE_MOCK": "1"}, "RPG_FORCE_MOCK"),
    ({"RPG_GOOGLE_PLAY_FAKE": "1"}, "RPG_GOOGLE_PLAY_FAKE"),
    ({"RPG_ADMIN_ALLOW_PROFILE": "1"}, "RPG_ADMIN_ALLOW_PROFILE"),
    ({"RPG_KILL_SWITCHES_OFF": "image_generation"}, "RPG_KILL_SWITCHES_OFF"),
    ({"RPG_EXPOSE_OPENAPI": "1"}, "RPG_EXPOSE_OPENAPI"),
    ({"RPG_ALLOW_LEGACY_EXPOSED": "1"}, "RPG_ALLOW_LEGACY_EXPOSED"),
])
def test_hosted_bad_value_fails(override: dict[str, str], needle: str) -> None:
    with pytest.raises(ValueError, match="hosted_config_insecure") as exc:
        RuntimeConfig.from_env(secure_env(**override))
    assert needle in str(exc.value)


def test_hosted_app_captcha_mode_with_secret_ok() -> None:
    RuntimeConfig.from_env(secure_env(RPG_AUTH_CAPTCHA_MODE="app", RPG_TURNSTILE_SECRET="t"))


def test_hosted_provider_key_substitutes_no_mock() -> None:
    env = without("RPG_NO_MOCK")
    env["DEEPSEEK_API_KEY"] = "k"
    RuntimeConfig.from_env(env)


def test_rate_limit_positive_and_absent_ok() -> None:
    RuntimeConfig.from_env(secure_env(RPG_RATE_LIMIT="30"))
    RuntimeConfig.from_env(secure_env())


def test_validate_error_lists_all_missing_at_once() -> None:
    env = secure_env(RPG_COOKIE_SECURE="0", RPG_SESSION_SECRET="", RPG_AUTH_CAPTCHA_REQUIRED="0")
    with pytest.raises(ValueError) as exc:
        RuntimeConfig.from_env(env)
    msg = str(exc.value)
    assert all(n in msg for n in ("RPG_COOKIE_SECURE", "RPG_SESSION_SECRET", "RPG_AUTH_CAPTCHA_REQUIRED"))


def test_allow_insecure_hosted_override_only_for_lab() -> None:
    env = secure_env(RPG_COOKIE_SECURE="0", RPG_ALLOW_INSECURE_HOSTED="1")
    RuntimeConfig.from_env(env)  # lab: sobe
    assert not is_hardened(env)  # mas nunca reporta hardened
    with pytest.raises(ValueError):  # e o próprio override é proibido num hosted "limpo"
        RuntimeConfig.from_env(secure_env(RPG_ALLOW_INSECURE_HOSTED="true", RPG_COOKIE_SECURE="0"))


def test_non_hosted_profiles_unaffected() -> None:
    RuntimeConfig.from_env({})  # legacy
    local = {
        "RPG_RUNTIME_PROFILE": "local",
        "DATABASE_URL": "postgresql://u:p@127.0.0.1:54322/postgres",
        "SUPABASE_URL": "http://127.0.0.1:54321",
    }
    RuntimeConfig.from_env(local)


# --- R4: fonte única ---------------------------------------------------------
def test_requirements_parity_with_release_checklist() -> None:
    from scripts.release import checklist

    names = {r.name for r in HOSTED_SECURITY_REQUIREMENTS}
    assert set(HOSTED_REQUIRED_ENV) <= names
    for env in ("staging", "production"):
        assert set(HOSTED_REQUIRED_ENV) <= set(checklist.REQUIRED_ENV[env])
    assert checklist.FORBIDDEN_IN_PROD == rt.FORBIDDEN_IN_HOSTED
    for forbidden in ("RPG_ALLOW_INSECURE_HOSTED", "RPG_ALLOW_LEGACY_EXPOSED", "RPG_EXPOSE_OPENAPI"):
        assert forbidden in checklist.FORBIDDEN_IN_PROD


def test_cloud_doctor_reports_presence_without_values() -> None:
    from scripts import cloud_doctor

    report = cloud_doctor.diagnose(secure_env(RPG_COOKIE_SECURE="0"))
    assert report["checks"]["security:RPG_COOKIE_SECURE"] == "missing"
    assert report["checks"]["security:RPG_SESSION_SECRET"] == "present"
    assert report["status"] == "invalid"
    assert SECRET not in str(report) and "SEGREDO_DB" not in str(report)


# --- R5: kill switch ---------------------------------------------------------
class _Broken:
    def load(self):
        raise RuntimeError("db down")


def _switches(monkeypatch: pytest.MonkeyPatch, profile: str, fail_closed: str | None):
    from services.kill_switches import KillSwitches

    monkeypatch.setenv("RPG_RUNTIME_PROFILE", profile)
    if fail_closed is None:
        monkeypatch.delenv("RPG_KILL_SWITCH_FAIL_CLOSED", raising=False)
    else:
        monkeypatch.setenv("RPG_KILL_SWITCH_FAIL_CLOSED", fail_closed)
    return KillSwitches(store=_Broken())


def test_kill_switch_default_fail_closed_in_hosted(monkeypatch: pytest.MonkeyPatch) -> None:
    sw = _switches(monkeypatch, "hosted-supabase", None)
    assert sw.is_enabled("image_generation") is False
    assert sw.is_enabled("stt_fallback_expensive") is False
    assert sw.is_enabled("new_purchases") is True  # revenue path segue fail-open (SPEC-196)


def test_kill_switch_explicit_empty_env_wins(monkeypatch: pytest.MonkeyPatch) -> None:
    sw = _switches(monkeypatch, "hosted-supabase", "")
    assert sw.is_enabled("image_generation") is True


def test_kill_switch_legacy_default_unchanged(monkeypatch: pytest.MonkeyPatch) -> None:
    sw = _switches(monkeypatch, "legacy", None)
    assert sw.is_enabled("image_generation") is True
    assert kill_switch_fail_closed_default("local") == ()


# --- R6/R9/R12: docs, health, cron schema -----------------------------------
def test_docs_enabled_matrix() -> None:
    assert docs_enabled({}) and docs_enabled({"RPG_RUNTIME_PROFILE": "local"})
    assert not docs_enabled({"RPG_RUNTIME_PROFILE": "hosted-supabase"})
    assert not docs_enabled({"RPG_RUNTIME_PROFILE": "portable"})
    assert docs_enabled({"RPG_RUNTIME_PROFILE": "hosted", "RPG_EXPOSE_OPENAPI": "1"})


def test_docs_visible_in_legacy() -> None:
    from fastapi.testclient import TestClient

    import api

    client = TestClient(api.app)
    assert client.get("/openapi.json").status_code == 200
    paths = client.get("/openapi.json").json()["paths"]
    assert not any(p.startswith("/internal/cron") for p in paths)  # R12


def _apply_env(monkeypatch: pytest.MonkeyPatch) -> None:
    # a suíte força RPG_FORCE_MOCK=1 e RPG_RATE_LIMIT=0 no os.environ real; hosted os proíbe.
    monkeypatch.delenv("RPG_FORCE_MOCK", raising=False)
    monkeypatch.delenv("RPG_RATE_LIMIT", raising=False)
    for key, value in secure_env().items():
        monkeypatch.setenv(key, value)


def test_docs_hidden_in_db_profile(monkeypatch: pytest.MonkeyPatch) -> None:
    from fastapi.testclient import TestClient

    import api

    _apply_env(monkeypatch)
    try:
        importlib.reload(api)
        client = TestClient(api.app)
        for path in ("/openapi.json", "/docs", "/redoc"):
            assert client.get(path).status_code in {401, 404}, path
    finally:
        monkeypatch.undo()
        importlib.reload(api)


def test_health_reports_profile_and_hardened(monkeypatch: pytest.MonkeyPatch) -> None:
    import api

    body = api.health_check()
    assert body["profile"] == "legacy" and body["hardened"] is False
    _apply_env(monkeypatch)
    body = api.health_check()
    assert body["profile"] == "hosted-supabase" and body["hardened"] is True
    assert set(body) >= {"status", "engine", "git_sha", "profile", "hardened"}


def test_cors_methods_and_headers_are_explicit() -> None:
    import api

    cors = next(m for m in api.app.user_middleware if m.cls.__name__ == "CORSMiddleware")
    assert "*" not in cors.kwargs["allow_methods"] and "*" not in cors.kwargs["allow_headers"]
    assert "x-csrf-token" in cors.kwargs["allow_headers"]


def test_serverless_defaults_force_no_mock_in_hosted() -> None:
    env = {"RPG_RUNTIME_PROFILE": "hosted-supabase"}
    rt.apply_serverless_defaults(env)
    assert env["RPG_NO_MOCK"] == "1"
    env2 = {"RPG_RUNTIME_PROFILE": "hosted-supabase", "RPG_NO_MOCK": "0"}
    rt.apply_serverless_defaults(env2)
    assert env2["RPG_NO_MOCK"] == "0"  # override explícito vence (e o validador o rejeita sem key)
    legacy = {}
    rt.apply_serverless_defaults(legacy)
    assert "RPG_NO_MOCK" not in legacy


# --- Revisao Astra: perfis nao-hosted expostos -------------------------------
def test_local_profile_exposed_fails() -> None:
    env = {"RPG_RUNTIME_PROFILE": "local", "VERCEL": "1",
           "DATABASE_URL": "postgresql://u:p@db.example.com:5432/postgres",
           "SUPABASE_URL": "https://projectref.supabase.co"}
    with pytest.raises(RuntimeError, match="local_profile_exposed"):
        assert_boot_policy(env)


def test_portable_profile_exposed_requires_hardening() -> None:
    base = {"RPG_RUNTIME_PROFILE": "portable", "PORT": "8000",
            "DATABASE_URL": "postgresql://u:p@db.example.com:5432/postgres",
            "RPG_OIDC_USERINFO_URL": "https://id.example/userinfo", "RPG_OIDC_ISSUER": "https://id.example"}
    with pytest.raises(ValueError, match="hosted_config_insecure"):
        assert_boot_policy(base)
    hardened = {**secure_env(), **base}
    for key in ("SUPABASE_URL", "SUPABASE_PUBLISHABLE_KEY", "SUPABASE_SERVICE_ROLE_KEY"):
        hardened.pop(key)
    assert_boot_policy(hardened)
