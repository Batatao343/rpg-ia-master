# SPEC-192 — Vercel staging (Hobby, gratuito)

## Projeto
- Projeto Vercel: `rpg-ia-master-staging` — `prj_NRIbmA1hKLW2jxh6j3nKyqIq8dGw`, time `team_iPosop3vmF0kD9AXhIqWj26i` (Hobby).
- URL: https://rpg-ia-master-staging.vercel.app (target `production` = site de staging).
- Último deploy: `dpl_DU7Epi6TjxwtBTRHLxJgvvFSsKJy` (gru1) e redeploy posterior com `regions: ["gru1"]`.
- Criado via REST (`POST /v11/projects`, framework `fastapi`): `vercel link` falhava porque o CLI detecta
  "services" e recusa `functions`/`buildCommand` top-level. `.vercel/project.json` escrito à mão (gitignored).

## Comandos
```bash
uv run python scripts/staging/vercel_env.py [--dry-run]   # envia env (só imprime nomes)
# deploy (token injetado do .env por subprocess; nunca na linha de comando)
npx vercel@64.2.0 deploy --prod --yes
uv run python scripts/staging/vercel_smoke.py             # grava docs/spec192/evidence/smoke.json
npx vercel@64.2.0 logs --environment production --since 15m --query level:error
```

## Empacotamento (achados)
- A Vercel instala SÓ as deps core de `uv.lock` ("Installing required dependencies from uv.lock"),
  ignorando extras e `requirements-vercel.txt`. Foram movidos para `[project].dependencies`:
  `psycopg[binary,pool]`, `langchain-openai`, `pillow` (este último importado por
  `services/asset_pipeline` no worker de jobs; antes só estava no grupo dev).
- `excludeFiles` tem limite de 256 chars; `scripts/**` NÃO pode ser excluído inteiro
  (`services/cron_internal` importa `scripts.recover_account_deletions`) — exclui só `scripts/staging/**`.
- Bundle (log de build): 261,96 MB -> 295,77 MB -> 314,51 MB (final, "optimizing dependencies"); limite Python 500 MB.
- Região da função: `gru1` (vercel.json `regions`), igual ao Postgres Supabase `sa-east-1`. `maxDuration` 300 s.

## Medidas (smoke 2026-10-15, evidência em `evidence/smoke.json`)
- Cold start (1a request após deploy, `/health`): ~6,8–10 s (import de langgraph/langchain); com função morna 85 ms.
- Warm `/health` p50 ~31–36 ms (gru1; antes em iad1: ~150–230 ms).
- `/internal/cron/*`: sem auth 401; com Bearer 200 (`jobs` 0,85 s, `account-deletions` 1,6 s, `operations` 0,6 s, DB real).
- Headers: HSTS, `x-content-type-options: nosniff`, `referrer-policy: same-origin`, `cache-control: public, max-age=0, must-revalidate`.
  Não há CSP/X-Frame-Options nas respostas.

## Variáveis (nomes)
- production: `DATABASE_URL, SUPABASE_URL, SUPABASE_PUBLISHABLE_KEY, SUPABASE_SERVICE_ROLE_KEY, RPG_SESSION_SECRET,
  RPG_CRON_SECRET, JINA_API_KEY` (encrypted) + `RPG_RUNTIME_PROFILE=hosted-supabase, RPG_BIND_HOST=0.0.0.0,
  RPG_COOKIE_SECURE=1, RPG_CORS_ORIGINS, RPG_AUTH_EMAIL_CONFIRMATION_REQUIRED=1, RPG_AUTH_CAPTCHA_MODE=gotrue,
  RPG_AUTH_CAPTCHA_REQUIRED=1, RPG_TURNSTILE_SITE_KEY` (chave pública de teste Cloudflare) `, RPG_FORCE_MOCK=1`.
- `RPG_BIND_HOST=0.0.0.0` é aceito pela validação (`_unsafe_hosted_host` só recusa loopback/127.*).
- Embeddings: `JINA_API_KEY` presente; sem `RPG_EMBEDDINGS` a cadeia escolhe Jina, que casa com o `embeddings_meta.json` dos índices FAISS.
  `RPG_FORCE_MOCK=1` afeta só o LLM.

## Política de preview (R6/R7)
Target `preview` recebe somente `RPG_RUNTIME_PROFILE`, `RPG_BIND_HOST`, `RPG_FORCE_MOCK`: nenhum `DATABASE_URL`,
`SUPABASE_*` ou segredo. O perfil hosted-supabase recusa subir sem eles (falha fechada); previews não alcançam o banco.
Teste: `tests/test_spec192_vercel_env.py`.

## Topologia do worker (decisão, 2026-10-15)

**Escolhido:** fila de jobs em Postgres (`app.jobs`, leases + heartbeat + fencing token) drenada por
`pg_cron` + `pg_net` (Supabase) chamando `POST /internal/cron/{jobs,account-deletions,operations}` na
própria função Vercel (`cron.md`). Nenhum processo contínuo, nenhum filesystem persistente.

Por que não as alternativas:
- **Vercel Cron nativo:** no plano Hobby só roda no máximo **1x/dia** (inviável p/ jobs a cada minuto e
  recuperação de exclusão a cada 5 min).
- **Vercel Queues / Services (beta):** dependem de beta/Pro, não são portáveis e duplicariam a fila já
  durável no Postgres (que também serve ao perfil `portable`/local). O `JobQueue` Postgres é a fonte da verdade;
  o gatilho é só um "relógio" substituível (pg_cron, Railway cron, `workers/run_worker.py` em container).
- **Worker contínuo (Railway/Render):** certo p/ produção com carga, mas custa fixo e não era necessário para
  provar os gates; fica como fallback (abaixo).

Efeitos: um tick nunca começa job com < 15 s de orçamento; sobreposição de ticks é segura (`SKIP LOCKED` + lease);
falha ao meio = lease expira (90 s) e o próximo tick reassume com novo token (token antigo recebe `LeaseHeld`).

## Evidências (todas em `evidence/`, sem segredos; e-mails viram hash)

| Gate | Resultado | Arquivo |
|---|---|---|
| Login/CSRF/cookies/SSE same-origin (5 turnos, `turn_count` +5 exato, retry `action_id` sem duplicar, logout, signup com captcha) | PASS | `e2e_session.json` |
| Preview isolado (sem env de DB/segredo; `/auth/config` 500, cron 503, `/game/saves` 401; deployment apagado) | PASS | `preview_isolation.json` |
| pg_cron + pg_net agendados (3 jobs), 200 em `net._http_response` | PASS | `cron_schedule.json`, `cron_runs.json` |
| Exclusão de conta interrompida recuperada pelo cron em ~2,3 min (137 s); falha permanente isolada + `rpg.cron` ERROR | PASS | `account_deletion_recovery.json` |
| Job sobrevive a crash (lease expirada, 2 tentativas, 1 efeito, token antigo fenceado) e a `deploy --prod` | PASS | `job_survival.json` |
| Medidas (cold start, p50/p95, SSE, bundle, plano) | registradas | `measurements.json` |

Ressalvas honestas:
- O handler de embedding dura ~1 s; **não foi possível cronometrar um redeploy exatamente no meio de um job**. O
  crash foi emulado (lease por SQL, worker "morto") e o redeploy real rodou sob carga contínua de jobs
  (4 jobs, todos `succeeded` com `attempts=1`). Fencing/idempotência vêm do código (`PostgresJobQueue`) e dos testes.
- Signup pelo app: o SMTP embutido do Supabase tem limite de e-mails (429 `over_email_send_rate_limit`), então o
  usuário pode não ser criado; o captcha é provado por GoTrue direto (sem token = erro de captcha; token de teste =
  passa o captcha). O app responde 202 genérico (anti-enumeração).
- `/internal/cron/*` devolve HTTP **500** com o mesmo corpo só-contagens (`"ok":false`) quando a tarefa reporta falhas
  (ex.: `failed>0` em exclusão de conta); assim `net._http_response.status_code` já acusa a falha. O watchdog
  `app.cron_health_check()` (pg_cron a cada 15 min, migration `20261015125000_cron_health.sql`) grava em
  `app.cron_health_alerts` quando as 3 últimas requisições resolvidas de um job são não-2xx (ver `cron.md`).
- Alerta `rpg.cron` nível ERROR (>= 3 falhas consecutivas por instância) confirmado com
  `npx vercel logs --environment production --since 10m --query level:error` (linhas `rpg.cron`).

## Medidas (2026-10-15, Hobby, `gru1`)
- Plano: **Vercel Hobby** (US$ 0; `GET /v1/usage` só existe no Pro) + **Supabase Free**; zero chamada paga de LLM
  (`RPG_FORCE_MOCK=1`). Função: `maxDuration` 300 s, bundle Python ~314,6 MB (limite 500 MB), build ~56 s,
  `vercel deploy --prod` ~90-110 s.
- Cold start (1a request após deploy): ~6,1 s; seguinte 181 ms. `/health` quente p50 ~30 ms / p95 ~180 ms;
  rota com DB (`/game/saves`, autenticada) p50 ~106 ms / p95 ~133 ms.
- SSE (`/game/action/stream`, MockLLM): primeiro byte p50 ~153 ms; turno completo p50 ~670 ms / p95 ~2,3 s.
- Chamadas cron: servidor 12-63 ms (fila vazia), cliente 45-95 ms.

## Runbooks

**Rollback (deploy ruim):** `npx vercel@64.2.0 rollback` (volta ao deploy de produção anterior) ou
`npx vercel@64.2.0 promote <deployment-url>` com a URL de um deploy `READY` conhecido
(`vercel ls --prod`). É instantâneo (troca de alias); migrations de banco NÃO revertem junto: só aplicar
migrations compatíveis com o código anterior (expand/contract). Depois: `uv run python scripts/staging/vercel_smoke.py`.

**Fallback se a Vercel falhar (limite, indisponibilidade, mudança de plano):** a mesma imagem/código roda como
container (Railway ou Render): serviço `api-web` (`uvicorn api:app --host 0.0.0.0 --port $PORT`, serve `web/dist`)
e serviço `worker` (`python workers/run_worker.py --worker-id w1`, loop contínuo; dispensa pg_cron p/ jobs). As env são
as mesmas de `vercel_env.py` (nomes na seção Variáveis). `pg_cron` pode continuar chamando
`/internal/cron/account-deletions` e `/operations` na nova URL: rode `scripts/staging/schedule_cron.py --base <nova-url>`
(idempotente). Atualizar `RPG_CORS_ORIGINS`/`site_url` do Supabase Auth para o novo host.

**Política de preview (R6/R7):** previews não recebem `DATABASE_URL`, `SUPABASE_*`, `RPG_SESSION_SECRET`,
`RPG_CRON_SECRET` nem `JINA_API_KEY`; o perfil `hosted-supabase` falha fechado e a Deployment Protection da Vercel
exige login (302). Previews nunca apontam para o banco de staging; testar banco em preview exige projeto Supabase
descartável. Verificação repetível: `uv run python -m scripts.staging.preview_isolation` (cria, testa e apaga o deploy).

**Scripts (todos em `scripts/staging/`, rodam com `uv run python -m scripts.staging.<nome>`):**
`e2e_session`, `preview_isolation`, `schedule_cron`, `verify_cron`, `account_deletion_recovery`,
`job_survival`, `measure [--redeploy]`, `vercel_smoke`. Dados sintéticos: `spec192-*@example.invalid`, removidos ao fim.

## SPEC-104
A preferência por Railway (estado da Vercel em 2026-08-16) está **superada** por esta evidência; nota datada
adicionada ao fim de `specs/SPEC-104-fase-10b-certificacao-cloud-portavel.md` (histórico preservado). Railway/Render
seguem como fallback operacional.

## Pendências
- Review Sol independente da topologia (último item do gate da spec).
- `site_url` do Supabase Auth deve ser a URL do staging; e-mail transacional real (SMTP próprio) para signup completo.

## SSE no Vercel e desconexão no meio do turno (F3)
O worker do turno SSE roda numa thread dona do lock/save e **continua após o cliente desconectar**; na Vercel a
função pode ser congelada/encerrada depois que a resposta fecha. Recuperação, sem intervenção manual: (1) a operação
fica com lease no Postgres; (2) o cron `/internal/cron/operations` libera operações de lease vencida; (3) o cliente
repete a mesma ação (`action_id`) pelo fallback POST, idempotente: aplica o turno uma única vez ou devolve o
resultado já gravado. Evidência: `evidence/sse_disconnect.json` (`scripts/staging/sse_disconnect.py`).
