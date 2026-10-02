# SPEC-172 — Frontend Evals e Jornadas Críticas

> **Status:** `draft`
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

- [ ] critical journeys 100%;
- [ ] pageerror/console.error/5xx inesperado = 0;
- [ ] serious/critical a11y = 0;
- [ ] sem sleeps fixos para sincronização normal;
- [ ] responsive sem overlap/overflow crítico.
