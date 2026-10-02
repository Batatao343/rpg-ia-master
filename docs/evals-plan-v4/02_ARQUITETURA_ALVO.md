# 02 — Arquitetura alvo

## Estrutura sugerida

```text
evals/
  README.md
  manifest.lock.json
  registry.yaml
  core/
    case_schema.py
    result_schema.py
    runner.py
    compare.py
    seeds.py
  evaluators/
    deterministic.py
    retrieval.py
    routing.py
    state.py
    narrative.py
    judge.py
  datasets/
    dev/
      routing.jsonl
      state_transitions.jsonl
      memory_retrieval.jsonl
      context_grounding.jsonl
      narrative_claims.jsonl
    regression/
      bugs.jsonl
  reports/
  fixtures/
    states/
    rag/
    npcs/

web/
  e2e/
    playwright.config.ts
    fixtures/
    pages/
    contracts/
    journeys/
      auth.spec.ts
      create-character.spec.ts
      resume.spec.ts
      action-stream.spec.ts
      combat.spec.ts
      map-travel.spec.ts
      quest.spec.ts
      death-recovery.spec.ts
      art.spec.ts
      session-failures.spec.ts
      responsive.spec.ts

project_index/
  manifest.json
  domains.yaml
  repo_graph.json
  state_ownership.yaml
  eval_map.yaml

scripts/
  build_project_index.py
  eval_backend.py
  eval_frontend.py
  eval_compare.py
  post_deploy_smoke.py
```

## Não duplicar o `playtest/`

`evals/` mede componentes e cenários fechados.

`playtest/` continua responsável por:

- campanhas longas;
- interação emergente;
- invariantes sistêmicas;
- distribuição de comportamentos;
- custo/latência E2E;
- regressões que só aparecem após dezenas/centenas de turnos.

Fluxo padrão:

```text
unit/regression
    ↓
component evals determinísticas
    ↓
frontend deterministic journeys
    ↓
short real-provider contracts (quando a feature realmente depende do provider)
    ↓
post-deploy smoke (quando aplicável)
```

Fluxo manual opcional:

```text
usuário solicita long-run / spec de horizonte longo
    ↓
playtest sistêmico existente
```

Long-run não é dependência da baseline-v1 nem do aceite normal de mudanças.

## Interface única de resultado

Todos os runners devem produzir JSON com schema comum:

```json
{
  "eval_run_id": "...",
  "product_sha": "...",
  "suite": "memory_retrieval",
  "dataset_hash": "sha256:...",
  "evaluator_version": "1",
  "environment": {},
  "metrics": {},
  "cases": [],
  "hard_failures": [],
  "passed": true
}
```

Isso permite comparar baseline/candidato sem parsing ad hoc.

## Instrumentação necessária

### RAG

Criar uma interface de diagnóstico que retorne documentos estruturados, não só texto formatado:

```python
RetrievedEvidence(
    id: str,
    source: str,
    score: float,
    text: str,
    visibility: str,
    metadata: dict,
)
```

A rota de produção continua devolvendo texto. A rota de eval observa IDs/ranking.

### Context builder

O `ContextPack` deve expor, em modo eval, os IDs das evidências usadas e descartadas, com motivo de descarte. Isso transforma grounding em um problema mensurável.

### Router

Capturar decisão estruturada antes de qualquer narração:

- `route`;
- `target`;
- `loot_context`;
- `combat_origin_hint`;
- confiança se houver.

### Turn state

Capturar snapshots canônicos mínimo antes/depois, em vez de comparar JSON inteiro com campos voláteis.

### Narrative evidence

Reutilizar `services/narrative_evidence.py` como camada determinística para claims cobertas pelo estado. Adicionar apenas novas regras quando houver bug real demonstrável.


## Camada de navegação para coding agents

`project_index/` é uma camada derivada/curada de orientação. Ela não participa do runtime do RPG e não substitui `AGENTS.md`, source code ou testes.

Responsabilidades:

- `manifest.json`: freshness/hash/SHA do índice;
- `domains.yaml`: mapa semântico pequeno, curado;
- `repo_graph.json`: símbolos/dependências com proveniência;
- `state_ownership.yaml`: ownership pretendido de estado + invariantes;
- `eval_map.yaml`: produto → métricas → testes/datasets.

O agent usa o índice para **localizar** contexto. Antes de editar qualquer símbolo, deve abrir o source real no SHA atual. O plano completo e os limites estão em `11_INDEXACAO_REPO_E_GRAFOS.md`.
