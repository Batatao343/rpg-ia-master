# SPEC-218 — Revisão Astra independente (adversarial)

- **Data:** 2026-10-17
- **Revisor:** Astra (≡ Opus, contexto separado; não escreveu a implementação)
- **Base:** branch `spec-218` rebaseada em `main` (rebase limpo, sem conflitos)
- **Veredito:** **APPROVED** (com 3 correções aplicadas nesta revisão). Status da spec segue `in-progress`
  só pelo smoke de staging (§6 itens 3–4).

## Escopo revisado

`infrastructure/runtime.py` (`exposure_markers`, `assert_boot_policy`, `HOSTED_SECURITY_REQUIREMENTS`,
`FORBIDDEN_IN_HOSTED`, `docs_enabled`, `is_hardened`, `kill_switch_fail_closed_default`,
`apply_serverless_defaults`), `api.py` (boot no import, docs/openapi, CORS, cron fora do schema, `/health`),
`services/kill_switches.py`, `scripts/{cloud_doctor,post_deploy_smoke}.py`, `scripts/release/checklist.py`,
`Procfile`, `vercel_app.py`, `scripts/staging/vercel_env.py`, `tests/conftest.py`, `tests/test_boot_policy.py`.

## Ataques tentados

| Ataque | Resultado |
|---|---|
| `RPG_BIND_HOST=127.0.0.1` + `--host 0.0.0.0` em plataforma (exigido pelo §5) | **Falha** pelo marcador da plataforma (`RAILWAY_ENVIRONMENT`, `VERCEL`, `RENDER`, `K_SERVICE`, `FLY_APP_NAME`, `DYNO`). Verificado em processo real (`uvicorn`) e em teste. |
| Mesmo bypass só com `PORT` (Heroku-like) | Antes: passava (Heroku injeta `DYNO`, não estava na lista). **Corrigido:** `DYNO` é marcador. |
| `python api.py` com `RPG_HOST=0.0.0.0` (bind real lido pelo próprio app) | Antes: legacy subia exposto sem marcador. **Corrigido:** `RPG_HOST` não-loopback é marcador. |
| Processo sem nenhum marcador + bind manual 0.0.0.0 | **Limite aceito (D-B):** uvicorn não expõe o host ao app; responsabilidade do operador. `Procfile` liga em loopback por default. |
| `RPG_RUNTIME_PROFILE` vazio / caixa alta / espaços | `""` → tratado como legacy pelo guard (marcadores checados) e como DB pelo middleware → fecha. Normalização `strip().lower()` coerente com `from_env`. |
| `local`/`portable` expostos | `local` exposto recusa; `portable` exposto exige o mesmo hardening de `hosted*`. |
| Mock/flags de teste em hosted | `RPG_FORCE_MOCK`, `RPG_GOOGLE_PLAY_FAKE`, `RPG_ADMIN_ALLOW_PROFILE`, `RPG_KILL_SWITCHES_OFF`, overrides de laboratório e `RPG_EXPOSE_OPENAPI` → boot recusa. Sem key e sem `RPG_NO_MOCK=1` → recusa. `.env` com `override=True` não contorna (o guard roda depois do `load_dotenv`). |
| Segredo de telemetria | `RPG_TELEMETRY_SECRET` < 32 → recusa; `/health.hardened` ignora o override de laboratório. |
| `/openapi.json`, `/docs`, `/redoc`, `/docs/oauth2-redirect` | 404 em perfil DB (cobre automaticamente rotas novas da main: `/game/cards/prepare`, `/game/map`, `/game/codex/dossiers`, `/game/{id}/audit-export`, `/auth/refresh/logout`). `/internal/cron/*` fora do schema mesmo com docs ligados. |
| CORS explícito vs. frontend | Frontend usa só GET/POST/DELETE e headers `X-CSRF-Token`, `X-Operation-Id`, `X-RPG-Client`, `Idempotency-Key` — todos na allowlist. Nenhuma rota PUT/PATCH. |
| Vazamento de valores em erros | Mensagens de boot/hosted só com nomes e motivo; teste com `DATABASE_URL` contendo `SEGREDO` passa; smoke real confirmou. Único eco é o nome de perfil inválido (não secreto, pré-existente). |
| Suíte com marcador no shell do dev/CI | **Defeito (R10):** `import api` ocorre na COLETA, antes da fixture autouse → `PORT=8000 pytest` derrubava a suíte com `legacy_profile_exposed`. **Corrigido:** conftest limpa os marcadores no próprio import + teste subprocess. |

## Correções aplicadas (com testes)

1. `tests/conftest.py`: limpeza de `VERCEL/PORT/RAILWAY_ENVIRONMENT/RENDER/K_SERVICE/FLY_APP_NAME/DYNO/RPG_BIND_HOST/RPG_HOST/RPG_ALLOW_LEGACY_EXPOSED` no import (além da fixture). Teste `test_suite_collection_survives_exposure_markers_in_parent_env` (reproduzido vermelho manualmente antes).
2. `infrastructure/runtime.py`: marcadores `DYNO` e `RPG_HOST` (não-loopback). Testes `test_rpg_host_non_loopback_is_exposure_marker` (vermelho → verde), parametrização com `DYNO`, `test_bind_host_loopback_does_not_hide_platform_marker`.
3. `tests/test_boot_policy.py::test_portable_profile_exposed_requires_hardening`: fixture ganhou `RPG_OIDC_JWKS_URL`/`RPG_OIDC_AUDIENCE` (a main, via SPEC-220, passou a exigir OIDC completo; o teste quebrava após o rebase).

## Smoke local (§6 itens 1–2)

- Negativo: sem perfil, `PORT=8011 uvicorn api:app --host 0.0.0.0` → exit 1, `RuntimeError: legacy_profile_exposed: markers=PORT ...`, sem o valor `SEGREDO` do `DATABASE_URL`.
- Bypass: `RPG_BIND_HOST=127.0.0.1 PORT=8012 RAILWAY_ENVIRONMENT=production ... --host 0.0.0.0` → `markers=RAILWAY_ENVIRONMENT`.
- Positivo legacy loopback: `/health` → `profile=legacy, hardened=false`; `/openapi.json` 200 (inalterado).
- Positivo `local` com Supabase local (`scripts/start_local_api.py`, Postgres 127.0.0.1:55322): sobe, `/health` → `profile=local`, `/openapi.json` 200; processo encerrado.

## Staging (read-only, sem valores)

`scripts/staging/vercel_env.build_env(.env + .env.staging)` avaliado por `hosted_security_problems` e `cloud_doctor.diagnose`:

- `present`: `RPG_COOKIE_SECURE`, `RPG_SESSION_SECRET`, `RPG_CORS_ORIGINS`, `RPG_AUTH_CAPTCHA_REQUIRED`, `RPG_AUTH_EMAIL_CONFIRMATION_REQUIRED`, `RPG_RATE_LIMIT`, `RPG_NO_MOCK` (há key de provider; na Vercel `apply_serverless_defaults` também seta `RPG_NO_MOCK=1`), `LLM_PROVIDER`.
- **Faltando:** `RPG_TELEMETRY_SECRET` (ausente em `.env.staging` e não enviado por `vercel_env.py`).
- **Violação:** `RPG_FORCE_MOCK=1` (literal em `vercel_env.py` para production e preview) agora é proibido em hosted.

**Consequência:** se a `main` com esta spec for redeployada no staging sem ajuste, o boot falha de propósito (todas as requisições 500). Antes do redeploy o dono deve: (a) gerar `RPG_TELEMETRY_SECRET` (≥32) e adicioná-lo a `.env.staging` + `SECRET_FROM_FILE` do `vercel_env.py`; (b) decidir o mock: remover `RPG_FORCE_MOCK` implica LLM real no staging (há `GROQ_API_KEY` opcional enviado) — custo/comportamento, decisão do dono, por isso **não** alterado nesta revisão. Preview continua falhando fechado (desejado).

## Observações não bloqueantes

- D-C × R11: `RPG_EXPOSE_OPENAPI` é proibido em todo `hosted*`, então nem o staging publica docs (R11 vence; registrado na spec).
- `cloud_doctor` rotula `FORBIDDEN_IN_HOSTED` violado como `missing` (semântica estranha, sem valor vazado).
- Evidência vermelha da Etapa 0 no HEAD original não foi capturada separadamente pelo executor.
