# SPEC-169 — Routing e Action Interpretation Evals

> **Status:** `done`
> **Depende de:** SPEC-168 `done`
> **Modelo executor mínimo:** Terra High
> **Revisão:** por escalada

## Objetivo

Medir route/intent/target e contratos estruturados independentemente da prosa.

## Entregas

- corpus fechado de ações com origem/racional;
- confusion matrix, route accuracy e target accuracy;
- target exact ou conjunto aceito;
- casos negativos e variantes metamórficas versionadas;
- diagnósticos de falha de structured output.

## Regras

- expected vem exclusivamente do dataset;
- adapter observa somente decisão estruturada anterior à narração;
- execução usa MockLLM forçado pelo harness, sem provider;
- variantes metamórficas são arquivos versionados, nunca geradas por LLM;
- taxonomia continua sendo `RouteType` existente; qualquer redefinição exige Sol.

## Aceite

- [x] evaluator não chama router para gerar expected;
- [x] corpus registra origem/racional;
- [x] variantes metamórficas preservam expected quando apropriado;
- [x] confusion matrix e métricas route/target são emitidas;
- [x] falha estruturada tem diagnóstico determinístico;
- [x] nenhuma narrativa final entra no score.

## Execução — 2026-09-28

- Aprovada pelo pedido do usuário para executar as specs draft em ordem, com
  SPEC-104 cloud mantida on hold.
- Implementação iniciada após SPEC-168 `done`.
- Entregues `RoutingAdapter` e `RoutingEvaluator`, com decisão pré-narração,
  target exato/conjunto aceito, validação estruturada e matriz de confusão no
  resultado JSON/Markdown do run.
- Corpus fechado com 25 casos: 21 de classificação nas quatro rotas e 4 de
  normalização/structured output. Variantes versionadas cobrem case, espaço e
  pontuação; negativos e fuga estruturada também estão presentes.
- Smoke CLI offline `spec169-routing-smoke-v2`: `route_accuracy=1.0`,
  `target_accuracy=1.0`, `exact_match=1.0`, matriz inteiramente diagonal e zero
  provider. O adapter silencia apenas a saída decorativa do router, evitando
  erro CP1252 no terminal Windows sem alterar o contrato avaliado.
- Achado de corpus: frases com `vendo/forjo` e a palavra `espada` colidem com o
  vocabulário de combate do MockLLM. As fixtures usam objetos sem ambiguidade
  para manter oracle único; o comportamento permanece observável no produto.
- 65 testes focados e Ruff verdes; Project Index regenerado com 5.358 nodes e
  13.713 edges. Suíte final: **1.851 passed, 35 skipped, 15 deselected**, zero
  falhas. Nenhum provider, judge ou long-run.
- A revisão era somente por escalada; a taxonomia `RouteType` existente não foi
  redefinida, portanto não houve handoff adicional.
