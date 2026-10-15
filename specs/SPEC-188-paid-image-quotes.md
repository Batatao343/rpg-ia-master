# SPEC-188 — Quote e cobrança explícita de geração de imagem

> **Status:** `done`
> **Depende de:** SPEC-187 `done`
> **EXECUTOR_MODEL obrigatório:** `Sol`
> **EXECUTOR_EFFORT obrigatório:** `High`
> **REVIEW_MODEL obrigatório:** `Sol`
> **REVIEW_EFFORT:** `High`
> **REVIEW_REQUIRED:** `true`
> **SUBSTITUIÇÃO DE MODELO:** proibida sem aprovação explícita do usuário; mismatch => `MODEL_HANDOFF_REQUIRED`
> **Delegação Luna permitida:** Luna: inventário de triggers de arte e relatório de testes; quote/wallet/worker ficam com Sol.
> **MODEL_BREAKDOWN:** `docs/planos/rpg-next-jev-golive-plan/examples/spec-model-contract.yaml` → `SPEC-188` é source of truth para subtarefas/review focus

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

- [x] nenhum provider call antes de confirmação/reserva.
- [x] replay não gera segunda imagem/cobrança.
- [x] quote expirado falha fechado.
- [x] uncertain external effect é visível/reconciliável.

## Gates / evidência

Fake generator + fault injection. Uma geração real só por pedido/orçamento explícito.

## Regra de produto crítica — triggers existentes

O código atual possui triggers automáticos de retrato/NPC/cena épica. Após esta spec, trigger automático pode criar **offer/cue/placeholder**, mas **nenhum caminho** pode chamar `ImageGenerator.generate` ou reservar Estilhas sem quote válido + confirmação explícita do owner. Não existe “imagem automática paga”.

Se o custo real do provider exceder o quote confirmado, registrar margem negativa/anomalia para FinOps; não debitar mais Estilhas do que o quote sem nova confirmação.

## Gate de fechamento

- [x] busca/source prova que todos os caminhos que chegam ao provider passam pelo gate quote+confirm;
- [x] triggers NPC/epic não geram nem debitam automaticamente;
- [x] quote é owner-bound, one-time, expira e não pode ter credits/model/type alterados pelo client;
- [x] duplicate confirm/replay = uma geração e um settlement no máximo;
- [x] `external_result_uncertain` mantém hold/reconciliation explícita e não retry cego;
- [x] review Sol independente aprova todos os provider-call paths.

## Implementação e validação — 13/10/2026

Sol High executou e outro Sol High aprovou a revisão independente sobre o
commit `a82adea` (`SPEC-188-SOL-20261013-INDEPENDENT-01`), sem achados abertos.
SPEC-187 permaneceu `done`; nenhum provider/modelo foi recarregado.

Quotes vinculam owner/campanha/epoch, tipo, modelo, brief/hash, teto, versão
FX/pricing e hash do card técnico de imagem. A validade é janela de aceite;
uma confirmação já persistida pode continuar no worker e ser consultada após
essa janela sem uma nova cobrança. Confirmação exige booleano literal e não
aceita alterações financeiras do cliente. `reserve → generation → enqueue →
game state` fazem commit na mesma transação. O worker lê dados canônicos,
valida fence/quote/reserva e grava ticket antes da rede; nenhum branch local ou
job antigo sem cotação passa pelo gate.

A revisão identificou quatro falhas e elas foram corrigidas: visibilidade de
resultado/hold de NPC/cena após reopen; reset de busy ao mudar sessão; parâmetro
`response_format` incompatível removido do adapter; custo normal por tokens
documentados agora liquida por card separado Standard, sem desconto Batch/cache.
O card identifica snapshot e fontes/derivação; nenhum preço comercial ou SKU foi
publicado. Unknown usage/effect preserva hold; custo acima do teto registra
anomalia e nunca debita o excesso ao usuário.

Gates: **78 focados**, incluindo **22 Postgres real** com dados em rollback;
**7 E2E da SPEC**, **38 browser completos passed + 1 skipped**, build e Ruff
verdes. Suíte Python revisada: **2.118 passed, 90 skipped, 15 deselected**,
exit 0, 213,41s; repetição de fechamento: **2.121 passed, 87 skipped,
15 deselected**, exit 0. Smoke live de imagem não executado: só permitido com pedido/budget
explícito de imagem; o gate aprovado usa gerador/HTTP fake e fault injection.

Evidência e inventário de todos os paths:
[docs/spec188/README.md](../docs/spec188/README.md).
Handoff para decisão independente:
[handoffs/SPEC-188-SOL-review.md](../handoffs/SPEC-188-SOL-review.md).
Parecer independente:
[handoffs/SPEC-188-SOL-independent-review.md](../handoffs/SPEC-188-SOL-independent-review.md).
