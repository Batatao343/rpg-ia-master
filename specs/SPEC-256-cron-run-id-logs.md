# SPEC-256 — Crons: run_id, linha de início, falhas por item e autenticação rejeitada

> **Status:** `draft` — aguardando aprovação do dono. Prioridade sugerida: **P2**.
> **Criada:** 2026-10-18 · **Atualizada:** 2026-10-18
> **Depende de:** SPEC-255
> **Desbloqueia:** SPEC-262
> **Origem:** auditoria de logs 2026-10-18 ([relatório](../docs/auditorias/logs-api-2026-10-18.md))
> **EXECUTOR_MODEL:** `Terra` (≡ Sonnet) · **REVIEW_MODEL:** `Sol` (≡ Opus, contexto separado) · **REVIEW_REQUIRED:** `false`
> **EVAL_AUTHORING_REQUIRED:** `false`

Rótulos: **[F]** fato (com evidência `arquivo:linha` no commit `4d60cf7`) · **[R]** recomendação.

---

## 1. Contexto & Objetivo

**[F]** `services/cron_internal.py::_record` (`57-66`) emite 1 linha no fim (task, outcome, duração, contadores) — sem `run_id`, sem linha de início; exceção vira `error_type` + 500 opaco `cron_task_failed` (`74-75`). `_failures` (`25`) é memória do processo: em serverless o “3 falhas consecutivas ⇒ ERROR” zera a cada cold start. 401/503 de autorização (`29-37`) não logam. Silenciosos: varredura de wallet em `/operations` (`128-129`), `_finops_recorder` (`180-181`), falhas por owner em `/account-deletions` (`100-109`, `scripts/recover_account_deletions.py:48`), `services/wallet_recovery.py:117-118,143-145`.

**Objetivo:** tornar o debug desta área possível só com logs, sem reproduzir localmente — sem logar conteúdo de jogo nem dado pessoal.

## 2. Requisitos

- **R1** — Cada execução gera `run_id` (uuid curto) na correlação; `cron.started` (`info`) e `cron.finished` (já existente, ganha `run_id`).
- **R2** — Falha da task: `cron.failed` com `error_type` + stack resumida (helper da SPEC-241).
- **R3** — Contagem de falhas consecutivas persistida (tabela existente `app.cron_health_alerts` ou nova coluna) — não em memória; nível `error` a partir de 3 consecutivas entre instâncias.
- **R4** — Itens: `cron.item_failed` (`warning`) com `task`, `item_kind` (`account_deletion|wallet_reservation|finops`), `item_ref` (pseudônimo), `error_type` — nos sites silenciosos listados.
- **R5** — `cron.auth_rejected` (`warning`, `reason` `missing|invalid|not_configured`).

### Restrições transversais

- **Privacidade (SPEC-222):** nenhum campo novo carrega texto do jogador, narração, nome de personagem, e-mail, IP cru, token, cookie, DSN, URL assinada ou corpo de resposta de provider. Ids de usuário/jogo/ação só como pseudônimo (`observability.telemetry.pseudonym`, HMAC com `RPG_TELEMETRY_SECRET`). Exceções: só `type(exc).__name__` + código fechado; nunca `str(exc)`.
- **Formato:** toda linha nova via `log_event(area, event, ...)` (`rpg.<area>`, JSON `safe_json`); nada de `print` (teste AST `tests/test_no_print_in_production.py` continua verde).

### Fora de escopo

Agenda dos crons (pg_cron).

## 3. Design técnico

- **Alterados:** `services/cron_internal.py`, `services/wallet_recovery.py`, `scripts/recover_account_deletions.py`.

## 4. Plano passo a passo

### Etapa 1 — Testes vermelhos

`tests/test_cron_logging.py`: `test_run_id_on_start_and_finish`, `test_item_failure_logged`, `test_consecutive_failures_persisted`, `test_auth_rejected_logged`.

### Etapa 2 — Implementação

R1–R5.

### Etapa 3 — Verificação

`uv run pytest` verde.

## 5. Critérios de aceite

- [ ] Toda execução de cron reconstruível por `run_id`.
- [ ] Falhas por item nunca silenciosas.
- [ ] Teste de sentinela: nenhuma linha nova contém texto do jogador, e-mail, IP cru, token ou id cru.
- [ ] `uv run pytest` verde (suíte completa offline).
- [ ] Guard de FallbackLLM preservado em todo `with_structured_output` tocado.
- [ ] Saves antigos continuam carregando.

## 6. Smoke test

1. Staging: disparar `/internal/cron/jobs` manualmente com o Bearer ⇒ `cron.started`/`cron.finished` com mesmo `run_id`; chamada sem Bearer ⇒ `cron.auth_rejected`.

## 7. Riscos & compatibilidade

- Nenhum.
- Logs são aditivos: nenhum contrato de resposta muda, salvo onde a spec diz explicitamente.
- MockLLM/FallbackLLM: comportamento inalterado; só passa a ser visível em log.
