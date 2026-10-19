# SPEC-254 — Postgres: conflitos de lease/fencing/CAS, timeouts de pool/statement e queries lentas logados

> **Status:** `done` — revisão Sol APPROVED + smoke staging (2026-10-19, [handoff](../handoffs/LOGS-P1-SOL-review.md)).
> **Criada:** 2026-10-18 · **Atualizada:** 2026-10-18
> **Depende de:** SPEC-240
> **Desbloqueia:** SPEC-255
> **Origem:** auditoria de logs 2026-10-18 ([relatório](../docs/auditorias/logs-api-2026-10-18.md))
> **EXECUTOR_MODEL:** `Terra` (≡ Sonnet) · **REVIEW_MODEL:** `Sol` (≡ Opus, contexto separado) · **REVIEW_REQUIRED:** `true — caminho quente de toda requisição DB`
> **EVAL_AUTHORING_REQUIRED:** `false`

Rótulos: **[F]** fato (com evidência `arquivo:linha` no commit `4d60cf7`) · **[R]** recomendação.

---

## 1. Contexto & Objetivo

**[F]** `infrastructure/postgres_turns.py` e `postgres_jobs.py` não têm logger. Levantam sem log `LeaseHeld("game_busy")` (`postgres_turns.py:107`), `LeaseHeld("operation_in_progress")` (`140`), `StaleVersion` (`100`, `226`), `Conflict("idempotency …")` (`127-134`), `LeaseHeld("fencing token inválido")` (`199,340,411,485,509,549,566`), `LeaseHeld("worker atrasado…")` (`524`); `services/lease_heartbeat.py:40` `lease_lost` idem. `PostgresPool` (`infrastructure/postgres.py:61-98`) define `connect_timeout` 5 s, pool timeout 5 s, `statement_timeout` 15 s, `lock_timeout` 5 s — mas `PoolTimeout`, `QueryCanceled` e `LockNotAvailable` só propagam, sem log nem métrica; não há duração de query. O achado da SPEC-191 (handshake intermitente do Supavisor) só foi visto por medição manual.

**Objetivo:** tornar o debug desta área possível só com logs, sem reproduzir localmente — sem logar conteúdo de jogo nem dado pessoal.

## 2. Requisitos

- **R1** — `db.lease_conflict` (`warning`) com `reason` (`game_busy|operation_in_progress|fence_invalid|worker_late|lease_lost`), `op_kind`, `op_ref`, `game_ref`; `db.stale_version` e `db.idempotency_conflict` análogos.
- **R2** — `_checkout`: `db.pool_timeout` (`error`, `pool` = `request|admin`, `wait_ms`, `pool_size`, `in_use`); `db.connect_failed` (`error`, `error_type`, `attempt`) — sem host/DSN.
- **R3** — `QueryCanceled`/`LockNotAvailable` ⇒ `db.statement_timeout`/`db.lock_timeout` (`error`) com `query_name` (rótulo estático por chamada, nunca SQL nem parâmetros).
- **R4** — Métrica `rpg_db_query_seconds{query_name}` e `db.slow_query` (`warning`) acima de `RPG_DB_SLOW_MS` (default 500).
- **R5** — Teste: nenhum SQL, parâmetro, DSN ou host em log (sentinela no DSN de teste).

### Restrições transversais

- **Privacidade (SPEC-222):** nenhum campo novo carrega texto do jogador, narração, nome de personagem, e-mail, IP cru, token, cookie, DSN, URL assinada ou corpo de resposta de provider. Ids de usuário/jogo/ação só como pseudônimo (`observability.telemetry.pseudonym`, HMAC com `RPG_TELEMETRY_SECRET`). Exceções: só `type(exc).__name__` + código fechado; nunca `str(exc)`.
- **Formato:** toda linha nova via `log_event(area, event, ...)` (`rpg.<area>`, JSON `safe_json`); nada de `print` (teste AST `tests/test_no_print_in_production.py` continua verde).

### Fora de escopo

Mudar timeouts/pool; RLS (comportamento).

## 3. Design técnico

- **Alterados:** `infrastructure/postgres.py` (wrapper `timed(query_name)`), `postgres_turns.py`, `postgres_jobs.py`, `services/lease_heartbeat.py`.

## 4. Plano passo a passo

### Etapa 1 — Testes vermelhos

`tests/test_db_logging.py` (unit com fakes) + marker Postgres local: `test_pool_timeout_logged`, `test_fence_conflict_logged`, `test_statement_timeout_logged`, `test_no_sql_or_dsn_in_logs`.

### Etapa 2 — Implementação

R1–R5.

### Etapa 3 — Verificação

`uv run pytest` verde (+ `-m infra_local` quando disponível).

## 5. Critérios de aceite

- [x] Todo 409 de lease/versão tem causa DB em log.
- [x] Timeouts de pool/statement visíveis com `query_name`.
- [x] Teste de sentinela: nenhuma linha nova contém texto do jogador, e-mail, IP cru, token ou id cru.
- [x] `uv run pytest` verde (suíte completa offline).
- [x] Guard de FallbackLLM preservado em todo `with_structured_output` tocado.
- [x] Saves antigos continuam carregando.

## 6. Smoke test

1. Staging: 2 turnos concorrentes no mesmo jogo ⇒ `db.lease_conflict reason=game_busy`; checar `rpg_db_query_seconds` no `/metrics`.

## 7. Riscos & compatibilidade

- Overhead de medição mínimo; `query_name` estático evita cardinalidade alta.
- Logs são aditivos: nenhum contrato de resposta muda, salvo onde a spec diz explicitamente.
- MockLLM/FallbackLLM: comportamento inalterado; só passa a ser visível em log.

## Execução (logs-p1, 2026-10-18)

Implementado: `infrastructure/db_log.py` (`db.lease_conflict`/`db.stale_version`/`db.idempotency_conflict` com motivo fechado e pseudônimos, `db.pool_timeout`/`db.connect_failed`/`db.statement_timeout`/`db.lock_timeout`/`db.slow_query`, métrica `rpg_db_query_seconds{query_name}` e decorator `timed_call`); `PostgresPool._checkout` loga falha de checkout (pool request|admin, wait_ms, tamanho) e timeouts de query; todos os `raise LeaseHeld/StaleVersion/Conflict(idempotency…)` de `postgres_turns.py`/`postgres_jobs.py`/`lease_heartbeat.py` ganham a linha de causa antes de levantar (teste AST). Testes: `tests/test_db_logging.py` (pool com DSN inválido, fakes, sentinelas). Este commit também carrega o campo aditivo `JobRequest.trace` e o split de `_trace` em `postgres_jobs.py` (usados pela SPEC-255, commit seguinte). Falta: execução contra Postgres local (`-m infra_local`, sem Docker aqui), o smoke de staging (§6) e a revisão Sol.
