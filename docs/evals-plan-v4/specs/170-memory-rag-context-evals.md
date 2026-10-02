# SPEC-170 — Memory, RAG e Context Evals

> **Status:** `draft`
> **Depende de:** SPEC-169 `done`
> **Modelo executor mínimo:** Sol High
> **Revisão obrigatória:** **Astra**

## Objetivo

Separar formalmente `store -> retrieve -> context -> generation` para localizar falhas de memória sem confundir camadas.

## Entregas

- fact/evidence IDs;
- retrieval trace estruturado;
- Recall@1/3/5 e MRR;
- forbidden/secret leak hard gate;
- context evidence inclusion/exclusion;
- memory write precision;
- provider/embedding/index metadata no report.

## Model routing

Luna pode preparar corpus/relatórios a partir de fatos rotulados. Terra pode implementar partes mecânicas já definidas. Sol é owner da implementação/integração por cruzar RAG, context builder, memory provenance e telemetry. Astra revisa definição de métricas, leakage e separação causal das camadas.

## Aceite

- [ ] store/retrieve/context/generate falham separadamente;
- [ ] secret leak = hard fail;
- [ ] métricas não dependem da string final do storyteller;
- [ ] Astra review aprovada.
