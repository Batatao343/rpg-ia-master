# SPEC-176 — Restaurar integridade de evals e CI em checkout limpo

> **Status:** `draft`
> **Depende de:** SPEC-175 `done`
> **EXECUTOR_MODEL obrigatório:** `Sol`
> **EXECUTOR_EFFORT obrigatório:** `High`
> **REVIEW_MODEL obrigatório:** `Sol`
> **REVIEW_EFFORT:** `High`
> **REVIEW_REQUIRED:** `true`
> **SUBSTITUIÇÃO DE MODELO:** proibida sem aprovação explícita do usuário; mismatch => `MODEL_HANDOFF_REQUIRED`
> **Delegação Luna permitida:** Luna: logs, hashes e comparação mecânica somente; não decide semântica da régua.
> **MODEL_BREAKDOWN:** `examples/spec-model-contract.yaml` → `SPEC-176` é source of truth para subtarefas/review focus

## Contexto observado

No push do `main` `1beefc432cce5ded4e3468e42c5e583aa4431a44`, o GitHub Actions expôs divergências que o workspace local não capturou:

- `eval-gates / deterministic-evals` falhou antes de executar as evals com `dataset hash mismatch: datasets/regression/narrative_npc.jsonl`;
- `eval-gates / backend-selective` e `validate / test` herdaram a mesma falha de governance;
- `validate / test` também encontrou `project index is stale: source tree or generated artifacts changed`;
- `eval-gates / protected-evaluator-review` falhou corretamente porque paths protegidos mudaram sem aprovação no environment `eval-governance`;
- frontend, audit-local e scope passaram, portanto não interpretar os vermelhos acima como score ruim de gameplay/modelo.

Runs observados: `eval-gates` 36955976005 e `validate` 36955975775.

## Objetivo

Fazer um **checkout limpo do commitado** reproduzir os mesmos gates verdes do workspace de desenvolvimento, sem enfraquecer a governança e sem alterar produto para “fazer CI passar”. Só depois desta spec é permitido iniciar o experimento Jev.

## Regras críticas

- **Não** apagar, relaxar ou bypassar `evals/protected-paths.txt`, hashes, environment approval ou `project_index check`.
- **Não** regenerar `evals/manifest.lock.json` às cegas. Primeiro provar que o conteúdo atual de cada dataset protegido é o conteúdo aprovado pela spec/evidência que o originou.
- Se `narrative_npc.jsonl` tiver mudança semântica não aprovada, **não** aceitar o arquivo só porque é o estado atual: restaurar o dataset aprovado ou abrir tarefa separada de eval-authoring/review.
- Se o dataset atual for o aprovado e apenas o lock estiver stale, regenerar o lock determinística e explicitamente.
- O Project Index continua `selective-only` por decisão da SPEC-175; esta spec apenas sincroniza os artefatos versionados porque o CI atual ainda verifica freshness. Não reintroduzir o índice no contexto padrão.
- Nenhum provider real, Jev, long-run, gameplay, prompt ou mudança de modelo nesta spec.

## Procedimento obrigatório

1. Partir de clone/worktree limpo do HEAD e registrar `git status --porcelain`, SHA e árvore.
2. Reproduzir exatamente:
   - `uv run python -m evals.core.governance check --root .`
   - `uv run python -m project_index check`
   - testes focados de governance/harness/evals.
3. Auditar a divergência de `narrative_npc.jsonl` contra:
   - SPEC-171 e sua evidência de execução;
   - baseline v1 e hashes congelados aplicáveis;
   - `git diff`/histórico local disponível;
   - `evals/manifest.lock.json`.
4. Classificar a causa como `STALE_LOCK`, `UNAPPROVED_DATASET_DRIFT` ou `OTHER`; registrar evidência.
5. Se `STALE_LOCK`, regenerar schemas/lock somente pelo comando/código canônico de governance e revisar o diff antes de aceitar.
6. Regenerar `project_index` a partir do source final e confirmar freshness no checkout limpo.
7. Rodar a suíte focada e depois `uv run pytest -q`; frontend só precisa ser repetido se os arquivos afetados o selecionarem.
8. Garantir que artefatos gerados necessários estejam realmente versionados no commit, não apenas presentes no workspace.
9. Passar pelo `protected-evaluator-review` real do environment `eval-governance`; não fixar `EVALUATOR_CHANGE_APPROVED=true` como bypass permanente.
10. Fazer novo push e exigir verde nos jobs aplicáveis antes de marcar `done`.

## Critérios de aceite

- [ ] `evals.core.governance check` verde em checkout limpo;
- [ ] `project_index check` verde em checkout limpo;
- [ ] `uv run pytest -q` verde no commit final;
- [ ] `deterministic-evals` realmente executa as suites em vez de parar no governance check;
- [ ] `backend-selective` verde quando selecionado;
- [ ] `protected-evaluator-review` passa por aprovação explícita e auditável quando paths protegidos mudam;
- [ ] nenhum gate foi removido, convertido em warning ou tornado permissivo;
- [ ] nenhuma mudança de produto/modelo/JeV;
- [ ] `ESTADO_ATUAL.md` registra causa raiz e run verde final;
- [ ] somente após tudo acima a SPEC-177 pode começar.

## Model routing

Executor desta spec é **Sol High** porque o problema cruza evaluator governance, protected boundaries e diferença entre workspace/checkout limpo. Luna pode apenas agregar logs/hashes/diffs. Review final também é Sol High em contexto independente, além do approval humano `eval-governance` quando houver path protegido.

## Gate de fechamento adicional

- [ ] o commit corretivo não altera gameplay, prompts, provider routing ou thresholds de produto;
- [ ] `git status --porcelain` é vazio no checkout usado para o gate final;
- [ ] o reviewer Sol recebe causa raiz + diff + logs dos runs vermelhos/verdes e retorna `APPROVED`;
- [ ] se a causa for `UNAPPROVED_DATASET_DRIFT`, esta spec NÃO pode absorver a mudança: deve parar com `EVAL_AUTHORING_REQUIRED`.
