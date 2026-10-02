# SPEC-170 — Memory, RAG e Context Evals

> **Status:** `done`
> **Depende de:** SPEC-169 `done`
> **Modelo executor mínimo:** Sol High
> **Revisão obrigatória:** **Astra**

## Objetivo

Separar formalmente `store -> retrieve -> context -> generation` para localizar
falhas de memória sem confundir camadas.

## Entregas

- fact/evidence IDs;
- retrieval trace estruturado;
- Recall@1/3/5 e MRR;
- forbidden/secret leak hard gate;
- context evidence inclusion/exclusion;
- memory write precision;
- provider/embedding/index metadata no report.

## Regras

- expected e listas required/acceptable/forbidden vêm somente do dataset;
- adapters observam APIs estruturadas e não pontuam a string final do storyteller;
- write, retrieve, context e generation precisam ter resultados distinguíveis;
- ranking usa IDs estáveis e denominadores explícitos;
- leaks proibidos são blocking com limite zero;
- métricas de ranking ficam `after_baseline` até a SPEC-174;
- nenhum provider real, reindex global ou long-run nesta spec.

## Model routing

Luna pode preparar corpus/relatórios a partir de fatos rotulados. Terra pode
implementar partes mecânicas já definidas. Sol é owner da implementação/integração
por cruzar RAG, context builder, memory provenance e telemetry. Astra revisa
definição de métricas, leakage e separação causal das camadas.

## Aceite

- [x] store/retrieve/context/generate falham separadamente;
- [x] retrieval retorna IDs/ranking com Recall@1/3/5 e MRR;
- [x] context expõe evidências incluídas/descartadas e motivo;
- [x] secret/forbidden leak = hard fail;
- [x] métricas não dependem da string final do storyteller;
- [x] known-good e known-bad validam evaluator e adapters;
- [x] Astra review aprovada.

## Execução — 2026-09-29

- Aprovada pelo pedido do usuário para executar as specs draft em ordem, com
  SPEC-104 cloud mantida on hold.
- Corpus público versionado com 27 casos: 11 store, 7 retrieve, 8 context e 1
  boundary de generation. Os adapters exercitam os validadores/commit/expiração
  reais de memória, o ranking FAISS usado pelo produto, o context builder e o
  guard determinístico pós-geração.
- Trace de retrieval usa IDs estáveis por evidência. Chunks distintos da mesma
  entidade recebem `entity#chunk_<hash>` e preservam `entity_id`, sem alterar o
  `k` ou a política de visibilidade dos caminhos legacy de sessão/NPC.
- Smoke offline final `spec170-memory-context-smoke-v3`: 27/27 casos verdes;
  Recall@1 `0.5833`, Recall@3/5 `1.0`, MRR `0.8333`, context Recall@5 `1.0`,
  write precision `1.0`, zero forbidden/secret leak e zero violação de budget.
- Revisão independente Astra aprovada em `SPEC-170-ASTRA-20260929-01`, sem
  bloqueadores restantes.
- Limites: vetores fixos não medem qualidade semântica de embeddings; generation
  cobre o guard determinístico, não prosa de LLM; o corpus público mede regressão,
  não generalização; write precision é conformidade integral por caso; a spec não
  prova rastreabilidade de IDs em todos os caminhos legacy/cloud.
