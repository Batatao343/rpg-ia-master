# SPEC-185 — Conta, dashboard e custo por turno

> **Status:** `done`
> **Depende de:** SPEC-184 `done`
> **EXECUTOR_MODEL obrigatório:** `Terra`
> **EXECUTOR_EFFORT obrigatório:** `High`
> **REVIEW_MODEL obrigatório:** `Sol`
> **REVIEW_EFFORT:** `High`
> **REVIEW_REQUIRED:** `true`
> **SUBSTITUIÇÃO DE MODELO:** usuário autorizou Sol High executor após handoff Terra High; outro Sol High fez revisão independente.
> **Delegação Luna permitida:** Luna: fixtures de dashboard, inventário de rotas e relatório visual; ownership/DTOs ficam com Terra.
> **MODEL_BREAKDOWN:** `docs/rpg-next-jev-golive-plan/examples/spec-model-contract.yaml` → `SPEC-185` é source of truth para subtarefas/review focus

## Objetivo

Adicionar uma camada de conta fora da tela de jogo: saldo, compra futura, histórico, gráfico de consumo e custo on-demand associado a cada mensagem/turno.

## Requisitos

- **R1** — rota/tela Account acessível sem entrar numa campanha.
- **R2** — saldo discreto no shell principal.
- **R3** — 24h/7d/30d; categorias game/image/voice; purchase history; usage history paginado.
- **R4** — cada turno expõe apenas custo agregado próprio do owner; desktop hover/focus, mobile tap. O vínculo vem de `app.turns`/operation/usage e timeline epoch; **não** gravar Estilhas/custo dentro de `GameState` ou `presentation_history`.
- **R5** — nenhum provider/token técnico na UI padrão; detalhe avançado opcional.
- **R6** — gráfico não faz cálculo financeiro no client; consome séries agregadas server-side.
- **R7** — acessibilidade teclado/touch e 390/1440.

### Fora de escopo

Stripe/Play checkout; admin dashboard.

## Plano

1. Endpoints DTOs read-only e testes ownership.
2. App shell/navigation.
3. Account screen + chart simples sem nova lib se SVG/CSS bastar.
4. StoryLog cost affordance.
5. browser tests desktop/mobile.

## Critérios de aceite

- [x] usuário vê saldo/consumo sem quebrar imersão.
- [x] custo por mensagem pertence à operation correta.
- [x] mobile não depende de hover.
- [x] outro usuário nunca acessa ledger/usage.
- [x] sem N+1 material no histórico.

## Gates / evidência

Node tests + Playwright/browser local + visual/accessibility contracts.

## Gate de fechamento

- [x] restauração/timeline epoch não associa custo de um turno antigo à mensagem errada;
- [x] history DTO continua compatível e o enrichment financeiro falha de forma degradada (mensagem continua visível sem custo se read model indisponível);
- [x] queries de 50 mensagens são bounded/paginadas e não fazem uma query financeira por mensagem;
- [x] 390px usa tap/focus; 1440px pode usar hover/focus; teclado e screen reader recebem texto equivalente;
- [x] outro owner recebe 404/empty conforme contrato, nunca valor financeiro alheio;
- [x] review Sol independente aprova ownership/read-model boundary.

## Resultado e limite de cobrança

`app.turns.presentation_entry_id` liga o narrador persistido à operação e ao
`timeline_epoch` no commit; o histórico consulta os custos em lote por página.
O StoryLog mostra custo técnico da operação em USD, com origem e exatidão, e
separa eventual débito liquidado em Estilhas. O dashboard agrega no servidor
somente `wallet_entries.settle` em 24h/7d/30d. Atividade de usage, reservas e
liberações não são consumo liquidado; ausência de liquidação aparece como tal.
Saldo e valores inteiros do ledger trafegam em strings decimais. Abertura de
campanha e saves antigos sem vínculo ficam sem custo por mensagem.

Esta spec é somente leitura financeira. A integração
`reserve → execute → settle → release` das jogadas normais em `/game/action`
continua pendente conforme `02_BILLING_E_MARGIN.md`, para uma spec futura; não
há cobrança comercial ativa. Evidência e limites: `docs/spec185/README.md`.
