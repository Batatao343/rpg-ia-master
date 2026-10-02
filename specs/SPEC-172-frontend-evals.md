# SPEC-172 — Frontend Evals e Jornadas Críticas

> **Status:** `done`
> **Depende de:** SPEC-171 `done`
> **Modelo executor mínimo:** Terra High
> **Revisão:** por escalada

## Reuso

`web/tests/*.test.mjs`, browser tests Python, `scripts/audit_local_gate.py`.

## Entregas

- Playwright TS em `web/e2e`;
- fixtures determinísticas;
- F01–F16;
- console/pageerror/network gates;
- responsive 320/390/768/1440;
- accessibility;
- visual snapshots só em ambiente pinado;
- regressão do logout mobile overlap.

## Model routing

Luna pode inventariar telas/rotas e gerar matriz de casos a partir do contrato. Terra implementa Playwright/fixtures. Escalar Sol apenas para race conditions, auth/session complexa, flake sem causa local ou contrato frontend/backend ambíguo.

## Aceite

- [x] critical journeys 100%;
- [x] pageerror/console.error/5xx inesperado = 0;
- [x] serious/critical a11y = 0;
- [x] sem sleeps fixos para sincronização normal;
- [x] responsive sem overlap/overflow crítico.

## Execução — 2026-09-30

- Aprovada pelo pedido do usuário para executar as specs draft em ordem, com
  SPEC-104 cloud mantida on hold.
- Implementação iniciada após SPEC-171 `done` e seu gate final verde.
- Matriz canônica em `web/e2e/critical-journeys.yaml` e suíte Playwright TS em
  `web/e2e/critical-journeys.spec.ts`: F01–F16 executam a aplicação React real
  contra uma API determinística interceptada, sem provider, rede externa ou
  sleeps fixos de sincronização.
- Guard global falha por `pageerror`, `console.error`, request abortado e HTTP
  5xx inesperados. As únicas exceções são falhas deliberadamente injetadas e
  assertadas por F05/F13/F14 e o cancelamento via `AbortController` do retrato
  durante o remount de desenvolvimento.
- Axe bloqueia impactos `serious`/`critical`; F16 cobre 320×568, 390×844,
  768×1024 e 1440×900, overflow horizontal, controles do topo, HUD, mapa e
  input. Snapshots são opt-in somente em Chromium/Linux pinado.
- `scripts/frontend_eval_report.py` normaliza o JSON do Playwright nas sete
  métricas frontend bloqueantes do registry 1.6.0. Smoke canônico: 16/16,
  `frontend_critical_journey_pass_rate=1.0` e todos os seis contadores em zero.
- Achados corrigidos no produto: render prematuro de rotas protegidas antes do
  bootstrap de auth; narração perdida quando o único chunk SSE tinha
  `done=true`; mapa sem ação clicável/teclável; metadado de quest com contraste
  3,77:1; e HUD móvel que cobria seu próprio botão de fechar.
- Build Vite, 5 testes Node, Ruff e 5 contratos Python específicos verdes.
  Gate final offline: 1.883 passed, 35 skipped, 15 deselected. Nenhuma chamada
  paga, long-run ou cloud; SPEC-104 permanece on hold.
