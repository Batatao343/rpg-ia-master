# Staging wave 2026-10-17 — security/finops (SPEC-213/218/219/220/222/224/236)

Operador: Claude (autorização do dono, 17/10: "Autorizo você a configurar"). Escopo: **só staging**
(Supabase `uzeagzcyvxzrpjgrhaql`, Vercel `rpg-ia-master-staging`). Branch `staging-wave`
(main `d39da17` + SPEC-218 + SPEC-219 + SPEC-224 + correções abaixo). Nada foi enviado ao GitHub.
Evidência em `evidence/` (só nomes, status, contagens e pseudônimos; nenhum valor secreto).

## Fase A — integração local

| Gate | Resultado |
|---|---|
| `dev_stack.py reset --confirm-local` | exit 0; local com as 28 migrations (5 novas) e roles `rpg_api/rpg_runtime/rpg_admin` |
| `uv run pytest` (1ª rodada) | exit 1: 2 falhas `test_project_index` (índice stale, regenerado no fim) + **`test_rls_runtime_config::test_rate_limiter_is_system_only`** (defeito real) |
| defeito | `PostgresDailyQuota.bump` (SPEC-219) abria conexão de **request**; com RLS efetivo (SPEC-224) a tabela `owner_daily_counters` é vetada a `rpg_api` → *permission denied* → handler falhava **aberto**: a cota diária nunca valeria em hosted. Corrigido para `admin_connection` + regressão no teste de runtime completo (`test_rls_effective.py`) |
| `uv run pytest` (após fix) | 3615 passed, 227 skipped, 15 deselected (só as 2 do índice, regenerado depois) |
| `-m infra_local` normal / `RPG_TEST_REQUEST_RLS=1` | 145 passed, 13 skipped / 144 passed, 14 skipped — exit 0 nos dois |
| export/delete/retention de `owner_daily_counters` | já usam `admin_connection` (ok) |

## Fase B — staging, na ordem

1. **Snapshot.** Deploy de produção anterior: `rpg-ia-master-staging-jfyjlt4pq-…vercel.app`
   (`git_sha 5a87a65`). Nomes de env antes: ver tabela "Env". Backup `backup_restore export`
   (dump app + plataforma, 0 objetos) fora do repo; contagens em `evidence/backup_export_pre.json`.
2. **Migrations** (`migrations push --apply`): `20261016120000`, `20261016121500`, `20261017100000`,
   `20261017110000`, `20261017120000` aplicadas; histórico **28/28 em sync**
   (`evidence/migrations_status_pre.json`, `migrations_push.json`).
3. **Roles/env.** `runtime_role --role rpg_admin --apply` e re-rotação de `rpg_runtime` (ambos sem
   superuser/createdb/createrole/replication/bypassrls). `RPG_TELEMETRY_SECRET` gerado
   (`secrets.token_urlsafe(48)`) só no `.env.staging` do checkout principal e na Vercel.
   `scripts/staging/vercel_env.py`: `GROQ_API_KEY` e `RPG_TELEMETRY_SECRET` obrigatórios,
   `RPG_DAILY_SPEND_CAP_BRL=5`, apaga `RPG_FORCE_MOCK`/`LLM_PROVIDER` (o upsert não apagava) e,
   ao alternar o modo RLS, a variável do outro modo. `cloud_doctor`: `ok`, nenhum requisito
   hosted faltando (`evidence/cloud_doctor.json`).
   **Auth (SPEC-220):** `password_min_length` 6→10, reautenticação para trocar senha, allow-list
   sem curinga (`RPG_STAGING_REDIRECT_URLS` = só o site; o app não usa `redirect_to`).
   `rate_limit_email_sent` recusado pela API (exige SMTP próprio — gate da SPEC-197).
4. **Deploy.** `vercel deploy --prod -e GIT_SHA=<HEAD>`; `/health` = `git_sha` do HEAD,
   `profile=hosted-supabase`, `hardened=true`; `/openapi.json` e `/docs` = 404.

## Smokes (LLM real: Groq)

| Smoke | Resultado |
|---|---|
| `post_deploy_smoke.py` | verde (health, hardened, git_sha, /auth/config, /data/*) |
| `vercel_smoke` | verde (health, estático, 3 crons 200; warm p50 29,5 ms) |
| `e2e_session` (cookie/CSRF/captcha + 5 turnos SSE + retry `action_id`) | verde ×3 com RLS e ×2 sem RLS; `simulated=false` |
| `sse_disconnect` | verde (desconexão no meio + retry = 1 turno) |
| `two_user_smoke` (SPEC-224 isolamento A/B) | verde: 404 em ler/agir/cotar no jogo do outro, saves só do dono, wallet, logout, delete |
| log `pool.request_role_applied role=rpg_api` | presente em toda implantação com RLS; ausente na de rollback |
| SPEC-220 logout sem access → refresh antigo | logout 204, `POST /auth/refresh` com o refresh antigo = **401** |
| SPEC-220 lockout | 10×401 e **429** na 11ª (`Retry-After` 898 s) |
| SPEC-219 owner 21 turnos/min | 20×200 e **429** no 21º em 28,7 s, `Retry-After` 32, `scope=owner` |
| SPEC-219 outro owner, mesmo IP | 200 |
| SPEC-219 token inválido | 401; **nenhum** `GET /user` 401 nos logs do Supabase Auth na janela (`evidence/auth_logs_invalid_token.json`) |
| SPEC-219 `/game/chronicle/search` | 10×200 e **429** no 11º (`Retry-After` 55) |
| SPEC-219 cota diária | `owner_daily_counters` turn=20 (agora via pool de sistema) |
| SPEC-219 R5 (IP real) | a chave `ip:<pseudônimo>:turn` do bucket = HMAC do IP público do chamador ⇒ `client_ip` = `x-vercel-forwarded-for` (1 rede só; 2ª rede não disponível) |
| SPEC-219 `rpg_rate_limited_total` | `/metrics` exige `RPG_METRICS_TOKEN` (não configurado no staging); o mesmo `record_block` gravou `rpg.abuse blocked class=turn scope=owner` e `class=embedding scope=owner` com owner pseudonimizado |
| SPEC-222 sentinela | 0 ocorrências da sentinela nos logs da função (145 e 192 linhas de `/game/action` inspecionadas) |
| SPEC-222 export | 200 com as tabelas novas (`owner_daily_counters`, …), sem chave `purchase_token` |
| SPEC-222 compra fake / delete com arte | **não exercidos**: Play fake é proibido em hosted e não há arte sem gerador pago |
| SPEC-236 falhas | 429 do Groq gravados como `failed_no_usage`, custo 0, `counts_as_spend=false` (28 linhas) |
| SPEC-236 §6.1–6.3 literais | **não exercidos**: sem chave DeepSeek no staging (candidato pulado, não falha de rede), teto cross-day só em teste offline, sem chave OpenAI p/ fallback de STT |
| Security Advisor | **0 ERROR**; 4 WARN pré-existentes (`evidence/advisors_security.json`) |
| release checklist `--env staging` | config verde (migrations, env names, health_sha, kill switches, evals); bloqueado por itens do gate de release (páginas legais, riscos P0/P1 abertos, environments do GitHub, árvore suja pela própria evidência) |

### Latência (SPEC-224, A/B no mesmo commit, RLS on vs `--use-admin-dsn`)

| | turnos | SSE total p50 | SSE total p95 | fase `persistence` p50/p95 |
|---|---|---|---|---|
| RLS on | 15 | 1456 ms | 2552 ms | 119–154 / 154–167 ms |
| RLS off | 10 | 1251 ms | 3895 ms | 92–100 / 100–104 ms |

p95 do turno dentro de +5% (dominado pela variância do LLM); o custo real do `SET LOCAL ROLE` aparece
na fase de persistência: **+25–55 ms p50 por turno**. Amostra pequena; o baseline anterior do staging
era MockLLM e não é comparável.

## Achados

1. **Corrigido:** cota diária SPEC-219 falhava aberta sob o role de request da SPEC-224 (Fase A).
2. **Corrigido no tooling:** `vercel_env.py` nunca apagava variáveis (MOCK sobrevivia; o modo rollback
   deixava `RPG_REQUEST_RLS=off` ao voltar).
3. **Aberto (precisa de spec):** o rate card não tem **Jina**; cada embedding vira estimativa
   conservadora de **US$ 1** (`estimated`, conta como gasto). Com `RPG_DAILY_SPEND_CAP_TEXT=1` todo turno
   passou a 503 após ~17 turnos. No staging o cap de **texto** ficou desligado (o de 5 BRL segue para
   imagem/STT); o gasto real de texto fica limitado pelo free tier do Groq. O custo por turno no ledger
   está inflado em US$ 1 por embedding até a correção (o rate card é versionado/pinado por sha nas
   `pricing_versions`, por isso não foi alterado aqui).
4. **Capacidade:** a chave Groq é free tier (8k tokens/min por modelo). Turnos com prompt grande tomam
   429 e caem na narração de erro; só 2 dos 15 turnos SSE com RLS on tiveram narração longa. Para staging jogável: tier pago
   do Groq ou chave DeepSeek.
5. Excluir uma campanha apaga (cascata) os `usage_events` dela: fatos de gasto somem do teto diário.

## Rollback

`npx vercel@64.2.0 promote <url>` (ou `rollback`). **Atenção:** o deploy anterior à onda
(`jfyjlt4pq`, sha `5a87a65`) tem a senha antiga do `rpg_runtime` embutida e falharia no banco.
Alvo de rollback que funciona: `rpg-ia-master-staging-5set5e8vx-…vercel.app` (mesmo commit, RLS off,
credenciais atuais) ou rodar `vercel_env.py --use-admin-dsn` + novo deploy. As migrations são aditivas
(exceto o drop das policies de Storage de cliente, que o cliente não usa). Produção atual:
`rpg-ia-master-staging-kie02bmt0-…vercel.app` (RLS on).

## Adendo 2026-10-17 (tarde) — DeepSeek no staging, SPEC-236 §6.1 e gate real da SPEC-214

Autorização do dono (17/10): "Sim, use a DeepSeek". Branch `staging-ds` (main `0241e4c` + tooling), sem push.

* **Env/deploy.** `vercel_env.py` agora envia `DEEPSEEK_API_KEY` (opcional, nunca no preview; Groq mantido como
  fallback) e tem `--invalid-deepseek-key` (literal público) para o smoke §6.1. Dois deploys do mesmo código com
  `GIT_SHA=9807ab9`: o primeiro com a chave inválida (§6.1), o segundo com a chave real —
  `rpg-ia-master-staging-eovi9utqp-…vercel.app`, `/health` com o sha, `hosted-supabase`, `hardened=true`.
  Teto `RPG_DAILY_SPEND_CAP_BRL=5` mantido; cap de texto continua desligado (achado Jina).
* **Turnos antes/depois.** Antes (Groq free, 4 turnos): 4/4 HTTP 200 mas **0/4 narrações reais** (63–102 chars =
  narração de erro; 6 tentativas Groq 429). Depois (DeepSeek): `e2e_session` verde (`simulated=false`, 5/5 + retry
  idempotente, `evidence/e2e_session_deepseek.json`) e mais 20 turnos: **25/25 narrações reais** (210–1 706 chars),
  `providers_used=[deepseek]`, 0 tentativas falhas, 0 fallback.
* **SPEC-236 §6.1 verde**: com a chave inválida, `deepseek invoke_error` ×9 → `failed_no_usage`, custo 0,
  `counts_as_spend=false`; LLM do turno só Groq. §6.2 não exercido (precisaria escrever um trip retroativo no audit
  imutável `app.kill_switch_audit` — recusado; segue coberto offline). §6.3 sem chave OpenAI. 236 segue `in-progress`.
* **SPEC-214 gate real: `GO` pela regra** (context p50/p95 414/762 ms; TTLT p50/p95 10 487/14 774 ms;
  share 3,94 %). Spec segue `draft`, sem implementação. [gate-real](../spec214/gate-real-2026-10-17.md).
* **Gasto real:** DeepSeek ≈ US$ 0,10 no total (20 turnos = US$ 0,076 pelo log `usage`; ledger em
  `conservative_peak` dá US$ 0,079; + e2e/jogos novos). Groq/Jina free tier. O ledger ainda mostra US$ 1 por
  embedding Jina (estimativa; achado 3 aberto). Usuários/jogos sintéticos apagados (sweep = 0 sobras).
* **Achado:** `cost_basis` do DeepSeek no ledger é `estimated` (`pricing_mode=conservative_peak` do card) enquanto o
  log do turno diz `usage`; coerente com o card, mas o ledger nunca fica `billing_exact` para DeepSeek.
* **Rollback** (inalterado): promover `kie02bmt0` (mesmo runtime, Groq-only, RLS on) ou repetir `vercel_env.py`
  sem a chave + deploy. Para tirar a DeepSeek: apagar `DEEPSEEK_API_KEY` no projeto Vercel e redeploy.

## Adendo 2026-10-17 (noite) — SPEC-237 no staging e SPEC-219 R5 em 2ª rede

Branch `staging-237` (main `8823bb0` + 1 commit de tooling), sem push. Escopo inalterado (Supabase `uzeagzcyvxzrpjgrhaql`,
Vercel `rpg-ia-master-staging`).

* **Deploy.** `vercel_env.py` agora liga `RPG_DAILY_SPEND_CAP_TEXT=1` por padrão (`--no-text-cap` apaga a variável).
  Deploy `rpg-ia-master-staging-6wy6q129o-…vercel.app`, `GIT_SHA=3250cdb`, `/health` com o sha, `hosted-supabase`,
  `hardened=true`. A Vercel instala do **`uv.lock`** ("Installing required dependencies from uv.lock"), não do
  `requirements-vercel.txt`; ambos fixam multidict 6.9.1 / urllib3 2.8.0 / langgraph-sdk 0.4.8 (SPEC-225).
* **SPEC-237 (`done`).** Com o cap de texto ligado e teto R$ 5: 32/32 turnos SSE 200 (DeepSeek, `simulated=false`),
  **0 × 503 `daily_spend_cap`**; 56 embeddings Jina `token_priced` = US$ 0,000098 (antes 56 × US$ 1); 2 turnos extras:
  `billing_exact=true`, `pricing_version=embedding-2026-10-17-v1-8e04a9bb33e8be9b`, custo 4e-7…2e-5 USD, nenhuma linha
  `unknown-conservative` nas últimas 2 h. Gasto real ≈ US$ 0,12. Jogos/usuários sintéticos apagados (sweep = 0).
  [evidência](evidence/spec237_text_cap_32_turns.json).
* **SPEC-219 R5 (2ª rede).** `GET /game/saves` com `rpg_access` lixo (→ 401 → balde `authfail:HMAC(client_ip)`):
  ISP local ×2 → `authfail:650ecd10c6f2b575` (mesmo pseudônimo de todo o tráfego anterior desta rede); `pg_net` do
  banco de staging ×3 (com XFF/X-Real-IP/X-Vercel-Forwarded-For forjados diferentes e sem cabeçalho) →
  `authfail:4bd80ef0598437db` (count 3). Nenhuma chave é HMAC dos valores forjados, dos IPs A do edge, do IPv6 do
  servidor (host sem AAAA ⇒ saída IPv4 NAT) nem de `unknown`. Conclusão: `client_ip` = `x-vercel-forwarded-for`
  sobrescrito pela plataforma, por origem, não spoofável. Limite: o IPv4 literal do `pg_net` não aparece no Postgres nem
  nos runtime logs da Vercel (sem campo de IP) e eco de terceiros estava fora do escopo — prova diferencial.
  [evidência](evidence/spec219_r5_second_network.json). Sem mudança de schema; nenhuma Edge Function criada.
* **SPEC-218/219.** O código da 218 está na `main`; `release/checklist.py --env staging` segue BLOQUEADO por
  `legal_pages`, `open_p0_p1`, `environments_restricted`, `ci_green` (sha sem push), árvore suja e uma leitura
  `kill_switch_store_reachable` com `OperationalError` local (passou na rodada anterior). 218 e 219 seguem `in-progress`.
* **Rollback.** Promover `rpg-ia-master-staging-eovi9utqp-…vercel.app` (pré-onda, cap de texto desligado, mesmo
  runtime DeepSeek) ou `vercel_env.py --no-text-cap` + novo deploy.

## Adendo 2026-10-18 (tarde) — chaves reais: SMTP (R-02), Turnstile (R-01), OpenAI (SPEC-236 §6.3)

Branch `staging-keys` (main `f2516b2` + tooling), sem push. Deploy de produção do staging = `f2516b2` (`/health` com o sha,
`hardened=true`, site key real em `/auth/config`).

* **R-02 `fechado`.** `auth_config.py` agora aplica SMTP de `.env.staging` (`RPG_STAGING_SMTP_*`, tudo-ou-nada) e os
  templates/assuntos de `supabase/templates` + `config.toml`; `rate_limit_email_sent` 2→10/h aceito. A chave "Full access"
  entregue é na verdade só-envio (`restricted_api_key` em `/api-keys`), então virou a senha SMTP direto e nenhuma chave
  nova foi criada. Signup → confirmação → `/auth/verify` 200; reset ×2 → `/auth/reset/confirm` 200 → login 200; e-mails
  conferidos na caixa do titular, sem variável não resolvida; usuário apagado. Modo teste: destinatário ≠ titular → Resend
  550 → GoTrue 500. [evidência](evidence/keys_r02_smtp_resend.json)
* **R-01 (segue `aceito`).** Secret real no Supabase Auth, site key real na Vercel. `siteverify` confirma o secret; widget
  renderiza no host; GoTrue/app rejeitam sem token e com token falso. O Turnstile bloqueia o Chrome automatizado, então o
  200 com token humano depende de 1 cadastro manual. Smokes trocaram login por senha (precisa de captcha) por
  `generate_link`(signup) + `POST /auth/verify` (`s192.app_login`); `/auth/reauth` usa `RPG_STAGING_SMOKE_CAPTCHA_TOKEN`
  quando exportado. `e2e_session` verde com as chaves reais. [evidência](evidence/keys_r01_turnstile.json)
* **SPEC-236 §6.3.** `scripts/staging/stt_fallback_smoke.py`: burst no Groq (45 req, 24×429) + 1 transcrição pelo app →
  Groq 429 `definitive_no_charge` → OpenAI 429 `insufficient_quota` (conta sem crédito) → 502 `speech_provider_failed`,
  custo 0, reserva `settled`, `reserved_milli=0`. [evidência](evidence/spec236_s63_stt_fallback.json)
* **Checklist** (`f2516b2`, URLs legais): 13/14; só `ci_green` (sha não enviado ao GitHub).
  [relatório](../spec197/evidence/checklist-f2516b20976a.md)
