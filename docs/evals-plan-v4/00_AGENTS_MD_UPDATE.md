# 00 — Conteúdo obrigatório para atualização do AGENTS.md

A SPEC-164 deve incorporar no `AGENTS.md` somente regras operacionais, apontando para documentação especializada.

## Retomada

```text
1. Leia ESTADO_ATUAL.md e specs/index.yaml.
2. Identifique a SPEC-ID ativa e suas dependências.
3. Leia project_index/domains.yaml quando existir.
4. Consulte repo_graph/state_ownership/eval_map somente se relevante.
5. Abra source real antes de modificar comportamento.
6. Consulte MODEL_EXECUTION_POLICY e use o menor tier suficiente.
7. Rode a menor suíte determinística que prova a mudança.
```

## Model routing

```text
Luna  -> inventário, histórico, transforms, reports, manifests, execução mecânica
Terra -> implementação bounded definida pela spec
Sol   -> cross-domain, state/concurrency, debugging difícil, technical review
Astra -> scarce review de arquitetura/evaluator semantics
```

Se reviewer/model mínimo não estiver disponível: `MODEL_HANDOFF_REQUIRED`; não autoaprovar.

## Eval integrity

Optimizer não altera evaluator, expected, regression dataset, denominator, baseline ou exclusions na mesma tarefa.

## State ownership

Antes de novo writer persistente, consultar ownership, canonical owner e invariantes/save-load.

## Long-run

Long-run, 100/200 turns e 10x200 NÃO pertencem a baseline, PR, deploy ou optimization gates. Somente pedido explícito do usuário ou futura spec explicitamente aprovada.

## Não duplicar

Não copiar schemas completos, lista de métricas ou repo graph para AGENTS. Apontar para os arquivos correspondentes.
