# SPEC-221 — Superfícies operacionais: `/metrics` autenticado, cache/HSTS/CSP e limites de borda

> **Status:** `done`
> **Criada:** 2026-10-15 · **Atualizada:** 2026-10-16
> **Depende de:** nenhuma · SPEC-218 desliga `/docs`; esta cobre o resto da superfície e NÃO a exige (índice corrigido); evolui SPEC-106 e SPEC-192 F6 (ordem final 2026-10-15)
> **Desbloqueia:** gate da SPEC-197 (scrape `/metrics` seguro) (ordem final 2026-10-15)
> **Origem:** auditoria de segurança 2026-10-15 — achados SESS-01/AUTHZ-06, SESS-08, SESS-09, INJ-01, INJ-02
> **EXECUTOR_MODEL:** `Terra` (≡ Sonnet)
> **REVIEW_MODEL:** `Sol` (≡ Opus em contexto separado) · **REVIEW_REQUIRED:** `false` — mudanças localizadas em headers/um endpoint; testes de contrato cobrem
> **EVAL_AUTHORING_REQUIRED:** `false`

---

## 1. Contexto & Objetivo

`GET /metrics` é público, fica fora de `_session_boundary` (só `/game|/account`) e do `_rate_limit`, e em perfil DB executa **três queries** (`app.jobs`, `app.operations`, `app.memory_documents`) a cada scrape, além de publicar `rpg_llm_cost_usd_total{provider,tier}`, filas por `kind/status`, idade de backup e estado do pool. Em `hosted-supabase` o pool tem **1 conexão por instância**: um loop anônimo de scrapes esgota o pool e derruba usuários reais, além de entregar inteligência operacional/custo a qualquer um. Na mesma família de "superfície": respostas autenticadas não têm `Cache-Control: no-store`; HSTS depende da Vercel; CSP com `style-src 'unsafe-inline'` e sem `form-action`; não há teto global de body antes do parse Pydantic (DoS de memória em self-host); e o `Content-Disposition` do export da crônica usa `isalnum()` Unicode e devolve 500 para nomes fora de latin-1.

Fatos observados no HEAD:

- [F] `api.py:1608-1692` `prometheus_metrics`: `@app.get("/metrics", include_in_schema=False)` sem dependência de auth; 3 `execute` por request quando `_database_profile()`; `except Exception: pass`.
- [F] `api.py:94` fronteira só `/game|/account`; `api.py:794-801` lista do rate limit não inclui `/metrics`.
- [F] `api.py:164-205` `_correlation_boundary` seta `X-Content-Type-Options`, `Referrer-Policy`, `Permissions-Policy`, `X-Frame-Options`, CSP; **não** seta `Cache-Control` nem `Strict-Transport-Security`; `grep no-store api.py` só em export/delete/checkout/google/STT.
- [F] `api.py:151-160` CSP: `style-src 'self' 'unsafe-inline' https://fonts.googleapis.com`; sem `form-action`; `vercel.json` só adiciona headers de SSE.
- [F] `api.py:3736-3738` `hero = "".join(c for c in name if c.isalnum())` → header latin-1 → `UnicodeEncodeError` → 500 (sem splitting: CR/LF/aspas filtrados).
- [F] Sem middleware de tamanho de body; só webhook Stripe (256 KB) e STT (8 MiB) leem o stream com teto.
- [R] `/metrics` é consumido pelo stack opcional Prometheus (SPEC-106) e por `publish_evaluation_age` (SPEC-196 F7) — o scrape precisa continuar funcionando com token.

Objetivo: `/metrics` só com Bearer e com cache curto do bloco SQL; headers de cache/HSTS/CSP corretos por padrão; teto de body e export robusto.

## 2. Requisitos

- **R1** — `/metrics` em perfil DB exige `Authorization: Bearer <RPG_METRICS_TOKEN>` (≥ 32 chars, `hmac.compare_digest`); ausente/errado → **404** (não revela a rota). Em `legacy`/`local` sem a env → comportamento atual (scrape local sem token), com a env → exige. `RPG_METRICS_TOKEN` entra em `HOSTED_SECURITY_REQUIREMENTS` (SPEC-218) e no `.env.example`.
- **R2** — O bloco SQL de `/metrics` é cacheado por processo por 15 s (`RPG_METRICS_SQL_CACHE_S`), e cada scrape faz no máximo 1 conexão; falha de DB → mantém últimos valores + gauge `rpg_metrics_db_error` = 1.
- **R3** — `/metrics` entra no rate limit (classe própria: 12/min por IP) — se SPEC-219 ainda não estiver feita, usar a lista atual.
- **R4** — Middleware: `Cache-Control: no-store` em toda resposta cujo path começa com `/game`, `/account` ou `/auth` (setdefault; SSE mantém `no-cache, no-transform` da Vercel). `Strict-Transport-Security: max-age=63072000; includeSubDomains` quando `RPG_COOKIE_SECURE=1` (preload só por decisão D-A).
- **R5** — CSP: adicionar `form-action 'self'`; manter `style-src 'unsafe-inline'` até migrar estilos inline (ponto D-B; o `motion`/React inline styles exigem `unsafe-inline` ou nonce). Documentar a decisão no README.
- **R6** — Teto de body: middleware ASGI `BodyLimitMiddleware` recusa `Content-Length > limite` com **413** antes do parse e aborta leitura por contagem quando sem `Content-Length`; limites: `256 KiB` default, `/account/transcriptions` `8 MiB + 64 KiB`, `/payments/stripe/webhook` `256 KiB` (já), `/game/new`/`/game/prologue` `64 KiB`. Resposta JSON `{"detail":"payload_too_large"}`.
- **R7** — Export da crônica: `filename` ASCII derivado por `unicodedata.normalize("NFKD")` + `[^A-Za-z0-9_-]` removido + `[:40]` (fallback `cronica`), e `filename*=UTF-8''<quote(name)>` para preservar o nome original; nunca 500. Mesmo tratamento em `/account/export` se o nome entrar no header (hoje fixo — só confirmar).
- **R8** — Nenhuma dessas mudanças altera o `GameResponse`; paridade POST/SSE preservada (headers aplicados pelo middleware).

### Fora de escopo

- Autenticação de `/health` (só `status/engine/git_sha/profile/hardened`).
- Rate limit por owner (SPEC-219); docs/OpenAPI (SPEC-218).

## 3. Design técnico

- **Arquivos alterados**
  - `api.py`: `prometheus_metrics` (R1–R3: `_metrics_authorized(request)`, `_MetricsSqlCache`), `_correlation_boundary` (R4), `CONTENT_SECURITY_POLICY` (R5), export (R7), registro de `BodyLimitMiddleware` (R6).
  - `observability/metrics.py`: gauge `rpg_metrics_db_error`.
  - `services/body_limit.py` (novo): `BodyLimitMiddleware(app, default_limit, per_path: dict[str, int])` ASGI puro (sem `BaseHTTPMiddleware`, para não bufferizar SSE).
  - `infra/`/docs do stack Prometheus (SPEC-106): `bearer_token` no scrape config; runbook `docs/spec197/runbooks/` ganha `RPG_METRICS_TOKEN`.
  - `tests/test_metrics_auth.py`, `tests/test_security_headers.py`, `tests/test_body_limit.py`, `tests/test_chronicle_export_filename.py` (novos); `tests/test_observability_stack.py` ajustado (token).
- **Assinaturas**
  ```python
  def _metrics_authorized(request: Request) -> bool
  class _MetricsSqlCache:  # ttl_s, snapshot(), refresh(pool)
  class BodyLimitMiddleware:  # __call__(scope, receive, send)
  def safe_attachment_filename(name: str, fallback: str = "cronica") -> tuple[str, str]  # (ascii, utf8_quoted)
  ```

## 4. Plano passo a passo

### Etapa 0 — Reprodução (vermelhos no HEAD)
1. **Testes:** `test_metrics_is_public_today` (perfil DB simulado, `GET /metrics` sem token = 200); `test_game_state_has_no_cache_control_today`; `test_export_unicode_name_500_today` (nome `Ωmega`); `test_oversized_json_body_is_parsed_today` (POST 2 MiB em `/auth/login` → 422, não 413).

### Etapa 1 — `/metrics` (R1–R3)
1. **Testes:** sem token → 404; token errado → 404; token certo → 200 `text/plain; version=0.0.4`; 2 scrapes em 15 s → 1 conexão (pool fake conta); DB falhando → 200 + `rpg_metrics_db_error 1`; legacy sem env → 200.
2. **Implementação:** §3. **Verificação:** `uv run pytest tests/test_metrics_auth.py tests/test_observability_stack.py -q`.

### Etapa 2 — Headers (R4, R5)
1. **Testes:** `/game/state`, `/account/balance`, `/auth/config` → `Cache-Control: no-store`; `/data/options` sem no-store; HSTS presente só com `RPG_COOKIE_SECURE=1`; CSP contém `form-action 'self'`; SSE mantém `no-cache, no-transform`.
2. **Implementação:** §3.

### Etapa 3 — Body limit (R6) e export (R7)
1. **Testes:** 413 com `Content-Length` acima; 413 por contagem sem `Content-Length` (chunked); STT 8 MiB passa; SSE/stream inalterado (teste existente de SSE); export com `Ωmega`, `José-Ângelo`, nome vazio → 200 + `filename="cronica_..."` ASCII + `filename*`.
2. **Implementação:** §3. **Verificação:** `uv run pytest -q` completo; `npm run build`.

## 5. Critérios de aceite
- [x] R1–R8 cobertos por `tests/test_surfaces_221.py`; `uv run pytest` verde (ver `docs/spec221/README.md`).
- [x] Smoke (substituído por smoke LOCAL equivalente, revisão Sol 2026-10-16 — staging remoto fora do escopo da onda): uvicorn perfil `local` contra Supabase local (Postgres :55322 + Auth) + 2º processo `legacy` p/ save MockLLM. `/metrics` 404 sem token/token errado, 200 com Bearer (gauges `rpg_db_pool`/`rpg_jobs` do Postgres real); `/game/state`, `/account/balance`, `/auth/config` → `no-store` (`/data/options` sem); HSTS só com `RPG_COOKIE_SECURE=1`; CSP com `form-action 'self'`; `Content-Length: 1 MiB` → 413 sem ler corpo; chunked 320 KiB → 413 `payload_too_large`; export `Ωmega José-Ângelo` → 200 `filename="cronica_megaJose-Angelo.txt"` + `filename*`. Transcrição: `docs/spec221/evidence/local_smoke.txt`.
- [x] Prometheus local (imagem `prom/prometheus:v3.13.2` do stack SPEC-106, config temporária com `authorization.credentials_file`, intervalo 2 s) → `up == 1`; após 45 s `min_over_time(up[40s]) == 1` com 20 amostras (scraper autenticado não cai no rate limit). Container removido em seguida.

## 6. Smoke test
Sem LLM: os 5 `curl` acima no staging + export da crônica de um personagem com nome Unicode (MockLLM local basta para gerar o save).

## 7. Riscos & compatibilidade
- **Scrape existente** quebra até configurar o token (documentar no runbook; `pg_cron` não scrapeia `/metrics`).
- **Body limit vs SSE**: middleware ASGI puro não toca em respostas; só conta `receive`. Testar `/game/action/stream`.
- **HSTS em domínio custom**: só com `RPG_COOKIE_SECURE=1`; `preload` fora por default.

## 8. Pontos de decisão do dono
- **D-A (HSTS preload):** **Default recomendado:** não incluir `preload` até domínio definitivo.
- **D-B (`unsafe-inline` em `style-src`):** migrar para nonce exige tocar `motion`/inline styles do React. **Default recomendado:** manter e registrar como dívida de hardening; `form-action 'self'` agora.
- **D-C (404 vs 401 em `/metrics`):** **Default recomendado:** 404 (não enumerável).

## 9. Evidência requerida
- Saída de `uv run pytest` + vermelhos da Etapa 0; transcrição dos `curl` do staging (headers, sem token impresso); `docs/secXX/README.md` com decisões D-A..D-C; `ESTADO_ATUAL.md`/`ROADMAP.md`.

## 10. Registro de execução (2026-10-16)

- Defaults de decisão: D-A sem `preload`; D-B `unsafe-inline` mantido (dívida); D-C 404.
- Desvios: (1) `RPG_METRICS_TOKEN` NÃO entrou em `HOSTED_SECURITY_REQUIREMENTS` (SPEC-218 não está na main);
  sem a env em perfil DB o `/metrics` simplesmente responde 404, sem afetar o boot. (2) Rate limit de
  `/metrics` é em memória por processo (SPEC-219 ausente). (3) Export da crônica já tinha `filename*` (SPEC-235);
  helper `safe_attachment_filename` unifica o fallback ASCII (NFKD, `[:40]`, fallback `cronica`).
  `/account/export` e audit-export (SPEC-207) têm filename fixo/pseudônimo ASCII, intocados.
- Revisão Sol (2026-10-16, independente): (a) **defeito corrigido** — o rate limit 12/min contava o
  scraper autenticado; o stack SPEC-106 raspa a cada 5 s (12/min exatos) → 429 intermitente/`up==0`.
  Agora só sondas sem token válido contam (teste `test_metrics_rate_limit_so_para_sondas...`).
  (b) webhook Stripe: teto do middleware 256→320 KiB para o handler (stream cru) aplicar o próprio
  413 de 256 KiB antes do corte do middleware (que entregaria corpo truncado ao handler).
  (c) auditoria de todos os POST/PUT/PATCH/DELETE: nenhum uso legítimo excede o teto; pior caso de
  `/game/new` com `scenario` (todos os campos no `max_length`, 4 B/char) < 64 KiB (teste novo).
  Nota: com upload ainda em curso, o 413 seguido de `connection: close` pode chegar ao cliente como
  RST (comportamento TCP normal; o servidor não lê o excedente).
- Smoke local + scrape Prometheus real executados (substituem o staging); ver §5.
