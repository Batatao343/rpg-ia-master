# SPEC-219 — Cota de custo por owner, cobertura do rate limit e IP real atrás de proxy

> **Status:** `in-progress` (17/10: todos os critérios próprios verdes no staging — R5 medido em 2 redes (ISP local + `pg_net` do Supabase), cap de texto R8 ligado com 32 turnos sem 503; código da SPEC-218 já está na `main`. Único pendente: a dependência SPEC-218 virar `done`, que espera itens do gate de release da SPEC-197 (páginas legais, riscos P0/P1, environments do GitHub, CI do sha). Ver `docs/staging-wave-2026-10-17/README.md`)
> **Criada:** 2026-10-15 · **Atualizada:** 2026-10-15
> **Depende de:** SPEC-218 `done` (processo exposto sempre em perfil DB) · evolui SPEC-182/185/196 `done` e SPEC-197 `in-progress` sem reabri-las (ordem final 2026-10-15)
> **Desbloqueia:** SPEC-212; gate da SPEC-197; follow-up de cobrança por turno (SPEC-185) (ordem final 2026-10-15)
> **Origem:** auditoria de segurança 2026-10-15 — achados PAG-01, LLM-04, SESS-02/AUTHZ-05/PAG-05, SESS-03/AUTHZ-04/PAG-03, AUTHZ-03, PAG-06
> **EXECUTOR_MODEL:** `Terra` (≡ Sonnet)
> **REVIEW_MODEL:** `Sol` (≡ Opus em contexto separado) · **REVIEW_REQUIRED:** `true` — toca caminho de custo real e fronteira anti-abuso
> **EVAL_AUTHORING_REQUIRED:** `false` — contratos determinísticos; medição empírica do IP no staging é evidência, não eval

---

## 1. Contexto & Objetivo

Os turnos de texto (`/game/action`, `/game/action/stream`, `/game/prologue`) são **gratuitos** para o jogador e não passam pela wallet (SPEC-185 deixou "ligar reserve→execute→settle às jogadas normais" para spec futura). O único freio é o rate limit por **IP** (30 req por janela) numa lista fechada de 8 rotas; o teto diário de gasto (SPEC-197 R7) é opt-in, reage só no cron e, por decisão documentada (R-11), **não cobre LLM de texto**. Conta: 1 conta/IP × 30 turnos/min × 1440 min ≈ 43.200 turnos/dia × US$ 0,0008–0,01 ≈ **US$ 35–430/dia por conta**; o saldo pré-pago do provider esgota e **todos** os jogadores caem para `FallbackLLM`/erro (negação de serviço financeira). Rotas com custo externo fora de qualquer limite: `/game/chronicle/search` (embedding Jina por request, operação "auxiliar" não liquidada), `/game/art/brief` (LLM), `/game/{id}/art/quote` (linhas imutáveis), `/account/checkout` (sessões Stripe), `/account/purchases/google/verify` (Play API).

Além disso, o IP vem de `request.client.host` sem tratamento de proxy. Atrás da Vercel/Railway isso pode ser o IP do edge (bucket único para todos — um atacante bloqueia login/signup/turnos de todo mundo) ou, se um dia for "corrigido" confiando em `X-Forwarded-For` cru, spoofável. E cada cookie `rpg_access` inválido gera uma chamada HTTP ao GoTrue sem pré-validação local nem cache — amplificação barata contra a cota do Auth.

Fatos observados no HEAD:

- [F] `api.py:790-831` `_rate_limit`: lista fixa `("/game/action","/game/action/stream","/game/new","/game/combat-simulator","/game/equip","/game/levelup","/game/prologue")` + `DELETE /game/save/*`; chave `f"ip:{pseudonym(ip)}"`, `ip = request.client.host`; `RPG_RATE_LIMIT` default 30, janela `_RATE_WINDOW_S`.
- [F] `services/account_security.py:81-91` `auth_limit`: IP=20 e e-mail=5 por 900 s, `remote = request.client.host`. `api.py:374` captcha `remoteip` idem.
- [F] grep `forwarded|proxy_headers|x-real-ip|x-vercel` em `api.py`, `infrastructure/`, `vercel_app.py` = 0 ocorrências. [H] comportamento de `client` no runtime Vercel não medido.
- [F] `services/daily_spend_cap.py:1-15` docstring: "Text-LLM spend is bounded by the providers' prepaid balances, NOT by this cap"; `CAP_SWITCHES = (IMAGE, STT_FALLBACK)`; só roda em `services/finops_job.py` (cron).
- [F] `api.py:3677-3707` `/game/chronicle/search` → `_meter_auxiliary_operation("chronicle_search")` → `semantic_candidates` (embedding por request), fora da lista do rate limit; `api.py:2369` `/game/art/brief`, `:2445` `art/quote`, `:2035` `checkout`, `:2113` `google/verify` idem. Só `/account/transcriptions` tem limite próprio por owner (5/min, `api.py:2199`).
- [F] `api.py:103-105` → `infrastructure/supabase_identity.py:146-160` `verify()` faz `GET /auth/v1/user` para QUALQUER string não vazia; sem cache, sem checagem local de formato/`exp`.
- [F] `infrastructure/postgres_turns.py` `PostgresRateLimiter.consume(key, limit, window_seconds)` já é atômico (`on conflict`) e é exigido em todo perfil DB (`runtime.validate`).
- [R] SPEC-197 R-11 (risk-register) reconhece a lacuna e delega "tetos nos dashboards dos provedores" ao dono — isso continua necessário, mas não substitui cota por owner.

Objetivo: (1) todo caminho com custo externo tem limite **por owner** (além do IP) com chave e política declaradas num único mapa; (2) cota diária de turnos por owner, barata (contador Postgres) e checada ANTES de `app.invoke`; (3) IP real derivado de header confiável só quando a plataforma o garante; (4) falhas de autenticação têm bucket próprio e `verify` pré-valida localmente.

## 2. Requisitos

- **R1** — `services/abuse_policy.py` (novo) define `ROUTE_CLASSES: dict[str, RouteClass]` com `RouteClass(name, matcher, ip_limit, owner_limit, window_s, daily_owner_quota | None)`. Classes mínimas: `turn` (`/game/action`, `/game/action/stream`, `/game/death`), `llm_aux` (`/game/new`, `/game/prologue`, `/game/art/brief`, `/game/combat-simulator`), `embedding` (`/game/chronicle/search`), `mutation` (`/game/equip`, `/game/levelup`, `DELETE /game/save/*`, `/game/*/art/*/quality`), `quote` (`/game/*/art/quote`, `/game/*/art/confirm`), `payments` (`/account/checkout`, `/account/purchases/google/verify`), `read_auth` (demais GET `/game|/account`). Matcher por regex compilada (ids UUID), não por lista de strings literais.
- **R2** — `_rate_limit` aplica, para a classe da rota: limite por IP (`ip:{pseudonym(ip)}:{class}`) E, quando há principal, limite por owner (`user:{owner}:{class}`). Defaults (configuráveis por env `RPG_LIMIT_<CLASS>_OWNER`/`_IP`): `turn` 20/min por owner, 60/min por IP; `llm_aux` 6/min owner; `embedding` 10/min owner; `quote` 10/min owner; `payments` 5/min owner e 3 ordens `created` abertas por owner (checado em `checkout()`); `mutation` 30/min owner; `read_auth` 120/min owner.
- **R3** — Cota diária por owner para `turn` + `llm_aux`: `RPG_DAILY_TURN_QUOTA` (default 600; `0` desliga). Contador `app.owner_daily_counters(owner_id, day, class, count)` incrementado por `INSERT … ON CONFLICT DO UPDATE … RETURNING count` ANTES de `app.invoke`; estourou → `429 {"detail":"daily_quota_exceeded","retry_after_seconds":…}` sem chamar LLM. Mesma transação curta e índice único `(owner_id, day, class)`; purge de linhas > 7 dias no cron existente (`/internal/cron/operations`).
- **R4** — `client_ip(request) -> str` em `services/abuse_policy.py`: se `VERCEL` setado → primeiro valor de `x-vercel-forwarded-for` (header definido pela plataforma, não sobrescrevível pelo cliente) senão `x-real-ip` da Vercel; se `RPG_TRUSTED_PROXY_HOPS=N>0` → N-ésimo valor da direita de `x-forwarded-for`; caso contrário `request.client.host`. Usada por `_rate_limit`, `auth_limit`, captcha `remoteip` e telemetria. Testes unitários cobrem os três modos e header ausente/malformado (fallback `client.host`, nunca exceção).
- **R5** — Medição empírica (evidência, não código): endpoint temporário de diagnóstico **não** — usar o log estruturado `rpg.http` já existente para registrar, no staging, `client.host` vs `x-vercel-forwarded-for` (pseudonimizados) em 2 requests de origens distintas; conclusão registrada no README da spec. Se `client.host` já for o IP real, R4 continua (defesa contra regressão); se for o do proxy, R4 corrige o bucket único.
- **R6** — Bucket de falha de autenticação: `_session_boundary` ao capturar `Unauthorized` consome `authfail:{ip}` (limite 60/15 min); acima disso responde 429 sem chamar o verificador. `/auth/login|signup|reset|verify` já têm `auth_limit` (inalterado).
- **R7** — Pré-validação local em `SupabaseIdentityVerifier.verify`: token deve ter 3 segmentos base64url, payload JSON com `exp` futuro (tolerância 60 s), `aud == "authenticated"` e `iss` com prefixo `{SUPABASE_URL}/auth/v1`; caso contrário `Unauthorized` SEM rede. Cache em memória `token_sha256 -> (Principal, verified_at)` por 20 s (configurável), invalidado por `logout`/`refresh` do mesmo processo. A validação final continua no GoTrue (assinatura/revogação) — a pré-checagem só corta lixo.
- **R8** — Cap diário (SPEC-197 R7) ganha: (a) leitura barata do estado de cap em memória (cache 30 s) consultada no caminho `turn`/`llm_aux` quando `RPG_DAILY_SPEND_CAP_BRL` definido e `RPG_DAILY_SPEND_CAP_TEXT=1`: excedido → 503 `daily_spend_cap` para novos turnos (sem desligar leitura/save); (b) `RPG_DAILY_SPEND_CAP_MODEL_SWITCHES` passa a aceitar `text` como atalho para todos os modelos de `ROUTES`. Default continua opt-in (decisão do dono, D-B).
- **R9** — Telemetria: métrica `rpg_rate_limited_total{class, scope=ip|owner|daily|authfail}` (labels fechados, sem ids) e log `rpg.abuse` pseudonimizado por decisão de bloqueio.
- **R10** — Paridade POST/SSE: `/game/action/stream` consome os mesmos buckets/cota que `/game/action` (uma vez por turno, não por chunk); replay por `action_id` existente (recibo) NÃO consome cota.
- **R11** — Perfil `legacy` mantém o limitador em memória atual (só IP, mesma lista de classes) — nada de Postgres.

### Fora de escopo

- Cobrar Estilhas por turno (decisão de produto; SPEC-185 follow-up) — esta spec só impede abuso gratuito.
- Alterar limites do Turnstile/GoTrue (SPEC-191/197).
- Lockout por e-mail e logout (SPEC-220).

## 3. Design técnico

- **Arquivos novos**
  - `services/abuse_policy.py`: `RouteClass`, `ROUTE_CLASSES`, `classify(method, path) -> RouteClass | None`, `client_ip(request)`, `limits_for(cls, env)`.
  - `supabase/migrations/2026MMDD_owner_daily_counters.sql`: tabela `app.owner_daily_counters(owner_id uuid, day date, class text, count int not null default 0, primary key(owner_id, day, class))`, RLS `enable+force`, sem grants a `anon/authenticated/rpg_api` (acesso só pelo backend), função `app.bump_daily_counter(owner uuid, cls text, max int) returns int` (`security invoker`), purge no cron.
  - `infrastructure/postgres_turns.py`: `PostgresDailyQuota.bump(owner_id, cls, limit) -> QuotaDecision(allowed, count, retry_after_seconds)`.
  - `tests/test_abuse_policy.py`, `tests/test_daily_quota_postgres.py` (marker Postgres local), `tests/test_session_boundary_authfail.py`.
- **Arquivos alterados**
  - `api.py`: `_rate_limit` reescrito sobre `classify`; cota diária em `/game/action`, `/game/action/stream`, `/game/prologue`, `/game/new`, `/game/art/brief` (helper `_enforce_turn_quota(principal)` chamado antes de `_run_turn_collected`); `_session_boundary` com `authfail`; `checkout()` com teto de ordens abertas; `/health` inalterado.
  - `services/account_security.py`: `auth_limit` e `validate_captcha` usam `client_ip`.
  - `infrastructure/supabase_identity.py`: pré-validação + cache (R7).
  - `services/daily_spend_cap.py`, `services/finops_job.py`, `services/kill_switches.py`: R8.
  - `observability/metrics.py`: nova métrica.
  - `web/src/http.ts` + `PlayScreen.tsx`: 429 com `daily_quota_exceeded`/`Retry-After` vira banner "cota diária atingida; volta em HH:MM" (sem retry automático).
- **Schemas**
  ```python
  class RouteClass(NamedTuple):
      name: str; pattern: re.Pattern[str]; methods: frozenset[str]
      ip_limit: int; owner_limit: int; window_s: int; daily_quota: bool
  class QuotaDecision(NamedTuple):
      allowed: bool; count: int; limit: int; retry_after_seconds: int
  ```
- **Resposta 429** (JSON, sem ids): `{"detail": "rate_limited" | "daily_quota_exceeded", "scope": "ip|owner|daily|authfail", "retry_after_seconds": N}` + header `Retry-After`.

## 4. Plano passo a passo

### Etapa 0 — Reprodução (vermelhos no HEAD)

1. **Testes:** `test_chronicle_search_has_no_rate_limit_today` (31 POSTs seguidos com MockLLM/embeddings offline → nenhum 429); `test_two_owners_same_ip_share_bucket_today` (owner B recebe 429 por causa de A); `test_invalid_cookie_hits_identity_verifier_every_time` (verifier mock conta 50 chamadas para 50 requests com `rpg_access=garbage`); `test_turn_quota_absent_today` (601 turnos sem 429 com limite de IP desligado). Registrar vermelho.

### Etapa 1 — `abuse_policy` + `_rate_limit` por classe/owner (R1, R2, R9, R10, R11)

1. **Testes** (`tests/test_abuse_policy.py`): classificação de cada rota (tabela parametrizada, inclui UUIDs e `DELETE`); limites por owner independentes por IP; SSE consome 1×; replay não consome; legacy continua em memória.
2. **Implementação:** §3.
3. **Verificação:** `uv run pytest tests/test_abuse_policy.py tests/test_api_*.py -q`.

### Etapa 2 — `client_ip` (R4) + medição no staging (R5)

1. **Testes:** três modos + fallback; `auth_limit`/captcha usam a função (spy).
2. **Implementação + medição:** deploy staging, 2 requests de redes distintas, ler `rpg.http` (pseudônimos) e registrar no README.

### Etapa 3 — Cota diária por owner (R3) + UI

1. **Testes:** `tests/test_daily_quota_postgres.py` (Postgres local): 600 ok, 601 → 429 com `retry_after_seconds` até 00:00 UTC; concorrência (2 threads, 1 conexão cada) nunca ultrapassa; purge. Node: `http.ts` trata 429 `daily_quota_exceeded`.
2. **Implementação:** migration, `PostgresDailyQuota`, helper em `api.py`, banner.

### Etapa 4 — `authfail` + pré-validação/cache do verifier (R6, R7)

1. **Testes:** `tests/test_session_boundary_authfail.py` (verifier chamado 0× para token malformado; 1× para 20 requests do mesmo token válido em 20 s; 61ª falha → 429); `tests/test_account_auth_transport.py` ganha caso "token com `aud` errado → 401 sem rede".
2. **Implementação:** §3.

### Etapa 5 — Cap de texto opt-in (R8)

1. **Testes:** `tests/test_spec197_daily_cap.py` ganha `text` em `MODEL_SWITCHES` e 503 no turno quando excedido com `RPG_DAILY_SPEND_CAP_TEXT=1`; sem a env, comportamento atual byte a byte.
2. **Implementação:** §3. **Verificação:** `uv run pytest -q` completo.

## 5. Critérios de aceite

- [x] Etapa 0 vermelha no HEAD e verde ao final; R1–R11 (exceto a medicao empirica R5) com testes verdes; `uv run pytest` completo verde (exit 0); Node (120 testes)/`npm run build` verdes.
- [x] Tabela de classes × limites publicada em `docs/spec219/README.md` e em `.env.example`.
- [x] Medição R5 registrada (qual header carrega o IP real na Vercel) e `client_ip` validada contra ela. **17/10:** 1ª rede — a chave do bucket `ip:<HMAC>` bate com o IP público do chamador. **17/10 (2ª rede):** `pg_net` do banco de staging (sa-east-1) e o ISP local, com `X-Forwarded-For`/`X-Real-IP` e até `X-Vercel-Forwarded-For` forjados, caem em baldes `authfail:` distintos e estáveis por rede (`650ecd..` ×2, `4bd80e..` ×3); nenhum é HMAC de valor forjado, dos IPs do edge, do IPv6 do servidor nem de `unknown` ⇒ `client_ip` vem do `x-vercel-forwarded-for` sobrescrito pela plataforma. O IPv4 literal de saída do `pg_net` não é legível sem eco de terceiros (prova diferencial; `evidence/spec219_r5_second_network.json`).
- [x] Playtest offline: o harness usa `app.invoke` (nao a API); cota e limites vivem em `api.py`/`_execute_action`, fora do grafo - sem impacto (confirmado por leitura; nao reexecutado).
- [x] Smoke staging: usuário A 21 turnos/min → 429 no 21º; usuário B no mesmo IP joga normalmente; token inválido não aparece nos logs do Supabase Auth; `/game/chronicle/search` 11º/min → 429. **Staging 17/10:** 20×200 + 429 no 21º (28,7 s, `Retry-After` 32, `scope=owner`); B no mesmo IP 200; token inválido 401 sem `GET /user` 401 no Auth; `chronicle/search` 10×200 + 429 (`Retry-After` 55).
- [x] Revisão Sol independente APPROVED (com 4 correcoes; `handoffs/SPEC-219-SOL-independent-review.md`).

### Pendente para fechar a spec (evidencia a gerar no staging pelo dono/coordenador)

- [x] Medicao R5: 2 redes distintas registradas no README e `client_ip` validada contra elas (via chave do balde, nao `rpg.http`: o log nao carrega IP). Ver acima.
- [x] Aplicar `20261017110000_owner_daily_counters.sql` no staging ANTES do deploy. **Staging 17/10:** aplicada antes do deploy; histórico 28/28.
- [x] Smoke staging (item acima) com a transcricao dos codigos/`Retry-After` e a metrica `rpg_rate_limited_total`. **Staging 17/10:** códigos/`Retry-After` transcritos no README da onda; `/metrics` exige `RPG_METRICS_TOKEN` (não configurado no staging), então a métrica foi evidenciada pelo log `rpg.abuse blocked class=turn|embedding scope=owner` emitido pelo mesmo `record_block` que incrementa `rpg_rate_limited_total`.
- [x] Revisao Sol independente APPROVED; parecer em `handoffs/SPEC-219-SOL-independent-review.md`.
- [ ] SPEC-218 (`done`) aterrissar na `main` antes desta. **17/10:** codigo da 218 ja esta na `main`; a 218 segue `in-progress` (so o `release/checklist.py --env staging` pendente por gate da SPEC-197), entao a 219 nao fecha ainda.

### Desvios / decisoes (defaults da spec usados)

D-A numeros da spec; D-B cap de texto OFF por padrao; D-C cache 20 s (so o GoTrue e cacheado - a checagem de sessao no banco roda a cada request, entao revogacao e imediata); D-D fora de escopo. `/game/art/brief` e `/game/combat-simulator` nao chamam LLM: so limite por minuto, sem cota diaria. Limite por owner de `/game/action*` fica dentro do handler (replay nao consome). Detalhes em `docs/spec219/README.md`.

## 6. Smoke test

Staging (custo mínimo, ~25 requests reais): login A/B; loop de turnos de A até 429; 1 turno de B OK; 11 buscas de crônica → 429; cookie lixo × 70 → 429 `authfail` a partir do 61º e zero chamadas no painel Auth; `checkout` 6× em 1 min → 429 no 6º (test mode, sem pagamento).

## 7. Riscos & compatibilidade

- **Falsos positivos para jogadores reais**: 20 turnos/min e 600/dia estão acima do p50 real (~15 s/turno ⇒ ~4/min, ~240/h teórico máximo). Ajustável por env sem deploy.
- **Harness/playtest** usa o grafo direto — sem impacto; smokes de API (`scripts/smoke_api.sh`, `audit_local_server.py`) precisam de limites altos via env de teste (documentar).
- **Serverless**: cota e buckets ficam no Postgres (já exigido); custo = 1 upsert por turno (desprezível vs. LLM).
- **Cache do verifier** (R7) atrasa em até 20 s a percepção de logout/revogação dentro do MESMO processo; `logout`/`refresh` invalidam localmente; aceitável (documentar) — ponto D-C.
- **Proxy desconhecido** (self-host): sem `RPG_TRUSTED_PROXY_HOPS`, comportamento atual (IP do proxy) — documentar no runbook de deploy.

## 8. Pontos de decisão do dono

- **D-A (números):** 20/min e 600/dia por owner para turnos; 6/min `llm_aux`; 10/min embedding/quote; 5/min payments. **Default recomendado:** adotar e revisar após 1 semana de beta com a métrica R9.
- **D-B (cap de texto):** ligar `RPG_DAILY_SPEND_CAP_TEXT=1` em produção (503 para novos turnos quando o cap diário global estoura). **Default recomendado:** ligar no beta pago, com cap em BRL definido pelo dono (R-11 continua pedindo tetos nos dashboards dos providers).
- **D-C (cache do verifier):** 20 s vs. 0 (sem cache, só pré-validação). **Default recomendado:** 20 s.
- **D-D (cobrança por turno):** fora desta spec; registrar se a cota diária gratuita deve virar "turnos gratuitos/dia + Estilhas depois" (SPEC-185 follow-up).

## 9. Evidência requerida

- Saída completa de `uv run pytest`; vermelhos da Etapa 0; Postgres local para `tests/test_daily_quota_postgres.py` (marker).
- README da spec com tabela de classes/limites, medição R5 (header real da Vercel, pseudonimizado), transcrição do smoke §6 (status codes + `Retry-After`), métrica `rpg_rate_limited_total` após o smoke.
- Parecer Sol em `handoffs/`; atualização de `docs/spec197/risk-register.md` R-11 (cota por owner implementada; tetos de provider continuam com o dono), `ESTADO_ATUAL.md`, `ROADMAP.md`.
