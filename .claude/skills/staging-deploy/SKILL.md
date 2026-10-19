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
   `--owner-approved-primary`…) só com decisão explícita do dono; o default é o
   estado atual descrito em `ESTADO_ATUAL.md`.
3. Migrations pendentes primeiro (expand/contract): `scripts/staging/migrations.py status`
   → se houver pendente, `push` (plano) → `push --apply`.
4. Deploy: `vercel deploy --prod -e GIT_SHA=$(git rev-parse HEAD)` (~90–110 s; Bash com
   `timeout: 300000`).
5. Verificação (uma chamada cada):
   - `uv run --frozen python scripts/post_deploy_smoke.py --base-url https://rpg-ia-master-staging.vercel.app --expected-git-sha $(git rev-parse HEAD) --output readiness_artifacts/post_deploy.json`
     → `git_sha` = HEAD, `hardened=true`;
   - `uv run --frozen python scripts/staging/vercel_smoke.py`;
   - `uv run --frozen python scripts/staging/e2e_session.py` (5 turnos SSE, retry idempotente).
6. Rollback: promover o deploy anterior na Vercel (`vercel promote <url>`) ou o
   kill switch citado no ESTADO.

Saída: sha publicado, URL do deploy, resultado dos 3 smokes (1 linha cada).
