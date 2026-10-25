---
name: staging-deploy
description: Deploy do staging Vercel (rpg-ia-master-staging) a partir do HEAD — env vars via vercel_env.py, vercel deploy --prod com GIT_SHA, /health com o sha certo e smokes (post_deploy_smoke, vercel_smoke, e2e_session). Use em "/staging-deploy", "redeploy do staging", "sobe pro staging". Só quando o dono/coordenador autorizou deploy nesta sessão.
---

# /staging-deploy

Segredos: **nunca** imprima valores de `.env`/`.env.staging`; os scripts leem por
nome e mostram só nomes. Rode do checkout principal (é onde está o `.env.staging`).

1. Pré: `git status` limpo, HEAD = commit a publicar, CI verde nele
   (`gh run list --commit $(git rev-parse HEAD)`).
2. Env vars (mostra só nomes/targets):
   `uv run --frozen python scripts/staging/vercel_env.py --dry-run` → revise →
   sem `--dry-run`. Flags de modo (`--jev-router-mode`, `--projection-mode`,
   `--owner-approved-primary`…) só com decisão explícita do dono. **Sem flags, o script carrega
   `scripts/staging/staging_flags.json`** (estado aprovado pelo dono; flags da CLI sobrescrevem;
   `--no-preset` volta aos defaults antigos, que DESLIGAM o mundo vivo). Decisão nova do dono →
   editar o JSON com data e commitar antes do deploy.
3. Migrations pendentes primeiro (expand/contract): `scripts/staging/migrations.py status`
   → se houver pendente, `push` (plano) → `push --apply`.
4. Deploy: `vercel deploy --prod -e GIT_SHA=$(git rev-parse HEAD) -b GIT_SHA=$(git rev-parse HEAD)`
   (`-e` = runtime/`/health`; `-b` = build do bundle web — sem ele o `X-RPG-Build` sai `dev+…` e o
   `build_skew` nunca dispara; o upload não leva `.git`) (~90–110 s; Bash com
   `timeout: 300000`).
5. Warm-up (SPEC-317 R12): logo após o deploy, `curl -s https://rpg-ia-master-staging.vercel.app/health`
   uma vez (aquece a função e confere o `git_sha`) antes de medir/fumar; o 1º turno do
   `e2e_session.py` abaixo é o turno sintético que aquece o grafo. Medição de latência
   (`measure.py`) sempre em função morna; cold start medido à parte, de propósito.
6. Verificação (uma chamada cada):
   - `uv run --frozen python scripts/post_deploy_smoke.py --base-url https://rpg-ia-master-staging.vercel.app --expected-git-sha $(git rev-parse HEAD) --output readiness_artifacts/post_deploy.json`
     → `git_sha` = HEAD, `hardened=true`;
   - `uv run --frozen python scripts/staging/vercel_smoke.py`;
   - `uv run --frozen python scripts/staging/e2e_session.py` (5 turnos SSE, retry idempotente).
7. Rollback: promover o deploy anterior na Vercel (`vercel promote <url>`) ou o
   kill switch citado no ESTADO.

Saída: sha publicado, URL do deploy, resultado dos 3 smokes (1 linha cada).
