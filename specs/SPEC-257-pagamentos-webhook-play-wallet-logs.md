# SPEC-257 — Pagamentos: webhook Stripe, verificação Google Play e wallet com desfecho em log

> **Status:** `done` — revisão Sol APPROVED + smoke staging (2026-10-19, [handoff](../handoffs/LOGS-P1-SOL-review.md)).
> **Criada:** 2026-10-18 · **Atualizada:** 2026-10-18
> **Depende de:** SPEC-240
> **Desbloqueia:** SPEC-262 (runbook pagamento)
> **Origem:** auditoria de logs 2026-10-18 ([relatório](../docs/auditorias/logs-api-2026-10-18.md))
> **EXECUTOR_MODEL:** `Terra` (≡ Sonnet) · **REVIEW_MODEL:** `Sol` (≡ Opus, contexto separado) · **REVIEW_REQUIRED:** `true — dinheiro; nada de token/ids de pagamento crus`
> **EVAL_AUTHORING_REQUIRED:** `false`

Rótulos: **[F]** fato (com evidência `arquivo:linha` no commit `4d60cf7`) · **[R]** recomendação.

---

## 1. Contexto & Objetivo

**[F]** Webhook Stripe (`api.py:2784-2815`): assinatura inválida ⇒ 400 `stripe_event_invalid` sem log; 413/408 idem; duplicado (`infrastructure/stripe_payments.py:226-257`) e replay com hash diferente sem log; o crédito (`credit_verified_purchase`, `late_paid_after_delete`, sku mismatch) só fica no banco. `reconcile_fee` engole `StripeError` (`stripe_payments.py:400`); checkout/order viram 503 sem log (`api.py:2679,2777`). Google Play verify (`api.py:2745-2767`): `GooglePlayError` (cancelled, token_conflict, already_consumed, test_purchase_rejected, product_mismatch, unavailable) vira 4xx/503 sem log nem métrica; erros de transporte colapsam em `google_play_unavailable` (`services/google_play.py:175-182,227-228`). Wallet: `services/wallet_recovery.py:117-118,143-145`, `infrastructure/speech_finance.py:79-82`, `services/dynamic_art.py:227-232` silenciosos.

**Objetivo:** tornar o debug desta área possível só com logs, sem reproduzir localmente — sem logar conteúdo de jogo nem dado pessoal.

## 2. Requisitos

- **R1** — `payments.stripe_webhook` (`info`/`warning`) com `outcome` (`applied|duplicate|replay_conflict|signature_invalid|too_large|timeout|ignored_type`), `event_type`, `event_ref` (pseudônimo do `evt_…`), `apply_result` (`credited|late_paid_after_delete|sku_mismatch|noop`), `duration_ms`.
- **R2** — `payments.google_verify` com `outcome` (código `GooglePlayError` ou `credited`), `product_id` (catálogo), `order_ref` (pseudônimo), `upstream_status` (HTTP da Play API quando houver), `duration_ms`; métrica `rpg_payment_verifications_total{provider,outcome}`.
- **R3** — `payments.checkout_failed` (`error`, `error_type`, `stage`) nos 503 de checkout/order; `payments.fee_reconcile_failed` em `stripe_payments.py:400`.
- **R4** — Wallet: `wallet.settle_failed`, `wallet.recovery_item_failed`, `wallet.reservation_uncertain` (`warning`, `op_ref`, `error_type`, `stage`).
- **R5** — Nunca em log: `purchase_token`, `client_secret`, e-mail do pagador, valores de cartão; teste com sentinelas.

### Restrições transversais

- **Privacidade (SPEC-222):** nenhum campo novo carrega texto do jogador, narração, nome de personagem, e-mail, IP cru, token, cookie, DSN, URL assinada ou corpo de resposta de provider. Ids de usuário/jogo/ação só como pseudônimo (`observability.telemetry.pseudonym`, HMAC com `RPG_TELEMETRY_SECRET`). Exceções: só `type(exc).__name__` + código fechado; nunca `str(exc)`.
- **Formato:** toda linha nova via `log_event(area, event, ...)` (`rpg.<area>`, JSON `safe_json`); nada de `print` (teste AST `tests/test_no_print_in_production.py` continua verde).

### Fora de escopo

Mudar a lógica de crédito/reconciliação.

## 3. Design técnico

- **Alterados:** `api.py` (rotas de pagamento), `infrastructure/stripe_payments.py`, `services/google_play.py`, `infrastructure/google_play_payments.py`, `services/wallet_recovery.py`, `infrastructure/speech_finance.py`, `services/dynamic_art.py`.

## 4. Plano passo a passo

### Etapa 1 — Testes vermelhos

`tests/test_payment_logging.py`: `test_bad_signature_logged`, `test_duplicate_logged`, `test_google_cancelled_logged_with_outcome`, `test_no_purchase_token_in_logs`, `test_wallet_settle_failure_logged`.

### Etapa 2 — Implementação

R1–R5.

### Etapa 3 — Verificação

`uv run pytest` verde (+ Postgres local).

## 5. Critérios de aceite

- [x] Todo evento de webhook e toda verificação Play tem 1 linha com `outcome`.
- [x] Zero segredo de pagamento em log.
- [x] Teste de sentinela: nenhuma linha nova contém texto do jogador, e-mail, IP cru, token ou id cru.
- [x] `uv run pytest` verde (suíte completa offline).
- [x] Guard de FallbackLLM preservado em todo `with_structured_output` tocado.
- [x] Saves antigos continuam carregando.

## 6. Smoke test

1. Staging (modo teste): `stripe trigger checkout.session.completed` ⇒ `payments.stripe_webhook outcome=applied`; reenviar ⇒ `duplicate`; POST com assinatura errada ⇒ `signature_invalid`.

## 7. Riscos & compatibilidade

- Nenhum.
- Logs são aditivos: nenhum contrato de resposta muda, salvo onde a spec diz explicitamente.
- MockLLM/FallbackLLM: comportamento inalterado; só passa a ser visível em log.

## Execução (logs-p1, 2026-10-18)

Implementado: `infrastructure/payment_log.py` — `payments.stripe_webhook` (outcome applied|duplicate|replay_conflict|signature_invalid|too_large|timeout|ignored_type|rejected|disabled, `apply_result`, `event_ref` pseudonimizado, `duration_ms`), `payments.google_verify` (outcome = código `GooglePlayError`/credited/pending, `upstream_status`, `order_ref`) + métrica `rpg_payment_verifications_total{provider,outcome}`, `payments.checkout_failed`, `payments.fee_reconcile_failed`, `wallet.settle_failed|recovery_item_failed|reservation_uncertain`. `accept_event` devolve `apply_result` (aditivo, só classificação). Testes: `tests/test_payment_logging.py` (sentinelas de purchase_token/client_secret/evt id). Falta: smoke de staging em modo teste (§6) e a revisão Sol; Postgres local não executado.
