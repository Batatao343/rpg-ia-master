# SPEC-176 — Restaurar integridade de evals e CI em checkout limpo

> **Status:** `review-pending`
> **Depende de:** SPEC-175 `done`
> **EXECUTOR_MODEL obrigatório:** `Sol`
> **EXECUTOR_EFFORT obrigatório:** `High`
> **REVIEW_MODEL obrigatório:** `Sol`
> **REVIEW_EFFORT:** `High`
> **REVIEW_REQUIRED:** `true`
> **SUBSTITUIÇÃO DE MODELO:** proibida sem aprovação explícita do usuário; mismatch => `MODEL_HANDOFF_REQUIRED`
> **Delegação Luna permitida:** Luna: logs, hashes e comparação mecânica somente; não decide semântica da régua.
> **MODEL_BREAKDOWN:** `docs/rpg-next-jev-golive-plan/examples/spec-model-contract.yaml` → `SPEC-176` é source of truth para subtarefas/review focus

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

- [x] `evals.core.governance check` verde em checkout limpo;
- [x] `project_index check` verde em checkout limpo;
- [ ] `uv run pytest -q` verde no commit final;
- [ ] `deterministic-evals` realmente executa as suites em vez de parar no governance check;
- [ ] `backend-selective` verde quando selecionado;
- [ ] `protected-evaluator-review` passa por aprovação explícita e auditável quando paths protegidos mudam;
- [x] nenhum gate foi removido, convertido em warning ou tornado permissivo;
- [x] nenhuma mudança de produto/modelo/JeV;
- [ ] `ESTADO_ATUAL.md` registra causa raiz e run verde final;
- [x] somente após tudo acima a SPEC-177 pode começar (não iniciada).

## Model routing

Executor desta spec é **Sol High** porque o problema cruza evaluator governance, protected boundaries e diferença entre workspace/checkout limpo. Luna pode apenas agregar logs/hashes/diffs. Review final também é Sol High em contexto independente, além do approval humano `eval-governance` quando houver path protegido.

## Gate de fechamento adicional

- [x] o commit corretivo não altera gameplay, prompts, provider routing ou thresholds de produto;
- [x] `git status --porcelain` é vazio no checkout usado para o gate final;
- [x] o reviewer Sol recebe causa raiz + diff + logs dos runs vermelhos/verdes e retorna `APPROVED` técnico local;
- [ ] se a causa for `UNAPPROVED_DATASET_DRIFT`, esta spec NÃO pode absorver a mudança: deve parar com `EVAL_AUTHORING_REQUIRED`.

## Execução local — 2026-10-02

- Executor selecionado pelo harness: Sol High (`gpt-6.1-sol/high`), task/session
  `/root/spec176_executor`; proveniência: parâmetros `spawn_agent` atestados
  pelo coordenador. Nenhum run ID adicional foi inventado.
- Causa: `STALE_LOCK` por LF/CRLF, sem drift semântico; 27 IDs/expected e bytes
  aprovados comprovados antes do relock. Detalhes/auditoria em
  `docs/spec176/README.md` e `docs/spec176/dataset-audit.json`.
- O relock canônico muda apenas um hash; hashing continua raw. `.gitattributes`
  fixa bytes LF e três regressões provam clones true/false e tamper fail-closed.
  Nenhum evaluator/dataset/expected/registry/schema semântico/baseline/workflow
  foi alterado. Project Index final: 5.516 nós/14.089 arestas, selective-only.
- Snapshot local de código validado:
  `d988991fc35f2f4532131eb8c748b7f6609b5d55`, somente no clone de verificação.
  Focused: 80 verdes; CLI sete suites: 86/86; smoke 14 perfis × 3 turnos,
  zero erro/violações. Suíte completa no clone: **1.898 passed, 35 skipped,
  15 deselected**, 1 warning, 317,92 s.
- Baseline v1 é evidência histórica intocada e estritamente incompatível com
  a régua LF; hashes históricos de artifacts também divergem. Não alegar
  score delta A/B contra v1 nem reescrever seus hashes nesta tarefa.
- Revisão Sol independente **APPROVED técnico local**, tarefa
  `/root/spec176_reviewer`; parecer em
  `handoffs/SPEC-176-SOL-independent-review.md`. Status máximo permanece
  `review-pending`: approval humano `eval-governance` e push/CI real verde
  são gates ainda pendentes.
  SPEC-177 não iniciou; artes preexistentes preservadas. Nenhum provider real,
  cloud, JeV ou long-run foi executado.
