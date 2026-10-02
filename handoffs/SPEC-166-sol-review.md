# Review handoff — SPEC-166 — Sol

`MODEL_HANDOFF_REQUIRED: gpt-5.6-sol`

## Escopo

Revisar o Project Index somente leitura, sem implementar:

1. determinismo e detecção de staleness por SHA/tree hash;
2. risco de o índice virar autoridade falsa sobre o source;
3. proveniência/confidence de edges exatas vs best-effort;
4. preservação de `state_ownership.yaml` curado;
5. exclusão de lore, assets, FAISS, saves, artefatos e configuração privada;
6. queries bounded para memory/context/state/tests;
7. ausência de mudança no comportamento do RPG.

## Arquivos

- `specs/SPEC-166-project-index-core.md`
- `project_index/generator.py`
- `project_index/query.py`
- `project_index/__main__.py`
- `project_index/manifest.json`
- `project_index/repo_graph.json`
- `project_index/repo_graph.schema.json`
- `project_index/domains.yaml`
- `project_index/state_ownership.yaml`
- `project_index/eval_map.yaml`
- `tests/test_project_index.py`
- seção `Operação de specs e evals` de `AGENTS.md`.

## Evidência

- `python -m project_index --root . build` + `check`: verdes;
- 5 testes focados e Ruff verdes;
- 5.252 nodes, 13.406 edges;
- sem provider, graph DB, reorganização ou alteração de produto.

Retorne `APPROVED` ou `CHANGES_REQUESTED`, modelo/run id, bloqueadores e riscos
residuais. O executor não pode autoaprovar.

## Histórico

- `SPEC-166-SOL-20260928-01`: `CHANGES_REQUESTED`.
- Correções: tree hash é o gate forte e commit drift vira warning verificável;
  descoberta usa `git ls-files --cached --others --exclude-standard`; imports
  relativos respeitam package/level; TS/JS são nodes `file`; schema entra no
  manifest; payloads internos também têm teto; endpoints exatos exigem
  binding estático criado por `FastAPI`/`APIRouter`; fixtures adversariais cobrem
  os bypasses.
- `SPEC-166-SOL-20260928-02`: `CHANGES_REQUESTED` porque qualquer objeto chamado
  `app`/`router` ainda podia produzir endpoint `static_exact`. Corrigido com
  análise do construtor, teste negativo de router falso, suporte a
  `from . import b`, validação estrutural completa e teto aplicado também a
  `matched_nodes`.
- Evidência atual: build/check frescos (5.258 nodes, 13.449 edges), 7 testes
  focados e Ruff verdes; nenhuma chamada a provider.
- `SPEC-166-SOL-20260928-03`: `CHANGES_REQUESTED` por construtor local
  sombreando `FastAPI` importado e divergência do schema para hash não hexadecimal
  e `bool` aceito como integer. Corrigido com snapshots lexicais de bindings cuja
  origem é `fastapi`, invalidação por shadow/rebinding, regex hexadecimal exata e
  checagem estrita de `int`.
- Evidência atual: build/check frescos (5.260 nodes, 13.457 edges), 7 testes
  focados e Ruff verdes; nenhuma chamada a provider.
- `SPEC-166-SOL-20260928-04`: `CHANGES_REQUESTED` por mutação de atributo do
  binding FastAPI e valores não hashable provocarem `TypeError`. Corrigido com
  coleta conservadora de writes/mutações em statements e guards explícitos de
  string em todos os campos consultados em sets.
- Evidência atual: build/check frescos (5.274 nodes, 13.477 edges), 7 testes
  focados e Ruff verdes; suíte anterior 1.832 passed/35 skipped/zero falhas.
- `SPEC-166-SOL-20260928-05`: `CHANGES_REQUESTED` por captures de pattern matching
  e efeitos imediatos em headers de funções/classes. Corrigido com visitors para
  `MatchStar`/`MatchMapping`, análise seletiva de defaults/decorators/annotations/
  bases e `route_to` deliberadamente `static_best_effort`.
- Evidência atual: build/check frescos (5.277 nodes, 13.482 edges), 7 testes
  focados e Ruff verdes; nenhuma chamada a provider.
