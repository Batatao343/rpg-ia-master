# SPEC-241 — Access log por requisição e handler global de exceção com request_id

> **Status:** `in-progress` — implementado em 2026-10-18 (branch `logs-p0`); falta a revisão Sol obrigatória e o smoke em staging.
> **Criada:** 2026-10-18 · **Atualizada:** 2026-10-18
> **Depende de:** SPEC-239, SPEC-240
> **Desbloqueia:** SPEC-242, SPEC-243
> **Origem:** auditoria de logs 2026-10-18 ([relatório](../docs/auditorias/logs-api-2026-10-18.md))
> **EXECUTOR_MODEL:** `Terra` (≡ Sonnet) · **REVIEW_MODEL:** `Sol` (≡ Opus, contexto separado) · **REVIEW_REQUIRED:** `true — toca o middleware de todas as rotas`
> **EVAL_AUTHORING_REQUIRED:** `false`

Rótulos: **[F]** fato (com evidência `arquivo:linha` no commit `4d60cf7`) · **[R]** recomendação.

---

## 1. Contexto & Objetivo

**[F]** Não existe linha por requisição: `_correlation_boundary` (`api.py:290-340`) só alimenta métricas (`rpg_http_requests_total`, `rpg_http_duration_seconds`) e um span OTel opcional sem status. Não há handler para `Exception`/`HTTPException`/`RequestValidationError`. Uma exceção que escapa de `call_next` só incrementa a métrica 5xx e é relançada (`api.py:306-311`): **nenhum log com request_id**, o header `X-Request-ID` não é setado (só no caminho feliz, `api.py:323`) e o cliente recebe `Internal Server Error` em texto. Das ~134 `raise HTTPException` em `api.py`, ~10 têm log próximo. Os 401/403/503 do `_session_boundary` (`api.py:182-192`) também não deixam rastro.

**Objetivo:** tornar o debug desta área possível só com logs, sem reproduzir localmente — sem logar conteúdo de jogo nem dado pessoal.

## 2. Requisitos

- **R1** — Uma linha `http.request` por requisição (exceto `/health`, `/metrics` e assets estáticos) emitida no fim do middleware: `method`, `route` (template, `{id}` normalizado), `status`, `duration_ms`, `request_id`, `owner_ref` (se houver), `client` (`web|android|unknown` de `X-RPG-Client`), `error_code` (quando o corpo de erro tiver código). Nível: `info` para 2xx/3xx, `warning` 4xx, `error` 5xx. 404 de asset e 401 de bootstrap sem cookie podem ser `debug` (anti-ruído).
- **R2** — Handler global `@app.exception_handler(Exception)`: loga `http.unhandled_exception` (`level=error`) com `request_id`, `route`, `error_type`, e **stack resumida** (`module:lineno` dos 5 frames mais internos do código do projeto, sem mensagens/valores locais); responde 500 `{"detail": "internal_error", "code": "internal_error", "request_id": ...}` com header `X-Request-ID`.
- **R3** — Handlers para `HTTPException` e `RequestValidationError` preservam o corpo atual (compat) e acrescentam `request_id` ao corpo e ao header; 422 loga `http.validation_failed` com a lista de `loc` (nunca os valores).
- **R4** — `X-Request-ID` presente em 100% das respostas, inclusive respostas devolvidas por middlewares anteriores (`_session_boundary`, `_rate_limit`, `BodyLimitMiddleware`) — ordem de middleware ajustada ou header aplicado também nesses retornos.
- **R5** — Teste: rota de teste que levanta `RuntimeError("segredo-XYZ")` ⇒ 500 JSON com `request_id` igual ao header; caplog tem `http.unhandled_exception` com `error_type=RuntimeError` e **sem** `segredo-XYZ`.

### Restrições transversais

- **Privacidade (SPEC-222):** nenhum campo novo carrega texto do jogador, narração, nome de personagem, e-mail, IP cru, token, cookie, DSN, URL assinada ou corpo de resposta de provider. Ids de usuário/jogo/ação só como pseudônimo (`observability.telemetry.pseudonym`, HMAC com `RPG_TELEMETRY_SECRET`). Exceções: só `type(exc).__name__` + código fechado; nunca `str(exc)`.
- **Formato:** toda linha nova via `log_event(area, event, ...)` (`rpg.<area>`, JSON `safe_json`); nada de `print` (teste AST `tests/test_no_print_in_production.py` continua verde).

### Fora de escopo

Unificação de códigos de erro (SPEC-242); logs de auth com motivo (SPEC-245).

## 3. Design técnico

- **Alterados:** `api.py` (`_correlation_boundary`, novos exception handlers, ordem de middlewares). Helper `observability/telemetry.py::safe_stack(exc, limit=5)`.

## 4. Plano passo a passo

### Etapa 1 — Testes vermelhos

`tests/test_api_access_log.py`: `test_one_access_line_per_request`, `test_unhandled_exception_logged_with_request_id`, `test_500_body_has_request_id`, `test_request_id_header_on_401_csrf_413`, `test_validation_error_logs_loc_not_values`, `test_stack_has_no_exception_message`.

### Etapa 2 — Implementação

R1–R4.

### Etapa 3 — Verificação

`uv run pytest` verde.

## 5. Critérios de aceite

- [x] Toda resposta tem `X-Request-ID`; toda 5xx tem linha `error` com `request_id`.
- [x] Sem `str(exc)` em log.
- [x] Teste de sentinela: nenhuma linha nova contém texto do jogador, e-mail, IP cru, token ou id cru.
- [x] `uv run pytest` verde (suíte completa offline).
- [x] Guard de FallbackLLM preservado em todo `with_structured_output` tocado.
- [x] Saves antigos continuam carregando.

## 6. Smoke test

1. Staging: provocar 404/401/422/409 e (rota de diagnóstico desligada por default ou payload inválido) 500.
2. Cada request aparece em `vercel logs` com status e duração.

## 7. Riscos & compatibilidade

- Volume: 1 linha/requisição — polling (`/game/state`, `/account/*`) pode dominar; usar `debug` para GETs 2xx de polling conhecidos se a medição do smoke indicar.
- Logs são aditivos: nenhum contrato de resposta muda, salvo onde a spec diz explicitamente.
- MockLLM/FallbackLLM: comportamento inalterado; só passa a ser visível em log.

## 8. Notas de implementação

- `_correlation_boundary` agora e o middleware MAIS EXTERNO (registrado depois de `_rate_limit`), entao 401/403/413/429 dos middlewares internos tambem recebem `X-Request-ID` e entram no access log; a raiz usa `request_scope` (contexto limpo, sem herdar game/action de fora).
- `http.request` (info 2xx/3xx, warning 4xx, error 5xx; debug para 404 de rota nao-API, 401 sem cookie e GET 2xx de polling: `/game/state`, `/game/saves`, `/game/map`, `/game/codex*`, `/data/*`). `/health`, `/metrics` e assets estaticos nao logam.
- 500 nao tratado e capturado no proprio middleware (dentro do escopo de correlacao): `http.unhandled_exception` com `error_type` + `stack` (`safe_stack`: `modulo:linha` dos 5 frames internos do projeto, sem mensagem) e corpo `{detail, code:internal_error, request_id}`.
- Handlers de `HTTPException` e `RequestValidationError` preservam o corpo e acrescentam `request_id` (corpo + header); 422 loga so os `loc`. Handlers especificos (QuotaExceeded etc.) nao foram alterados (header presente).
- Desvio: `error_code` no access log so e preenchido quando o erro passou por esses handlers (detail ja em formato de codigo); respostas montadas diretamente por middlewares (ex.: boundary de sessao) saem com `error_code=null` ate a SPEC-245/242.
- Testes existentes que comparavam o corpo de erro inteiro (`test_auth_gotrue_error_mapping`, `test_session_hardening`, `test_speech_api`) passaram a ignorar `request_id` (campo aditivo da R3).
- Pendente: smoke em staging (404/401/422/409/500) e revisao Sol.
