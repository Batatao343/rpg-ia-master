# Review handoff — SPEC-164 — Sol

`MODEL_HANDOFF_REQUIRED: gpt-5.6-sol`

## Escopo da revisão independente

Verificar se a nova seção `Operação de specs e evals` em `AGENTS.md`:

1. conflita com alguma instrução operacional preexistente;
2. duplica documentação especializada além do necessário;
3. permite long-run implícito por baseline, release ou regressão;
4. deixa ambígua a precedência entre source, project index e evaluators;
5. permite que o executor autoaprove uma revisão obrigatória.

## Arquivos relevantes

- `specs/SPEC-164-agents-md-model-routing.md`
- `AGENTS.md`
- `tests/test_agents_contract.py`
- `docs/evals-plan-v4/00_AGENTS_MD_UPDATE.md`
- `docs/evals-plan-v4/12_MODEL_EXECUTION_POLICY.md`
- `docs/evals-plan-v4/08_CONTRATO_CODING_AGENT.md`

## Gates do executor

- `uv run pytest tests/test_agents_contract.py tests/test_spec_index.py tests/test_spec_migration_safety.py -q`
- suíte completa obrigatória antes da promoção para `done`.

## Decisão esperada

Registrar `APPROVED` ou `CHANGES_REQUESTED`, modelo, run id e achados na seção
de execução da SPEC-164. O executor atual não pode preencher essa decisão como
revisão independente.

## Histórico

- `SPEC-164-SOL-20260928-01`: `CHANGES_REQUESTED`. A instrução legada
  `specs/<nome>.md` conflitava com a identidade canônica introduzida pela
  SPEC-163.
- Correção aplicada: próximo ID nunca utilizado, filename
  `specs/SPEC-NNN-<slug>.md`, registro obrigatório em `specs/index.yaml` e teste
  que proíbe a forma legada. Re-review solicitado.
- `SPEC-164-SOL-20260928-02`: `APPROVED`. Riscos residuais não bloqueantes:
  contrato textual não detecta toda contradição futura e alocação concorrente de
  IDs exige serialização operacional.
