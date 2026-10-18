# SPEC-239 — Configuração central de logging (handler JSON para todo `rpg.*`)

> **Status:** `in-progress` — implementado em 2026-10-18 (branch `logs-p0`); falta a revisão Sol obrigatória e o smoke em staging.
> **Criada:** 2026-10-18 · **Atualizada:** 2026-10-18
> **Depende de:** nenhuma
> **Desbloqueia:** todas as specs 240–262 (sem isto, linhas `info` nunca chegam à Vercel)
> **Origem:** auditoria de logs 2026-10-18 ([relatório](../docs/auditorias/logs-api-2026-10-18.md))
> **EXECUTOR_MODEL:** `Terra` (≡ Sonnet) · **REVIEW_MODEL:** `Sol` (≡ Opus, contexto separado) · **REVIEW_REQUIRED:** `true — muda o que vai para stdout em produção (volume/custo de log)`
> **EVAL_AUTHORING_REQUIRED:** `false`

Rótulos: **[F]** fato (com evidência `arquivo:linha` no commit `4d60cf7`) · **[R]** recomendação.

---

## 1. Contexto & Objetivo

**[F]** Hoje só o logger `rpg.turn` tem handler e nível (`api.py:832-838`: `StreamHandler(sys.stderr)`, `setLevel(INFO)`, `propagate=False`). Não existe `basicConfig`/`dictConfig` no caminho de produção (o único `basicConfig` é o CLI de `rag.py:1459`); `vercel_app.py` só chama `apply_serverless_defaults()` e importa `api`. Resultado: todo `log_event(..., level="info"|"debug")` (`observability/telemetry.py:93-101`) cai no root logger (nível WARNING) e é **descartado** — por exemplo `jev.*` (SPEC-217, `services/jev_rollout.py:100-106`), `combat.started`, `api.character_create`, `rpg.cron` em sucesso (`services/cron_internal.py:57-66`). Warnings/errors saem pelo `lastResort` do `logging`, sem formatter nem garantia de uma linha JSON por evento.

Há ainda divergência de chave: `rpg.turn` usa `"evt"` (`api.py:4002`, `4473`, `2142`) e `log_event` usa `"event"`; `observability/latency.py:145` usa `logging.getLogger(__name__)`; `services/abuse_policy.py:168-181` loga string `%s` sem JSON. Objetivo: uma configuração única, idempotente, que todo entrypoint (API, Vercel, workers, CLI de scripts) aplica, com nível por env e saída JSON uniforme.

**Objetivo:** tornar o debug desta área possível só com logs, sem reproduzir localmente — sem logar conteúdo de jogo nem dado pessoal.

## 2. Requisitos

- **R1** — Novo `observability/logging_setup.py::configure_logging(env=os.environ) -> None`, idempotente (2ª chamada não duplica handler). Configura o logger `rpg` (pai de `rpg.*`) com um `StreamHandler(sys.stdout)` e `propagate=False`; `rpg.turn` deixa de ter handler próprio e passa a herdar (sem linha duplicada).
- **R2** — Nível via `RPG_LOG_LEVEL` (`debug|info|warning|error`, default `info`); valor inválido ⇒ `info` + uma linha `logging.config_invalid_level`. Override por área opcional `RPG_LOG_LEVEL_<AREA>` (ex.: `RPG_LOG_LEVEL_LIBRARIAN=warning`).
- **R3** — Formatter JSON: se a mensagem já é JSON (`safe_json`), é emitida como está acrescida de `level`, `logger`, `ts` (ISO-8601 UTC ms); se não é JSON (logs legados `%s`), vira `{"event": "<logger>.legacy", "message": <redact(msg)>}`. Uma linha por registro; quebras de linha escapadas.
- **R4** — Chave canônica `event` em todas as linhas: `rpg.turn` passa a emitir `"event": "turn"|"turn_delivery"|"client_latency"` mantendo `evt` como alias por 1 release (dashboards/alertas existentes).
- **R5** — `configure_logging()` é chamado em `api.py` (import), `vercel_app.py`, `workers/*` entrypoints e `scripts/*` que já usam `log_event`; `rag.py:1459` passa a usá-lo.
- **R6** — Teste de contrato: com `RPG_LOG_LEVEL=info`, `log_event("jev","shadow",level="info")` aparece em stdout como 1 linha JSON parseável com `event`, `level`, `logger`, `ts`; com `warning`, não aparece.

### Restrições transversais

- **Privacidade (SPEC-222):** nenhum campo novo carrega texto do jogador, narração, nome de personagem, e-mail, IP cru, token, cookie, DSN, URL assinada ou corpo de resposta de provider. Ids de usuário/jogo/ação só como pseudônimo (`observability.telemetry.pseudonym`, HMAC com `RPG_TELEMETRY_SECRET`). Exceções: só `type(exc).__name__` + código fechado; nunca `str(exc)`.
- **Formato:** toda linha nova via `log_event(area, event, ...)` (`rpg.<area>`, JSON `safe_json`); nada de `print` (teste AST `tests/test_no_print_in_production.py` continua verde).

### Fora de escopo

Sampling/limites de volume (SPEC-262 decide retenção/drain); correlação automática (SPEC-240).

## 3. Design técnico

- **Novo:** `observability/logging_setup.py` (`configure_logging`, `JsonLineFormatter`).
- **Alterados:** `api.py:832-838` (remove handler manual de `rpg.turn`; `evt`→`event`+alias), `vercel_app.py`, `rag.py:1459`, `services/abuse_policy.py` (passa a `log_event`, ver SPEC-246), `observability/latency.py:145` (`rpg.latency`).

## 4. Plano passo a passo

### Etapa 1 — Testes vermelhos

`tests/test_logging_setup.py`: `test_info_event_reaches_stdout`, `test_idempotent_no_duplicate_lines`, `test_invalid_level_falls_back_info`, `test_legacy_string_wrapped_and_redacted` (mensagem com e-mail vira `[EMAIL]`), `test_turn_line_has_event_key`.

### Etapa 2 — Implementação

módulo + chamadas nos entrypoints; remover handler manual do `rpg.turn`.

### Etapa 3 — Verificação

`uv run pytest` verde; `uv run uvicorn api:app` + 1 turno MockLLM: stdout mostra `combat.*`/`router.*` info em JSON.

## 5. Critérios de aceite

- [x] Toda linha `rpg.*` em stdout é JSON com `event`, `level`, `logger`, `ts`.
- [x] Nenhuma linha duplicada de `rpg.turn`.
- [x] `RPG_LOG_LEVEL` documentado em `.env.example`.
- [x] Teste de sentinela: nenhuma linha nova contém texto do jogador, e-mail, IP cru, token ou id cru.
- [x] `uv run pytest` verde (suíte completa offline).
- [x] Guard de FallbackLLM preservado em todo `with_structured_output` tocado.
- [x] Saves antigos continuam carregando.

## 6. Smoke test

1. Deploy em staging com `RPG_LOG_LEVEL=info`; 1 turno real.
2. `npx vercel logs --since 5m` mostra `jev.*` (se modo shadow/primary) e `rpg.turn` como JSON.
3. Medir linhas/turno (anotar no README da spec para a decisão de volume da SPEC-262).

## 7. Riscos & compatibilidade

- Volume de log sobe (info passa a sair): medir no smoke; `RPG_LOG_LEVEL=warning` é o rollback sem deploy de código.
- Logs são aditivos: nenhum contrato de resposta muda, salvo onde a spec diz explicitamente.
- MockLLM/FallbackLLM: comportamento inalterado; só passa a ser visível em log.

## 8. Notas de implementação

- `configure_logging()` em `observability/logging_setup.py` (handler stdout JSON dinamico, idempotente, `RPG_LOG_LEVEL` e `RPG_LOG_LEVEL_<AREA>`); chamado em `api.py`, `vercel_app.py`, `workers/run_worker.py`, `rag.py` (CLI).
- `propagate=False` em producao; `RPG_LOG_PROPAGATE=1` (setado em `tests/conftest.py`) deixa o caplog ver os registros.
- `rpg.turn` agora emite `event` e mantem `evt` como alias (1 release). `abuse_policy.record_block` passou a `log_event('abuse','blocked')` (campos `owner_ref`/`ip_ref` pseudonimos).
- Excecao em log legado: so `error_type` (sem traceback/mensagem).
- Pendente: smoke em staging (linhas/turno) e revisao Sol.
