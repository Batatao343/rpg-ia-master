# SPEC-191 — evidência do staging Supabase remoto

Ferramentas em `scripts/staging/` (rodar da raiz: `uv run python -m scripts.staging.<modulo> ...`).
Toda execução exige `--confirm-staging <ref>` igual a `SUPABASE_PROJECT_REF` e recusa refs listados em
`RPG_PROTECTED_PROJECT_REFS` (lista separada por vírgula). Saídas são JSON sem segredos (tokens/chaves/DSN
mascarados; e-mails viram `email:<hash>`), por padrão em `docs/spec191/evidence/<nome>.json` (`--out` muda).

## Ordem de execução

1. `auth_config plan` → revisar diff → `auth_config apply` (e-mail confirmado, Turnstile nativo, rate limits).
2. `migrations status` → (`repair --apply` se as versões foram aplicadas por MCP com timestamp do servidor)
   → `migrations push --apply`.
3. `smoke_ab` (RLS, Storage privado/signed URL, pgvector, wallet, CAPTCHA nativo, pooler).
4. `backup_restore export <dir>` → `restore <dir> --target-dsn <local> --objects-dir <dir2> --confirm-disposable`
   → `verify` (mesmos argumentos).
5. Security/Performance Advisors (MCP) e custos/config registrados manualmente em `evidence/`.

```
uv run python -m scripts.staging.auth_config plan --confirm-staging $REF [--turnstile-test-keys]
uv run python -m scripts.staging.migrations status|repair|push --confirm-staging $REF [--apply]
uv run python -m scripts.staging.smoke_ab --confirm-staging $REF [--only rls storage ...]
uv run python -m scripts.staging.backup_restore export --confirm-staging $REF <dir>
```

## Variáveis de ambiente (nomes apenas)

`SUPABASE_PROJECT_REF`, `RPG_PROTECTED_PROJECT_REFS`, `SUPABASE_ACCESS_TOKEN`, `SUPABASE_URL`,
`SUPABASE_SERVICE_ROLE_KEY`, `SUPABASE_PUBLISHABLE_KEY` (ou `SUPABASE_ANON_KEY`), `DATABASE_URL` (transaction
pooler 6543), `RPG_STAGING_DB_URL` (direto/session, para migrations e pg_dump), `RPG_STAGING_SITE_URL`,
`RPG_STAGING_REDIRECT_URLS`, `RPG_STAGING_TURNSTILE_SECRET`, `RPG_STAGING_SMOKE_CAPTCHA_TOKEN` (opcional:
token Turnstile para o password grant do smoke quando CAPTCHA está ativo).

## Turnstile — chaves de teste

`--turnstile-test-keys` usa o secret de teste documentado pela Cloudflare (always-pass). Serve só para
staging descartável: com ele o CAPTCHA aceita qualquer token, então a rejeição "sem token" é provada, mas
a validação de token real fica pendente até haver chaves de produção do widget.

## Layout da evidência

`evidence/auth_config_{plan,apply}.json`, `migrations_{status,repair,push}.json`, `smoke_ab.json`,
`backup_{export,restore,verify}.json`. Sem segredos; IDs de usuários sintéticos não são persistidos.

## Gate backup -> restore e migrations do zero (executado)

Dados sintéticos: `synthetic_data seed|cleanup` (2 usuários `spec191-backup-*@example.invalid`, 1 jogo,
1 documento pgvector e 2 objetos webp cada; manifesto sem segredos em `.tmp/spec191/`, gitignored).

```
uv run python -m scripts.staging.synthetic_data seed --confirm-staging $REF
uv run python -m scripts.staging.backup_restore export --confirm-staging $REF .tmp/spec191/backup
npx supabase db reset                      # lab local: replay de supabase/migrations do zero (18 migrations, ~31 s)
npx supabase test db                       # pgTAP valoria_rls_test.sql: 14/14 PASS
# LOCAL_SUPABASE_URL / LOCAL_SERVICE_ROLE_KEY vêm de `npx supabase status -o env` (nunca impressos)
uv run python -m scripts.staging.backup_restore restore .tmp/spec191/backup --target-dsn <local-lab-dsn> --confirm-disposable
uv run python -m scripts.staging.backup_restore verify  .tmp/spec191/backup --target-dsn <idem> --confirm-disposable
uv run python -m scripts.staging.synthetic_data cleanup --confirm-staging $REF   # 0 usuários/jogos/objetos restantes
```

Resultado: contagens de linhas das 27 tabelas `app.*` e sha256 dos 4 objetos (baixados da Storage API local) batem
com o export. RTO medido: reset do zero ~31 s + restore 2,6 s + verify 1,0 s (~35 s). Restore é *data-only*
sobre o schema recriado pelas migrations (prova migrations-do-zero + dados); `pg_restore` precisa de superuser
(`supabase_admin`) por `--disable-triggers`; `app.embedding_profiles` (seed de migration) é limpo antes; linhas
`storage.objects` do dump são descartadas e recriadas pelo upload (bytes) via Storage API.
Quirk do lab: storage-api v1.69.11 devolve 42P10 em qualquer upload (ON CONFLICT (name,bucket_id) sem índice
único após a migration 72 do storage); a prova usou um índice único só do lab, removido pelo reset final.
Evidência: `evidence/{backup_export,restore_verify,db_reset_from_zero,pgtap,synthetic_cleanup}.json`.

## Revisão independente — correções e decisões (2026-10-15)

### (a) Desvio R2 — projeto reutilizado
Em vez de criar um projeto novo, reutilizou-se o projeto existente do usuário `rpg-ia-master`
(`uzeagzcyvxzrpjgrhaql`, sa-east-1) como staging dedicado. Foi limpo com aprovação explícita do usuário em
2026-10-15; não existe produção, e as tabelas legadas foram removidas. Staging tem **17 migrations**; a
`20261015130000_google_play_purchases` (SPEC-194) está só no repo e fica fora da comparação de schema.

### Paridade de schema
`scripts/staging/schema_diff.py` compara um snapshot normalizado (tabelas/colunas, constraints, índices,
policies app+public+storage, funções com definer/search_path/md5 do corpo sem CR, grants de tabelas e funções,
triggers) do staging contra o lab local recém-resetado. Resultado em `evidence/schema_diff.json`: **diff vazio**
(348 colunas, 229 constraints, 79 índices, 37 policies, 15 funções, 32 triggers). Excluídos explicitamente:
objetos `google_play*`. Normalizações: `search_path=''` na sessão (deparse independente do role) e remoção de CR
(migrations aplicadas no lab a partir de arquivos CRLF no Windows).

### Pooler (transaction, 6543)
Reexecutado 3 vezes com 50 conexões sequenciais + 10 concorrentes, separando tempo de conexão e de query
e usando `pgconn.ssl_in_use` (não mais substring do DSN). Evidência `evidence/pooler_run{1,2,3}.json` (antigas) e `pooler_run{7,8,9}.json`.

| run | seq p50/p95/max (ms) | seq connect p95 / query p95 (ms) | conc10 p50/p95 (ms) | erros |
|---|---|---|---|---|
| 1 | 86.33 / 107.83 / 277.73 | 97.89 / 11.19 | 130.24 / 142.4 | 0 |
| 2 | 87.93 / 116.5 / 146.96 | 106.14 / 11.07 | 123.91 / 128.26 | 0 |
| 3 | 84.15 / 94.46 / 113.12 | 81.54 / 10.68 | 120.81 / 128.01 | 0 |

**Achado honesto (diagnóstico de 2026-10-15; substitui a alegação anterior de estabilidade).** O host
`aws-1-sa-east-1.pooler.supabase.com` resolve para 3 IPs. O TCP conecta em todos, mas no IP `54.232.77.43` o
handshake Postgres/TLS **trava de forma intermitente** (`ConnectionTimeout`); os outros dois IPs não travaram.
Com `connect_timeout=15` o psycopg espera 15 s e faz failover para o próximo endereço: daí os outliers de ~15 s em
`smoke_ab.json`/`pooler_run4.json` (as 3 execuções limpas anteriores foram sorte de roteamento DNS, não prova).
Diagnóstico por IP (`evidence/pooler_per_ip.json`, `smoke_ab --per-ip`, 25 conexões/IP, connect_timeout 5 s):

| IP | timeouts / 25 | taxa | p95 das conexões ok (ms) |
|---|---|---|---|
| 18.228.163.245 | 0 | 0% | 109.55 |
| 52.67.188.92 | 0 | 0% | 85.45 |
| 54.232.77.43 | 3 | 12% | 106.07 |

A taxa do IP ruim varia entre sondagens (12% aqui, maior numa sondagem prévia do orquestrador): é intermitente.
É um problema do lado da plataforma (Supavisor), não do app. **Mitigação no runtime**: `RPG_DB_CONNECT_TIMEOUT_SECONDS`
(default 3 s nos perfis `hosted`/`hosted-supabase`, 5 s nos demais; faixa 1..30) + failover nativo do psycopg para o
próximo IP + `RPG_DB_POOL_TIMEOUT_SECONDS` default 10 s no `hosted-supabase` (validado: deve ser > 2x o connect
timeout, para que um failover caiba antes do `PoolTimeout`). **Limite residual de pior caso**: uma conexão fria que
caia no IP ruim custa ~connect_timeout (3 s) + conexão normal (~0,1 s), ou seja ~3,2 s; dois IPs ruins seguidos
~6,2 s (por isso o critério de max < 2x timeout + 1 s). Conexões do pool persistente não pagam isso no caminho quente.

Critério do smoke atualizado (`check_pooler`, connect_timeout 3 s, registra peer `c.info.hostaddr`, conexões lentas
>1000 ms e failovers): zero erros **e** p95 total < 1000 ms **e** max total < 2x timeout + 1 s. Resultados (60
conexões cada):

| run | erros | p50 / p95 / max (ms) | lentas / failovers | peers | ok |
|---|---|---|---|---|---|
| 7 | 0 | 87.34 / 3160.41 / 3178.39 | 8 / 8 | 3 IPs (12 no IP ruim) | **não** (p95) |
| 8 | 0 | 77.16 / 104.51 / 105.94 | 0 / 0 | 1 IP | sim |
| 9 | 0 | 77.54 / 113.68 / 115.76 | 0 / 0 | 1 IP | sim |
| smoke final | 0 | p95 94.01 / max 113.19 | 0 / 0 | 2 IPs | sim |

A run 7 reproduziu o problema (8/60 failovers, todos limitados a ~3,2 s: a mitigação funciona, sem erro). O critério
falha de propósito nessa condição: o pooler **não** é declarado estável, e sim tolerável com latência de cauda
limitada. Recomendações: abrir chamado no suporte Supabase citando o IP `54.232.77.43` (sa-east-1, handshake TLS
intermitente) e reexecutar `--per-ip` periodicamente; se persistir, avaliar conexão direta/IPv4 add-on ou outra
região. No runtime Vercel gru1 o p50 warm medido é ~33 ms (`docs/spec192/evidence/smoke.json`).

### Wallet A/B
O smoke agora credita uma compra real a A via `PostgresWallet.credit_verified_purchase` e confirma que A vê
exatamente 1 linha em `rpg_wallet_balance` (311 milli) e 1 em `rpg_wallet_history`, B vê 0 em ambas, anon recebe 401.
`wallet_entries`/`wallet_accounts` são append-only/com FK; **não há limpeza possível**. Linhas sintéticas retidas por
execução: 1 conta + 1 entrada (owner = usuário sintético já apagado); `pricing_versions`/`purchase_skus`
`spec191-smoke*` são idempotentes (1 linha cada). Retenção atual: 1 execução com sucesso do wallet.

### (b) Security Advisor (estado final, `evidence/advisors.json`)
- 3x WARN `authenticated_security_definer_function_executable` (`rpg_current_session_active`, `rpg_wallet_balance`,
  `rpg_wallet_history`): intencionais; só `authenticated`, filtradas por `auth.uid()` + sessão viva, `search_path=''`,
  revogadas de public/anon/rpg_api.
- 6x INFO `rls_enabled_no_policy` (`stripe_events`, `wallet_accounts|entries|reservations|settled_usage|attempt_tickets`):
  tabelas só de backend; deny-all por desenho; o backend usa o pool privilegiado.

### (c) Auth / R9
- Rejeição sem CAPTCHA provada (`auth_captcha` no smoke; `evidence/auth_burst_recover.json`: 15 chamadas a
  `/auth/v1/recover` sem token, todas HTTP 400 captcha; **nenhum 429** e nenhum e-mail enviado).
- O secret Turnstile da Cloudflare é de teste (always-pass): **validação de token real NÃO provada**. Gate de release:
  chaves Turnstile reais (SPEC-197). O caminho "token válido repassado pelo proxy" é exercitado no e2e da SPEC-192
  (`docs/spec192/evidence/e2e_session.json`).
- IP de egress compartilhado: o backend chama o GoTrue a partir de IPs de egress da Vercel, então limites por IP
  nativos são compartilhados entre usuários. `Sb-Forwarded-For` não é enviado (exige chave `sb_secret` + opt-in).
  Decisão: manter limiter app-level por usuário/IP no proxy (rate limiter em Postgres) + limites nativos como teto
  global. Valores aplicados: `rate_limit_verify=60`, `rate_limit_token_refresh=150`, `rate_limit_otp=30`,
  `rate_limit_anonymous_users=10`. O teto nativo por IP não é mensurável aqui: o CAPTCHA rejeita antes da contagem
  (15 chamadas sem 429) e sondar além disso exigiria enviar e-mails reais.

### (d) `rate_limit_email_sent`
Não aplicado (GoTrue exige SMTP customizado). Gate de release (R6/SPEC-197).

### (e) Custo/config
Plano Free, sa-east-1, pooler `aws-1-sa-east-1` (transaction 6543), US$ 0. `evidence/cost_config.json`.

### (f) Migration 20261015120000
Mudança de comportamento: as views `wallet_balance_view`/`wallet_history_view` foram removidas (sem consumidores no
app) e substituídas por funções definer; `rpg_wallet_history` tem limite padrão 50, teto 200, ordem `created_at desc`.

### (g) Evidências manuais
`db_reset_from_zero.json`, `pgtap.json`, `restore_verify.json` têm `"source": "manual transcription of command output"`.

### (h) Limites do restore
O conjunto sintético não contém linhas de wallet/pagamento; os metadados de owner de `storage.objects` não são
preservados no re-upload (o objeto é recriado pela API de Storage local).

### (i) Raio de explosão
A Vercel recebe o `DATABASE_URL` privilegiado do pooler (role `postgres`); o RLS é defesa em profundidade via
`rpg_api`. Follow-up: role de login dedicada com menor privilégio.

### Guardas
`synthetic_data`, `backup_restore export`, `smoke_ab` e `schema_diff` exigem que cada alvo aponte de fato para o ref
(`common.assert_ref_in`, agora **estrito**: hostname `<ref>.supabase.co`/`*.<ref>.supabase.co` ou usuário de tenant
`<role>.<ref>`; substring em path/query/outro domínio é recusada, com testes). Senha de DSN nunca vai em argv:
`pg_dump`/`pg_restore` recebem `PGPASSWORD` por env.

### Follow-ups (2026-10-15)
- **Leitura de volta da config de Auth**: `auth_config plan --turnstile-test-keys` reexecutado
  (`evidence/auth_config_readback.json`): o diff contém apenas `rate_limit_email_sent` (2 -> 10, depende de SMTP
  customizado, não aplicável no Free) e o segredo write-only do CAPTCHA (`<write-only>`; GoTrue não devolve o valor).
  Nenhuma outra deriva.
- **Escopo do `schema_diff`**: agora também compara config de buckets (`storage.buckets`: public, limite, mimes) e
  versões de extensões. Buckets: iguais. Extensões: diferença só informativa e não bloqueante (plataforma: `pg_cron`,
  `pg_graphql`, `pg_net` só no remoto; `vector` 0.8.0 remoto vs 0.8.2 local). Continua sem diff de config de Auth
  (coberta por `auth_config`).
- **Backups**: o plano Free não tem backups gerenciados nem PITR; o `backup_restore` (export lógico + restore
  descartável) é o único mecanismo. Gate de release na SPEC-197, junto de SMTP customizado, chaves reais do
  Turnstile e role de banco com menor privilégio.
