# SPEC-255 — Fila de jobs: logs por job (claim, sucesso, falha, retry, dead) e correlação com a requisição de origem

> **Status:** `in-progress` — implementada em `logs-p1` (REVIEW_REQUIRED; smoke staging pendente)
> **Criada:** 2026-10-18 · **Atualizada:** 2026-10-18
> **Depende de:** SPEC-240, SPEC-254
> **Desbloqueia:** SPEC-256
> **Origem:** auditoria de logs 2026-10-18 ([relatório](../docs/auditorias/logs-api-2026-10-18.md))
> **EXECUTOR_MODEL:** `Terra` (≡ Sonnet) · **REVIEW_MODEL:** `Sol` (≡ Opus, contexto separado) · **REVIEW_REQUIRED:** `true — payload de job (schema aditivo)`
> **EVAL_AUTHORING_REQUIRED:** `false`

Rótulos: **[F]** fato (com evidência `arquivo:linha` no commit `4d60cf7`) · **[R]** recomendação.

---

## 1. Contexto & Objetivo

**[F]** `workers/job_worker.py::_run` (`90-124`) não loga nada: exceção do handler vira `error_code` (`getattr(exc,"error_code","handler_error")`) e a classe se perde — a maioria das falhas fica `handler_error`; `LeaseHeld` é engolido 3× (`106-107,115-116,122-123`); `JobDeferred` só no banco. `postgres_jobs.py` move jobs para `dead` (`lease_expired_max_attempts`, `77-92`) só em SQL. `workers/drain.py` não conta falhas, então o cron reporta `ok` mesmo se todos os jobs morrerem. `JobRequest` (`infrastructure/contracts.py:164-170`) não carrega `request_id`; o worker não abre `correlation_scope` — um job de arquivamento/arte não se liga ao turno que o criou. Também silenciosos: `workers/run_worker.py:~57,87`, `blob_purge_jobs.py:40`, `projection_jobs.py` (falha só em `last_error_code`), `services/lease_heartbeat.py:38,61-66`.

**Objetivo:** tornar o debug desta área possível só com logs, sem reproduzir localmente — sem logar conteúdo de jogo nem dado pessoal.

## 2. Requisitos

- **R1** — `JobRequest` ganha `trace` opcional `{request_id, action_ref}` preenchido de `correlation()` no enqueue (campo aditivo no payload JSON; jobs antigos sem `trace` funcionam).
- **R2** — Worker abre `correlation_scope(job_id=, job_kind=, request_id=trace.request_id, action_ref=trace.action_ref)` e emite `job.started` (`debug`), `job.completed` (`info`, `duration_ms`, `attempt`), `job.failed` (`warning`, `error_type`, `error_code`, `attempt`, `will_retry`, `next_run_in_s`), `job.dead` (`error`), `job.deferred` (`info`, `reason`), `job.lease_lost` (`warning`).
- **R3** — `error_code` gravado no banco passa a ser `<error_code>` ou `exc:<ErrorClass>` (nunca só `handler_error`).
- **R4** — `drain_jobs` retorna `failed`, `dead`, `deferred`; o cron (SPEC-256) usa para `outcome`.
- **R5** — Expiração de lease que mata job (`postgres_jobs.py:77-92`) emite `job.dead reason=lease_expired_max_attempts` (via `RETURNING` dos ids afetados).

### Restrições transversais

- **Privacidade (SPEC-222):** nenhum campo novo carrega texto do jogador, narração, nome de personagem, e-mail, IP cru, token, cookie, DSN, URL assinada ou corpo de resposta de provider. Ids de usuário/jogo/ação só como pseudônimo (`observability.telemetry.pseudonym`, HMAC com `RPG_TELEMETRY_SECRET`). Exceções: só `type(exc).__name__` + código fechado; nunca `str(exc)`.
- **Formato:** toda linha nova via `log_event(area, event, ...)` (`rpg.<area>`, JSON `safe_json`); nada de `print` (teste AST `tests/test_no_print_in_production.py` continua verde).

### Fora de escopo

Mudar política de retry/backoff.

## 3. Design técnico

- **Alterados:** `infrastructure/contracts.py`, `infrastructure/postgres_jobs.py`, `workers/job_worker.py`, `workers/drain.py`, `workers/run_worker.py`, `workers/projection_jobs.py`, `workers/blob_purge_jobs.py`, `services/lease_heartbeat.py`.

## 4. Plano passo a passo

### Etapa 1 — Testes vermelhos

`tests/test_job_logging.py` (fila fake + Postgres local): `test_job_failure_logs_class_and_retry`, `test_job_inherits_request_id_from_enqueue`, `test_drain_counts_failures`, `test_lease_expiry_dead_logged`, `test_old_payload_without_trace_ok`.

### Etapa 2 — Implementação

R1–R5.

### Etapa 3 — Verificação

`uv run pytest` verde.

## 5. Critérios de aceite

- [x] Buscar um `request_id` de turno retorna também o job `project_archive` que ele gerou.
- [x] Nenhum job falha com `handler_error` genérico.
- [x] Teste de sentinela: nenhuma linha nova contém texto do jogador, e-mail, IP cru, token ou id cru.
- [x] `uv run pytest` verde (suíte completa offline).
- [x] Guard de FallbackLLM preservado em todo `with_structured_output` tocado.
- [x] Saves antigos continuam carregando.

## 6. Smoke test

1. Staging com `RPG_PROJECTION_MODE=post_response`: 1 turno ⇒ `job.completed kind=project_archive` com o mesmo `request_id` do turno.

## 7. Riscos & compatibilidade

- Payload de job: só ids de correlação, nada de conteúdo.
- Logs são aditivos: nenhum contrato de resposta muda, salvo onde a spec diz explicitamente.
- MockLLM/FallbackLLM: comportamento inalterado; só passa a ser visível em log.

## Execução (logs-p1, 2026-10-18)

Implementado: `JobRequest.trace` ({request_id, action_ref}, aditivo; vai em `payload._trace`, retirado no lease; jobs antigos sem trace funcionam), `JobWorker` abre `correlation_scope` com o request de origem e emite `job.started/completed/failed/dead/deferred/lease_lost` (`error_code` = código do handler ou `exc:<Classe>`, nunca só `handler_error`), `fail()` devolve `{status,next_run_in_s}`, `drain_jobs` retorna `failed/dead/deferred`, expiração de lease que mata job emite `job.dead reason=lease_expired_max_attempts`; falhas silenciosas de `run_worker`/`blob_purge_jobs` agora logam. Testes: `tests/test_job_logging.py`. Falta: Postgres local (`infra_local`), smoke de staging com `post_response` (§6) e a revisão Sol.
