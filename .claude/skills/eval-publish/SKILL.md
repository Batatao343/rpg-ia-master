---
name: eval-publish
description: Prepara a publicação de uma mudança em caminhos protegidos de eval (evals/core, datasets/regression, manifest.lock, web/e2e/contracts...) para aprovação do dono em 1 clique — valida o escopo, acha o run do eval-gates e imprime o comando de aprovação. Use em "/eval-publish", "publicar evals", ou quando um handoff diz EVAL_AUTHORING_REQUIRED / "publicar exige aprovação do environment eval-governance".
---

# /eval-publish

O agente **nunca** aprova o environment, nunca liga/desliga variáveis do GitHub e
não faz push sem o coordenador decidir. Ele só prepara e informa.

1. Lote: junte TODAS as autorias de eval pendentes da onda num único commit/branch
   (1 aprovação por onda, não por spec). Nada de código de produto no mesmo commit.
2. Rode:
   ```bash
   bash scripts/dev/py.sh scripts/dev/eval_publish.py --base origin/main
   ```
   - "refusing: … product code" → separe o commit.
   - "HEAD is not on the remote yet" → o coordenador faz o push e roda de novo.
3. Com o run esperando `eval-governance`, o script imprime o link e o comando que o
   **dono** roda (ou ele aprova pelo app do GitHub):
   `gh api -X POST repos/<owner>/<repo>/actions/runs/<id>/pending_deployments -F 'environment_ids[]=<env>' -f state=approved -f comment='…'`
   Passe isso ao dono numa linha e termine o turno (não espere em loop).
4. Depois da aprovação, uma chamada: `bash scripts/dev/py.sh scripts/dev/eval_publish.py --watch`.

**Régua mudou → regenerar a baseline do CI (SPEC-380).** Toda mudança de dataset,
adapter/evaluator, registry ou `--suite` deixa `evals/baselines/deterministic.json`
stale: o `compare` do `eval-gates` sai **2** e `tests/test_eval_baseline.py` falha.
Esperado, não é bug. No mesmo lote:
- commit A = a mudança de régua; push; no run do `eval-gates`, o `run` passa e o
  `compare` sai 2;
- `gh run download <run_id> --pattern 'deterministic-evals-*'` e copie
  `ci-<run_id>-<attempt>.json` para `evals/baselines/deterministic.json` **sem editar**
  (commit B, só esse arquivo); push; o `compare` sai 0;
- A e B vão na mesma aprovação. Nunca pouse A sozinho (o pytest completo fica vermelho).
- `compare` local (Windows) contra essa baseline sai 2 por `platform`: por construção,
  não se conserta. Subir o patch do Python fixado no `eval-gates.yml` também exige B.

Pré-requisito único (feito pelo dono uma vez): `EVALUATOR_CHANGE_APPROVED=true`
como variável **do environment** `eval-governance` (não do repositório) — ver
`.github/EVAL_GATES.md`. Assim a aprovação do environment é o único gate.
