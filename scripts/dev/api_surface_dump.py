"""SPEC-381 R6/R7: dump da superficie HTTP de ``api.app`` (oraculo temporario da refatoracao).

Uso: ``bash scripts/dev/py.sh scripts/dev/api_surface_dump.py --out <dir> [--profile legacy|hosted]``.
Sem ``--profile`` gera os dois, cada um num subprocesso limpo (``<dir>/legacy`` e ``<dir>/hosted``).
Arquivos: openapi.json, routes.json, middleware.json, handlers.json, lifecycle.json, modules.json.
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
_SECRET = "s" * 48
HOSTED_ENV = {
    "RPG_RUNTIME_PROFILE": "hosted-supabase",
    "RPG_BIND_HOST": "0.0.0.0",
    "DATABASE_URL": (
        "postgresql://rpg_runtime.projectref:SEGREDO_DB@"
        "aws-0-us-east-1.pooler.supabase.com:6543/postgres?sslmode=require"
    ),
    "RPG_ADMIN_DATABASE_URL": (
        "postgresql://rpg_admin.projectref:SEGREDO_ADMIN@"
        "aws-0-us-east-1.pooler.supabase.com:6543/postgres?sslmode=require"
    ),
    "SUPABASE_URL": "https://projectref.supabase.co",
    "SUPABASE_PUBLISHABLE_KEY": "sb_publishable_PUBLIC",
    "SUPABASE_SERVICE_ROLE_KEY": "sb_secret_PRIVATE",
    "RPG_COOKIE_SECURE": "1",
    "RPG_SESSION_SECRET": _SECRET,
    "RPG_TELEMETRY_SECRET": _SECRET,
    "RPG_CORS_ORIGINS": "https://app.example.com",
    "RPG_AUTH_CAPTCHA_REQUIRED": "1",
    "RPG_AUTH_CAPTCHA_MODE": "gotrue",
    "RPG_TURNSTILE_SITE_KEY": "site",
    "RPG_AUTH_EMAIL_CONFIRMATION_REQUIRED": "1",
    "RPG_NO_MOCK": "1",
}
FILES = (
    "openapi.json",
    "routes.json",
    "middleware.json",
    "handlers.json",
    "lifecycle.json",
    "modules.json",
)


def _qualname(obj: object) -> str | None:
    return getattr(obj, "__qualname__", None) if obj is not None else None


def _class_name(c: object) -> str:
    c = getattr(c, "value", c)  # DefaultPlaceholder -> classe real
    return getattr(c, "__name__", str(c))


def _route_entry(r: object) -> list:
    kind = type(r).__name__
    if kind == "APIRoute":
        endpoint = getattr(r, "endpoint", None)
        return [
            kind,
            r.path,
            sorted(r.methods or []),
            r.name,
            _qualname(endpoint),
            r.include_in_schema,
            r.status_code,
            _qualname(getattr(r, "response_model", None)),
            _class_name(r.response_class),
        ]
    if kind in ("Route", "Mount"):
        return [kind, r.path, r.name]
    inner = (
        getattr(getattr(r, "original_router", None), "routes", None)
        or getattr(r, "routes", None)
        or []
    )
    return [kind, [getattr(x, "path", None) for x in inner]]


def _dump(out: Path) -> None:
    """Roda no subprocesso: importa ``api`` e escreve os arquivos."""
    before = set(sys.modules)
    sys.path.insert(0, str(ROOT))
    import api  # noqa: PLC0415

    after = set(sys.modules)
    app = api.app
    out.mkdir(parents=True, exist_ok=True)

    def write(name: str, data: object) -> None:
        text = json.dumps(data, sort_keys=False, ensure_ascii=False, indent=1) + "\n"
        (out / name).write_bytes(text.encode("utf-8"))  # LF fixo (byte-igual entre SOs)

    write("openapi.json", app.openapi())
    write("routes.json", [_route_entry(r) for r in app.routes])
    mids = []
    for m in app.user_middleware:
        disp = m.kwargs.get("dispatch") if hasattr(m, "kwargs") else None
        kw = {
            k: repr(v) for k, v in sorted(dict(getattr(m, "kwargs", {})).items()) if k != "dispatch"
        }
        mids.append([getattr(m.cls, "__name__", str(m.cls)), getattr(disp, "__name__", None), kw])
    write("middleware.json", mids)
    write(
        "handlers.json",
        [
            [getattr(k, "__qualname__", str(k)), getattr(v, "__name__", str(v))]
            for k, v in app.exception_handlers.items()
        ],
    )
    write(
        "lifecycle.json",
        {
            "on_startup": len(app.router.on_startup),
            "on_shutdown": len(app.router.on_shutdown),
            "lifespan_context": type(app.router.lifespan_context).__name__,
        },
    )
    write("modules.json", {"added": sorted(after - before)})


def _spawn(profile: str, out: Path) -> None:
    env = {
        k: v
        for k, v in os.environ.items()
        if not k.startswith(("RPG_", "DATABASE_URL", "SUPABASE_"))
    }
    env["PYTHONUTF8"] = "1"
    if profile == "hosted":
        env.update(HOSTED_ENV)
    else:
        env["RPG_FORCE_MOCK"] = "1"
    subprocess.run(
        [sys.executable, str(Path(__file__).resolve()), "--worker", "--out", str(out)],
        check=True,
        env=env,
        cwd=str(ROOT),
    )


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", required=True)
    ap.add_argument("--profile", choices=("legacy", "hosted"))
    ap.add_argument("--worker", action="store_true")
    a = ap.parse_args()
    out = Path(a.out)
    if a.worker:
        _dump(out)
        return
    for profile in (a.profile,) if a.profile else ("legacy", "hosted"):
        _spawn(profile, out / profile)


if __name__ == "__main__":
    main()
