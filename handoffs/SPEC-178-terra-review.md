# SPEC-178 — handoff de executor (`MODEL_HANDOFF_REQUIRED`)

> Atualização 2026-10-05: este handoff histórico foi superado pela autorização
> expressa do usuário para Sol High executar a SPEC-178 e para o A/B live com
> teto de 100 chamadas/US$ 1. O runner offline está em
> `evals/experiments/jev_router_ab.py`. Uma chamada Jev anterior retornou 401;
> o estado e os próximos passos atuais estão em `docs/spec178/README.md`.

Data: 2026-10-03. Base técnica: `9e00415bf62c1534daaab55636de96b49ba1d38d`
(SPEC-177, PR #13). SPEC-176 e 177 constam `done`; PRs #12 e #13
permanecem draft/empilhados enquanto a integração em `main` aguarda
autorização específica.

## Motivo do handoff

A [SPEC-178](../specs/SPEC-178-jev-router-ab-eval.md) exige executor Terra
High e revisão Sol High independente. Terra não está disponível nesta sessão;
a spec proíbe substituição silenciosa. Foi solicitada autorização expressa ao
usuário para Sol High executar a 178; ainda não recebida. Por isso não há
implementação, chamada externa ou interpretação de score nesta branch.

A chave `JEVMODEL_API_KEY` foi detectada como **presente** no `.env` do
workspace principal por teste booleano, sem ler/registrar valor. O usuário
ainda precisa autorizar expressamente as chamadas live e o teto de 100
requisições externas/US$ 1 proposto. Não copiar a chave para fixtures, PR,
log ou bundle web.

## Source e régua confirmados

- Dataset protegido read-only:
  `evals/datasets/regression/routing_actions.jsonl`, SHA-256
  `ad6f48be2a66f1e5f5b55c5f61bdd9f457dcb611c2568fa0008d35fbf2596bb4`
  igual ao `evals/manifest.lock.json`; 25 linhas totais, 21 casos
  `oracle=classification` com operação `route`.
- `evals/core/runner.py` força `RPG_FORCE_MOCK=1`; não reutilizar/modificar
  esse runner para o A/B live.
- `agents/router.py` aplica gates determinísticos antes de chamar
  `get_llm(tier=ModelTier.CLASSIFY)`; o experimento deve provar elegibilidade
  por instrumentação, sem lista manual e sem alterar a rota de produção.
- O adapter Jev da SPEC-177 está em `services/jev_decision.py`; DTO mínimo,
  tipos fechados, idempotência, timeout e erros tipados já foram aprovados.
- A/B exige três réplicas pareadas completas por `classifier_eligible`,
  uma passada `pipeline_full`, dados brutos antes do resumo, run IDs e cap
  explícitos. Resultado é apenas development/regression evidence, sem
  promoção e sem long-run.

## Próximo executor

Após autorização do modelo e das chamadas, implementar em
`evals/experiments/` sem alterar `evals/core`, evaluator, expected, dataset,
lock, baseline ou registry. Separar input sanitizado (`AdapterCase`) de
`expected`/`oracle`, registrar product SHA, hash do corpus, modelo/provider,
latência, usage/cost ou `unavailable`, erros e resultados por caso. Rodar
preflight offline, uma chamada de sanidade por braço e somente então as
réplicas completas; abortar em falha de auth/quota/config sem escolher casos
depois de observar scores. Exigir revisão Sol independente.
