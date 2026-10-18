# SPEC-247 — Turno: decisão do roteador (fonte+motivo), ciclo de vida do SSE e 409 de operação logados

> **Status:** `draft` — aguardando aprovação do dono. Prioridade sugerida: **P1**.
> **Criada:** 2026-10-18 · **Atualizada:** 2026-10-18
> **Depende de:** SPEC-240
> **Desbloqueia:** SPEC-262 (runbook “turno falhou”)
> **Origem:** auditoria de logs 2026-10-18 ([relatório](../docs/auditorias/logs-api-2026-10-18.md))
> **EXECUTOR_MODEL:** `Terra` (≡ Sonnet) · **REVIEW_MODEL:** `Sol` (≡ Opus, contexto separado) · **REVIEW_REQUIRED:** `false`
> **EVAL_AUTHORING_REQUIRED:** `false`

Rótulos: **[F]** fato (com evidência `arquivo:linha` no commit `4d60cf7`) · **[R]** recomendação.

---

## 1. Contexto & Objetivo

**[F]** A decisão do roteador só sai em `debug` e só com `route` (`agents/router.py:294`); gates (`_combat_gate`), `interlocutor.pre_classify`, atalho de recuperação e regex de história retornam sem log; o motivo de fallback do CLASSIFY fica só no estado (`router.py:266,272`) e o caso “não é RouterDecision” é silencioso (`270-272`). O `rpg.turn` tem a rota final mas não a **fonte** (gate/jev/classify) nem o motivo.

SSE (`api.py:4488-4586`): sem linha de início, sem linha de desconexão do cliente (só inferível de `outcome=client_gone` no `turn_delivery`), erros no meio do stream (`4552-4558`) e exceções do worker (`4528-4534`) não são logados ali; nada registra “worker seguiu após desconexão”. Os 409 de operação (`operation_in_progress`, `operation_conflict`, `stale_version`, replay idempotente — `api.py:3574`, `3600-3611`, `3677-3681`, `3715-3719`, `4831-4835`) não deixam linha.

**Objetivo:** tornar o debug desta área possível só com logs, sem reproduzir localmente — sem logar conteúdo de jogo nem dado pessoal.

## 2. Requisitos

- **R1** — `router.decision` em `info` com `route`, `source` (`combat_gate|interlocutor|recovery|story_regex|jev|classify|classify_fallback`), `fallback_reason` (código fechado), `jev_mode` (`off|shadow|primary`) e `target_kind` (tipo, não nome). O mesmo par `route_source`/`fallback_reason` entra no `rpg.turn`.
- **R2** — SSE: `sse.started` (transport, `action_ref`), `sse.client_disconnected` (fase em que caiu, ms desde início), `sse.worker_finished_after_disconnect` (outcome), `sse.error` (`code`, `error_type`). `turn_delivery` ganha `error_type` quando `outcome=error`.
- **R3** — 409/replay de operação: `operation.rejected` com `reason` (`operation_in_progress|operation_conflict|stale_version|pending_operation|request_mismatch`), `op_kind`, `op_ref` (pseudônimo); replay idempotente servido do recibo ⇒ `operation.replayed` (`info`).
- **R4** — Teste: um turno MockLLM em combate gera `router.decision source=combat_gate`; um turno com FallbackLLM no CLASSIFY gera `source=classify_fallback` com `fallback_reason`.

### Restrições transversais

- **Privacidade (SPEC-222):** nenhum campo novo carrega texto do jogador, narração, nome de personagem, e-mail, IP cru, token, cookie, DSN, URL assinada ou corpo de resposta de provider. Ids de usuário/jogo/ação só como pseudônimo (`observability.telemetry.pseudonym`, HMAC com `RPG_TELEMETRY_SECRET`). Exceções: só `type(exc).__name__` + código fechado; nunca `str(exc)`.
- **Formato:** toda linha nova via `log_event(area, event, ...)` (`rpg.<area>`, JSON `safe_json`); nada de `print` (teste AST `tests/test_no_print_in_production.py` continua verde).

### Fora de escopo

Logs por tentativa de LLM (SPEC-248); trace mecânico (SPEC-251).

## 3. Design técnico

- **Alterados:** `agents/router.py`, `api.py` (SSE generator/worker, handlers de operação, `_log_turn`).

## 4. Plano passo a passo

### Etapa 1 — Testes vermelhos

`tests/test_turn_trace_logs.py`: `test_router_decision_source_gate`, `test_router_classify_fallback_reason`, `test_sse_disconnect_logged`, `test_operation_conflict_logged`, `test_replay_logged`.

### Etapa 2 — Implementação

R1–R3.

### Etapa 3 — Verificação

`uv run pytest` verde.

## 5. Critérios de aceite

- [ ] Um turno é reconstruível por `action_ref`: decisão de rota (com fonte), LLMs, entrega SSE, desfecho.
- [ ] Todo 409 de operação tem linha com motivo.
- [ ] Teste de sentinela: nenhuma linha nova contém texto do jogador, e-mail, IP cru, token ou id cru.
- [ ] `uv run pytest` verde (suíte completa offline).
- [ ] Guard de FallbackLLM preservado em todo `with_structured_output` tocado.
- [ ] Saves antigos continuam carregando.

## 6. Smoke test

1. Staging: 1 turno SSE fechado no meio (Ctrl+C no curl) ⇒ `sse.client_disconnected` + `sse.worker_finished_after_disconnect`.

## 7. Riscos & compatibilidade

- Nenhum de privacidade (só enums/pseudônimos).
- Logs são aditivos: nenhum contrato de resposta muda, salvo onde a spec diz explicitamente.
- MockLLM/FallbackLLM: comportamento inalterado; só passa a ser visível em log.
