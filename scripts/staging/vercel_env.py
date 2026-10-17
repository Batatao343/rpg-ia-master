"""SPEC-192: monta e envia as env vars do projeto Vercel de staging.

Segredos são lidos de .env.staging/.env e enviados pela API REST (type=encrypted).
Imprime apenas NOMES e targets, nunca valores.

Política: target `production` (= site de staging) recebe tudo; `preview` NÃO recebe
nenhum segredo de banco/serviço (falha fechada: o perfil hosted-supabase recusa subir).
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from collections.abc import Mapping
from pathlib import Path

import httpx
from dotenv import dotenv_values

PROJECT_NAME = "rpg-ia-master-staging"
PUBLIC_HOST = f"{PROJECT_NAME}.vercel.app"
TURNSTILE_TEST_SITE_KEY = "1x00000000000000000000AA"  # chave pública de teste Cloudflare
ROOT = Path(__file__).resolve().parents[2]

# (nome, origem) — origem "file" lê de .env.staging/.env; senão literal.
SECRET_FROM_FILE = (
    "DATABASE_URL", "SUPABASE_URL", "SUPABASE_PUBLISHABLE_KEY", "SUPABASE_SERVICE_ROLE_KEY",
    "RPG_SESSION_SECRET", "RPG_CRON_SECRET", "JINA_API_KEY",
)
NON_SECRET_LITERALS = {
    "RPG_RUNTIME_PROFILE": "hosted-supabase",
    "RPG_BIND_HOST": "0.0.0.0",
    "RPG_COOKIE_SECURE": "1",
    "RPG_AUTH_EMAIL_CONFIRMATION_REQUIRED": "1",
    "RPG_AUTH_CAPTCHA_MODE": "gotrue",
    "RPG_AUTH_CAPTCHA_REQUIRED": "1",
    "RPG_TURNSTILE_SITE_KEY": TURNSTILE_TEST_SITE_KEY,
    "RPG_FORCE_MOCK": "1",
    # STT (SPEC-186): synthetic pricing version seeded by synthetic_data.seed_wallet_prereqs; WAV only (no ffmpeg).
    "RPG_SPEECH_ENABLED": "1",
    "RPG_SPEECH_PRICING_VERSION": "spec197-restore-b",
}
# Preview: só flags inertes. Sem DATABASE_URL/SUPABASE_*/RPG_*_SECRET.
PREVIEW_LITERALS = {"RPG_RUNTIME_PROFILE": "hosted-supabase", "RPG_BIND_HOST": "0.0.0.0",
                    "RPG_FORCE_MOCK": "1"}
# SPEC-194: HMAC key for Play obfuscated account ids (>=32 chars). Pushed only when present in the env files.
# SPEC-197 R6 voice: Groq only (no OPENAI_API_KEY => no paid STT fallback candidate).
OPTIONAL_SECRET_FROM_FILE = ("RPG_PLAY_ACCOUNT_KEY", "GROQ_API_KEY")
RLS_SECRETS = ("RPG_ADMIN_DATABASE_URL",)  # SPEC-224: so no modo RLS efetivo
FORBIDDEN_IN_PREVIEW = frozenset(SECRET_FROM_FILE) | frozenset(OPTIONAL_SECRET_FROM_FILE) | frozenset(RLS_SECRETS)


def _load_files() -> dict[str, str]:
    merged: dict[str, str] = {}
    for name in (".env", ".env.staging"):  # .env.staging vence
        merged.update({k: v for k, v in dotenv_values(ROOT / name).items() if v})
    return merged


def build_env(files: Mapping[str, str], public_host: str = PUBLIC_HOST, use_admin_dsn: bool = False
              ) -> tuple[dict[str, str], dict[str, str]]:
    """Retorna (production, preview). Levanta KeyError com NOME do segredo ausente."""
    production = dict(NON_SECRET_LITERALS)
    production["RPG_CORS_ORIGINS"] = f"https://{public_host}"
    missing = [k for k in SECRET_FROM_FILE if not files.get(k)]
    if missing:
        raise KeyError(f"ausentes em .env.staging/.env: {', '.join(missing)}")
    for key in SECRET_FROM_FILE:
        production[key] = files[key]
    for key in OPTIONAL_SECRET_FROM_FILE:
        if files.get(key):
            production[key] = files[key]
    # SPEC-197 R-05 + SPEC-224: o runtime usa o papel de menor privilégio (`rpg_runtime`) com RLS por request
    # e um segundo DSN (`rpg_admin`) para workers/cron/wallet. `use_admin_dsn` e o rollback: DSN unico
    # `postgres` e RPG_REQUEST_RLS=off (comportamento anterior). Sem papeis provisionados, idem.
    if files.get("RPG_RUNTIME_DATABASE_URL") and not use_admin_dsn:
        if not files.get("RPG_ADMIN_DATABASE_URL"):
            raise KeyError("ausentes em .env.staging/.env: RPG_ADMIN_DATABASE_URL "
                           "(rode scripts/staging/runtime_role.py --role rpg_admin --apply)")
        production["DATABASE_URL"] = files["RPG_RUNTIME_DATABASE_URL"]
        production["RPG_ADMIN_DATABASE_URL"] = files["RPG_ADMIN_DATABASE_URL"]
    else:
        production["RPG_REQUEST_RLS"] = "off"
    preview = dict(PREVIEW_LITERALS)
    assert not FORBIDDEN_IN_PREVIEW & preview.keys()
    return production, preview


def push(token: str, project_id: str, team_id: str, target: str, values: Mapping[str, str],
         secret_names: frozenset[str]) -> list[str]:
    pushed = []
    headers = {"Authorization": f"Bearer {token}"}
    url = f"https://api.vercel.com/v10/projects/{project_id}/env"
    for key, value in values.items():
        body = {"key": key, "value": value, "target": [target],
                "type": "encrypted" if key in secret_names else "plain"}
        for attempt in range(3):
            try:
                r = httpx.post(url, params={"upsert": "true", "teamId": team_id},
                               headers=headers, json=body, timeout=60)
                break
            except httpx.HTTPError:
                if attempt == 2:
                    raise
        if r.status_code >= 300:
            raise RuntimeError(f"vercel env {key}@{target}: HTTP {r.status_code} "
                               f"{r.json().get('error', {}).get('code', '?')}")
        pushed.append(key)
    return pushed


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--project-name", default=PROJECT_NAME)
    ap.add_argument("--public-host", default=PUBLIC_HOST)
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--use-admin-dsn", action="store_true", help="rollback: DATABASE_URL = postgres")
    args = ap.parse_args(argv)
    if args.project_name != PROJECT_NAME:
        print(f"recusado: projeto deve ser {PROJECT_NAME}", file=sys.stderr)
        return 2
    link = json.loads((ROOT / ".vercel" / "project.json").read_text(encoding="utf-8"))
    if link.get("projectName", PROJECT_NAME) != PROJECT_NAME:
        print("recusado: .vercel/project.json aponta para outro projeto", file=sys.stderr)
        return 2
    files = _load_files()
    try:
        production, preview = build_env(files, args.public_host, args.use_admin_dsn)
    except KeyError as exc:
        print(exc.args[0], file=sys.stderr)
        return 1
    secrets = frozenset(SECRET_FROM_FILE) | frozenset(OPTIONAL_SECRET_FROM_FILE) | frozenset(RLS_SECRETS)
    print("production:", ", ".join(sorted(production)))
    print("preview:", ", ".join(sorted(preview)), "(sem segredos de DB/serviço)")
    if args.dry_run:
        return 0
    token = files.get("VERCEL_TOKEN") or os.environ.get("VERCEL_TOKEN", "")
    if not token:
        print("VERCEL_TOKEN ausente", file=sys.stderr)
        return 1
    push(token, link["projectId"], link["orgId"], "production", production, secrets)
    push(token, link["projectId"], link["orgId"], "preview", preview, secrets)
    print("ok: variáveis enviadas")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
