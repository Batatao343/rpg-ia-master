# SPEC-178 — A/B live Jev vs CLASSIFY atual no dm_router

> **Status:** `approved`
> **Depende de:** SPEC-177 `done`
> **EXECUTOR_MODEL obrigatório:** `Terra`
> **EXECUTOR_EFFORT obrigatório:** `High`
> **REVIEW_MODEL obrigatório:** `Sol`
> **REVIEW_EFFORT:** `High`
> **REVIEW_REQUIRED:** `true`
> **SUBSTITUIÇÃO DE MODELO:** proibida sem aprovação explícita do usuário; mismatch => `MODEL_HANDOFF_REQUIRED`
> **Delegação Luna permitida:** Luna: agregação matemática dos runs já produzidos; não escolhe thresholds nem interpreta promoção.
> **MODEL_BREAKDOWN:** `docs/rpg-next-jev-golive-plan/examples/spec-model-contract.yaml` → `SPEC-178` é source of truth para subtarefas/review focus

## Objetivo

Medir Jev contra o classifier real atual para a decisão fechada de `route`, reutilizando o corpus/oráculos da SPEC-169 sem alterar a eval determinística protegida.

## Regra arquitetural obrigatória

`evals.core.runner.run_eval()` força `RPG_FORCE_MOCK=1` e metadata sem provider. Portanto **não usar nem modificar o runner canônico para o A/B live**.

Criar runner experimental em `evals/experiments/` que:

- lê `evals/datasets/regression/routing_actions.jsonl` read-only através do loader/governance existente;
- passa ao backend somente `AdapterCase`/input/state, nunca `expected`/`oracle`;
- grava artifacts próprios com product SHA, dataset hash, model identity, latência, usage/cost e resultado por caso;
- deixa core/evaluators/datasets/registry/schemas/manifest lock byte-identical.

## Braços

- **A — CLASSIFY atual real:** deterministic gates idênticos ao produto; quando elegível, usar a cascata CLASSIFY atual com Mock desativado e fail-closed se nenhum provider real estiver disponível.
- **B — Jev:** mesmos gates e informação semanticamente equivalente; Choice fechado `{storyteller, combat_agent, npc_actor, loot, none}`.

## Recortes

- `pipeline_full`: todos os 21 casos de classification, incluindo gates Python.
- `classifier_eligible`: apenas casos que realmente chegam ao backend de decisão. O runner deve provar elegibilidade por instrumentação, não por lista manual escondida.

## Métricas

- route accuracy e confusion matrix por braço/recorte;
- divergências pareadas por case;
- p50/p95 end-to-end do backend;
- provider/model/fallback attempts do braço A;
- resolved Jev model do braço B;
- usage/custo real quando reportado; se ausente, marcar `unavailable`, nunca inventar;
- failure/unavailable rate.

## Governança

- Dataset regression e evaluator são read-only.
- Não criar threshold pós-hoc.
- Sem holdout privado, o resultado é **development/regression evidence**. Esta spec não promove Jev.
- Se quiser criar casos novos ou semântica nova, emitir `EVAL_AUTHORING_REQUIRED` e fazê-lo em tarefa separada antes de observar o candidato nesses casos.

## Critérios de aceite

- [ ] runner experimental não altera paths protegidos;
- [ ] A/B pareado reproduzível com SHA/dataset/model metadata;
- [ ] `classifier_eligible` e `pipeline_full` separados;
- [ ] nenhuma decisão recebe expected/oracle como input;
- [ ] todas divergências inspecionáveis por case;
- [ ] custo/latência não estimados quando provider não fornece usage;
- [ ] produção permanece no CLASSIFY atual;
- [ ] sem long-run.

## Protocolo confirmatório pré-registrado

1. Rodar preflight offline e provar que corpus/hash permanecem iguais.
2. Executar uma passada live de sanidade por braço; qualquer auth/quota/config failure interrompe antes da comparação.
3. Executar **3 réplicas pareadas** dos casos `classifier_eligible`, mesma ordem/inputs por réplica, com `run_id` distintos e budget/call-cap explícitos.
4. `pipeline_full` roda ao menos uma vez para provar que gates Python não mudaram.
5. Persistir resultados brutos antes de calcular resumo; nenhum run completo pode ser descartado após olhar o score.

## Gate de fechamento

- [ ] corpus protegido permanece byte-identical;
- [ ] 3 réplicas pareadas completas ou spec fica `blocked-by-provider`, nunca `done` com amostra parcial;
- [ ] relatório separa `A current CLASSIFY cascade` de `B Jev-only` e não mistura fallback futuro;
- [ ] cada caso mostra route, confidence/probabilities quando disponíveis, latency, attempts e erro;
- [ ] review Sol independente valida que candidate code nunca recebeu expected/oracle e que comparação não sofreu cherry-picking.
