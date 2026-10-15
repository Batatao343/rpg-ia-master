# SPEC-185 — Conta, dashboard e custo por turno

> **Status:** `draft`
> **Depende de:** SPEC-184 `done`
> **EXECUTOR_MODEL obrigatório:** `Terra`
> **EXECUTOR_EFFORT obrigatório:** `High`
> **REVIEW_MODEL obrigatório:** `Sol`
> **REVIEW_EFFORT:** `High`
> **REVIEW_REQUIRED:** `true`
> **SUBSTITUIÇÃO DE MODELO:** proibida sem aprovação explícita do usuário; mismatch => `MODEL_HANDOFF_REQUIRED`
> **Delegação Luna permitida:** Luna: fixtures de dashboard, inventário de rotas e relatório visual; ownership/DTOs ficam com Terra.
> **MODEL_BREAKDOWN:** `examples/spec-model-contract.yaml` → `SPEC-185` é source of truth para subtarefas/review focus

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

- [ ] usuário vê saldo/consumo sem quebrar imersão.
- [ ] custo por mensagem pertence à operation correta.
- [ ] mobile não depende de hover.
- [ ] outro usuário nunca acessa ledger/usage.
- [ ] sem N+1 material no histórico.

## Gates / evidência

Node tests + Playwright/browser local + visual/accessibility contracts.

## Gate de fechamento

- [ ] restauração/timeline epoch não associa custo de um turno antigo à mensagem errada;
- [ ] history DTO continua compatível e o enrichment financeiro falha de forma degradada (mensagem continua visível sem custo se read model indisponível);
- [ ] queries de 50 mensagens são bounded/paginadas e não fazem uma query financeira por mensagem;
- [ ] 390px usa tap/focus; 1440px pode usar hover/focus; teclado e screen reader recebem texto equivalente;
- [ ] outro owner recebe 404/empty conforme contrato, nunca valor financeiro alheio;
- [ ] review Sol independente aprova ownership/read-model boundary.
