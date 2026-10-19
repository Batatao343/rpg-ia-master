# SPEC-242 — Envelope de erro único `{detail, code, request_id}` e fim de `str(exc)` em respostas

> **Status:** `in-progress` — implementada em `logs-p1` (REVIEW_REQUIRED; smoke staging pendente)
> **Criada:** 2026-10-18 · **Atualizada:** 2026-10-18
> **Depende de:** SPEC-241
> **Desbloqueia:** SPEC-243
> **Origem:** auditoria de logs 2026-10-18 ([relatório](../docs/auditorias/logs-api-2026-10-18.md))
> **EXECUTOR_MODEL:** `Terra` (≡ Sonnet) · **REVIEW_MODEL:** `Sol` (≡ Opus, contexto separado) · **REVIEW_REQUIRED:** `true — contrato de erro consumido pelo web e Android`
> **EVAL_AUTHORING_REQUIRED:** `false`

Rótulos: **[F]** fato (com evidência `arquivo:linha` no commit `4d60cf7`) · **[R]** recomendação.

---

## 1. Contexto & Objetivo

**[F]** As respostas de erro têm 4+ formatos: `{"detail":"<codigo>"}` (~60 sites, ex.: `api.py:2589`, `3611`); `{"detail":"<prosa em pt-BR>"}` (~45 sites, ex.: `"Jogo não encontrado."` em `api.py:2581,2900,3089,...`, `"Erro interno ao processar o turno."` `4176`); `{"detail":{code,...}}` (`3666`, `3875`); 429 com `{detail,scope,retry_after_seconds}` (`services/abuse_policy.py:166`); 409 `{detail,code}` só em `api.py:88-91`. Além disso `detail=str(exc)` vaza mensagem interna em `api.py:2875,2884,2893,4879` e `detail=err` em `4647,4692,4737`. Sem código estável o suporte não sabe o que o usuário viu, e o web exibe prosa/códigos crus.

**Objetivo:** tornar o debug desta área possível só com logs, sem reproduzir localmente — sem logar conteúdo de jogo nem dado pessoal.

## 2. Requisitos

- **R1** — Todo erro HTTP responde `{"detail": <str legível ou código legado>, "code": "<snake_case estável>", "request_id": "..."}` (+ campos extras já existentes, ex.: `retry_after_seconds`, `operation_id`). `detail` mantém o valor atual (compat do cliente); `code` é novo e obrigatório.
- **R2** — Catálogo `services/error_codes.py` (enum/`frozenset`) com todos os códigos; teste AST/grep falha se um `HTTPException` em `api.py`/`services/cron_internal.py` não tiver `code` do catálogo (via helper `api_error(status, code, detail=None, **extra)`).
- **R3** — Mapeamento das ~45 mensagens em prosa para códigos (`game_not_found`, `no_saved_game`, `death_pending`, `internal_turn_error`, `game_id_invalid`, ...).
- **R4** — Os 7 sites com `str(exc)`/`err` passam a código fechado; a mensagem interna vai só para o log (`error_type` + código), nunca para a resposta.
- **R5** — SSE `event: error` (`api.py:4553-4558`) usa o mesmo envelope (`code`, `request_id`).
- **R6** — Documentar o catálogo em `docs/operacao/CODIGOS_DE_ERRO.md` (gerado do módulo; teste de frescor).

### Restrições transversais

- **Privacidade (SPEC-222):** nenhum campo novo carrega texto do jogador, narração, nome de personagem, e-mail, IP cru, token, cookie, DSN, URL assinada ou corpo de resposta de provider. Ids de usuário/jogo/ação só como pseudônimo (`observability.telemetry.pseudonym`, HMAC com `RPG_TELEMETRY_SECRET`). Exceções: só `type(exc).__name__` + código fechado; nunca `str(exc)`.
- **Formato:** toda linha nova via `log_event(area, event, ...)` (`rpg.<area>`, JSON `safe_json`); nada de `print` (teste AST `tests/test_no_print_in_production.py` continua verde).

### Fora de escopo

Tradução para mensagens amigáveis (SPEC-243); mudar status HTTP existentes.

## 3. Design técnico

- **Novo:** `services/error_codes.py`, helper `api_error`. **Alterados:** `api.py` (todos os raises), `services/cron_internal.py`.

## 4. Plano passo a passo

### Etapa 1 — Testes vermelhos

`tests/test_error_envelope.py`: `test_every_http_exception_has_catalog_code` (AST), `test_no_str_exc_in_detail`, `test_404_game_has_code_and_request_id`, `test_sse_error_event_envelope`.

### Etapa 2 — Implementação

helper + varredura mecânica.

### Etapa 3 — Verificação

`uv run pytest` + `cd web && npm run build` + e2e existentes verdes (detail inalterado).

## 5. Critérios de aceite

- [x] 100% dos erros com `code` + `request_id`.
- [x] Zero `str(exc)` em resposta.
- [x] Catálogo documentado e testado.
- [x] Teste de sentinela: nenhuma linha nova contém texto do jogador, e-mail, IP cru, token ou id cru.
- [x] `uv run pytest` verde (suíte completa offline).
- [x] Guard de FallbackLLM preservado em todo `with_structured_output` tocado.
- [x] Saves antigos continuam carregando.

## 6. Smoke test

1. Staging: 404 de jogo inexistente, 409 de operação pendente, 429 — os três com `code` e `request_id`.

## 7. Riscos & compatibilidade

- Cliente Android antigo ignora `code` (compat garantida por `detail` inalterado).
- Logs são aditivos: nenhum contrato de resposta muda, salvo onde a spec diz explicitamente.
- MockLLM/FallbackLLM: comportamento inalterado; só passa a ser visível em log.

## Execução (logs-p1, 2026-10-18)

Implementado: `services/error_codes.py` (catálogo `CODE_DOCS`/`PROSE_CODES`, `ApiError`/`api_error`, `envelope`), `api._error_response` em todos os handlers/middlewares (inclui 429, 413, 401/403/503 de borda, 500), SSE `event: error` com `error_code`+`request_id`. Doc gerado `docs/operacao/CODIGOS_DE_ERRO.md` (+ `web/src/lib/errorCodes.json`) com teste de frescor. Testes: `tests/test_error_envelope.py`; 9 asserções antigas de corpo exato ajustadas para comparar `detail`.

Desvios registrados: (1) `detail` mantém a prosa histórica (compat) e o `code` é derivado via `PROSE_CODES` no handler — não houve varredura de 134 raises; o teste AST garante que todo `HTTPException` mapeia para o catálogo. (2) Os `detail=err` de equip/prepare/levelup são texto de regra de domínio (não de exceção, mostrado ao jogador): mantidos em `detail` com `code` `equip_rejected`/`prepare_rejected`/`levelup_rejected`; os `str(exc)` foram trocados por códigos fechados. (3) No SSE o campo `code` segue numérico (compat do cliente atual); o código estável vai em `error_code`. Falta o smoke de staging (§6) e a revisão Sol.
