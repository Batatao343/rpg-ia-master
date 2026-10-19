# SPEC-248 — LLM: tentativas, fallbacks, circuito e ativação de Mock/FallbackLLM em log estruturado

> **Status:** `done` — revisão Sol APPROVED + smoke staging (2026-10-19, [handoff](../handoffs/LOGS-P1-SOL-review.md)).
> **Criada:** 2026-10-18 · **Atualizada:** 2026-10-18
> **Depende de:** SPEC-239, SPEC-240
> **Desbloqueia:** SPEC-262 (runbook provider fora)
> **Origem:** auditoria de logs 2026-10-18 ([relatório](../docs/auditorias/logs-api-2026-10-18.md))
> **EXECUTOR_MODEL:** `Terra` (≡ Sonnet) · **REVIEW_MODEL:** `Sol` (≡ Opus, contexto separado) · **REVIEW_REQUIRED:** `false`
> **EVAL_AUTHORING_REQUIRED:** `false`

Rótulos: **[F]** fato (com evidência `arquivo:linha` no commit `4d60cf7`) · **[R]** recomendação.

---

## 1. Contexto & Objetivo

**[F]** `RoutedLLM` loga texto livre em `rpg.llm` (`llm_setup.py:744,764,801,824-829,860,944,980,1011`) só com `provider:model (ErrorClass)` — sem tier, latência, status HTTP, `fell_back` ou `request_id`. O evento rico (`LLMAttemptEvent`: provider/model/tier/attempt/latency/outcome/usage) só vai para o hook (`api.py:912-956`) que alimenta métricas e o agregado do `rpg.turn` — que não tem classe de erro nem status por tentativa. Skip por circuito aberto (`llm_setup.py:725-735`) e por kill switch (`719-721`) não geram linha. A escolha de **MockLLM** (`llm_setup.py:1068-1101`: `RPG_FORCE_MOCK`, sem chave, Gemini sem chave) e de **FallbackLLM** é silenciosa — um deploy sem chaves vira jogo simulado sem nenhuma linha de alerta. `RPG_ROUTES` inválido loga texto (`1033`).

**Objetivo:** tornar o debug desta área possível só com logs, sem reproduzir localmente — sem logar conteúdo de jogo nem dado pessoal.

## 2. Requisitos

- **R1** — Cada tentativa vira `llm.attempt` (nível `debug` em sucesso, `warning` em falha) com `provider`, `model`, `tier`, `node` (nó do grafo, via contexto), `attempt_index`, `outcome` (`success|error|invalid_structured|circuit_open|kill_switch|stream_interrupted`), `http_status` (de `openai.APIStatusError`/`httpx` quando houver; senão 0), `error_type`, `structured_failure_code`, `latency_ms`, `fell_back`, `cost_basis`. Substitui as strings `_LOG.warning`.
- **R2** — `llm.exhausted` (`error`) quando todos os candidatos de um tier falham: `tier`, `node`, lista de `(provider, outcome)`.
- **R3** — `llm.mock_selected` (`warning`; `error` se `RPG_RUNTIME_PROFILE` ≠ `legacy`) com `reason` (`force_mock|no_keys|legacy_gemini_no_key`) e `llm.fallback_llm_selected` (`error`) com `reason`; emitidos 1× por processo por motivo.
- **R4** — `rpg.turn` ganha `llm_errors` (contagem por `error_type`, top 5) e `llm_http_statuses` (contagem por status).
- **R5** — `RPG_ROUTES` inválido ⇒ `llm.routes_invalid` com `error_type` (nunca o JSON da env).

### Restrições transversais

- **Privacidade (SPEC-222):** nenhum campo novo carrega texto do jogador, narração, nome de personagem, e-mail, IP cru, token, cookie, DSN, URL assinada ou corpo de resposta de provider. Ids de usuário/jogo/ação só como pseudônimo (`observability.telemetry.pseudonym`, HMAC com `RPG_TELEMETRY_SECRET`). Exceções: só `type(exc).__name__` + código fechado; nunca `str(exc)`.
- **Formato:** toda linha nova via `log_event(area, event, ...)` (`rpg.<area>`, JSON `safe_json`); nada de `print` (teste AST `tests/test_no_print_in_production.py` continua verde).

### Fora de escopo

Mudar ordem de ROUTES/timeout; embeddings (SPEC-258).

## 3. Design técnico

- **Alterados:** `llm_setup.py` (`RoutedLLM` invoke/stream/apply, `get_llm`), `api.py` (`_llm_log_fields`). `node` vem de um contextvar setado pelos nós (helper `observability.telemetry.node_scope(name)` usado em `main.py` wrappers).

## 4. Plano passo a passo

### Etapa 1 — Testes vermelhos

`tests/test_llm_logging.py`: `test_failed_attempt_logs_status_and_latency` (fake 429), `test_circuit_open_logged`, `test_mock_selected_logged_once`, `test_exhausted_logged_with_node`, `test_no_prompt_in_llm_logs` (sentinela).

### Etapa 2 — Implementação

R1–R5.

### Etapa 3 — Verificação

`uv run pytest` verde; `uv run pytest -m llm_contract` opcional.

## 5. Critérios de aceite

- [x] Toda falha de provider tem `http_status`, `latency_ms`, `tier`, `node`, `request_id`.
- [x] Mock/FallbackLLM nunca é escolhido em silêncio.
- [x] Teste de sentinela: nenhuma linha nova contém texto do jogador, e-mail, IP cru, token ou id cru.
- [x] `uv run pytest` verde (suíte completa offline).
- [x] Guard de FallbackLLM preservado em todo `with_structured_output` tocado.
- [x] Saves antigos continuam carregando.

## 6. Smoke test

1. Staging: chave DeepSeek inválida temporária num preview (ou `RPG_ROUTES` apontando para modelo inexistente) ⇒ `llm.attempt outcome=error http_status=401` + fallback para Groq visível.

## 7. Riscos & compatibilidade

- Volume: sucesso em `debug`; só falhas em `warning`.
- Logs são aditivos: nenhum contrato de resposta muda, salvo onde a spec diz explicitamente.
- MockLLM/FallbackLLM: comportamento inalterado; só passa a ser visível em log.

## Execução (logs-p1, 2026-10-18)

Implementado: `llm.attempt` por candidato (debug em sucesso, warning em falha; provider/model/tier/node/attempt_index/outcome/http_status/error_type/structured_failure_code/latency_ms/fell_back/cost_basis) a partir de `_emit_attempt_telemetry`, `kill_switch` logado, `llm.exhausted`, `llm.mock_selected`/`llm.fallback_llm_selected` (1x por processo e motivo; error fora do perfil legacy), `llm.routes_invalid`; `node` via `observability.telemetry.node_scope/with_node` aplicado aos nós em `main.py`; `rpg.turn` ganha `llm_errors`/`llm_http_statuses`. As strings `_LOG.warning` de tentativa foram removidas (substituídas). `LLMAttemptEvent` ganhou `http_status` e `error_type` (aditivos). Testes: `tests/test_llm_logging.py`. Falta o smoke de staging (§6) e a revisão Sol.
