# SPEC-195 — Reconciliação cross-channel, refunds e reversals

> **Status:** `done`
> **Depende de:** SPEC-194 `done`
> **EXECUTOR_MODEL obrigatório:** `Sol`
> **EXECUTOR_EFFORT obrigatório:** `High`
> **REVIEW_MODEL obrigatório:** `Astra`
> **REVIEW_EFFORT:** `High`
> **REVIEW_REQUIRED:** `true`
> **SUBSTITUIÇÃO DE MODELO:** proibida sem aprovação explícita do usuário; mismatch => `MODEL_HANDOFF_REQUIRED`
> **Delegação Luna permitida:** Luna: somente agregação de vetores/eventos; política e reconciliação ficam com Sol/Astra.
> **MODEL_BREAKDOWN:** `docs/planos/rpg-next-jev-golive-plan/examples/spec-model-contract.yaml` → `SPEC-195` é source of truth para subtarefas/review focus

## Objetivo

Unificar Stripe e Google Play numa máquina de estados de purchase/reconciliation que preserva auditabilidade quando há refund, dispute, revocation, webhook tardio ou wallet já consumida.

## Requisitos

- **R1** — estados fechados de purchase por provider.
- **R2** — reconciliation jobs idempotentes.
- **R3** — refund/revocation nunca apaga ledger.
- **R4** — política explícita para crédito já gasto: não criar saldo negativo silencioso; marcar debt/risk/lock conforme regra aprovada e auditável.
- **R5** — payment fees reais atualizam economics sem reescrever purchase original.
- **R6** — provider event IDs dedupados e out-of-order safe.
- **R7** — admin adjustment exige motivo/audit id e não é endpoint público.

### Fora de escopo

Fraud scoring avançado; cobrança judicial; tax.

## Plano

1. State machine e vectors antes do código.
2. Stripe/Google adapters normalizados.
3. Reconciliation scheduler/job.
4. Refund after partial/full spend tests.
5. Astra review da trust boundary.

## Critérios de aceite

- [x] money/credits conservation sob eventos fora de ordem.
- [x] nenhuma compra/refund duplicado.
- [x] gasto anterior não é reescrito.
- [x] política de debt/risk é explícita.
- [x] Astra review aprovada.

## Gates / evidência

Golden vectors financeiros + fault injection + fake provider events.

## Policy gate antes do código

Antes da implementação, o executor deve produzir `refund-debt-policy.md` com a decisão explícita para créditos já consumidos. Até aprovação humana, usar `PRODUCT_POLICY_APPROVAL_REQUIRED` e não codificar comportamento irreversível. Recomendação conservadora: saldo spendable nunca fica negativo; diferença vira `debt/financial_hold` separado e bloqueia novo uso pago até reconciliação, sem reescrever histórico.

## Gate de fechamento

- [x] state machine cobre Stripe paid/refund/dispute e Google purchased/acknowledged/consumed/revoked com eventos fora de ordem;
- [x] duplicate provider event IDs são no-op idempotente;
- [x] refund antes/depois de gasto preserva conservação e audit trail;
- [x] debt/hold policy aprovada está implementada e testada, sem saldo disponível negativo;
- [x] admin adjustment exige actor/reason/reference e não é endpoint público;
- [x] Astra independente retorna `APPROVED` — equivalente Opus independente: CHANGES_REQUIRED → correções → APPROVED_WITH_FOLLOWUPS (15/10), follow-ups corrigidos.

## Addendum 2026-10-15 (execução Claude)

Equivalência de modelo ([mapa aprovado pelo usuário](../docs/planos/equivalencia-modelos-claude.md)): executor → Claude Sonnet; planejamento pelo orquestrador Opus; revisões independentes por Opus em contexto separado.

Veredito: revisão equivalente a Astra (Opus independente) deu CHANGES_REQUIRED, correções aplicadas, nova rodada APPROVED_WITH_FOLLOWUPS; follow-ups corrigidos (inclui disputa `created` tardia após `won`). Política de dívida/hold: `docs/spec195/refund-debt-policy.md`. Limitação: reembolso Google depende de `voidedpurchases` (janela de 30 dias) e não foi exercitado contra o Google real (SPEC-198).
