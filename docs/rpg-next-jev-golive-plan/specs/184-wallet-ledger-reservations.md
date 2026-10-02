# SPEC-184 — Wallet ledger, reservas e settlement atômico

> **Status:** `draft`
> **Depende de:** SPEC-183 `done`
> **EXECUTOR_MODEL obrigatório:** `Sol`
> **EXECUTOR_EFFORT obrigatório:** `High`
> **REVIEW_MODEL obrigatório:** `Astra`
> **REVIEW_EFFORT:** `High`
> **REVIEW_REQUIRED:** `true`
> **SUBSTITUIÇÃO DE MODELO:** proibida sem aprovação explícita do usuário; mismatch => `MODEL_HANDOFF_REQUIRED`
> **Delegação Luna permitida:** Luna: somente execução/compilação de testes e relatório; nenhuma edição em ledger/transações.
> **MODEL_BREAKDOWN:** `examples/spec-model-contract.yaml` → `SPEC-184` é source of truth para subtarefas/review focus

## Objetivo

Criar a fonte de verdade financeira da conta: ledger append-only, saldo derivável, reserva pré-operação, settlement/release e invariantes de concorrência.

## Requisitos

- **R1** — `wallet_accounts`, `wallet_entries`, `wallet_reservations`; valores inteiros em subunidade canônica (`shard_milli` ou equivalente versionado), nunca float.
- **R2** — tipos fechados: purchase, reserve, settle, release, refund, reversal, adjustment_admin.
- **R3** — nenhuma mutação financeira em GameState.
- **R4** — operation/purchase idempotency unique keys.
- **R5** — saldo disponível nunca negativo; duas requests concorrentes não gastam a mesma Estilha.
- **R6** — reserve/settle vinculados ao custo normalizado e pricing version; settlement normal nunca pode exceder a reserva. A operação recebe `spend_ceiling` e o roteamento/provider layer deve recusar nova tentativa que ultrapasse o teto restante.
- **R7** — falha antes de efeito pago libera; resultado externo incerto segue política específica do efeito.
- **R8** — RLS/permissions impedem A↔B e cliente não escreve ledger.

### Fora de escopo

Stripe/Google; UI; créditos grátis; overdraft.

## Plano

1. Modelar ledger e invariantes com testes antes da migration.
2. Implementar transações SQL com locks/constraints adequados.
3. Integrar reservation API ao operation boundary sem cobrar ainda produção.
4. Chaos/concurrency: crash entre reserve/settle/release.
5. Astra revisa dupla cobrança, dinheiro criado/destruído, ownership e compensações.

## Critérios de aceite

- [ ] conservação financeira em todos os testes.
- [ ] replay não cobra duas vezes.
- [ ] saldo nunca negativo.
- [ ] crash converge.
- [ ] cliente só lê views próprias; backend é único writer.
- [ ] Astra review aprovada.

## Gates / evidência

pytest financeiro + Postgres local concorrente + fault injection + pgTAP/RLS. Sem provider pago.

## Invariantes formais

Para cada wallet: `purchases + releases + positive_adjustments - settles - refunds - reversals - negative_adjustments = available + reserved + explicitly_accounted_debt/holds`. Reservas nunca podem ser gastas duas vezes e `available >= 0` é hard invariant.

Normal turns referenciam `operation_id`; outros efeitos usam reference type/id próprio. Não ampliar `app.operations.kind` apenas para “caber billing” sem necessidade arquitetural.

## Gate de fechamento

- [ ] corrida com duas reservas sobre o mesmo saldo permite no máximo o valor disponível, sem overspend;
- [ ] replay do mesmo operation/reference gera zero débito adicional;
- [ ] crash em cada fronteira reserve->effect->settle/release converge por recovery idempotente;
- [ ] RLS/client roles não conseguem INSERT/UPDATE/DELETE ledger;
- [ ] soma do ledger reconstrói o saldo armazenado/cacheado em property/fault tests;
- [ ] Astra independente retorna `APPROVED`; sem isso a spec não fecha.
