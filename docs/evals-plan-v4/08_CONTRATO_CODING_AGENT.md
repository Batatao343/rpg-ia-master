# 08 — Contrato do Coding Agent

## Seleção de modelo antes de qualquer tarefa

Ler `12_MODEL_EXECUTION_POLICY.md` e `examples/model-routing.yaml`.

O agente deve usar o menor modelo permitido para a etapa. Se puder delegar subtarefas, Luna recebe primeiro trabalho mecânico; Terra recebe implementação bounded; Sol entra por complexidade/escalation; Astra apenas nos checkpoints definidos.

Não declarar revisão Sol/Astra se ela não ocorreu em execução/contexto independente. Se indisponível, criar handoff e marcar `MODEL_HANDOFF_REQUIRED`.

Este arquivo pode ser transformado em instrução operacional para Claude Code/Codex.

## Missão 1: construir o harness, não otimizar o jogo

```text
Você está trabalhando no repositório rpg-ia-master.

Antes de editar:
1. leia AGENTS.md, ESTADO_ATUAL.md, ROADMAP.md;
2. leia playtest/{runner,invariants,telemetry,metrics,scenarios}.py;
3. leia rag.py, services/context_builder.py, services/narrative_evidence.py e services/memory_provenance.py;
4. leia os browser/frontend tests atuais.

Objetivo desta missão:
criar o sistema de avaliação descrito nas specs de eval, SEM tentar melhorar scores do produto nesta mesma missão.

Restrições:
- não mude prompts/modelos/gameplay para fazer a baseline parecer melhor;
- não apague ou enfraqueça invariantes existentes;
- não transforme LLM-as-judge em gate onde há oráculo estruturado;
- não reimplemente playtest/ em outro framework;
- cada evaluator deve ter testes próprios com known-good e known-bad;
- toda métrica deve documentar unidade, numerador, denominador e casos excluídos;
- toda saída deve carregar product SHA e dataset hash.

Critério de conclusão:
consigo rodar uma baseline reproduzível do build atual e identificar em qual camada um caso falhou.
```

## Missão de otimização futura

Template:

```text
OBJECTIVE
metric: <metric_id>
baseline: <value>
target: <value>

AUTHORIZED PATHS
<paths>

PROTECTED PATHS
/evals/core
/evals/evaluators
/evals/datasets/regression
<holdout inaccessible>

GUARDRAILS
<metric floors / hard invariants>

PROCESS
1. run baseline-compatible eval;
2. inspect per-case failures;
3. write hypothesis to experiments/EXP-xxx.md;
4. make one coherent change;
5. run dev eval;
6. run regression + guardrails;
7. revert if any hard guardrail fails;
8. keep only improvement supported by measurement;
9. do not alter evaluator/dataset;
10. once target reached, stop and request holdout evaluation.
```


## Política obrigatória de long-run

```text
LONG-RUN POLICY

Long-run playtests are NOT part of the default acceptance flow.

Do not run:
- long multi-profile campaigns;
- 100/200-turn simulations;
- real-provider long-runs;
- the 10x200 matrix;

unless:
1. the user explicitly requests it; or
2. a spec explicitly approved by the user requires long-horizon validation.

Do not treat "release", "baseline", "optimization" or "regression" as implicit permission to run long-run.
Default to the smallest deterministic eval/regression suite that proves the changed behavior.
Never use long-run as a substitute for a focused deterministic eval.
```

## Anti-gaming checks

Rejeitar mudança se:

- hardcodes para strings/IDs do dataset sem justificativa de domínio;
- ignora casos que falham;
- altera denominador para aumentar score;
- captura exception e retorna pass;
- aumenta timeout para esconder deadlock;
- adiciona retry indiscriminado para esconder flake;
- muda expected junto com implementação;
- lê holdout durante otimização;
- usa judge para substituir um check determinístico que estava falhando.

## Registro de experimento

Cada tentativa relevante:

```markdown
# EXP-001

Hypothesis:
...

Changed:
...

Before:
...

After:
...

Guardrails:
...

Decision: ACCEPTED | REVERTED
Reason:
...
```
