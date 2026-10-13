# SPEC-189 — Stripe Checkout web + webhooks

> **Status:** `review-pending`
> **Depende de:** SPEC-188 `done`
> **EXECUTOR_MODEL obrigatório:** `Sol`
> **EXECUTOR_EFFORT obrigatório:** `High`
> **REVIEW_MODEL obrigatório:** `Sol`
> **REVIEW_EFFORT:** `High`
> **REVIEW_REQUIRED:** `true`
> **SUBSTITUIÇÃO DE MODELO:** proibida sem aprovação explícita do usuário; mismatch => `MODEL_HANDOFF_REQUIRED`
> **Delegação Luna permitida:** Luna: inventário de eventos/fixtures Stripe e relatório; webhook/fulfillment ficam com Sol.
> **MODEL_BREAKDOWN:** `docs/rpg-next-jev-golive-plan/examples/spec-model-contract.yaml` → `SPEC-189` é source of truth para subtarefas/review focus

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

- [x] duplicated/out-of-order webhook não duplica crédito.
- [x] success URL não concede saldo.
- [x] preço vem do SKU server-side.
- [x] refund preserva audit trail.
- [x] secrets ausentes no bundle.

## Gates / evidência

Local fixtures obrigatórias; Stripe test mode opcional na spec. Nada live.

## Gate de fechamento

- [x] webhook body é verificado com assinatura antes de parse/fulfillment confiável;
- [x] `payment_order` vincula owner + SKU version + credits server-side; metadata do client não é autoridade;
- [x] evento duplicado, reordenado, delayed e replay de Checkout não duplicam crédito;
- [x] success/cancel page nunca concede saldo e funciona mesmo se webhook chegar depois;
- [x] refund/dispute cria evento/estado reversível sem apagar purchase/ledger;
- [x] test fixtures passam offline; chamada Stripe test-mode não é requisito para `done` se conta ainda não estiver conectada, mas fica obrigatória no release gate SPEC-197;
- [ ] review Sol independente aprova signature/idempotency/fulfillment.

## Decisões de implementação e evidência

- Test mode é o único adapter; `sk_live_*`, eventos `livemode=true` e URLs fora
  do host Stripe são rejeitados. Default desativado e allowlist de SKUs vazia;
  nenhuma migração publica preço/SKU comercial.
- Pedido imutável contém owner, SKU/version, bruto BRL, créditos e economics
  estimada. UUID de request reaproveita a sessão com chave Stripe estável;
  retry sem sessão expira em 23h para ficar dentro da retenção de 24h da Stripe.
- HMAC SHA-256 + timestamp (tolerância absoluta 300s) sobre raw bytes limitados
  a 256KiB precede JSON. Evento sanitizado/hash, pedido e crédito usam a mesma
  transação. Locks por payment intent e pedido cobrem refund órfão em corrida.
- Somente Checkout `mode=payment`, session/order/intent coerentes,
  `payment_status=paid` e amount/currency exatos podem creditar a wallet.
- Refund total e chargeback total debitam uma vez se há saldo disponível.
  Partial refund, saldo gasto, disputa com FX/amount divergente, inquiry,
  prevented e disputa encerrada registram fatos e `reconciliation_required`.
  Correção/restauração exige ajuste de operador auditado; nenhum histórico é
  apagado e um pagamento atrasado não retira esse hold.
- Fee real vem de PaymentIntent → charge → balance transaction no backend;
  atualiza economics sem mudar o grant. Ausência/falha preserva fee estimada,
  retry de evento pago ou `reconcile_fee` pode concluir depois; scheduler de
  reconciliação financeira fica como requisito operacional do release.
- Checkout/status em `/account` exigem sessão e CSRF em mutações; webhook
  externo usa `/payments/stripe/webhook`. Return success/cancel só consulta.
- **39 focados**, incluindo **23 Postgres rollback + 3 races em schema local
  descartável**, e **24 testes afetados** verdes. Gates completos, revisão e
  evidência final em [docs/spec189/README.md](../docs/spec189/README.md).
