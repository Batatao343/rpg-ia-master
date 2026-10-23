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
    "DATABASE_URL",
    "SUPABASE_URL",
    "SUPABASE_PUBLISHABLE_KEY",
    "SUPABASE_SERVICE_ROLE_KEY",
    "RPG_SESSION_SECRET",
    "RPG_CRON_SECRET",
    "JINA_API_KEY",
    "RPG_TELEMETRY_SECRET",  # SPEC-218/222: requisito hosted (pseudonimizacao de telemetria)
    "GROQ_API_KEY",  # 2026-10-17: staging joga com LLM real (Groq); sem MockLLM em hosted (SPEC-218)
)
NON_SECRET_LITERALS = {
    "RPG_RUNTIME_PROFILE": "hosted-supabase",
    "RPG_BIND_HOST": "0.0.0.0",
    "RPG_COOKIE_SECURE": "1",
    "RPG_AUTH_EMAIL_CONFIRMATION_REQUIRED": "1",
    "RPG_AUTH_CAPTCHA_MODE": "gotrue",
    "RPG_AUTH_CAPTCHA_REQUIRED": "1",
    "RPG_TURNSTILE_SITE_KEY": TURNSTILE_TEST_SITE_KEY,
    # Teto diario de gasto variavel (SPEC-197 R7): 5 BRL; o cron desliga imagem/STT ao passar.
    # SPEC-237: embeddings Jina passaram a ser precificados por token (card versionado), entao o cap de
    # TEXTO (SPEC-219 R8: 503 `daily_spend_cap` para novos turnos) volta LIGADO. Rollback: --no-text-cap.
    "RPG_DAILY_SPEND_CAP_BRL": "5",
    "RPG_DAILY_SPEND_CAP_TEXT": "1",
    # STT (SPEC-186): synthetic pricing version seeded by synthetic_data.seed_wallet_prereqs; WAV only (no ffmpeg).
    "RPG_SPEECH_ENABLED": "1",
    "RPG_SPEECH_PRICING_VERSION": "spec197-restore-b",
}
# Preview: só flags inertes. Sem DATABASE_URL/SUPABASE_*/RPG_*_SECRET.
PREVIEW_LITERALS = {"RPG_RUNTIME_PROFILE": "hosted-supabase", "RPG_BIND_HOST": "0.0.0.0"}
# Nomes que NAO podem continuar no projeto (o upsert nao apaga): RPG_FORCE_MOCK e proibido em hosted
# (SPEC-218 boot fail-closed) e LLM_PROVIDER forcaria um provider unico fora de ROUTES.
# SPEC-217: RPG_JEV_ROUTER_PRIMARY_APPROVED e aprovacao exclusiva do dono para o Jev em `primary`; so e enviada
# com ``--jev-router-mode primary --owner-approved-primary`` (OPTIONAL_FLAGS: apagada em off/shadow).
REMOVED_NAMES = ("RPG_FORCE_MOCK", "LLM_PROVIDER")
# Pares exclusivos do modo RLS (SPEC-224): ao alternar rollback <-> RLS o upsert deixaria a variavel do
# outro modo para tras (ex.: RPG_REQUEST_RLS=off sobrevivendo a volta ao RLS efetivo).
MODE_EXCLUSIVE = ("RPG_REQUEST_RLS", "RPG_ADMIN_DATABASE_URL")
# Flags opcionais: saem do projeto quando nao estao em ``production`` (ex.: --no-text-cap).
OPTIONAL_FLAGS = (
    "RPG_DAILY_SPEND_CAP_TEXT",
    "RPG_PROJECTION_MODE",
    "RPG_JEV_ROUTER_MODE",
    "TYPESAFE_API_KEY",
    "RPG_JEV_ROUTER_PRIMARY_APPROVED",
    "RPG_NPC_KNOWLEDGE",
)
# SPEC-217 R15: Jev no router. ``off`` (default) = variaveis ausentes; ``shadow`` observa sem mudar a rota e
# envia a chave TypeSafe (secreta). ``primary`` exige ``owner_approved_primary`` (flag explicita
# ``--owner-approved-primary``) e so vale para ESTE projeto de staging. Aprovacao do dono, 2026-10-18 (literal):
# "já coloquei credito na OpenAi e pode ligar o primary no staging". Rollback: ``--jev-router-mode off`` + deploy.
JEV_ROUTER_MODES = ("off", "shadow", "primary")
OWNER_PRIMARY_APPROVAL = (
    '2026-10-18: "já coloquei credito na OpenAi e pode ligar o primary no staging"'
)
JEV_KEY_FROM_FILE = ("TYPESAFE_API_KEY", "JEVMODEL_API_KEY")
# SPEC-213: modo do arquivista. ``inline`` (default do produto) = variavel ausente; ``post_response`` tira os
# derivados (resumo/memoria/cronica) do caminho do jogador. Rollback: --projection-mode inline.
PROJECTION_MODES = ("inline", "post_response")
# SPEC-296 R1: propagação de notícias entre NPCs (SPEC-215). ``off`` (default do produto) = variavel ausente.
NPC_KNOWLEDGE_MODES = ("off", "shadow", "on")
# SPEC-302 D5: motor de mundo. Default do CODIGO e `on`; no staging o default e `shadow`
# ate o smoke real (sempre enviado explicitamente).
WORLD_ENGINE_MODES = ("off", "shadow", "on")
# SPEC-236 §6.2: teto diario temporariamente baixo (ex.: 0.01) para provocar um trip REAL pelo cron finops.
# Reverter com um push sem a flag (volta ao default 5).
DEFAULT_DAILY_CAP_BRL = NON_SECRET_LITERALS["RPG_DAILY_SPEND_CAP_BRL"]


def _valid_cap(raw: str) -> str:
    from decimal import Decimal, InvalidOperation

    try:
        value = Decimal(str(raw))
    except InvalidOperation:
        raise ValueError(f"daily_cap_brl invalido: {raw}") from None
    if not value > 0:
        raise ValueError(f"daily_cap_brl invalido: {raw}")
    return str(raw)


def stale_names(production: Mapping[str, str]) -> tuple[str, ...]:
    """Variaveis a apagar: as removidas + as do outro modo RLS/flags opcionais ausentes de ``production``."""
    return REMOVED_NAMES + tuple(n for n in MODE_EXCLUSIVE + OPTIONAL_FLAGS if n not in production)


# SPEC-194: HMAC key for Play obfuscated account ids (>=32 chars). Pushed only when present in the env files.
# SPEC-197 R6 voice: Groq primary. 2026-10-18 (dono): OPENAI_API_KEY opcional entra no staging (fallback pago de
# STT/imagem, SPEC-236 §6.3); sem a chave nao ha candidato pago.
# 2026-10-17 (dono: "Sim, use a DeepSeek"): DEEPSEEK_API_KEY e o candidato PRIMARIO de ROUTES em todos os tiers;
# Groq segue como fallback. Opcional: sem a chave o candidato e pulado e o Groq assume.
OPTIONAL_SECRET_FROM_FILE = ("RPG_PLAY_ACCOUNT_KEY", "DEEPSEEK_API_KEY", "OPENAI_API_KEY")
# R-01: site key real do Turnstile (publica) quando o operador a tem; senao a de teste da Cloudflare.
SITE_KEY_FROM_FILE = ("RPG_TURNSTILE_SITE_KEY", "TURNSTILE_SITE_KEY")
# SPEC-236 §6.1: chave DeepSeek deliberadamente invalida (literal publico, nao e segredo) para forcar 1 falha
# do primario + fallback Groq. Reverter com um push normal (o upsert regrava a chave real).
INVALID_DEEPSEEK_KEY = "sk-spec236-smoke-invalid-key"
RLS_SECRETS = ("RPG_ADMIN_DATABASE_URL",)  # SPEC-224: so no modo RLS efetivo
JEV_SECRETS = ("TYPESAFE_API_KEY",)  # SPEC-217 R15: so com --jev-router-mode shadow
FORBIDDEN_IN_PREVIEW = (
    frozenset(SECRET_FROM_FILE)
    | frozenset(OPTIONAL_SECRET_FROM_FILE)
    | frozenset(RLS_SECRETS)
    | frozenset(JEV_SECRETS)
)


def _load_files() -> dict[str, str]:
    merged: dict[str, str] = {}
    for name in (".env", ".env.staging"):  # .env.staging vence
        merged.update({k: v for k, v in dotenv_values(ROOT / name).items() if v})
    return merged


def build_env(
    files: Mapping[str, str],
    public_host: str = PUBLIC_HOST,
    use_admin_dsn: bool = False,
    invalid_deepseek_key: bool = False,
    text_cap: bool = True,
    projection_mode: str = "inline",
    jev_router_mode: str = "off",
    owner_approved_primary: bool = False,
    daily_cap_brl: str = DEFAULT_DAILY_CAP_BRL,
    npc_knowledge: str = "off",
    world_engine: str = "shadow",
) -> tuple[dict[str, str], dict[str, str]]:
    """Retorna (production, preview). Levanta KeyError com NOME do segredo ausente."""
    if projection_mode not in PROJECTION_MODES:
        raise ValueError(f"projection_mode invalido: {projection_mode}")
    if world_engine not in WORLD_ENGINE_MODES:
        raise ValueError(f"world_engine invalido: {world_engine}")
    if npc_knowledge not in NPC_KNOWLEDGE_MODES:
        raise ValueError(f"npc_knowledge invalido: {npc_knowledge}")
    if jev_router_mode not in JEV_ROUTER_MODES:
        raise ValueError(f"jev_router_mode invalido: {jev_router_mode}")
    if jev_router_mode == "primary" and not owner_approved_primary:
        raise ValueError("jev_router_mode=primary exige owner_approved_primary (aprovacao do dono)")
    production = dict(NON_SECRET_LITERALS)
    production["RPG_DAILY_SPEND_CAP_BRL"] = _valid_cap(daily_cap_brl)
    if not text_cap:
        production.pop("RPG_DAILY_SPEND_CAP_TEXT", None)
    if projection_mode != "inline":
        production["RPG_PROJECTION_MODE"] = projection_mode
    if npc_knowledge != "off":
        production["RPG_NPC_KNOWLEDGE"] = npc_knowledge
    production["RPG_WORLD_ENGINE"] = world_engine
    production["RPG_CORS_ORIGINS"] = f"https://{public_host}"
    site_key = next((files[k] for k in SITE_KEY_FROM_FILE if files.get(k)), None)
    if site_key:
        production["RPG_TURNSTILE_SITE_KEY"] = site_key
    missing = [k for k in SECRET_FROM_FILE if not files.get(k)]
    if missing:
        raise KeyError(f"ausentes em .env.staging/.env: {', '.join(missing)}")
    for key in SECRET_FROM_FILE:
        production[key] = files[key]
    for key in OPTIONAL_SECRET_FROM_FILE:
        if files.get(key):
            production[key] = files[key]
    if invalid_deepseek_key:
        production["DEEPSEEK_API_KEY"] = INVALID_DEEPSEEK_KEY
    if jev_router_mode in ("shadow", "primary"):
        key = next((files[k] for k in JEV_KEY_FROM_FILE if files.get(k)), None)
        if not key:
            raise KeyError("ausentes em .env.staging/.env: TYPESAFE_API_KEY (ou JEVMODEL_API_KEY)")
        production["RPG_JEV_ROUTER_MODE"] = jev_router_mode
        production["TYPESAFE_API_KEY"] = key
    if jev_router_mode == "primary":
        production["RPG_JEV_ROUTER_PRIMARY_APPROVED"] = "1"
    # SPEC-197 R-05 + SPEC-224: o runtime usa o papel de menor privilégio (`rpg_runtime`) com RLS por request
    # e um segundo DSN (`rpg_admin`) para workers/cron/wallet. `use_admin_dsn` e o rollback: DSN unico
    # `postgres` e RPG_REQUEST_RLS=off (comportamento anterior). Sem papeis provisionados, idem.
    if files.get("RPG_RUNTIME_DATABASE_URL") and not use_admin_dsn:
        if not files.get("RPG_ADMIN_DATABASE_URL"):
            raise KeyError(
                "ausentes em .env.staging/.env: RPG_ADMIN_DATABASE_URL "
                "(rode scripts/staging/runtime_role.py --role rpg_admin --apply)"
            )
        production["DATABASE_URL"] = files["RPG_RUNTIME_DATABASE_URL"]
        production["RPG_ADMIN_DATABASE_URL"] = files["RPG_ADMIN_DATABASE_URL"]
    else:
        production["RPG_REQUEST_RLS"] = "off"
    preview = dict(PREVIEW_LITERALS)
    assert not FORBIDDEN_IN_PREVIEW & preview.keys()
    assert not set(REMOVED_NAMES) & (production.keys() | preview.keys())
    return production, preview


def push(
    token: str,
    project_id: str,
    team_id: str,
    target: str,
    values: Mapping[str, str],
    secret_names: frozenset[str],
) -> list[str]:
    pushed = []
    headers = {"Authorization": f"Bearer {token}"}
    url = f"https://api.vercel.com/v10/projects/{project_id}/env"
    for key, value in values.items():
        body = {
            "key": key,
            "value": value,
            "target": [target],
            "type": "encrypted" if key in secret_names else "plain",
        }
        for attempt in range(3):
            try:
                r = httpx.post(
                    url,
                    params={"upsert": "true", "teamId": team_id},
                    headers=headers,
                    json=body,
                    timeout=60,
                )
                break
            except httpx.HTTPError:
                if attempt == 2:
                    raise
        if r.status_code >= 300:
            raise RuntimeError(
                f"vercel env {key}@{target}: HTTP {r.status_code} "
                f"{r.json().get('error', {}).get('code', '?')}"
            )
        pushed.append(key)
    return pushed


def remove(token: str, project_id: str, team_id: str, names: tuple[str, ...]) -> list[str]:
    """Apaga (todos os targets) as variaveis em ``names``; devolve 'NOME@target' apagados."""
    headers = {"Authorization": f"Bearer {token}"}
    base = f"https://api.vercel.com/v10/projects/{project_id}/env"
    envs = (
        httpx.get(base, params={"teamId": team_id}, headers=headers, timeout=60)
        .json()
        .get("envs", [])
    )
    removed = []
    for env in envs:
        if env.get("key") in names:
            r = httpx.delete(
                f"https://api.vercel.com/v9/projects/{project_id}/env/{env['id']}",
                params={"teamId": team_id},
                headers=headers,
                timeout=60,
            )
            if r.status_code >= 300:
                raise RuntimeError(f"vercel env delete {env['key']}: HTTP {r.status_code}")
            removed += [f"{env['key']}@{t}" for t in env.get("target") or []]
    return removed


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--project-name", default=PROJECT_NAME)
    ap.add_argument("--public-host", default=PUBLIC_HOST)
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument(
        "--use-admin-dsn", action="store_true", help="rollback: DATABASE_URL = postgres"
    )
    ap.add_argument(
        "--invalid-deepseek-key",
        action="store_true",
        help="SPEC-236 §6.1: envia uma chave DeepSeek invalida (forca fallback Groq); reverter sem a flag",
    )
    ap.add_argument(
        "--no-text-cap",
        action="store_true",
        help="rollback SPEC-237: desliga o cap diario de TEXTO (apaga RPG_DAILY_SPEND_CAP_TEXT)",
    )
    ap.add_argument(
        "--projection-mode",
        choices=PROJECTION_MODES,
        default="inline",
        help="SPEC-213: post_response tira os derivados do arquivista do hot path; inline apaga a variavel",
    )
    ap.add_argument(
        "--jev-router-mode",
        "--jev-router",
        choices=JEV_ROUTER_MODES,
        default="off",
        help="SPEC-217: shadow observa; primary decide (exige --owner-approved-primary); off apaga tudo",
    )
    ap.add_argument(
        "--owner-approved-primary",
        action="store_true",
        help=f"SPEC-217: aprovacao do dono para primary no staging ({OWNER_PRIMARY_APPROVAL})",
    )
    ap.add_argument(
        "--npc-knowledge",
        choices=NPC_KNOWLEDGE_MODES,
        default="off",
        help="SPEC-296 R1: propagacao de noticias entre NPCs (SPEC-215); off apaga a variavel",
    )
    ap.add_argument(
        "--world-engine",
        choices=WORLD_ENGINE_MODES,
        default="shadow",
        help="SPEC-302 D5: motor de mundo; staging fica em shadow ate o smoke real",
    )
    ap.add_argument(
        "--daily-cap-brl",
        default=DEFAULT_DAILY_CAP_BRL,
        help="SPEC-236 §6.2: teto diario em BRL (default 5); valor baixo provoca trip real; reverter sem a flag",
    )
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
        production, preview = build_env(
            files,
            args.public_host,
            args.use_admin_dsn,
            args.invalid_deepseek_key,
            text_cap=not args.no_text_cap,
            projection_mode=args.projection_mode,
            jev_router_mode=args.jev_router_mode,
            owner_approved_primary=args.owner_approved_primary,
            daily_cap_brl=args.daily_cap_brl,
            npc_knowledge=args.npc_knowledge,
            world_engine=args.world_engine,
        )
    except (KeyError, ValueError) as exc:
        print(exc.args[0], file=sys.stderr)
        return 1
    secrets = FORBIDDEN_IN_PREVIEW
    print("production:", ", ".join(sorted(production)))
    print("preview:", ", ".join(sorted(preview)), "(sem segredos de DB/serviço)")
    print("a remover:", ", ".join(stale_names(production)))
    print("RPG_DAILY_SPEND_CAP_BRL =", production["RPG_DAILY_SPEND_CAP_BRL"])
    if args.dry_run:
        return 0
    token = files.get("VERCEL_TOKEN") or os.environ.get("VERCEL_TOKEN", "")
    if not token:
        print("VERCEL_TOKEN ausente", file=sys.stderr)
        return 1
    push(token, link["projectId"], link["orgId"], "production", production, secrets)
    push(token, link["projectId"], link["orgId"], "preview", preview, secrets)
    removed = remove(token, link["projectId"], link["orgId"], stale_names(production))
    print("removidas:", ", ".join(removed) or "nenhuma")
    print("ok: variáveis enviadas")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
