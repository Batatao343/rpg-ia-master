# SPEC-184 — Wallet ledger, reservas e settlement atômico

> **Status:** `done`
> **Depende de:** SPEC-183 `done`
> **EXECUTOR_MODEL obrigatório:** `Sol`
> **EXECUTOR_EFFORT obrigatório:** `High`
> **REVIEW_MODEL obrigatório:** `Astra`
> **REVIEW_EFFORT:** `High`
> **REVIEW_REQUIRED:** `true`
> **SUBSTITUIÇÃO DE MODELO:** proibida sem aprovação explícita do usuário; mismatch => `MODEL_HANDOFF_REQUIRED`
> **Delegação Luna permitida:** Luna: somente execução/compilação de testes e relatório; nenhuma edição em ledger/transações.
> **MODEL_BREAKDOWN:** `docs/rpg-next-jev-golive-plan/examples/spec-model-contract.yaml` → `SPEC-184` é source of truth para subtarefas/review focus

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

- [x] conservação financeira em todos os testes.
- [x] replay não cobra duas vezes.
- [x] saldo nunca negativo.
- [x] crash converge.
- [x] cliente só lê views próprias; backend é único writer.
- [x] Astra review aprovada ([parecer](../handoffs/SPEC-184-ASTRA-independent-review.md)).

## Gates / evidência

pytest financeiro + Postgres local concorrente + fault injection + pgTAP/RLS. Sem provider pago.

## Invariantes formais

Para cada wallet: `purchases + positive_adjustments - settles - refunds - reversals - negative_adjustments = available + reserved`. `reserve` transfere valor de `available` para `reserved`; `release` faz a transferência inversa. Nenhum dos dois cria valor. Débito ou hold além da reserva fica fora de escopo nesta versão, que não permite overdraft. Reservas nunca podem ser gastas duas vezes e `available >= 0` é hard invariant. Correção conceitual registrada na implementação após revisão Astra: a equação anterior somava `releases` ao patrimônio e criava valor fictício.

Normal turns referenciam `operation_id`; outros efeitos usam reference type/id próprio. Não ampliar `app.operations.kind` apenas para “caber billing” sem necessidade arquitetural.

## Gate de fechamento

- [x] corrida com duas reservas sobre o mesmo saldo permite no máximo o valor disponível, sem overspend;
- [x] replay do mesmo operation/reference gera zero débito adicional;
- [x] crash em cada fronteira reserve->effect->settle/release converge por recovery idempotente;
- [x] RLS/client roles não conseguem INSERT/UPDATE/DELETE ledger;
- [x] soma do ledger reconstrói o saldo armazenado/cacheado em property/fault tests;
- [x] Astra independente retorna `APPROVED`; sem isso a spec não fecha.
