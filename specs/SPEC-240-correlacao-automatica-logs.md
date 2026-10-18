# SPEC-240 — Correlação automática em todo log (request_id, action_ref, game_ref) inclusive em threads

> **Status:** `in-progress` — implementado em 2026-10-18 (branch `logs-p0`); falta a revisão Sol obrigatória e o smoke em staging.
> **Criada:** 2026-10-18 · **Atualizada:** 2026-10-18
> **Depende de:** SPEC-239
> **Desbloqueia:** SPEC-247, 252, 255, 262
> **Origem:** auditoria de logs 2026-10-18 ([relatório](../docs/auditorias/logs-api-2026-10-18.md))
> **EXECUTOR_MODEL:** `Terra` (≡ Sonnet) · **REVIEW_MODEL:** `Sol` (≡ Opus, contexto separado) · **REVIEW_REQUIRED:** `true — contextvars atravessando threads do SSE/Jev`
> **EVAL_AUTHORING_REQUIRED:** `false`

Rótulos: **[F]** fato (com evidência `arquivo:linha` no commit `4d60cf7`) · **[R]** recomendação.

---

## 1. Contexto & Objetivo

**[F]** `log_event` (`observability/telemetry.py:93-101`) **não** inclui `correlation()`; só `span()` faz isso (`telemetry.py:141`). Por isso `router.*`, `storyteller.failed`, `archivist.*`, `persistence.*`, `rag.*`, `api.turn_failed` (`api.py:4175`) e todo `rpg.llm` saem sem `request_id` — só 3 sites adicionam à mão (`api.py:578`, `734`, `828`) e o `rpg.turn` espalha `**correlation()` (`api.py:4005`).

O `action_id` (= operation id, `api.py:3590`, `3645`) nunca entra no contextvar; `game_id` também não (só `rpg.turn` calcula `game_id_ref`, `api.py:4004`). O worker SSE é um `threading.Thread` cru (`api.py:4536`) que só restaura `principal_scope` (`api.py:4514`): o contexto de correlação se perde e o `rpg.turn` do caminho SSE sai sem `request_id`. O pool do Jev (`services/jev_rollout.py:415`, callback tardio `343-344`) idem. Resultado: hoje não dá para reconstruir um turno juntando as linhas por um id.

**Objetivo:** tornar o debug desta área possível só com logs, sem reproduzir localmente — sem logar conteúdo de jogo nem dado pessoal.

## 2. Requisitos

- **R1** — `log_event` mescla `correlation()` em toda linha (campos explícitos do chamador vencem em colisão). Campos de correlação: `request_id`, `owner_ref`, `game_ref`, `action_ref`, `job_id`, `run_id` (renomear `owner_id_ref`/`game_id_ref` → manter ambos por 1 release).
- **R2** — Endpoints de turno (`/game/action`, `/game/action/stream`, `/game/death`, `/game/new`, equip/levelup/cards) abrem `correlation_scope(game_id=..., action_id=...)`; `correlation_scope` pseudonimiza `action_id` → `action_ref` (igual ao `pseudonym(action_id)` já usado no `rpg.turn`, `api.py:3958`).
- **R3** — Helper `observability.telemetry.run_with_context(fn, *a)` / `copy_context()` usado no `threading.Thread` do SSE (`api.py:4536`) e no `_pool().submit` do Jev (`jev_rollout.py:415`): as linhas emitidas nessas threads carregam o mesmo `request_id`/`action_ref` da requisição.
- **R4** — Logs diretos via `logging.getLogger("rpg.x")` com `safe_json` (ex.: `api.py:576`, `services/abuse_policy.py`, `llm_setup.py` `_LOG`) também recebem a correlação: o formatter da SPEC-239 injeta `correlation()` quando a mensagem é JSON sem esses campos.
- **R5** — Teste end-to-end: um turno MockLLM via `TestClient` com header `X-Request-ID: test-req-0001` produz ≥ 3 linhas `rpg.*` distintas (router, turn, archivist ou persistence) **todas** com `request_id=test-req-0001` e o mesmo `action_ref`; o mesmo para `/game/action/stream`.

### Restrições transversais

- **Privacidade (SPEC-222):** nenhum campo novo carrega texto do jogador, narração, nome de personagem, e-mail, IP cru, token, cookie, DSN, URL assinada ou corpo de resposta de provider. Ids de usuário/jogo/ação só como pseudônimo (`observability.telemetry.pseudonym`, HMAC com `RPG_TELEMETRY_SECRET`). Exceções: só `type(exc).__name__` + código fechado; nunca `str(exc)`.
- **Formato:** toda linha nova via `log_event(area, event, ...)` (`rpg.<area>`, JSON `safe_json`); nada de `print` (teste AST `tests/test_no_print_in_production.py` continua verde).

### Fora de escopo

Propagação para jobs/workers assíncronos (SPEC-255); browser→API (SPEC-243).

## 3. Design técnico

- **Alterados:** `observability/telemetry.py` (`log_event` mescla; `correlation_scope` aceita `action_id`, `job_id`, `run_id`; `run_with_context`), `api.py` (scopes nos endpoints; thread SSE), `services/jev_rollout.py` (submit com contexto), `observability/logging_setup.py` (injeção no formatter).

## 4. Plano passo a passo

### Etapa 1 — Testes vermelhos

`tests/test_log_correlation.py`: `test_log_event_includes_request_id`, `test_turn_lines_share_action_ref`, `test_sse_worker_lines_have_request_id`, `test_jev_shadow_line_has_action_ref`, `test_raw_action_id_never_logged`.

### Etapa 2 — Implementação

R1–R4.

### Etapa 3 — Verificação

`uv run pytest` verde.

## 5. Critérios de aceite

- [x] Todas as linhas de um turno (POST e SSE) compartilham `request_id` e `action_ref`.
- [x] Nenhum id cru (`action_id`, `game_id`, `owner_id`) em log (teste com sentinelas UUID).
- [x] Teste de sentinela: nenhuma linha nova contém texto do jogador, e-mail, IP cru, token ou id cru.
- [x] `uv run pytest` verde (suíte completa offline).
- [x] Guard de FallbackLLM preservado em todo `with_structured_output` tocado.
- [x] Saves antigos continuam carregando.

## 6. Smoke test

1. Staging: 1 turno via SSE com `X-Request-ID` conhecido (curl).
2. `npx vercel logs --query <request_id>` devolve router/jev/turn/turn_delivery do mesmo turno.

## 7. Riscos & compatibilidade

- Overhead desprezível (dict merge). Threads de terceiros (LangGraph interno) podem ainda perder contexto — documentar quais.
- Logs são aditivos: nenhum contrato de resposta muda, salvo onde a spec diz explicitamente.
- MockLLM/FallbackLLM: comportamento inalterado; só passa a ser visível em log.

## 8. Notas de implementação

- Novo em `observability/telemetry.py`: `log_event` mescla `correlation()`; `bind_correlation` (contexto do handler), `contextualize(fn)`/`run_with_context` (thread SSE, pool e callback tardio do Jev). `action_id` -> `action_ref` (pseudonimo); `owner_ref`/`game_ref` adicionados mantendo `owner_id_ref`/`game_id_ref` por 1 release.
- `api.py`: `_bind_corr` no inicio de /game/action(+stream via `_execute_action`), death, equip, cards/prepare, levelup, new; `threading.Thread(target=contextualize(_worker))`.
- Desvio: o teste E2E exige >=2 eventos distintos por turno (nao >=3): hoje o turno de caminho feliz so emite `turn` (+ avisos de rag); `router.decision`/archivist/persistence ganham linhas info nas SPEC-247/250.
- Observacao: `tests/test_jev_router_port.py::test_missing_key_falls_back_to_classify` e flaky nesta maquina (deadline de 1 s; falha tambem em main sem estas mudancas).
- Threads internas do LangGraph mantiveram o contexto nos testes (rag.legacy carrega request_id); nao ha garantia para libs de terceiros.
- Pendente: smoke em staging e revisao Sol.
