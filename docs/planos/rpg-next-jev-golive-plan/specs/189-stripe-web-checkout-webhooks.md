# SPEC-189 — Stripe Checkout web + webhooks

> **Status:** `draft`
> **Depende de:** SPEC-188 `done`
> **EXECUTOR_MODEL obrigatório:** `Sol`
> **EXECUTOR_EFFORT obrigatório:** `High`
> **REVIEW_MODEL obrigatório:** `Sol`
> **REVIEW_EFFORT:** `High`
> **REVIEW_REQUIRED:** `true`
> **SUBSTITUIÇÃO DE MODELO:** proibida sem aprovação explícita do usuário; mismatch => `MODEL_HANDOFF_REQUIRED`
> **Delegação Luna permitida:** Luna: inventário de eventos/fixtures Stripe e relatório; webhook/fulfillment ficam com Sol.
> **MODEL_BREAKDOWN:** `examples/spec-model-contract.yaml` → `SPEC-189` é source of truth para subtarefas/review focus

## Objetivo

Permitir compra web de Estilhas via Stripe Checkout com servidor como autoridade e fulfillment idempotente por webhook.

## Requisitos

- **R1** — `payment_orders` criado server-side a partir de SKU permitido; client não envia preço/créditos.
- **R2** — Checkout Session com metadata opaca mínima, idempotency key e success/cancel URLs.
- **R3** — webhook verifica assinatura e guarda `stripe_events` dedupados.
- **R4** — só evento pago/confirmado aplicável credita wallet; success page nunca credita.
- **R5** — fee real/reconciliada atualiza purchase economics quando disponível.
- **R6** — refund/dispute gera evento financeiro, nunca delete do histórico.
- **R7** — Stripe secret/webhook secret somente backend.
- **R8** — test mode primeiro; live mode é gate posterior.

### Fora de escopo

Stripe Billing/subscriptions; Pix obrigatório; alternate billing Android.

## Plano

1. Fake Stripe adapter + signed webhook fixtures.
2. payment orders/Stripe event store.
3. Checkout endpoint.
4. webhook fulfillment -> wallet purchase entry.
5. refund/idempotency/out-of-order tests.
6. Stripe test-mode smoke somente com aprovação de conexão.

## Critérios de aceite

- [ ] duplicated/out-of-order webhook não duplica crédito.
- [ ] success URL não concede saldo.
- [ ] preço vem do SKU server-side.
- [ ] refund preserva audit trail.
- [ ] secrets ausentes no bundle.

## Gates / evidência

Local fixtures obrigatórias; Stripe test mode opcional na spec. Nada live.

## Gate de fechamento

- [ ] webhook body é verificado com assinatura antes de parse/fulfillment confiável;
- [ ] `payment_order` vincula owner + SKU version + credits server-side; metadata do client não é autoridade;
- [ ] evento duplicado, reordenado, delayed e replay de Checkout não duplicam crédito;
- [ ] success/cancel page nunca concede saldo e funciona mesmo se webhook chegar depois;
- [ ] refund/dispute cria evento/estado reversível sem apagar purchase/ledger;
- [ ] test fixtures passam offline; chamada Stripe test-mode não é requisito para `done` se conta ainda não estiver conectada, mas fica obrigatória no release gate SPEC-197;
- [ ] review Sol independente aprova signature/idempotency/fulfillment.
