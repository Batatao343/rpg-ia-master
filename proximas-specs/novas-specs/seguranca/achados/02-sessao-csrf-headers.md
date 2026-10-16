# Auditoria de segurança — Área 02: Sessão, CSRF, cookies, CORS, headers, Turnstile, rate limit, reauth, Android

Data: 2026-10-15. Somente leitura.
Arquivos inspecionados: `api.py` (l.60-600, 785-830, 1595-1700, 1917-1935, 2019-2070, 2184-2215, 3466-3486), `services/auth_sessions.py`,
`services/account_security.py`, `infrastructure/supabase_identity.py` (l.1-160), `infrastructure/postgres_turns.py` (PostgresRateLimiter),
`infrastructure/runtime.py` (validação de perfis), `services/google_play_fake.py`, `vercel.json`, `vercel_app.py`, `scripts/staging/vercel_env.py`,
`web/src/http.ts`, `web/capacitor.config.ts`, lista de testes em `tests/`.
Limitação: não li o resto de `supabase_identity.verify` nem os testes por dentro; `web/src/native/*` só listado.

---

### SESS-01 — `/metrics` público sem autenticação, executa queries no Postgres a cada scrape
- **Severidade:** média
- **Categoria:** Config/Infra, DoS/custo, Info disclosure
- **Local:** `api.py:1608-1693` (`prometheus_metrics`); nem `_session_boundary` (só `/game`,`/account`) nem `vercel.json` protegem.
- **Evidência:** rota `@app.get("/metrics")` sem dependência de auth; em perfil DB abre conexão e roda 3 `group by` em `app.jobs`, `app.operations`, `app.memory_documents`, mais `publish_evaluation_age()` e devolve `metrics.render_prometheus()`. Teste `tests/test_observability_stack.py:14` chama `/metrics` sem credenciais (comportamento esperado hoje).
- **Cenário:** qualquer anônimo na internet faz `GET https://<host>/metrics` em loop (hosted/hosted-supabase na Vercel). Vaza contagens de jobs por kind/status, idade de fila, backlog de embeddings, saúde do pool, labels de rotas, métricas FinOps/margem (SPEC-196: `publish_evaluation_age`, alertas) e consome conexões do pool (max 1 em hosted-supabase) → starvation do pool para usuários reais. `/metrics` não está em `_rate_limit`.
- **Impacto:** reconhecimento operacional/negócio; DoS barato do pool de DB (pool de 1 conexão por instância).
- **Correção sugerida:** exigir `Authorization: Bearer RPG_METRICS_TOKEN` (ou reutilizar `RPG_CRON_SECRET` com `hmac.compare_digest`) quando `_database_profile()`; 404 sem token. Alternativa: desligar a rota em hosted. Teste: ajustar `test_observability_stack.py` + novo caso 401.
- **Confiança:** confirmado por leitura
- **Já coberto por spec?** não (SPEC-106 cobre observabilidade mas não auth do endpoint)
- **Status:** válido

### SESS-02 — Rate limit e `request.client.host` atrás da Vercel: IP possivelmente do proxy (bucket compartilhado) ou spoofável
- **Severidade:** média (hipótese a validar em staging)
- **Categoria:** Rate limit
- **Local:** `api.py:799-815` (`_rate_limit`), `services/account_security.py:81-92` (`auth_limit`), `api.py:2199` (STT por user), grep de `forwarded|proxy_headers|x-real-ip` em `api.py`/`infrastructure`/`vercel_app.py`: **nenhuma ocorrência**.
- **Evidência:** `ip = request.client.host if request.client else "?"` e `remote = request.client.host if request.client else "unknown"`. Não há leitura de `x-vercel-forwarded-for`/`x-forwarded-for`/uvicorn `--proxy-headers`/`forwarded_allow_ips`.
- **Cenário:** (a) se o runtime Vercel/ASGI expõe `client.host` = IP do edge/proxy, todos os usuários compartilham o bucket `ip:*` (20 logins/15 min e 30 req/janela para todo mundo → DoS legítimo auto-infligido e, inversamente, o atacante consome o balde de todos); (b) se algum adaptador reescreve `client` a partir do primeiro valor de `X-Forwarded-For`, o cliente forja o header e contorna o limite por IP. O bucket por e-mail (5/15 min) não depende de IP.
- **Impacto:** limite de IP ineficaz ou causador de bloqueio global em login/signup/reset e `/game/action`.
- **Correção sugerida:** em hosted, derivar o IP de `x-vercel-forwarded-for` (setado pela Vercel, não spoofável por cliente) com fallback para `client.host`; função única `client_ip(request)` usada por `_rate_limit`, `auth_limit`, `validate_captcha(remote_ip)`. Teste novo em `tests/test_auth_sessions.py`. Validar empiricamente no staging com duas origens.
- **Confiança:** hipótese
- **Já coberto por spec?** não
- **Status:** válido (a confirmar)

### SESS-03 — Rate limit de IP cobre só 8 rotas; rotas caras/mutáveis sem limite por IP/usuário
- **Severidade:** média
- **Categoria:** Rate limit, DoS/custo
- **Local:** `api.py:790-815` (lista fixa); rotas sem limite: `/game/art/brief` (l.2369), `/game/{id}/art/quote` (2445), `/game/{id}/art/*/confirm` (2493-2494), `/game/chronicle/search` (3677), `/account/checkout` (2035), `/account/purchases/google/verify` (2113), `/game/death` (3353), `/game/chronicle/export` (3710).
- **Evidência:** `request.url.path in ("/game/action", "/game/action/stream", "/game/new", "/game/combat-simulator", "/game/equip", "/game/levelup", "/game/prologue")` + DELETE `/game/save/`. Só `/account/transcriptions` tem limite por usuário (5/min, l.2199).
- **Cenário:** usuário autenticado (signup é barato) dispara `/game/art/brief` (LLM) e `/game/chronicle/search` (embedding/vector) em loop; `/account/checkout` cria sessões Stripe sem teto por usuário/IP. Custo de LLM/embedding/Stripe sem freio (a wallet limita apenas imagem confirmada, não brief/search).
- **Impacto:** consumo de quota/custo de provider e Stripe API; abuso de DB.
- **Correção sugerida:** trocar a lista por política por prefixo/handler: limite por `principal.user_id` (chave `user:{id}:{route_class}`) nas classes `llm`, `embedding`, `payments`, além do IP. Teste em `tests/test_account_auth_transport.py`.
- **Confiança:** confirmado por leitura (ausência); impacto de custo depende de cada handler ter outro guard — não verifiquei `art/brief`/`search` internamente (cruzar com a área de custo).
- **Já coberto por spec?** não
- **Status:** válido

### SESS-04 — Logout não revoga refresh token quando o cookie de acesso expirou; logout com CSRF inválido gera 500
- **Severidade:** média (revogação) / baixa (500)
- **Categoria:** Sessão
- **Local:** `api.py:577-595` (`auth_logout`), `infrastructure/supabase_identity.py` (`logout` usa o access token).
- **Evidência:** `access = request.cookies.get(ACCESS_COOKIE); if access: identity_verifier.logout(access)` — `logout` chama `/auth/v1/logout?scope=global` com o access token. Se o access (vida curta, ~1 h) expirou, nada é revogado no servidor; só os cookies são apagados no navegador. Se `logout(access)` falha com access vencido, levanta `Unauthorized` não tratado (a função não captura; `/auth/*` fica fora do `try` do `_session_boundary`) → 500. `_validate_auth_csrf` também levanta `Unauthorized` fora de `HTTPException` → 500 em vez de 401/403.
- **Cenário:** vítima clica "sair" depois que o access expirou; refresh token roubado (malware/backup de perfil do WebView Android, cookie com `max_age` de 14 dias no Android) continua válido até expirar/rotacionar. Em desktop o refresh já é session cookie.
- **Impacto:** logout não encerra a sessão server-side em parte dos casos; sessão Android persistente de 14 dias roubável não é invalidada pelo logout.
- **Correção sugerida:** no logout, se o access estiver inválido, tentar `refresh(refresh_cookie)` e então `logout(novo_access)` (ou usar Admin API `scope=global` por user_id); capturar `Unauthorized` e retornar 204/401 consistentes. Testes: `tests/test_account_auth_transport.py` (logout com access expirado deve revogar refresh; CSRF inválido → 403).
- **Confiança:** confirmado por leitura (parcial: não rodei).
- **Já coberto por spec?** não (SPEC-190/193 tratam rotação/revogação do refresh, não este caminho)
- **Status:** válido

### SESS-05 — Lockout de login/reset direcionado: bucket por e-mail conta tentativas, não falhas
- **Severidade:** média
- **Categoria:** Rate limit / DoS de conta
- **Local:** `services/account_security.py:81-92` (`auth_limit`: IP=20, e-mail=5 por 900 s, chave `auth:{action}:email:{sha256}`), chamado antes de validar credenciais (`api.py:297-300`, `_auth_abuse`).
- **Evidência:** `runtime.rate_limiter.consume(...)` incrementa a cada tentativa, certa ou errada, antes de verificar a senha.
- **Cenário:** atacante envia 5 `POST /auth/login` com e-mail da vítima (qualquer senha) a cada 15 min → vítima recebe 429 em todo login legítimo (mesma chave por e-mail, independente de IP). Também para `reset`/`verify` (impede recuperação). Os 5 pedidos podem vir de IPs diferentes.
- **Impacto:** negação de acesso direcionada a contas conhecidas.
- **Correção sugerida:** contar para o bucket de e-mail só falhas (ou usar chave composta `(email, ip)` + bucket de e-mail mais folgado, p.ex. 20) e exigir captcha ao exceder; manter o IP em 20. Testes em `test_account_lifecycle_security.py`.
- **Confiança:** confirmado por leitura
- **Já coberto por spec?** não (SPEC-190 definiu os limites; risco de lockout não discutido que eu tenha visto)
- **Status:** válido

### SESS-06 — Perfis hosted não falham fechado sem `RPG_COOKIE_SECURE=1`, `RPG_CORS_ORIGINS` e captcha obrigatório
- **Severidade:** média
- **Categoria:** Config/Infra
- **Local:** `api.py:262` (`secure = os.getenv("RPG_COOKIE_SECURE","0")=="1"`), `api.py:346`, `api.py:542`, `api.py:66-72` (CORS default localhost), `services/account_security.py:40-45,63-67` (`RPG_AUTH_CAPTCHA_REQUIRED` default 0 → `validate_captcha` retorna sem checar no modo `app`), `infrastructure/runtime.py` (validação de perfil não verifica nenhuma dessas variáveis).
- **Evidência:** `RuntimeConfig.validate` exige DB/blob/auth/bind mas não `RPG_COOKIE_SECURE`, `RPG_SESSION_SECRET` (só falha em runtime com 401), nem captcha. O script de staging (`scripts/staging/vercel_env.py:35-39`) define os valores corretos, porém o código não impõe.
- **Cenário:** deploy de produção (SPEC-197) cuja env esqueça `RPG_COOKIE_SECURE=1` emite cookies de sessão sem `Secure` (transmitidos em HTTP se algum http:// for tocado; Vercel redireciona para https, risco residual); esquecer `RPG_AUTH_CAPTCHA_REQUIRED=1` desliga Turnstile em signup/reset silenciosamente no modo `app`; esquecer CORS → Origin das mutações recusado (falha segura). `RPG_SESSION_SECRET` ausente → todas as mutações 401 (falha segura, mas só em runtime).
- **Impacto:** regressão de segurança silenciosa por configuração em produção.
- **Correção sugerida:** em `RuntimeConfig.validate` para `hosted*`: exigir `RPG_COOKIE_SECURE=1`, `len(RPG_SESSION_SECRET)>=32`, `RPG_CORS_ORIGINS` explícito sem localhost e sem `*`, e captcha `required` com site key (e secret no modo `app`). Já existe `scripts/release/checklist.py` — estender e criar teste de `validate` em `tests/test_runtime_config*.py`.
- **Confiança:** confirmado por leitura
- **Já coberto por spec?** parcial: SPEC-197 (checklist de release) lista as variáveis; imposição em código não
- **Status:** válido

### SESS-07 — Login em modo `app` não valida Origin nem captcha (login CSRF)
- **Severidade:** baixa
- **Categoria:** CSRF
- **Local:** `api.py:282-306` (`auth_login`, ramo `else` de `captcha_mode`: só `auth_limit`, sem `_auth_abuse`/Origin).
- **Evidência:** o ramo `gotrue` chama `_auth_abuse` (que exige `Origin ∈ _CORS_ORIGINS`); o ramo `app` chama apenas `auth_limit`. Login não passa pelo `_session_boundary` (não é `/game|/account`).
- **Cenário:** site terceiro faz `fetch('/auth/login',{mode:'no-cors',credentials:'include'})`? Body JSON exige preflight `Content-Type: application/json` → bloqueado por CORS (origem não permitida). Via `<form enctype=text/plain>` o corpo não é JSON válido → 422. Exploração prática improvável; permaneceria "login CSRF" (logar vítima na conta do atacante).
- **Impacto:** baixo; staging/prod usam `gotrue`.
- **Correção sugerida:** chamar a checagem de Origin também no ramo `app` (extrair de `_auth_abuse`).
- **Confiança:** provável
- **Já coberto por spec?** não
- **Status:** válido (baixa)

### SESS-08 — Respostas autenticadas sem `Cache-Control: no-store` e sem HSTS no app
- **Severidade:** baixa
- **Categoria:** Config/Infra, Privacidade
- **Local:** `api.py` (middleware `_correlation_boundary`, l.164-205, não seta `Cache-Control`/`Strict-Transport-Security`); `/game/state` (l.1917), `/game/history`, `/game/saves`, `/game/codex`, `/account/balance|purchases|usage|series` — só `export`, `delete`, checkout, google verify e STT têm `no-store`.
- **Evidência:** grep `no-store` no `api.py` só retorna as linhas 509, 539, 2024-2220.
- **Cenário:** dispositivo compartilhado/proxy corporativo/botão voltar reexibe JSON autenticado em cache heurístico; respostas sem validadores normalmente não são cacheadas pelo navegador para API JSON, o risco é baixo. HSTS: a Vercel adiciona `Strict-Transport-Security` em `*.vercel.app`; domínio custom e Android dependem disso.
- **Impacto:** baixo.
- **Correção sugerida:** no middleware, `setdefault("Cache-Control","no-store")` para paths `/game`,`/account`,`/auth`; `Strict-Transport-Security: max-age=63072000; includeSubDomains` quando `RPG_COOKIE_SECURE=1`.
- **Confiança:** confirmado por leitura
- **Já coberto por spec?** não
- **Status:** válido (baixa)

### SESS-09 — CSP com `style-src 'unsafe-inline'`; sem `form-action`
- **Severidade:** info
- **Categoria:** XSS hardening
- **Local:** `api.py:149-160` (`CONTENT_SECURITY_POLICY`)
- **Evidência:** `style-src 'self' 'unsafe-inline' https://fonts.googleapis.com`; sem `form-action`. `script-src 'self' https://challenges.cloudflare.com` (sem inline/eval — bom).
- **Impacto:** injeção de CSS apenas; scripts continuam bloqueados. Cruza com SPEC-211 (`mdLite` + `dangerouslySetInnerHTML`): a CSP mitiga XSS de script.
- **Correção sugerida:** adicionar `form-action 'self'`; migrar estilos inline para classes se viável.
- **Confiança:** confirmado por leitura
- **Já coberto por spec?** SPEC-192 F6 definiu a CSP
- **Status:** válido (info)

### SESS-10 — Token CSRF assinado mas não vinculado à sessão; `rpg_recent` não é de uso único
- **Severidade:** info
- **Categoria:** CSRF / Reauth
- **Local:** `services/auth_sessions.py:37-54`; `services/account_security.py:19-37`; `api.py:340-347,486-497`
- **Evidência:** `CsrfSigner.issue()` = `nonce.HMAC(nonce)` sem owner/access; qualquer token válido casa cookie==header. O cookie é `SameSite=Strict` e a mutação exige `Origin` na allowlist, então a ligação à sessão acrescentaria pouco. O comprovante `rpg_recent` é HMAC de `owner:purpose:ts:sha256(access)`, vale 300 s, `HttpOnly`, `SameSite=Strict`, preso ao access token, replay dentro da janela é aceito (não single-use) — aceitável para export/delete.
- **Impacto:** nenhum explorável sem XSS/cookie injection.
- **Status:** descartado como vulnerabilidade (registrado para referência)

---

## Verificado e OK

1. **Flags de cookie** (`services/auth_sessions.py:77-83`, `api.py:257-280`): access `HttpOnly`, `SameSite=Lax`, `Path=/`; refresh `HttpOnly`, `SameSite=Strict`, `Path=/auth/refresh`; `rpg_csrf` legível por JS (double-submit) `SameSite=Strict`; `rpg_recent`/`rpg_deletion` `HttpOnly`/`Strict` com path restrito; `Secure` condicionado a `RPG_COOKIE_SECURE` (staging seta 1 em `scripts/staging/vercel_env.py:35`). Ressalva: ver SESS-06.
2. **Cookies novos a cada login/refresh** (`_set_session_cookies` emite novo access, refresh, CSRF) → sem session fixation; refresh rotacionado pelo GoTrue (`/token?grant_type=refresh_token`); erro de login genérico "credenciais inválidas" (`supabase_identity.py:56`); signup/reset/verify devolvem `GENERIC_MESSAGE` 202 quando confirmação de e-mail ativa (sem enumeração; `api.py:309-340,396-424`).
3. **CSRF** (`api.py:91-146`, `auth_sessions.py:57-70`): todo método ≠ GET/HEAD/OPTIONS em `/game*` e `/account*` exige Origin na allowlist + cookie==header (`hmac.compare_digest`) + assinatura HMAC válida. Cobre `/game/action/stream`, `/account/transcriptions`, `/game/combat-simulator`, `DELETE /game/save/{id}`, `/account/checkout`, `/account/purchases/google/verify`. `/auth/refresh`, `/auth/logout`, `/auth/reauth` chamam `_validate_auth_csrf`. Exceções legítimas: `/auth/login|signup|verify|reset/*` (pré-sessão; limitadas por Origin em modo gotrue e rate limit/captcha), `/payments/stripe/webhook` (assinatura raw), `/internal/cron/*` (bearer secret). Cabeçalho `X-RPG-Client` **não** pula CSRF (só altera `max_age` — `api.py:240-255`).
4. **CORS** (`api.py:66-80`): lista explícita (default localhost), `allow_credentials=True` sem `*`; WebView Capacitor carrega o site remoto https (`web/capacitor.config.ts`), então Origin = host público na própria allowlist; sem origens `capacitor://`/`https://localhost` desnecessárias. `allow_headers=["*"]` com origem fechada: aceitável.
5. **Headers** (`api.py:164-205`): `X-Content-Type-Options: nosniff`, `Referrer-Policy: same-origin`, `Permissions-Policy: camera=(), microphone=(self), geolocation=()`, `X-Frame-Options: DENY`, CSP restritiva com `frame-ancestors 'none'`, `object-src 'none'`, sem `unsafe-eval`; swagger excluído da CSP. `vercel.json` só adiciona headers de SSE (sem conflito/duplicação). Docs OpenAPI (`/docs`, `/openapi.json`) permanecem habilitados — não avaliei exposição (info).
6. **Turnstile** (`account_security.py:47-78`, `api.py:358-381`): modo `gotrue` exige token presente e o encaminha ao GoTrue (verificação nativa, `gotrue_meta_security`); modo `app` verifica `siteverify` com secret no servidor, checa `hostname` ∈ origens e `action`. Chave de teste Cloudflare (`1x00000000000000000000AA`) aparece só em `scripts/staging/vercel_env.py`, não é default de código; uso em staging é o caveat conhecido (SPEC-191/197: chaves reais pendentes).
7. **Rate limit** em perfis DB é Postgres (`PostgresRateLimiter`, atômico por `on conflict`; `runtime.validate` exige `rate_limit_store=postgres` fora do legacy) → não é por instância serverless. Auth tem buckets IP (20) + e-mail normalizado (5) por 900 s; STT 5/min por usuário.
8. **Reauth / prova recente**: `/account/export` e `/account/delete` exigem `rpg_recent` (`_require_recent`), HMAC ligado a owner + hash do access cookie, 300 s, comparação com `compare_digest`; reauth confere senha e mesmo `user_id`, descarta a sessão temporária (`logout?scope=local`). Fluxo de retry de exclusão (`rpg_deletion`, 7 d) só retoma tombstone existente e ainda passa pelo CSRF.
9. **Logout** usa `scope=global` (revoga todas as sessões do usuário quando o access é válido); reset de senha encerra a sessão (`reset_password` → `logout`).
10. **Android**: `X-RPG-Client` só controla duração de cookies (documentado em `api.py:240-247`); Stripe recusado com header android (política, não fronteira — `api.py:2029-2032`); `google_play_fake` só com `RPG_RUNTIME_PROFILE=local`, nunca `hosted*` nem `VERCEL` (`google_play_fake.py:19-23`, `api.py:2060-2066` falha fechado); `capacitor.config.ts`: https obrigatório, `cleartext` só emulador debug (`10.0.2.2`), `allowNavigation: [host]`, `allowMixedContent:false`. `web/src/http.ts` envia `credentials: include` + `X-CSRF-Token` do cookie, sem armazenar bearer em JS.
11. **SSE** `/game/action/stream`: POST via `fetch` passa pelo `_session_boundary` (auth por cookie + CSRF) e rate limit (`api.py:3466-3485`, lista de `_rate_limit`).
12. **Testes existentes** (por nome; não li por dentro): `tests/test_auth_sessions.py` (CSRF/assinatura), `tests/test_account_auth_transport.py` (transporte de cookies/refresh/Android), `tests/test_account_lifecycle_security.py` (reauth/export/delete/rate limit), `tests/test_account_auth_gotrue_local.py`, `tests/test_frontend_auth_bootstrap.py`, `tests/test_storage_security_local.py`.
