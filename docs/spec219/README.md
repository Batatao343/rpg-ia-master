# SPEC-219 - evidencia

## O que mudou
- `services/abuse_policy.py` (novo): `ROUTE_CLASSES` (regex), `classify`, `limits_for` (env), `client_ip`,
  `MemoryDailyQuota`, `QuotaDecision`, `record_block` (metrica `rpg_rate_limited_total{class,scope}` + log `rpg.abuse`).
- `api.py`: `_rate_limit` (middleware, outer) aplica o limite por IP da CLASSE; `_session_boundary` aplica o limite
  por owner (`_owner_rate_limit`) e o balde `authfail` (60/15 min por IP, consumido na falha; IP bloqueado nao chama
  o verificador); `_enforce_owner_budget` (cap de texto R8 -> owner/min -> cota diaria) e chamado em `_execute_action`
  (POST e SSE compartilham; DEPOIS do replay por `action_id`, que nunca consome), `new_game` (dentro do `try`, falha
  encerra o claim) e `game_prologue`; `QuotaExceeded` (429/503 com corpo `{detail, scope, retry_after_seconds}` e
  `Retry-After`; no SSE vai no evento `error`); checkout recusa a 4a ordem aberta (`OpenOrdersLimit` -> 429).
- `infrastructure/supabase_identity.py`: pre-validacao local (3 segmentos, `exp`+60 s, `aud`, `iss`) e cache de 20 s
  (`RPG_VERIFY_CACHE_SECONDS`), invalidado por logout/refresh/revoke_all/delete_user.
- `infrastructure/postgres_turns.py`: `PostgresDailyQuota`; `runtime.daily_quota` (so perfis DB).
- Migration `supabase/migrations/20261017110000_owner_daily_counters.sql` (tabela + `app.bump_daily_counter`, RLS
  enable+force, sem grants a anon/authenticated/rpg_api, `grant_runtime_access()`); purge de 7 dias no cron
  `/internal/cron/operations` (`services/retention.py`); tabela entra em `PRIVATE_TABLES`/export (exclusao de conta).
  Aplicar a migration antes do deploy e o recomendado; sem ela o codigo e seguro: o contador falha aberto (log `daily_quota_unavailable`) e export/exclusao de conta pulam a tabela ausente (`OPTIONAL_TABLES`, revisao Sol).
- `services/daily_spend_cap.py`: atalho `text` em `RPG_DAILY_SPEND_CAP_MODEL_SWITCHES` (todos os modelos de ROUTES) e
  `text_cap_exceeded` (cache 30 s, fail-open) com `RPG_DAILY_SPEND_CAP_TEXT=1`; default OFF byte a byte.
- Frontend: `web/src/http.ts` (`rateLimitNotice`, `HttpError.retryAfterSeconds`), `api.ts` (SSE): banner "Cota diaria
  de turnos atingida; volta as HH:MM.", sem retry automatico.

## Tabela de classes (por minuto; override `RPG_LIMIT_<CLASSE>_IP|_OWNER`, 0 desliga o escopo)
| Classe | Rotas | IP | Owner | Cota diaria |
|---|---|---|---|---|
| turn | POST /game/action, /game/action/stream, /game/death | 60 | 20 (replay nao consome) | sim (600; so action/stream) |
| llm_aux | POST /game/new, /prologue, /art/brief, /combat-simulator | 30 | 6 | sim (new, prologue) |
| embedding | POST /game/chronicle/search | 30 | 10 | - |
| quote | POST /game/{id}/art/quote, /confirm, /player/confirm | 30 | 10 | - |
| mutation | POST equip, levelup, cards/prepare, art/{id}/quality; DELETE save | 60 | 30 | - |
| payments | POST /account/checkout, /purchases/google/verify | 15 | 5 (+3 ordens abertas) | - |
| export | GET /account/export, POST /game/{id}/audit-export | 30 | 6 | - |
| stt | POST /account/transcriptions | 30 | 5 (handler proprio) | - |
| read_auth | demais GET /game, /account | 300 | 120 | - |
| latency | POST /telemetry/client-latency | 30 | - | - |
`RPG_RATE_LIMIT=N` fixa o IP de todas as classes (menos read_auth); `0` desliga TODO limite por minuto (suite/smoke).
Perfil `legacy`: so IP, em memoria (R11). Cota diaria: `RPG_DAILY_TURN_QUOTA` (600; 0 desliga), dia UTC.

## Testes
`tests/test_abuse_policy.py` (classificacao + anti-esquecimento de rota, limites, `client_ip` nos 3 modos, API em
perfil DB com owners A/B no mesmo IP, authfail, replay, SSE=1x, cota), `tests/test_session_boundary_authfail.py`
(pre-validacao/cache do verificador), `tests/test_daily_quota_postgres.py` (`-m infra_local`, Postgres local:
limite, recusa nao consome, 2 threads nunca ultrapassam, RLS/privilegios, purge, migration idempotente),
`tests/test_spec197_daily_cap.py` (+5, R8), `web/tests/http.test.mjs` (+2). Vermelhos no HEAD: os testes de API
falham com `AttributeError` (sem `_enforce_owner_budget`/`_authfail_until`), o de busca de cronica nunca recebia 429.

## Desvios e defaults (decisoes do dono usadas)
D-A numeros da spec; D-B cap de texto OFF por padrao (ligar com `RPG_DAILY_SPEND_CAP_TEXT=1` + cap em BRL);
D-C cache do verificador 20 s; D-D cobranca por turno fora de escopo.
- `/game/art/brief` e deterministico (`provider_called=false`): entra em `llm_aux` so pelo limite por minuto, sem cota diaria.
  `/game/combat-simulator` idem (sem LLM). `/game/death` e turno so por minuto/IP.
- O limite por owner de `/game/action*` e checado dentro do handler (apos o replay) e nao no middleware.
- `authfail`: bloqueio pre-verificador usa memoria do processo (alimentada pelo balde compartilhado); instancias frias
  podem deixar passar ate a proxima falha (que consome o balde compartilhado e bloqueia).
- Contador de cota indisponivel => falha aberta com log `daily_quota_unavailable` (nao derruba o jogo).

## Pendente (evidencia que o dono/coordenador precisa gerar - NAO feita aqui)
- Medicao R5 no staging Vercel: ler `rpg.http` e comparar `client.host` vs `x-vercel-forwarded-for` em 2 requests de redes distintas; registrar aqui.
- Smoke staging (spec 6): A 21 turnos/min -> 429; B no mesmo IP joga; cookie lixo x70 -> 429 authfail a partir do 61o e
  zero chamadas no painel Auth; busca de cronica 11a -> 429; checkout 6x -> 429 no 6o; metrica `rpg_rate_limited_total`.
- Aplicar a migration no staging; revisao Sol independente; `docs/spec197/risk-register.md` R-11 (ver nota).

## Revisao Sol independente (17/10) - APPROVED com correcoes
Parecer: `handoffs/SPEC-219-SOL-independent-review.md`. Correcoes: (1) export/exclusao de conta toleram a tabela
`owner_daily_counters` ausente (deploy antes da migration); (2) payload JWT profundamente aninhado ou > 8 KiB vira 401 (antes
`RecursionError` -> 500 sem passar pelo balde `authfail`); (3) o cache de 20 s nunca aceita token depois do `exp`; (4) request sem
cookie `rpg_access` nao consome o balde `authfail` (visitante deslogado atras de NAT nao bloqueia o IP). Teste de retencao
local atualizado para a regra nova. Falha pre-existente `test_stale_jwt_denied_in_backend_direct_wallet_and_storage` (storage
owner B) reproduz na base SPEC-218 sem esta mudanca (estado do Supabase local compartilhado).
