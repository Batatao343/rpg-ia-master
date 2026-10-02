# Review handoff — SPEC-167 — Sol

`MODEL_HANDOFF_REQUIRED: gpt-5.6-sol`

## Escopo

Revisar somente leitura:

1. expected nunca é calculado pelo adapter/produto sob avaliação;
2. governança é validada antes de executar e a CLI também integra o ruler hash;
3. todo caso elegível vira result/error/skip, com diagnóstico, e hard fail retorna
   exit code não zero;
4. metadata contém product SHA, dataset/ruler/registry hashes, evaluator version,
   seed e ambiente;
5. baseline incompatível falha fechado antes de calcular delta;
6. `playtest.invariants.check_all` é reutilizado, sem regras duplicadas;
7. execução offline não alcança provider e restaura `RPG_FORCE_MOCK`;
8. não foi criado um segundo sistema de campanhas/telemetria longa.

## Arquivos principais

- `specs/SPEC-167-deterministic-eval-harness.md`
- `evals/core/adapters.py`
- `evals/core/runner.py`
- `evals/core/compare.py`
- `evals/core/schemas.py`
- `evals/core/governance.py`
- `evals/__main__.py`
- `evals/datasets/regression/harness.jsonl`
- `evals/manifest.lock.json`
- `evals/metrics-registry.yaml`
- `evals/protected-paths.txt`
- `tests/test_eval_harness.py`
- `tests/test_eval_governance.py`

## Evidência

- governance check e lock: verdes, 2 datasets;
- smoke `harness.jsonl`: 2/2, `exact_match=1.0`, provider nulo;
- 22 testes focados + Ruff verdes;
- Project Index regenerado/fresco: 5.317 nodes, 13.589 edges;
- nenhuma chamada paga, browser, cloud ou long-run.

## Histórico

- `SPEC-167-SOL-20260928-01`: `CHANGES_REQUESTED` por adapter receber o
  `EvalCase.expected` e `product_sha` não distinguir worktree dirty.
- Correções: `AdapterCase` não expõe expected/oracle; `repository_identity`
  registra HEAD + SHA-256 de todos os arquivos Git-visible + dirty state; reports
  e schemas carregam essa identidade; comparação exige que o run atual corresponda
  ao worktree ativo. Regressões adversariais cobrem roubo do expected e mudança
  de bytes sem mudança de HEAD.
- Evidência atual: governance válido, **25 testes focados** e Ruff verdes.
- `SPEC-167-SOL-20260928-02`: `APPROVED`, sem bloqueadores. Suíte final:
  **1.841 passed, 35 skipped, 15 deselected**, zero falhas.

Retorne `APPROVED` ou `CHANGES_REQUESTED`, modelo/run id, bloqueadores e riscos
residuais. O executor não pode autoaprovar.
