# SPEC-174 — Baseline v1 do build atual

> **Status:** `done`
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

- [x] SHA, environment, dataset hash e evaluator version registrados;
- [x] resultados brutos preservados;
- [x] nenhum target contínuo inventado antes dos números;
- [x] nenhuma mudança de gameplay/prompts para melhorar baseline.

## Execução — 2026-09-30

- Aprovada pelo pedido do usuário para executar as specs draft em ordem, com
  SPEC-104 cloud mantida on hold.
- Iniciada somente após os gates locais da SPEC-173 passarem.
- Baseline determinística executada com os sete suites de produto: 86 casos,
  zero error/skip/hard failure. O comparador candidato/baseline confirmou
  compatibilidade e deltas zero nas 16 métricas.
- Frontend executado novamente no build atual: F01–F16, 16/16 em 176,76 s,
  zero retry/flake/pageerror/console/request/5xx/overflow/a11y serious-critical.
  Snapshot visual permaneceu corretamente fora do ambiente Linux pinado.
- SHA, hash da árvore dirty, seis hashes de dataset, seleção, evaluator 1.6.0,
  registry, seed, Python/Node/Playwright/Chromium e hashes dos resultados foram
  congelados em `docs/eval-baselines/v1/manifest.json`. Resultados brutos e
  relatório factual estão no mesmo diretório.
- Provider real foi omitido pela restrição de custo já dada pelo usuário; não é
  pendência da baseline. Custo/latência reais não foram inventados. Long-run não
  foi executado e nenhum target foi definido. Nenhum gameplay/prompt mudou.
