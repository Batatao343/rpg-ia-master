# Review handoff — SPEC-165 — Astra

`MODEL_HANDOFF_REQUIRED: gpt-6-astra`

## Escopo

Revisar semantics/governance, sem reimplementar. Perguntas obrigatórias:

1. Há leakage entre dev/regression e o holdout privado?
2. Algum denominador, exclusão ou hash pode ser manipulado silenciosamente?
3. O evaluator deriva expected da implementação sob teste?
4. A compatibilidade de baseline falha fechado nas identidades que mudam a régua?
5. Um LLM judge consegue substituir oráculo determinístico ou bloquear sem
   calibração humana suficiente?
6. A proteção de paths separa de fato optimizer e evaluator-change?

## Arquivos

- `specs/SPEC-165-eval-governance.md`
- `evals/core/schemas.py`
- `evals/core/hashing.py`
- `evals/core/governance.py`
- `evals/evaluators/exact.py`
- `evals/metrics-registry.yaml`
- `evals/manifest.lock.json`
- `evals/protected-paths.txt`
- `evals/README.md`
- `evals/datasets/regression/governance.jsonl`
- `tests/test_eval_governance.py`

## Evidência do executor

- governance `lock` e `check`: verdes;
- 12 testes focados: verdes;
- Ruff: verde;
- nenhum provider, long-run ou mudança de produto.

## Decisão esperada

Retornar `APPROVED` ou `CHANGES_REQUESTED`, `review_model`, `review_run_id`,
achados bloqueantes e riscos residuais. O executor não pode registrar a própria
aprovação independente.

## Histórico

- `SPEC-165-ASTRA-20260928-01`: `CHANGES_REQUESTED`.
- Correções: hashes do registry e dos sources de evaluator integram manifesto e
  identidade de baseline; seleção/configuração também são comparadas; controles
  protegidos incluem a própria lista/registry/schemas e comparação case-insensitive;
  judge blocking foi proibido até a SPEC-171; exact match agora exige tipos JSON
  estritos; resultado de run contabiliza todo caso elegível como resultado, erro
  ou skip explícito.
- `SPEC-165-ASTRA-20260928-02`: `CHANGES_REQUESTED`; seleção efetiva não era
  vinculada ao hash e regras em `evals/core` não integravam a identidade.
- Correção: `EvalRunResult` recomputa o hash canônico da seleção não vazia; o
  manifesto e metadata agora congelam o bundle completo `core + evaluators`.
- `SPEC-165-ASTRA-20260928-03`: `APPROVED`. Riscos residuais transferidos às
  specs do runner/CI/holdout: aplicar obrigatoriamente os contratos e preservar
  erros/skips na contabilização.
