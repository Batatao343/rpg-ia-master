# SPEC-246 — Rate limit, cotas, spend cap e 413: linhas estruturadas com retry_after e request_id

> **Status:** `draft` — aguardando aprovação do dono. Prioridade sugerida: **P2**.
> **Criada:** 2026-10-18 · **Atualizada:** 2026-10-18
> **Depende de:** SPEC-239, SPEC-240
> **Desbloqueia:** —
> **Origem:** auditoria de logs 2026-10-18 ([relatório](../docs/auditorias/logs-api-2026-10-18.md))
> **EXECUTOR_MODEL:** `Terra` (≡ Sonnet) · **REVIEW_MODEL:** `Sol` (≡ Opus, contexto separado) · **REVIEW_REQUIRED:** `false`
> **EVAL_AUTHORING_REQUIRED:** `false`

Rótulos: **[F]** fato (com evidência `arquivo:linha` no commit `4d60cf7`) · **[R]** recomendação.

---

## 1. Contexto & Objetivo

**[F]** `abuse_policy.record_block` (`services/abuse_policy.py:168-181`) loga string `%s` (não JSON, sem `request_id`, sem `retry_after`/limite), envolto em `except Exception: pass`. Sem log: 429 de `/metrics` (`api.py:1072`), `audit_export_rate_limit` (`api.py:691`), `speech_rate_limit` (`api.py:2836`), 413 do `BodyLimitMiddleware` (`services/body_limit.py:32-47`, sem métrica também), 413 do webhook Stripe (`api.py:2799`) e da voz (`2843`). `daily_quota_unavailable` (`api.py:1202`) não registra a classe da exceção. Fail-open silencioso: `_record_authfail` (`api.py:234`) e `_owner_rate_limit` (`api.py:1143`) retornam `None` em qualquer exceção.

**Objetivo:** tornar o debug desta área possível só com logs, sem reproduzir localmente — sem logar conteúdo de jogo nem dado pessoal.

## 2. Requisitos

- **R1** — `record_block` vira `log_event("abuse","blocked", class=, scope=, owner_ref=, ip_ref=, retry_after_s=, limit=)` (nível `warning`), herdando `request_id`.
- **R2** — Todos os 429/503 de limite listados acima chamam `record_block` (ou equivalente) — teste varre `api.py` por `status_code=429` sem `record_block` próximo.
- **R3** — `BodyLimitMiddleware`: `http.body_too_large` com `route`, `limit_bytes`, `declared_bytes` (Content-Length, se houver) + métrica `rpg_http_body_too_large_total{route}`.
- **R4** — Fail-open do rate limiter (`api.py:234`, `1143`) e da cota diária (`1202`) loga `abuse.limiter_unavailable` com `error_type` (nível `error`) — continua fail-open (decisão SPEC-219), mas visível; métrica `rpg_rate_limiter_errors_total`.

### Restrições transversais

- **Privacidade (SPEC-222):** nenhum campo novo carrega texto do jogador, narração, nome de personagem, e-mail, IP cru, token, cookie, DSN, URL assinada ou corpo de resposta de provider. Ids de usuário/jogo/ação só como pseudônimo (`observability.telemetry.pseudonym`, HMAC com `RPG_TELEMETRY_SECRET`). Exceções: só `type(exc).__name__` + código fechado; nunca `str(exc)`.
- **Formato:** toda linha nova via `log_event(area, event, ...)` (`rpg.<area>`, JSON `safe_json`); nada de `print` (teste AST `tests/test_no_print_in_production.py` continua verde).

### Fora de escopo

Mudar limites ou a política fail-open/fail-closed.

## 3. Design técnico

- **Alterados:** `services/abuse_policy.py`, `services/body_limit.py`, `api.py` (sites listados).

## 4. Plano passo a passo

### Etapa 1 — Testes vermelhos

`tests/test_abuse_logging.py`: `test_record_block_json_with_retry_after`, `test_body_limit_logs_and_counts`, `test_limiter_exception_logged_failopen`, `test_every_429_records_block` (AST).

### Etapa 2 — Implementação

R1–R4.

### Etapa 3 — Verificação

`uv run pytest` verde.

## 5. Critérios de aceite

- [ ] Todo 429/413/503-de-limite tem linha JSON com `request_id`.
- [ ] Exceções do limiter visíveis em log e métrica.
- [ ] Teste de sentinela: nenhuma linha nova contém texto do jogador, e-mail, IP cru, token ou id cru.
- [ ] `uv run pytest` verde (suíte completa offline).
- [ ] Guard de FallbackLLM preservado em todo `with_structured_output` tocado.
- [ ] Saves antigos continuam carregando.

## 6. Smoke test

1. Staging: estourar `/telemetry/client-latency` ou login por IP (limite baixo no smoke) e ver `abuse.blocked` com `retry_after_s`.

## 7. Riscos & compatibilidade

- Sob ataque, `abuse.blocked` amostrado 1×/min por (classe, chave).
- Logs são aditivos: nenhum contrato de resposta muda, salvo onde a spec diz explicitamente.
- MockLLM/FallbackLLM: comportamento inalterado; só passa a ser visível em log.
