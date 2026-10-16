# Auditoria de seguranca — AREA 01: AuthN/AuthZ e isolamento multi-tenant

- **Data:** 2026-10-15 · **Modo:** somente leitura · **Auditor:** subagente seguranca 01
- **Arquivos inspecionados:** `api.py` (l.60-600, 745-835, 1597-1700, 1730-1850, 1849-2310, 2308-2650, 2936-3090, 3319-3753),
  `services/auth_sessions.py`, `services/account_security.py`, `services/cron_internal.py`, `services/image_quotes.py` (greps),
  `services/dynamic_art.py` (get/set_quality), `services/stripe_checkout.py` (verify_event, settings),
  `services/chronicle_repository.py`, `services/asset_pipeline.py`, `infrastructure/runtime.py`, `infrastructure/request_context.py`,
  `infrastructure/supabase_identity.py`, `infrastructure/oidc_identity.py`, `infrastructure/supabase_blob.py`,
  `infrastructure/postgres.py`, `infrastructure/postgres_turns.py`, `infrastructure/pgvector_memory.py`,
  `infrastructure/account_read_model.py` / `wallet.py` / `postgres_jobs.py` (greps de WHERE/owner), `persistence.py` (ramos DB),
  `vercel_app.py`, `vercel.json`, `Procfile`, `scripts/staging/vercel_env.py`, `scripts/start_local_api.py`,
  `supabase/config.toml`, `supabase/migrations/*.sql` (todas, por grep + leitura de auth_rls, lifecycle, wallet definer),
  `supabase/tests/valoria_rls_test.sql` (cabecalho), `docs/spec197/risk-register.md` (grep R-05).

Resumo: 0 critica · 1 alta · 5 media · 3 baixa · 5 info. Isolamento por `owner_id` em Python esta consistente em TODAS as rotas
`/game/*` e `/account/*` dos perfis DB (ver "Verificado e OK"). Os achados sao de configuracao/defaults, defesa em profundidade e abuso.

---

### AUTHZ-01 — Perfil `legacy` (sem login) e o default; `Procfile` sobe 0.0.0.0 sem exigir perfil e o guard de loopback e cego
- **Severidade:** alta
- **Categoria:** Config/Infra · AuthN (fail-open por default)
- **Local:** `Procfile:1`; `api.py:87-88` e `api.py:94`; `infrastructure/runtime.py:186,236-250,220`; `infrastructure/runtime.py:462`; `vercel.json` (sem env)
- **Evidencia:**
  ```
  Procfile:        web: uvicorn api:app --host 0.0.0.0 --port $PORT
  api.py:88        return os.getenv("RPG_RUNTIME_PROFILE", "legacy").strip().lower() != "legacy"
  api.py:94        if not _database_profile() or not request.url.path.startswith(("/game", "/account")): return await call_next(request)
  runtime.py:220   bind_host=values.get("RPG_BIND_HOST", "127.0.0.1")   # valor DECLARADO, nao o bind real
  runtime.py:249   if not _loopback_host(self.bind_host): raise ValueError("perfil legacy so pode escutar em loopback")
  ```
  O guard "legacy so em loopback" valida apenas a variavel `RPG_BIND_HOST` (default `127.0.0.1`), nunca o `--host` real do uvicorn,
  e `RuntimeConfig.from_env()`/`validate()` so roda lazy em `get_runtime()`, que no caminho legacy da API quase nunca e chamado
  (middleware nem o consulta). Resultado: o `Procfile` (alvo Railway citado em ESTADO_ATUAL/SPEC-104) sobe em `0.0.0.0` e, se
  `RPG_RUNTIME_PROFILE` nao estiver setado no painel, a API inteira roda em `legacy`: nenhuma autenticacao, `/game/*` aberto,
  principal unico local, saves em disco compartilhados entre todos os visitantes.
- **Cenario de exploracao / reproducao:** deploy via Procfile (Railway/Heroku-like) esquecendo `RPG_RUNTIME_PROFILE` (ou perfil
  de preview/ambiente novo sem as env). `curl https://host/game/saves` -> 200 com saves de todos; `POST /game/action` gasta
  chaves LLM do operador (DeepSeek/Groq) sem login; `GET /game/chronicle/export` le qualquer campanha. Perfil afetado: legacy exposto.
  (Vercel esta protegido porque `scripts/staging/vercel_env.py` seta o perfil; mas nada no codigo impede o esquecimento.)
- **Impacto:** acesso total anonimo a dados de jogo + abuso de custo de LLM; ao migrar para Railway o risco e real.
- **Correcao sugerida:**
  1. Em `api.py` (import time): se `RPG_RUNTIME_PROFILE` ausente/`legacy` E houver marcador de plataforma (`PORT`, `VERCEL`,
     `RAILWAY_ENVIRONMENT`, `RENDER`, `K_SERVICE`) E `RPG_ALLOW_LEGACY_EXPOSED != "1"` -> `raise RuntimeError` (fail-closed).
  2. Chamar `RuntimeConfig.from_env()` no startup (lifespan) para TODOS os perfis, inclusive legacy.
  3. Procfile: `uvicorn api:app --host ${RPG_HOST:-127.0.0.1} --port $PORT` e exigir `RPG_RUNTIME_PROFILE=hosted*` na doc de deploy.
  4. Teste novo em `tests/test_infrastructure_contracts.py`: import de `api` com `PORT` setado e profile legacy deve falhar.
- **Confianca:** confirmado por leitura
- **Ja coberto por spec?** nao (SPEC-104 cloud e `draft`; legacy=loopback "por design" mas sem guard de runtime)
- **Status:** valido

### AUTHZ-02 — RLS do Postgres nao e barreira efetiva: backend conecta como role elevada e nunca faz `SET ROLE rpg_api`/`request.jwt.claim.sub`
- **Severidade:** media (defesa em profundidade; isolamento depende 100% de `WHERE owner_id=%s` em Python)
- **Categoria:** AuthZ/IDOR (camada secundaria ausente)
- **Local:** `infrastructure/postgres.py:25-60` (PostgresPool), `supabase/migrations/20260819002358_auth_rls.sql`, `docs/spec197/risk-register.md` R-05
- **Evidencia:** grep por `set role|set_config|rpg_api|request.jwt` em `*.py` do runtime nao encontra nada; so em
  `scripts/staging/smoke_ab.py` e no pgTAP. As policies sao `TO rpg_api` e `FORCE ROW LEVEL SECURITY`, mas o pool usa o usuario do DSN
  (`postgres`, que no Supabase tem BYPASSRLS), entao nenhuma policy e avaliada em producao.
- **Cenario:** qualquer bug futuro de query sem `owner_id` (ou injection) vira vazamento cross-tenant sem rede de seguranca. Nao ha
  IDOR atual (ver OK abaixo).
- **Impacto:** perda da segunda camada prometida por SPEC-103 ("RLS defesa em profundidade").
- **Correcao sugerida:** (curto) role de login dedicada `rpg_runtime` (sem BYPASSRLS, `GRANT rpg_api`), e em
  `PostgresPool.connection()` fazer `SET LOCAL ROLE rpg_api; select set_config('request.jwt.claim.sub', %s, true)` quando houver
  `current_principal()`; manter conexao admin separada (workers/cron/wallet) via pool distinto. Teste: estender `tests/test_rls_local.py`
  para rodar o `PostgresGameStore` pelo pool com role e provar que `select * from app.games` sem filtro retorna so o owner.
- **Confianca:** confirmado por leitura
- **Ja coberto por spec?** sim, reconhecido: `docs/spec197/risk-register.md` R-05 (aberto), `docs/spec191/README.md:179` follow-up; nao ha spec de implementacao
- **Status:** valido (conhecido/aberto; incluir em SPEC de seguranca como item P1)

### AUTHZ-03 — Amplificacao de chamadas ao GoTrue por cookie invalido (verify remoto a cada request, sem rate limit na borda)
- **Severidade:** media
- **Categoria:** DoS/custo · Rate limit
- **Local:** `api.py:103-105` (`_session_boundary`), `api.py:213-238` (`/auth/config`), `infrastructure/supabase_identity.py:140-171`
- **Evidencia:** `verify(access_token)` faz `httpx.get(.../auth/v1/user)` para QUALQUER string nao vazia no cookie `rpg_access`
  (sem checar forma JWT/`exp` antes) e, se valido, mais 1 query em `auth.sessions`. O middleware roda antes do `_rate_limit`
  (que so cobre uma lista curta de POSTs) e `/game/saves`, `/game/state`, `/account/*`, `/auth/config` nao tem limite.
- **Cenario:** atacante anonimo envia milhares de `GET /game/saves` com `Cookie: rpg_access=x` (e `GET /auth/config`). Cada um dispara
  uma chamada HTTP da funcao Vercel ao Supabase Auth (IPs de saida compartilhados da Vercel). Pode esgotar o rate limit do Auth do
  projeto/instancia -> `verify` legitimo recebe 429 (tratado como `Unauthorized`) -> usuarios reais deslogados/401, alem de custo de
  invocacao Vercel. Perfil: hosted-supabase.
- **Impacto:** indisponibilidade seletiva de login/sessao; consumo de cota.
- **Correcao sugerida:** (a) pre-validacao local barata em `verify`: exigir 3 segmentos base64url, decodificar payload, checar `exp`,
  `aud=authenticated`, `iss`; rejeitar sem rede se invalido; (b) cache curto (15-30 s) token-hash -> Principal para tokens ja verificados;
  (c) rate limit por IP para requisicoes que falham a autenticacao (bucket `authfail:{ip}`). Testes: `tests/test_account_lifecycle_security.py`
  ou novo `tests/test_session_boundary.py` com `httpx` mockado contando chamadas.
- **Confianca:** provavel (comportamento de rate limit do Auth upstream nao verificado)
- **Ja coberto por spec?** nao
- **Status:** valido

### AUTHZ-04 — Cobertura do rate limit: rotas autenticadas caras fora da lista (embedding/quote/etc.) e chave apenas por IP
- **Severidade:** media
- **Categoria:** DoS/custo · Rate limit
- **Local:** `api.py:790-831` (`_rate_limit`), `api.py:3677-3707` (`/game/chronicle/search`), `api.py:2445` (`/game/{id}/art/quote`), `api.py:3353` (`/game/death`)
- **Evidencia:** o conjunto limitado e `{"/game/action","/game/action/stream","/game/new","/game/combat-simulator","/game/equip","/game/levelup","/game/prologue"}` + DELETE de save.
  `POST /game/chronicle/search` chama `_meter_auxiliary_operation("chronicle_search")` -> `semantic_candidates` -> embedding de provedor (Jina)
  a cada request, sem cobrar da wallet (operacao "auxiliar" nao liquidada) e sem limite. `art/quote` grava linhas `image_quotes` por chamada.
  O limite e por IP (`ip:{pseudonym(ip)}`), nao por owner.
- **Cenario:** usuario autenticado (signup aberto + captcha de teste em staging) faz loop em `/game/chronicle/search` -> custo de embedding
  nao reembolsado; ou usuarios atras do mesmo NAT compartilham os 30 req/min do IP.
- **Impacto:** custo do operador, degradacao; injustica entre usuarios no mesmo IP.
- **Correcao sugerida:** adicionar `/game/chronicle/search`, `/game/*/art/quote`, `/game/*/art/*/quality`, `/game/death` ao limite (match por
  prefixo/regex) e usar chave composta `user:{owner}` quando houver principal (com teto de IP separado). Teste em `tests/test_api_rate_limit*.py`.
- **Confianca:** confirmado por leitura (custo exato por embedding nao medido)
- **Ja coberto por spec?** nao
- **Status:** valido

### AUTHZ-05 — IP do cliente = `request.client.host` sem tratamento de proxy: rate limit/anti-abuso pode colapsar num unico bucket (ou ser burlado)
- **Severidade:** media
- **Categoria:** Rate limit · Config/Infra
- **Local:** `api.py:802`, `services/account_security.py:80-90` (`auth_limit`), `api.py:374` (captcha remoteip), `Procfile`
- **Evidencia:** nenhum uso de `X-Forwarded-For`/`--proxy-headers`/`--forwarded-allow-ips` (grep). Atras de Railway/Vercel/qualquer LB,
  `request.client.host` e o IP do proxy (ou, se algum dia configurarem `--forwarded-allow-ips '*'`, spoofavel pelo cliente).
- **Cenario:** (a) com proxy opaco: todos os usuarios compartilham os buckets `auth:*:ip` (20/15 min) e `ip:` (30/min) -> 1 atacante
  esgota login/signup/reset para todos; (b) se mais tarde habilitarem XFF confiando em `*`, o atacante troca o header por request
  e anula o limite. Em Vercel o comportamento do adapter ASGI nao foi verificado.
- **Impacto:** DoS de autenticacao global ou bypass do rate limit.
- **Correcao sugerida:** funcao unica `client_ip(request)` que le o ultimo hop confiavel (`x-vercel-forwarded-for` na Vercel; `x-forwarded-for` com N proxies
  confiaveis configurado por `RPG_TRUSTED_PROXY_HOPS`), usada por `_rate_limit`, `auth_limit` e captcha `remoteip`; testes unitarios dos formatos.
- **Confianca:** hipotese (depende da plataforma)
- **Ja coberto por spec?** nao
- **Status:** valido (verificar empiricamente em staging: logar `client.host` em /health debug local)

### AUTHZ-06 — `/metrics` publico (sem auth) expoe operacao interna, custo LLM por provedor e executa queries no Postgres a cada scrape
- **Severidade:** media
- **Categoria:** Privacidade/Info disclosure · DoS
- **Local:** `api.py:1608-1692`
- **Evidencia:** rota sem autenticacao (fora do prefixo `/game|/account`); no perfil DB executa 3 `select ... group by` em `app.jobs`/`app.operations`/`app.memory_documents` por request e
  publica `rpg_llm_cost_usd_total{provider,tier}`, filas por `kind/status`, idade da fila, idade do backup, estado do pool.
- **Cenario:** `curl https://host/metrics` anonimo -> telemetria de custo/volume/atrasos (inteligencia de negocio e de abuso), e loop de scrapes
  carrega o pool (max 1 conexao em hosted-supabase!) causando 503/timeouts para usuarios reais.
- **Impacto:** disclosure operacional + DoS barato do pool unico.
- **Correcao sugerida:** exigir `Authorization: Bearer $RPG_METRICS_TOKEN` (reaproveitar `hmac.compare_digest` de `cron_internal.authorize`) ou bloquear em hosted;
  cachear o resultado do bloco SQL por 15 s. Teste em `tests/test_metrics*.py`.
- **Confianca:** confirmado por leitura
- **Ja coberto por spec?** nao
- **Status:** valido

### AUTHZ-07 — Defaults inseguros nos perfis hosted: `RPG_COOKIE_SECURE` default 0, captcha desligado por default, sem checagem no doctor
- **Severidade:** media
- **Categoria:** Config/Infra · Sessao
- **Local:** `api.py:262,346,542` (`RPG_COOKIE_SECURE`), `services/account_security.py:44-47,61-62` (`RPG_AUTH_CAPTCHA_REQUIRED` default `0`, modo `app`),
  `infrastructure/runtime.py:275-325` (validate nao checa), `scripts/cloud_doctor.py`
- **Evidencia:** `secure = os.getenv("RPG_COOKIE_SECURE", "0") == "1"` -> cookies de sessao (access/refresh/CSRF/recent) sem `Secure`
  se a env faltar; `validate_captcha` retorna sem checar quando `required` e 0 (modo `app`). `RuntimeConfig.validate()` para `hosted*`
  nao exige `RPG_COOKIE_SECURE=1`, `RPG_SESSION_SECRET` (>=32), nem captcha. Somente `scripts/staging/vercel_env.py` seta tudo corretamente.
- **Cenario:** novo ambiente (Railway/preview/prod) esquece as env -> cookies trafegam sem Secure (downgrade/sniff em redes hostis) e
  signup/reset/verify ficam sem captcha. `RPG_SESSION_SECRET` ausente falha fechado (CsrfSigner levanta -> 401), o que e bom.
- **Impacto:** roubo de sessao em rede insegura; abuso de signup/reset (e-mail bombing).
- **Correcao sugerida:** em `RuntimeConfig.validate()` para `hosted`/`hosted-supabase`: exigir `RPG_COOKIE_SECURE=1`, `len(RPG_SESSION_SECRET)>=32`,
  `RPG_AUTH_CAPTCHA_REQUIRED=1` (override explicito `RPG_ALLOW_INSECURE_HOSTED=1` so para teste); adicionar as mesmas checagens ao `cloud_doctor.py`.
  Nota: staging usa chave Turnstile de TESTE (`1x0000...AA`, sempre passa) — ja listado como gate da SPEC-197; manter bloqueio de release.
- **Confianca:** confirmado por leitura
- **Ja coberto por spec?** parcialmente (chaves Turnstile reais = gate SPEC-191/197); defaults inseguros: nao
- **Status:** valido

### AUTHZ-08 — Bloqueio direcionado de conta por balde `auth:login:email` (5 tentativas / 15 min, inclui sucessos)
- **Severidade:** baixa
- **Categoria:** Rate limit · DoS de conta
- **Local:** `services/account_security.py:80-90`, `api.py:299-300` e `_auth_abuse` (`api.py:358-378`)
- **Evidencia:** `for scope, value, limit in (("ip", remote, 20), ("email", email.strip().casefold(), 5))` com `consume` incrementando a cada tentativa
  (qualquer IP) sob a mesma chave de e-mail.
- **Cenario:** atacante envia 5 `POST /auth/login` com o e-mail da vitima a cada 15 min (de IPs variados ou do mesmo, ate 20) -> a vitima recebe 429 `auth_rate_limit` ao logar. Idem `reset`/`verify`.
- **Impacto:** negacao de login/recuperacao de conta alvo (nao ha tomada de conta).
- **Correcao sugerida:** manter limite por e-mail so para falhas e com backoff por (email, ip) em vez de global; ou exigir captcha apos N falhas em vez de bloquear. Teste em `tests/test_account_security*.py`.
- **Confianca:** confirmado por leitura
- **Ja coberto por spec?** nao
- **Status:** valido (baixa)

### AUTHZ-09 — OIDC (perfis hosted/portable): sem validacao de `aud`/`azp` nem `email_verified`; `iss` assumido quando ausente
- **Severidade:** baixa (perfil nao usado em producao hoje)
- **Categoria:** AuthN
- **Local:** `infrastructure/oidc_identity.py:36-54`
- **Evidencia:** `claimed_issuer = str(payload.get("iss") or self.issuer)`; token validado apenas por `GET userinfo` 200. Qualquer access token emitido pelo mesmo IdP
  para OUTRO client (confused deputy) e aceito; `sub` nao UUID vira `uuid5(issuer#sub)`.
- **Cenario:** app terceiro no mesmo IdP obtem token de usuario e o replay na API do jogo -> sessao valida (cookie `rpg_access` carrega o bearer).
- **Impacto:** acesso indevido se o IdP for compartilhado entre aplicativos.
- **Correcao sugerida:** validar JWT localmente (JWKS com cache, `alg` allowlist RS256/ES256, rejeitar `none`/HS*), `aud == RPG_OIDC_AUDIENCE`, `exp`, `iss`;
  usar userinfo so como complemento. Testes novos em `tests/test_oidc_identity.py`.
- **Confianca:** confirmado por leitura
- **Ja coberto por spec?** nao
- **Status:** valido (baixa; bloquear antes de ativar perfil hosted/portable)

### AUTHZ-10 — `/docs`, `/redoc`, `/openapi.json` habilitados em producao; login sem checagem de Origin no modo `app`
- **Severidade:** baixa
- **Categoria:** Config/Infra
- **Local:** `api.py:60-64` (FastAPI sem `docs_url=None`), `api.py:161,202` (`_DOCS_PATHS` com CSP relaxada), `api.py:282-306` (login modo app)
- **Evidencia:** FastAPI default expoe schema completo (inclui rotas `/internal/cron/*`, `/payments/stripe/webhook`); `/docs` e isento da CSP (carrega scripts de CDN).
  `/auth/login` modo `app` so chama `auth_limit`, sem `Origin` (apenas modo gotrue passa por `_auth_abuse`) -> login-CSRF possivel (cookie SameSite do atacante nao se aplica a POST cross-site sem cookies, risco real minimo).
- **Impacto:** reconhecimento facilitado; Swagger UI sem CSP.
- **Correcao sugerida:** `FastAPI(docs_url=None, redoc_url=None, openapi_url=None)` quando `_database_profile()`; chamar checagem de Origin tambem no login modo app.
- **Confianca:** confirmado por leitura
- **Ja coberto por spec?** nao
- **Status:** valido (baixa)

### AUTHZ-11 — Informativos descartados / sem acao
- **Severidade:** info · **Status:** descartado (anotado para nao reauditar)
  - `app.rate_limit_buckets` e `app.embedding_profiles` sem `ENABLE ROW LEVEL SECURITY`: schema `app` revogado para `anon/authenticated` e sem grant a `rpg_api` (rate_limit) -> sem exposicao via PostgREST. Opcional: habilitar RLS para silenciar o advisor.
  - `postgres_turns.claim:84` responde `Conflict("idempotency key indisponivel")` quando a `operation_id` existe com outro owner: oraculo de existencia de UUID aleatorio — nao explotavel.
  - `/game/action` (e equip/levelup/death/stream) sem `game_id` operam sobre o jogo mais recente do owner (pode ser um laboratorio `combat_simulation`) — comportamento funcional, nao cross-tenant.
  - `minimum_password_length = 8` em `supabase/config.toml`, sem requisitos de complexidade (aceitavel; recomendavel 10-12 + checagem de vazamento no hosted).
  - Token CSRF e HMAC de nonce sem vinculo com a sessao (qualquer token assinado vale): mitigado por Origin allowlist + cookie `SameSite=Strict`; `vercel.app` esta na PSL (sem cookie tossing entre projetos).

---

## Verificado e OK (nao reauditar)

**Middleware / fronteira (`api.py:91-146`)**
- `_session_boundary` protege todo path que comeca com `/game` e `/account` nos perfis != legacy; principal vem so do cookie HttpOnly `rpg_access` (nao ha Bearer/header/query), verificado por `identity_verifier.verify`. Falha -> 401. Nenhum parametro `owner/user_id` aceito do cliente (grep em modelos Pydantic e query params: nenhum).
- Rotas fora da fronteira e quem as decide: `/auth/*` (CSRF/origem/captcha proprios em `_validate_auth_csrf`/`_auth_abuse`; `reauth`, `logout`, `refresh` validam CSRF), `/payments/stripe/webhook` (assinatura HMAC com `t=` +-300 s, corpo cru <= limite, `livemode` falso obrigatorio, segredo `whsec_`), `/internal/cron/*` (5/5 rotas chamam `authorize`: Bearer `RPG_CRON_SECRET` >= 32 chars, `hmac.compare_digest`, fail-closed 503), `/health` (so sha), `/data/*` (conteudo estatico), `/metrics` (ver AUTHZ-06), `/docs` (AUTHZ-10), arquivos estaticos `web/dist` (montados em `/` por ultimo; nao sobrepoem rotas).
- Normalizacao de path: `request.url.path` e o path ja decodificado do ASGI; `//game/..` nao casa com rotas (cai no static -> 404); roteamento case-sensitive.
- CSRF: toda mutacao (POST/PUT/DELETE) em `/game|/account` exige Origin em `_CORS_ORIGINS` + cookie==header + HMAC valido; nao ha GET com efeito colateral em `/game|/account` (verificado nas rotas listadas). Cookies: access `HttpOnly; SameSite=Lax`, refresh `HttpOnly; SameSite=Strict; Path=/auth/refresh`, `rpg_recent` Strict 300 s.
- `/account/delete`: ramo `deletion-retry` so cobre esse path exato, exige CSRF, e so retoma tombstone existente em `app.account_deletions` (recibo `rpg_deletion` HMAC, 7 d, HttpOnly, Path restrito).

**IDOR por `game_id` — todas owner-scoped via `load_game_state` -> `store.get(principal, uuid)` (`persistence.py` ramo DB, `postgres.py:149-155` `where id=%s and owner_id=%s`)**
- `/game/state`, `/game/codex`, `/game/history` (+ `history_costs` com owner), `/game/action`, `/game/action/stream` (principal propagado ao worker via `principal_scope`; retomada por `action_id` = `receipt()` `where id=%s and owner_id=%s`), `/game/death`, `/game/equip`, `/game/levelup`, `/game/saves` (`list(principal)`), `DELETE /game/save/{id}` (`commit_delete ... where id=%s and owner_id=%s`, Idempotency-Key UUID), `/game/chronicle/search` (pgvector com `owner_id=%s and game_id=%s`), `/game/chronicle/export` (confirmado), `/game/combat-simulator`, `/game/new`, `/game/prologue`, `/game/art/brief` (stateless).
- `/game/{id}/operations/{op}` e `/cost`: carregam o jogo owner-scoped ANTES e consultam `app.operations ... and owner_id=%s` / `turn_cost` com owner+game.
- `/game/{id}/art/quote|confirm|{generation_id}|{generation_id}/quality`: `ImageQuoteRepository` usa `owner_id`+`game_id`; `DynamicArtRepository.get/set_quality` usam `generation_id + owner_id`; status confere `generation.game_id == state.game_id`.
- Criacao com `game_id` alheio: `save_game_state` faz `store.get` (None p/ outro owner) -> `create` -> PK conflict -> `Conflict`, nunca sobrescreve; UPDATE sempre `owner_id` + `version`.
- `postgres_turns.claim/commit_game/commit_create/commit_delete/receipt/save_checkpoint/get_checkpoint`: todos `owner_id` no WHERE; operacao existente de outro owner -> `Conflict`.
- `app.memory_documents`: queries privadas exigem `owner_id`+`game_id` (`_filters`); `document_id` embute o `game_id` (UUID secreto) no hash -> sem colisao cross-tenant pratica.
- Blob: chaves `users/{owner}/games/{game}/...` com `safe_entity_id` (`[a-z0-9_-]`) e checagem de prefixo em `SupabaseBlobStore.put`; URLs assinadas de 300 s geradas so apos leitura owner-scoped.

**/account/***
- `export`, `delete`, `balance`, `purchases`, `usage`, `series`, `transcriptions`, `checkout`, `checkout/{order_id}`, `purchases/google/*`: todos usam `current_principal()`; `export`/`delete` exigem `rpg_recent` (prova HMAC vinculada ao hash do cookie de acesso + owner, 300 s). Listagens: `limit` 1..50, cursor validado. STT: limite 5/min por owner, corpo <= 8 MiB, timeout 15 s.

**Supabase / SQL**
- RLS `ENABLE + FORCE` em todas as tabelas `app.*` com dado de usuario (verificado por diff de `create table` x `enable row level security`; excecoes: `rate_limit_buckets`, `embedding_profiles` — ver AUTHZ-11; reconciliacao via loop `DO`). Policies usam `app.current_owner_id()` / `auth.uid()`; nenhum `USING (true)` em tabela de usuario (somente `image_price_profiles`, catalogo global `to rpg_api`).
- `revoke all on schema app from public, anon, authenticated` e revoke de tabelas; `app.current_owner_id()` nega contas com tombstone.
- Funcoes `SECURITY DEFINER` (`public.rpg_wallet_balance/history`, `public.rpg_current_session_active`, `app.guard_storage_account_write`, `app.set_kill_switch`, `app.cron_health_check`, `app.validate_usage_attribution`): todas com `set search_path=''`; as publicas filtram por `auth.uid()` e sessao viva; `revoke ... from public, anon, rpg_api` e `grant execute ... to authenticated` apenas nas duas de wallet/session; as de `app.*` revogadas de anon/authenticated. Views `public.wallet_*_view` removidas na migration 20261015120000 (estado final = so funcoes).
- Storage: bucket privado `rpg-dynamic`, policies por prefixo `users/{auth.uid()}` + sessao viva; trigger de fence contra escrita pos-delecao.
- `supabase/config.toml`: `enable_anonymous_sign_ins=false`, `enable_confirmations=true`, `jwt_expiry=3600`; (config remota hosted: confirmacao ligada conforme `docs/spec191`).

**Tokens / sessao (`supabase_identity.py`, `auth_sessions.py`)**
- Assinatura/`exp`/revogacao validadas pelo GoTrue (`/auth/v1/user`) e, no pool DB, `auth.sessions` ativa + sem tombstone; claims so lidos apos validacao. Logout usa `scope=global`; refresh rotaciona via GoTrue e `auth_refresh` revalida (tombstone bloqueia). Reset de senha revoga sessoes (`logout` global apos `PUT /user`). Signup com confirmacao de e-mail obrigatoria por default nos perfis `hosted*` e respostas genericas (sem enumeracao no modo hosted). Segredo de sessao <32 chars falha fechado.
- `service_role`: usado apenas em `delete_user` (admin) e `SupabaseBlobStore`; nunca enviado ao browser (validate rejeita `VITE_`); `SUPABASE_PUBLISHABLE_KEY` != service key validado em `runtime.py`.

**Admin**
- Nao ha endpoint HTTP admin (`grep @app\.|@router\.`): `scripts/admin_*.py`/`recover_*.py` sao CLI; unico router interno e `/internal/cron/*` (autorizado). `kill_switch` via script, nao via HTTP.

**Perfis**
- `hosted`/`hosted-supabase`: `RuntimeConfig.validate` recusa bind/DB em loopback, DSN com overrides, project-ref divergente; Vercel: `scripts/staging/vercel_env.py` seta `RPG_RUNTIME_PROFILE=hosted-supabase`, `RPG_COOKIE_SECURE=1`, captcha `gotrue`/required, e `preview` sem segredos (fail-closed). `scripts/start_local_api.py` usa perfil `local` e `--host 127.0.0.1`.
