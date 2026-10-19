"""Read-only, redacted preflight for hosted runtime configuration.

Prints env variable names and status only. It never opens a DB/HTTP socket or
includes DSN, hostname, project ref, key, or exception text in output.
"""

from __future__ import annotations

import json
import os
from collections.abc import Mapping
from urllib.parse import urlsplit

from infrastructure.runtime import (
    HOSTED_SECURITY_REQUIREMENTS,
    RuntimeConfig,
    _loopback_host,
    hosted_supabase_dsn_ref,
    privileged_request_db_user,
)

_REQUIRED = {
    "hosted-supabase": (
        "RPG_BIND_HOST",
        "DATABASE_URL",
        "SUPABASE_URL",
        "SUPABASE_PUBLISHABLE_KEY",
        "SUPABASE_SERVICE_ROLE_KEY",
    ),
    "hosted": (
        "RPG_BIND_HOST",
        "DATABASE_URL",
        "RPG_OIDC_JWKS_URL",
        "RPG_OIDC_AUDIENCE",
        "RPG_OIDC_ISSUER",
        "RPG_S3_BUCKET",
    ),
}
_ADAPTERS = {
    "hosted-supabase": {
        "RPG_GAME_STORE": "postgres",
        "RPG_MEMORY_STORE": "pgvector",
        "RPG_RUNTIME_CATALOG": "postgres",
        "RPG_BLOB_STORE": "supabase",
        "RPG_JOB_QUEUE": "postgres",
        "RPG_RATE_LIMIT_STORE": "postgres",
        "RPG_AUTH_MODE": "supabase",
    },
    "hosted": {
        "RPG_GAME_STORE": "postgres",
        "RPG_MEMORY_STORE": "pgvector",
        "RPG_RUNTIME_CATALOG": "postgres",
        "RPG_BLOB_STORE": "s3",
        "RPG_JOB_QUEUE": "postgres",
        "RPG_RATE_LIMIT_STORE": "postgres",
        "RPG_AUTH_MODE": "oidc",
    },
}


def diagnose(env: Mapping[str, str] | None = None) -> dict[str, object]:
    values = os.environ if env is None else env
    raw_profile = values.get("RPG_RUNTIME_PROFILE", "").strip().lower()
    profile = raw_profile if raw_profile in _REQUIRED else "invalid"
    checks: dict[str, str] = {
        name: "present" if values.get(name, "").strip() else "missing"
        for name in _REQUIRED.get(profile, ())
    }
    for name, expected in _ADAPTERS.get(profile, {}).items():
        checks[name] = (
            "valid" if values.get(name, expected).strip().lower() == expected else "invalid"
        )
    if profile == "hosted-supabase":
        try:
            hosted_supabase_dsn_ref(values.get("DATABASE_URL", ""))
            checks["dsn_shape"] = "valid"
        except ValueError:
            checks["dsn_shape"] = "invalid"
    elif profile == "hosted":
        try:
            parsed = urlsplit(values.get("DATABASE_URL", ""))
            checks["dsn_shape"] = (
                "valid"
                if parsed.scheme in {"postgres", "postgresql"}
                and parsed.hostname is not None
                and not _loopback_host(parsed.hostname)
                else "invalid"
            )
        except ValueError:
            checks["dsn_shape"] = "invalid"
    if profile in {"hosted", "hosted-supabase"}:
        # SPEC-224: so classes ("on"/"off", "present"/"missing", "least_privilege"/"superuser"), nunca DSN.
        rls_on = values.get("RPG_REQUEST_RLS", "on").strip().lower() not in {
            "0",
            "off",
            "false",
            "no",
        }
        checks["request_rls"] = "on" if rls_on else "off"
        if rls_on:
            checks["RPG_ADMIN_DATABASE_URL"] = (
                "present" if values.get("RPG_ADMIN_DATABASE_URL", "").strip() else "missing"
            )
            try:
                request_user = (urlsplit(values.get("DATABASE_URL", "")).username or "").lower()
            except ValueError:
                request_user = ""
            checks["runtime_db_role"] = (
                "superuser" if privileged_request_db_user(request_user) else "least_privilege"
            )
    if profile in {"hosted", "hosted-supabase"}:
        # SPEC-218: present/missing por requirement, nunca valores.
        for requirement in HOSTED_SECURITY_REQUIREMENTS:
            checks[f"security:{requirement.name}"] = (
                "missing" if requirement.check(values) else "present"
            )
    try:
        RuntimeConfig.from_env(values)
        valid = profile != "invalid" and all(
            value not in {"missing", "invalid", "superuser"} for value in checks.values()
        )
    except ValueError:
        valid = False
    checks["profile_contract"] = "valid" if valid else "invalid"
    return {"profile": profile, "status": "ok" if valid else "invalid", "checks": checks}


def main(env: Mapping[str, str] | None = None) -> int:
    report = diagnose(env)
    print(json.dumps(report, sort_keys=True, ensure_ascii=False))
    return 0 if report["status"] == "ok" else 1


if __name__ == "__main__":
    raise SystemExit(main())
