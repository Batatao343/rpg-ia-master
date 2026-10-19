# Área 08 — Infra/config e superfícies operacionais (auditoria de segurança, 2026-10-15)

Arquivos inspecionados: `api.py` (l.58-215 CORS/middlewares, 260-345 cookies/login, 370-490 captcha/lifecycle,
593-640 log de turno, 775-830 rate limit, 1599-1650 health/metrics, 1849-1905 /data/*, 2118-2262 erros,
2585-2610 arte, 3205-3225 log, 3300-3445 SSE, 3741-3753 mount estático), `services/cron_internal.py`,
`services/auth_sessions.py`, `observability/telemetry.py`, `llm_setup.py` (get_llm, FallbackLLM, circuits),
`infrastructure/runtime.py` (validate), `infrastructure/oidc_identity.py`, `infrastructure/supabase_identity.py`,
`scripts/release/checklist.py`, `scripts/staging/auth_config.py`, `scripts/staging/vercel_env.py`,
`services/google_play_fake.py`, `services/kill_switches.py`, `scripts/admin_wallet_adjust.py`, `Procfile`,
`vercel.json`, `vercel_app.py`, `.vercelignore`, `supabase/config.toml`,
`supabase/migrations/20260820113242_dynamic_storage_bucket_rls.sql`, `20261013173632_account_lifecycle.sql` (policies de storage),
`web/vite.config.ts`, `web/dist` (listagem).

---

### INFRA-01 — `_session_boundary` converte QUALQUER `ValueError` de handler em 401 com a mensagem interna
- **Severidade:** média
- **Categoria:** Config/Infra (vazamento de erro / mascaramento de falhas / DoS de sessão)
- **Local:** `api.py:144-146` (`except (Unauthorized, ValueError) as exc: return JSONResponse({"detail": str(exc)}, 401)`), envolvendo `await call_next(request)` em `api.py:139`.
- **Evidência:** o `try` engloba `return await call_next(request)`; no Starlette, exceções não tratadas da rota (FastAPI só converte `HTTPException`/`RequestValidationError`) sobem por `call_next`. `ValueError` é a base de `pydantic.ValidationError`, `json.JSONDecodeError`, `UnicodeDecodeError`, de `float("x")`, etc. O `ValueError` de `CsrfSigner` ("RPG_SESSION_SECRET precisa ter ao menos 32 caracteres", `auth_sessions.py:44`) também cai aí.
- **Cenário de exploração / reprodução:** perfil hosted*/local/portable, usuário autenticado: qualquer entrada que faça um handler `/game/*` ou `/account/*` levantar `ValueError` sem catch (ex.: `ValueError` em lib de serialização, `int()` de campo livre do save, `ValidationError` ao construir modelo manualmente) devolve `401 {"detail": "<texto interno do erro, p.ex. campos/valores do pydantic>"}` em vez de 500 genérico. Além do vazamento (nomes de campo, trechos de input, caminhos), o front trata 401 como sessão expirada (tenta refresh/logout) — erro de lógica vira "deslogado". Se `RPG_SESSION_SECRET` estiver curto/ausente em hosted, a mensagem "RPG_SESSION_SECRET precisa ter ao menos 32 caracteres" é entregue a qualquer cliente que faça uma mutação (confirma misconfig).
- **Impacto:** vazamento de detalhe interno; falhas de servidor mascaradas como 401 (observabilidade `rpg_http_requests_total` registra 4xx, não 5xx — alertas de erro não disparam); logout espúrio.
- **Correção sugerida:** limitar o `try` ao bloco de verificação de identidade/CSRF (chamar `call_next` FORA do `try`, como em `set_current_principal` → `try/finally` já separado), capturar só `Unauthorized`; mapear `ValueError` do signer para 503 `server_misconfigured` genérico. Teste em `tests/` (middleware com rota que levanta `ValueError` → espera 500, não 401).
- **Confiança:** confirmado por leitura (comportamento de `call_next` do Starlette é padrão; não executado)
- **Já coberto por spec?** não
- **Status:** válido

### INFRA-02 — Policies de Storage permitem escrita/DELETE direta do usuário autenticado no bucket `rpg-dynamic` (bypass da quota/fila do backend)
- **Severidade:** média
- **Categoria:** DoS/custo, Pagamentos/Integridade (arte paga)
- **Local:** `supabase/migrations/20260820113242_dynamic_storage_bucket_rls.sql:18-52` (4 policies `to authenticated`), reforçadas em `20261013173632_account_lifecycle.sql:48-67`.
- **Evidência:** `rpg_dynamic_insert_own ... with check (bucket_id='rpg-dynamic' and foldername[1]='users' and foldername[2]=auth.uid())`; comentário diz "defesa em profundidade caso uploads assinados sejam habilitados no futuro", mas as policies estão ATIVAS hoje. Bucket limita 20 MiB/arquivo e mime `image/webp`; não há limite de número de objetos nem de bytes por usuário.
- **Cenário de exploração / reprodução:** usuário legítimo faz login direto no GoTrue (URL + chave publishable são públicos no front) e obtém um JWT próprio; chama a Storage API (`POST /storage/v1/object/rpg-dynamic/users/<uid>/x.webp`) em loop com webp de ~20 MiB. Perfil hosted-supabase. Também pode `DELETE`/`UPDATE` os objetos de arte já pagos (apagar retrato comprado → jogo mostra placeholder; ou sobrescrever o asset com outro webp, que o backend serve depois como "geração ready" via signed URL).
- **Impacto:** consumo ilimitado de storage na cota do projeto (custo/cota Free 1 GiB → indisponibilidade para todos); adulteração/perda de ativos pagos do próprio usuário; arquivos arbitrários (webp malformado/gigante pixel-bomb) entram no mesmo prefixo que o backend pode vir a assinar/servir.
- **Correção sugerida:** como o backend usa service role, remover as 4 policies (RLS ligado sem policy = deny para `authenticated`) ou deixar só `select`; se mantiver insert, adicionar trigger/contagem por owner (`app.guard_storage_account_write` já existe — estendê-lo para quota de bytes/objetos por `users/<uid>`). Teste pgTAP em `supabase/tests` (authenticated não insere/atualiza/apaga em `rpg-dynamic`).
- **Confiança:** provável (policies lidas; comportamento Storage-RLS padrão do Supabase; não executado contra remoto)
- **Já coberto por spec?** não (cruzar com área de authz/RLS se já houver achado de storage)
- **Status:** válido

### INFRA-03 — `RPG_RATE_LIMIT=0` desliga o rate limit em TODOS os perfis, inclusive hosted; sem guard em `RuntimeConfig.validate` nem em `FORBIDDEN_IN_PROD`
- **Severidade:** baixa
- **Categoria:** Rate limit / Config
- **Local:** `api.py:782-790` (`if limit > 0 and ...`), `scripts/release/checklist.py:39`.
- **Evidência:** comentário "0 desliga (suíte/smoke)"; `_rate_limit_max()` aceita qualquer inteiro (negativo também desliga).
- **Cenário:** env de produção/staging com `RPG_RATE_LIMIT=0` herdado de smoke → sem nenhum limite em `/game/action`, `/game/new`, prologue (custo LLM). Só erro de operação, não explorável por atacante.
- **Impacto:** perda total do limitador de custo/abuso.
- **Correção sugerida:** em perfis `hosted*` ignorar valores `<=0` (clamp mínimo) e incluir `RPG_RATE_LIMIT` em checagem do `checklist.py` (valor numérico entre 1..N em production). Teste no checklist/runtime.
- **Confiança:** confirmado por leitura
- **Já coberto por spec?** não (ver SESS-02/03 para o limite em si)
- **Status:** válido

### INFRA-04 — Flags que enfraquecem segurança/integridade sem bloqueio em código hosted* nem em `FORBIDDEN_IN_PROD`
- **Severidade:** baixa
- **Categoria:** Config/Infra
- **Local:** `scripts/release/checklist.py:39` (`FORBIDDEN_IN_PROD = ("RPG_FORCE_MOCK", "RPG_GOOGLE_PLAY_FAKE")`); `llm_setup.py:1088-1112`; `api.py:262,346,542`; `services/account_security.py:42`.
- **Evidência / lista:** apenas `RPG_GOOGLE_PLAY_FAKE` tem bloqueio em código (`google_play_fake.fake_allowed`: só `local`, nunca `hosted`/`VERCEL`). Não bloqueadas em código nem no checklist:
  - `RPG_FORCE_MOCK` — em hosted vira MockLLM (narração fictícia cobrando Estilhas; só o checklist de release a proíbe, `get_llm` não olha o perfil).
  - `RPG_RATE_LIMIT` (INFRA-03), `RPG_COOKIE_SECURE=0` default (SESS-06), `RPG_AUTH_CAPTCHA_REQUIRED=0` default (SESS-06/AUTHZ-07), `RPG_AUTH_EMAIL_CONFIRMATION_REQUIRED` (default 1 em hosted, mas `=0` aceito), `RPG_AUTH_CAPTCHA_MODE`.
  - `RPG_KILL_SWITCHES_OFF` (override de emergência por env; documentar como break-glass, ver PAG-04), `RPG_KILL_SWITCH_FAIL_CLOSED`, `RPG_DAILY_SPEND_CAP_BRL` (ausente = sem teto?; está só em REQUIRED_ENV do checklist de *production*, não de staging).
  - `LLM_PROVIDER`, `RPG_ROUTES` (JSON arbitrário de rota LLM), `RPG_NO_MOCK`, `RPG_JEV_ROUTER_MODE` (`primary` exige `RPG_JEV_ROUTER_PRIMARY_APPROVED` — ok), `RPG_ADMIN_ALLOW_PROFILE=1` (script admin permite ajustar carteira fora de hosted-supabase; é CLI local).
  O `checklist.py` verifica só presença de NOMES de env, não valores (ex.: `RPG_COOKIE_SECURE=0` e `RPG_CORS_ORIGINS=*` passam).
- **Cenário:** erro de configuração de operador (não atacante externo).
- **Correção sugerida:** em `RuntimeConfig.validate` (hosted*): exigir `RPG_COOKIE_SECURE=1`, recusar `RPG_FORCE_MOCK`/`RPG_NO_MOCK`/`LLM_PROVIDER` não aprovados, `RPG_RATE_LIMIT>=1`, `RPG_AUTH_EMAIL_CONFIRMATION_REQUIRED=1`; no checklist validar VALORES (não só nomes) e ampliar `FORBIDDEN_IN_PROD` com `RPG_ADMIN_ALLOW_PROFILE`, `RPG_KILL_SWITCHES_OFF`. Teste em `tests/` do checklist/runtime.
- **Confiança:** confirmado por leitura
- **Já coberto por spec?** parcialmente (SPEC-197/198 checklist done; valores não cobertos)
- **Status:** válido

### INFRA-05 — `RPG_CORS_ORIGINS` sem validação (aceita `*`, `http://`, vazio); `*` + `allow_credentials=True` reflete qualquer Origin
- **Severidade:** baixa
- **Categoria:** CORS/Config
- **Local:** `api.py:68-80`; consumo em `_session_boundary` (`allowed_origins=set(_CORS_ORIGINS)`, `api.py:131`).
- **Evidência:** lista CSV crua; `allow_methods=["*"]`, `allow_headers=["*"]`, `allow_credentials=True`; sem `allow_origin_regex`; `expose_headers` não definido. Starlette, com `"*"` + credenciais, devolve `Access-Control-Allow-Origin` = Origin do pedido e `Allow-Credentials: true`. Comparação CSRF por `scheme://netloc` exato (case/trailing slash em `RPG_CORS_ORIGINS` quebram o match — falha segura, ver SESS-06).
- **Cenário:** operador define `RPG_CORS_ORIGINS=*` "para destravar o front" → qualquer site lê respostas credenciadas de GET. Mitigado por cookies `SameSite=Strict` (sem cookies cross-site) e porque `*` não casa no set do CSRF (mutações seguem bloqueadas) — logo severidade baixa/hipótese. Default `localhost:8000,5173` mantém origens de dev em produção se a env faltar (mutações recusadas, CORS dos GET liberado só para localhost).
- **Correção sugerida:** validar na subida hosted*: cada origem `https://host[:port]` sem path, sem `*`, sem localhost; `allow_headers` explícito (`content-type, x-csrf-token, x-request-id, x-rpg-client`) e `allow_methods` explícito. Teste em `tests/` do app (env `*` → erro de startup).
- **Confiança:** provável
- **Já coberto por spec?** parcial (SESS-06/AUTHZ-07 tratam a ausência da env)
- **Status:** válido

### INFRA-06 — Swagger/ReDoc/openapi.json públicos listam rotas internas (cron, billing, admin-like) e schemas completos; sem CSP nas páginas de docs
- **Severidade:** baixa
- **Categoria:** Config/Infra (superfície exposta) — aprofunda AUTHZ-10
- **Local:** `api.py:59-63` (`FastAPI(...)` sem `docs_url/redoc_url/openapi_url=None`), `api.py:161,202` (`_DOCS_PATHS` ficam sem CSP), `services/cron_internal.py:20` (router `/internal/cron/*`, `tags=["internal"]`, sem `include_in_schema=False`); só `/metrics` tem `include_in_schema=False` (`api.py:1608`).
- **Evidência:** `/docs` é servido pelo middleware principal sem login; `_correlation_boundary` NÃO aplica `Content-Security-Policy` a `/docs`, `/redoc`, `/openapi.json` para permitir o CDN do Swagger (jsdelivr) — a página roda sem CSP (mantém `X-Frame-Options: DENY`).
- **Cenário:** qualquer pessoa baixa `/openapi.json` e obtém: `/internal/cron/{jobs,account-deletions,operations,reconciliation,finops}` (existência + que usam Bearer), todos os modelos Pydantic (campos de pagamento: `purchase_token`, `product_id`, `quote_id`…), parâmetros de admin-like. Não vaza segredos, mas reduz custo de reconhecimento; a página `/docs` sem CSP é superfície XSS adicional somente se o CDN for comprometido (risco supply-chain baixo).
- **Impacto:** reconhecimento facilitado.
- **Correção sugerida:** `FastAPI(docs_url=None, redoc_url=None, openapi_url=None)` quando `RPG_RUNTIME_PROFILE` for hosted*/`VERCEL`; `include_in_schema=False` no router de cron; remover `_DOCS_PATHS` (e a exceção de CSP) quando docs estiverem off. Teste: GET `/docs` e `/openapi.json` → 404 em hosted.
- **Confiança:** confirmado por leitura
- **Já coberto por spec?** não (AUTHZ-10 só aponta a exposição)
- **Status:** válido

### INFRA-07 — Auth remoto de staging aplicado por `auth_config.py` não fixa política de senha/refresh/JWT; relies em defaults do Supabase (≠ `config.toml` local)
- **Severidade:** baixa
- **Categoria:** Config/Infra (Supabase Auth)
- **Local:** `scripts/staging/auth_config.py:30-52` (campos aplicados: `mailer_autoconfirm=False`, captcha Turnstile, `site_url`, `uri_allow_list`, 5 `rate_limit_*`) vs `supabase/config.toml` (`minimum_password_length=8`, `jwt_expiry=3600`, `enable_confirmations=true`, `enable_signup=true`).
- **Evidência:** o script não define `password_min_length`, `jwt_exp`, `refresh_token_rotation_enabled`, `security_refresh_token_reuse_interval`, `password_required_characters`, `security_update_password_require_reauthentication`, `disable_signup`. `config.toml` não tem `refresh_token_rotation`/`reuse_interval` nem `[auth.password_requirements]`. O app impõe `min_length=8` em `AuthRequest` (`api.py:152-156`), mas o GoTrue remoto pode ser chamado direto com a chave publishable.
- **Cenário:** atacante/usuário cria conta direto em `https://<ref>.supabase.co/auth/v1/signup` com senha curta (default Supabase = 6) e contorna rate limits do app (`auth_limit`) — ainda sob captcha GoTrue e rate limits `rate_limit_*`. Sem confirmar `refresh_token_rotation_enabled` (default true em projetos novos), o replay de refresh depende do default.
- **Correção sugerida:** acrescentar ao `desired_config` e ao diff: `password_min_length>=10`, `refresh_token_rotation_enabled=true`, `security_refresh_token_reuse_interval=10`, `jwt_exp=3600`, `security_update_password_require_reauthentication=true`; espelhar em `config.toml`. `uri_allow_list` é montada de `RPG_STAGING_REDIRECT_URLS` (default = site) — sem wildcard no repo (OK); validar no script que não contém `*`/`http://` fora de localhost. Teste: `tests` do script `auth_config` (diff desejado vs remoto simulado).
- **Confiança:** provável
- **Já coberto por spec?** parcial (SPEC-191/190 `done` configuram captcha/rate limits)
- **Status:** válido

### INFRA-08 — Mensagens de erro de auth/CSRF distinguem estados internos (info)
- **Severidade:** info
- **Categoria:** Config/Infra
- **Local:** `api.py:146` + `services/auth_sessions.py:69-76,90-93` + `supabase_identity.py:127-170`.
- **Evidência:** 401 distingue "Origin ausente" / "Origin não permitido" / "CSRF inválido" / "sessão revogada" / "account_delete_pending" / "sessão inválida". Falhas CSRF/Origin deveriam ser 403, não 401.
- **Impacto:** nenhum ganho material (só o titular da sessão vê); 401 para CSRF dispara fluxo de refresh/logout no cliente.
- **Correção sugerida:** 403 `csrf_failed` genérico para Origin/CSRF; manter detalhes só no log. (Cruza com INFRA-01.)
- **Confiança:** confirmado por leitura
- **Já coberto por spec?** não
- **Status:** válido (baixa prioridade)

### INFRA-09 — `pseudonym()` com chave default pública (`local-telemetry-only`)
- Já registrado como **PRIV-08** (`observability/telemetry.py:64-66`); aqui apenas confirmado: o mesmo `pseudonym()` é usado como chave do rate limit por IP (`api.py:807`) — lá é irrelevante para segurança (só agrupamento). Nenhum achado novo.
- **Status:** descartado como duplicata (ver PRIV-08).

---

## Verificado e OK
- **Erros 500 genéricos:** `api.py:2838,3312,3441` devolvem texto fixo ("Erro interno ao…"); SSE `exc` não envia stack nem `str(exc)`; handlers de criação usam `type(exc).__name__` só no registro da operação (`api.py:1870`). Nenhum `FastAPI(debug=True)`; sem `uvicorn --reload` nem `RPG_DEBUG` no código; `Procfile` e `vercel_app.py` sem `--reload`.
- **Erros de provider LLM:** `RoutedLLM` esgotado devolve `AIMessage(content="")` (`llm_setup.py:863,1011`); `FallbackLLM` só carrega strings de config ("Nenhuma key…", "Provider desconhecido") — não chega ao jogador com nome de exceção/chave. `_OPEN_CIRCUITS` guarda `str(exc)[:500]` só em memória/telemetria (não no GameResponse).
- **Logs:** `rpg.turn` (`api.py:3206-3224`) loga `game_id_ref` pseudonimizado + correlação + rota/latência/erro/custo via `safe_json` (redact de e-mail/Bearer/signed URL); sem texto do jogador; handler próprio no stderr, `propagate=False`; nenhum `logging.basicConfig`/DEBUG de httpx (logger root sem handler → `httpx` não emite URLs/headers). Cron loga só `error_type` (`cron_internal.py:79`). Vercel function logs não são públicos.
- **`/health`:** só `status`, `engine`, `git_sha` (baixo risco). `/data/options|onboarding|combat-simulator|map` são catálogos estáticos de `data/*.json` (exceto SPEC-210 para mapa).
- **Cron `/internal/cron/*`:** `authorize` fail-closed (503 sem `RPG_CRON_SECRET` ≥32), `hmac.compare_digest`, 500 genérico `cron_task_failed`, orçamento 50 s (`min(wanted, max-5)`), alertas de falhas consecutivas.
- **Estáticos:** `StaticFiles(directory=web/dist|frontend, html=True)` montado em `/` por último (rotas de API têm precedência); `web/dist` sem sourcemaps (`vite.config.ts` sem `sourcemap`; 0 `.map`); `.vercelignore` exclui `.env*`, `saves`, `.git`; não serve a raiz do repo, `/.env`, `/.git`, `/saves`, `data/runtime` não são alcançáveis; `html=True` não gera fallback SPA para paths desconhecidos (404). Fallback `frontend/` só na ausência do dist (legado, inofensivo).
- **Bucket `rpg-dynamic`:** `public=false`, 20 MiB, mime `image/webp`, policies amarradas a `users/<auth.uid()>` e a sessão ativa (`rpg_current_session_active`); trigger de fence em escrita pós-exclusão de conta (ressalva: INFRA-02).
- **Google Play fake:** só `local` e nunca `hosted`/`VERCEL` (`google_play_fake.py:21-25`).
- **Cookies:** `HttpOnly` + `SameSite=Strict`, path restrito do cookie de deleção (`api.py:542`); CSRF double-submit assinado com `compare_digest` e checagem de Origin.
- **Headers de segurança:** `nosniff`, `Referrer-Policy`, `Permissions-Policy` (microfone=self), `X-Frame-Options: DENY`, CSP restritiva no SPA (CSP/HSTS gaps em SESS-08/09).
- **Timeouts:** `vercel.json` maxDuration 300; `LLM_TIMEOUT_SECONDS` configurável; pool/connect timeout validados em `RuntimeConfig.validate` (`RPG_DB_POOL_*` limites seguros; `RPG_DB_CONNECT_TIMEOUT_SECONDS` 1..30). Concorrência de turnos por jogo protegida por lease Postgres e rate limit por IP (limites globais de custo em SESS-02/03, PAG-04); nada novo.
- **Uvicorn/Procfile:** `Procfile` roda `--host 0.0.0.0` sem `--proxy-headers`/`--forwarded-allow-ips` (ver AUTHZ-01 e SESS-02); não há `--workers`; Railway/Procfile fora da produção atual (SPEC-104 draft). Scripts `start_local_api.py`/`dev_stack.py` locais, não referenciados por `vercel.json`.
- **python-multipart/STT:** versão e uso de `UploadFile` ficam para a área 07 (supply chain) / injeção (INJ).
