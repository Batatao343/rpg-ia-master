# Promocao staging -> producao (SPEC-197)

## Decisao (pesquisada na doc Vercel, 2026-10-15)

Fatos: `vercel promote` e rollback instantaneo apenas reatribuem dominios dentro de **um mesmo projeto**; nao
existe promocao entre projetos. Promover um deploy de *preview* para producao **reconstroi** e passa a usar as
env vars do ambiente de producao. Um deploy de producao "staged" (auto-assign de dominios desligado) pode ser
promovido **sem rebuild**. Staging e producao usam bancos Supabase diferentes, entao as env vars diferem.

Opcoes:
1. Projeto unico, staging como custom environment/preview: promover = rebuild com outras env; custom
   environments exigem Pro; mistura segredos de dois bancos no mesmo projeto. Rejeitada.
2. **Dois projetos (`rpg-ia-master-staging`, `rpg-ia-master`), mesmo artefato pre-construido (RECOMENDADA).**
   Todo valor especifico de ambiente e lido em *runtime* (Python le env; `/auth/config` serve a site key do
   Turnstile), logo o mesmo build serve os dois. Constroi-se uma vez e implanta-se o mesmo `.vercel/output`
   nos dois projetos com `--prebuilt`; compara-se o checksum. "Promocao" de producao = deploy *staged* do
   artefato ja verificado + `vercel promote` (sem rebuild).

Premissa a verificar uma vez: o build (`web/dist`, bundle Python) nao embute env de ambiente. Provar com
`uv run python scripts/vercel_bundle_check.py` e `grep` do `web/dist` por URLs do staging (deve ser zero).
Se algum valor virar build-time, vira runtime, ou o criterio de checksum falha e o gate bloqueia.

## Procedimento

Pre: checklist staging verde para o SHA (`uv run python -m scripts.release.checklist --env staging --base-url ...`),
risk-register sem P0/P1, aprovacao humana registrada.

```bash
SHA=$(git rev-parse HEAD)               # arvore limpa, CI verde
npx vercel@64.2.0 pull --yes --environment=production   # projeto STAGING linkado
npx vercel@64.2.0 build --prod
find .vercel/output -type f -print0 | sort -z | xargs -0 sha256sum | sha256sum   # -> ARTEFATO_SHA
npx vercel@64.2.0 deploy --prebuilt --prod            # staging
uv run python scripts/post_deploy_smoke.py --base-url https://rpg-ia-master-staging.vercel.app --expected-sha $SHA
# trocar o link para o projeto de PRODUCAO (vercel link --project <prod>), com auto-assign de dominios DESLIGADO
npx vercel@64.2.0 deploy --prebuilt --prod --skip-domain   # mesmo .vercel/output; NAO rodar build de novo
# conferir que o hash de .vercel/output nao mudou; registrar ambos em docs/spec197/evidence/promotion-<sha>.json
uv run python scripts/post_deploy_smoke.py --base-url <url-do-deploy-staged> --expected-sha $SHA
npx vercel@64.2.0 promote <url-do-deploy-staged>
npx vercel@64.2.0 promote status
uv run python -m scripts.release.checklist --env production --base-url https://<prod> --strict --legal-url privacy=... 
```

(Confirmar flags `--skip-domain`/`--prebuilt` com `npx vercel deploy --help` na versao pinada antes do primeiro uso.)

Ordem obrigatoria no banco: migrations de producao aplicadas ANTES do deploy (expand-only; ver `rollback.md`).
`scripts/staging/migrations.py` exige `--confirm-staging`; para producao criar `--confirm-prod` com lista de refs
protegidos na execucao da SPEC-197 (R1: criacao do projeto prod exige aprovacao explicita do usuario).

Env de producao (nomes; valores so no dashboard/CLI): `REQUIRED_ENV["production"]` em
`scripts/release/checklist.py`. `RPG_FORCE_MOCK` NUNCA existe em producao.
Pins de processadores (devem constar no ambiente de producao para a lista da politica/Data Safety ser exata): `RPG_ROUTES` (JSON; somente DeepSeek + Groq) e `RPG_EMBEDDINGS=jina` (sem fallback para openai/ollama/gemini). Preview segue sem segredos (`vercel_env.py`).

Pos-promocao: aquecer `/health`; agendar crons (`schedule_cron.py`, `finops`); smoke de dois usuarios (R6).

## RLS efetivo (SPEC-224) — ordem obrigatoria antes do deploy
1. Aplicar `20261017120000_rls_effective_storage_no_client_write.sql` (expand-only; cria `rpg_admin`, remove policies de escrita do Storage).
2. `uv run python -m scripts.staging.runtime_role --role rpg_runtime --apply` e `--role rpg_admin --apply` (senhas so no `.env.*`).
3. `vercel_env.py` envia `DATABASE_URL` (rpg_runtime), `RPG_ADMIN_DATABASE_URL` (rpg_admin) — o deploy sem a segunda env falha no boot (fail-closed).
4. Deploy + `two_user_smoke` + 1 request com o log `pool.request_role_applied role=rpg_api`.
5. Rollback imediato: `RPG_REQUEST_RLS=off` (e DSN `postgres`: `vercel_env.py --use-admin-dsn`). Detalhes: `docs/spec224/README.md`.
