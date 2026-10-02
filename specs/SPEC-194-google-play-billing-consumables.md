# SPEC-194 — Google Play Billing — consumíveis

> **Status:** `approved`
> **Depende de:** SPEC-193 `done`
> **EXECUTOR_MODEL obrigatório:** `Sol`
> **EXECUTOR_EFFORT obrigatório:** `High`
> **REVIEW_MODEL obrigatório:** `Sol`
> **REVIEW_EFFORT:** `High`
> **REVIEW_REQUIRED:** `true`
> **SUBSTITUIÇÃO DE MODELO:** proibida sem aprovação explícita do usuário; mismatch => `MODEL_HANDOFF_REQUIRED`
> **Delegação Luna permitida:** Luna: inventário de SKUs/fixtures e relatório; purchase verification/fulfillment ficam com Sol.
> **MODEL_BREAKDOWN:** `docs/rpg-next-jev-golive-plan/examples/spec-model-contract.yaml` → `SPEC-194` é source of truth para subtarefas/review focus

## Objetivo

Adicionar compra de pacotes de Estilhas no Android com Google Play Billing, verificação server-side e consumo idempotente.

## Requisitos

- **R1** — SKUs one-time/consumable mapeados server-side para purchase SKU version.
- **R2** — preço exibido vem da Store, nunca hardcoded.
- **R3** — purchase token enviado ao backend autenticado; backend consulta/valida Google antes de creditar.
- **R4** — purchase/order token único; replay não duplica wallet.
- **R5** — acknowledge/consume somente após entrega confiável; recovery de compra pendente.
- **R6** — refund/revocation fica para reconciliation, mas eventos/IDs necessários são persistidos.
- **R7** — credencial Google só backend.
- **R8** — v1 não oferece Stripe/alternate billing dentro do app.
- **R9** — fee tier da conta precisa ser confirmado antes de preço de produção.

### Fora de escopo

Assinaturas; iOS; alternate billing.

## Plano

1. Escolher integração direta Google oficial; biblioteca third-party só com justificativa/review, sem SaaS obrigatório por default.
2. Implementar native purchase adapter.
3. Backend verification/fulfillment.
4. License/internal testing quando Play Console existir e houver aprovação.
5. Pending/cancel/retry/process-death tests.

## Critérios de aceite

- [ ] client adulterado não cria Estilhas.
- [ ] duplicate token não duplica.
- [ ] compra consumível pode ser recomprada após consume.
- [ ] cancelamento não cobra.
- [ ] preço UI é Store-provided.

## Gates / evidência

Fake Google first. Internal testing exige conta Play/approval e vem antes de publicação.

## Delimitação sem Play Console

Esta spec entrega a integração técnica e contratos usando fake/fixtures e seam server-side. Não exige que o usuário já possua Play Console. Teste com produto/licença real, package ID definitivo e track interno pertence à SPEC-198.

## Gate de fechamento

- [ ] purchase token/sku/order são tratados como dados não confiáveis até verificação server-side;
- [ ] token duplicado/replay/process death não duplica wallet;
- [ ] acknowledge/consume só ocorre depois de fulfillment idempotente persistido;
- [ ] pending/cancelled não gera crédito;
- [ ] UI usa preço/localização fornecidos pela Store adapter;
- [ ] nenhuma rota/link Stripe é oferecida dentro do Android v1;
- [ ] review Sol independente aprova purchase lifecycle/verification.
