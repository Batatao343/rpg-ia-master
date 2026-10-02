# SPEC-174 — Baseline v1 do build atual

> **Status:** `draft`
> **Depende de:** SPEC-173 `done`
> **Modelo executor mínimo:** Luna para execução/reporting
> **Modelo para correção de harness:** Terra
> **Mudança de produto:** proibida

## Objetivo

Medir o produto antes de definir targets.

## Baseline

- deterministic state/rules;
- routing/action;
- memory/RAG/context local/fixture;
- narrative hard claims;
- frontend journeys;
- short real-provider contracts quando autorizados/aplicáveis.

## Model routing

Luna roda comandos, agrega JSON e produz relatório factual. Não interpreta score como “bom/ruim” além dos hard contracts já definidos. Se o harness quebrar, Terra pode corrigir infraestrutura de eval; qualquer correção que altere produto exige parar e criar spec separada.

## Long-run

Não executar. Não marcar como pendente. Não incluir na baseline-v1.

## Aceite

- [ ] SHA, environment, dataset hash e evaluator version registrados;
- [ ] resultados brutos preservados;
- [ ] nenhum target contínuo inventado antes dos números;
- [ ] nenhuma mudança de gameplay/prompts para melhorar baseline.
