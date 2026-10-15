# SPEC-188 — Quote e cobrança explícita de geração de imagem

> **Status:** `draft`
> **Depende de:** SPEC-187 `done`
> **EXECUTOR_MODEL obrigatório:** `Sol`
> **EXECUTOR_EFFORT obrigatório:** `High`
> **REVIEW_MODEL obrigatório:** `Sol`
> **REVIEW_EFFORT:** `High`
> **REVIEW_REQUIRED:** `true`
> **SUBSTITUIÇÃO DE MODELO:** proibida sem aprovação explícita do usuário; mismatch => `MODEL_HANDOFF_REQUIRED`
> **Delegação Luna permitida:** Luna: inventário de triggers de arte e relatório de testes; quote/wallet/worker ficam com Sol.
> **MODEL_BREAKDOWN:** `examples/spec-model-contract.yaml` → `SPEC-188` é source of truth para subtarefas/review focus

## Objetivo

Colocar a geração dinâmica de imagem atrás de quote explícito em Estilhas, preservando a proteção atual contra duplicar efeito pago incerto.

## Requisitos

- **R1** — `image_quote` imutável, owner, type, credits, pricing_version, expiry.
- **R2** — UI mostra custo final em Estilhas e pede confirmação; o valor confirmado é o teto de débito do usuário para aquela geração.
- **R3** — confirmar quote cria reserve idempotente antes de enfileirar.
- **R4** — worker settle em sucesso; release em falha seguramente não enviada.
- **R5** — `external_result_uncertain` não faz retry pago automático nem refund automático sem política explícita.
- **R6** — reformulation gera quote novo.
- **R7** — saldo insuficiente não chama provider.
- **R8** — quote não é controlado pelo client.

### Fora de escopo

Imagem grátis automática; subscription; alterar orçamento narrativo de arte.

## Plano

1. Regressões sobre fluxo atual de art reservation.
2. Quote service + migration.
3. Wallet integration.
4. UI dialog.
5. Crash/fault tests worker/DB/provider boundary.

## Critérios de aceite

- [ ] nenhum provider call antes de confirmação/reserva.
- [ ] replay não gera segunda imagem/cobrança.
- [ ] quote expirado falha fechado.
- [ ] uncertain external effect é visível/reconciliável.

## Gates / evidência

Fake generator + fault injection. Uma geração real só por pedido/orçamento explícito.

## Regra de produto crítica — triggers existentes

O código atual possui triggers automáticos de retrato/NPC/cena épica. Após esta spec, trigger automático pode criar **offer/cue/placeholder**, mas **nenhum caminho** pode chamar `ImageGenerator.generate` ou reservar Estilhas sem quote válido + confirmação explícita do owner. Não existe “imagem automática paga”.

Se o custo real do provider exceder o quote confirmado, registrar margem negativa/anomalia para FinOps; não debitar mais Estilhas do que o quote sem nova confirmação.

## Gate de fechamento

- [ ] busca/source prova que todos os caminhos que chegam ao provider passam pelo gate quote+confirm;
- [ ] triggers NPC/epic não geram nem debitam automaticamente;
- [ ] quote é owner-bound, one-time, expira e não pode ter credits/model/type alterados pelo client;
- [ ] duplicate confirm/replay = uma geração e um settlement no máximo;
- [ ] `external_result_uncertain` mantém hold/reconciliation explícita e não retry cego;
- [ ] review Sol independente aprova todos os provider-call paths.
