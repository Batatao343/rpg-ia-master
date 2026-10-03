# SPEC-177 — Jev decision backend adapter (sem promoção)

> **Status:** `done`
> **Depende de:** SPEC-176 `done`
> **EXECUTOR_MODEL obrigatório:** `Terra`
> **EXECUTOR_EFFORT obrigatório:** `High`
> **REVIEW_MODEL obrigatório:** `Sol`
> **REVIEW_EFFORT:** `High`
> **REVIEW_REQUIRED:** `true`
> **SUBSTITUIÇÃO DE MODELO:** proibida sem aprovação explícita do usuário; mismatch => `MODEL_HANDOFF_REQUIRED`
> **Delegação Luna permitida:** Luna: inventário de fixtures/docs e relatório de respostas sanitizadas; não implementa cliente nem decide contrato.
> **MODEL_BREAKDOWN:** `docs/rpg-next-jev-golive-plan/examples/spec-model-contract.yaml` → `SPEC-177` é source of truth para subtarefas/review focus

## Objetivo

Integrar Jev/TypeSafe atrás de um seam server-side próprio, testável offline, sem alterar `dm_router` em produção.

## Requisitos

- **R1 — seam próprio:** `DecisionBackend`/adapter equivalente; não fingir que Jev é `RoutedLLM` ou `ModelTier.CLASSIFY`.
- **R2 — API atual:** implementar `POST https://jevmodel.org/v1/systemone` com Bearer auth, `Idempotency-Key` estável por tentativa lógica e contrato vigente no dia da execução; registrar modelo resolvido. Respeitar limites oficiais atuais (state serializado, perguntas e cardinalidade Choice) e testá-los localmente.
- **R3 — segredo/config:** nome canônico `JEVMODEL_API_KEY` (conforme documentação oficial Jev) apenas backend; `.env.example` contém apenas a chave vazia. Se o ambiente local ainda usar `JEV_API_KEY`, não copiar/ecoar o segredo: emitir migração de configuração explícita ou alias temporário testado; se ambos existirem e divergirem, falhar fechado.
- **R4 — tipos:** respostas Choice/Noul/Score necessárias ao experimento, validação estrita e erros tipados.
- **R5 — observabilidade:** correlation id, modelo, latência, usage/cost quando disponível; nunca state/prompt completo em log.
- **R6 — fixture/replay:** live response sanitizada pode virar fixture para testes do adapter; suíte default sem rede.
- **R7 — opt-in real:** live smoke curto, explicitamente autorizado e com teto; sem key não há fallback silencioso para LLM fingindo ser Jev.
- **R8 — information budget:** DTO mínimo; nunca enviar GameState inteiro.
- **R9 — zero gameplay change:** `agents/router.py` continua no backend atual.
- **R10 — eval integrity:** não modificar nenhum path protegido por `evals/protected-paths.txt`.
- **R11 — Project Index:** não carregar/atualizar por padrão; source é suficiente. Atualizar `eval_map` apenas se uma futura spec formalizar novo coverage canônico.

### Fora de escopo

Promoção, thresholds, regression dataset, holdout, billing e long-run.

## Plano TDD

1. Fixtures de sucesso e 401/422/429/5xx/timeout/resposta incompatível.
2. Interface + cliente HTTP com timeout/redaction.
3. Model identity + usage metadata.
4. `.env.example` somente com nome da variável.
5. Smoke real 2–3 calls somente com autorização.

## Critérios de aceite

- [x] suíte offline verde sem `JEVMODEL_API_KEY`;
- [x] Choice/Noul/Score retornam tipos fechados;
- [x] erro externo nunca vira decisão válida silenciosa;
- [x] nenhuma route/target de produção muda;
- [x] nenhum segredo/state sensível em log;
- [x] live smoke condicional: não autorizado/configurado nesta execução; sem
      `JEVMODEL_API_KEY`, nenhuma chamada foi feita;
- [x] paths protegidos da eval intactos;
- [x] revisão Sol independente `APPROVED`.

## Gate de fechamento — evidência obrigatória

- [x] `agents/router.py` e `llm_setup.py` permanecem byte-identical nesta spec;
- [x] client possui timeout total explícito, retry somente para 429/502 e reutiliza `Idempotency-Key`;
- [x] 401/402/422/429/5xx/timeout/resposta inválida têm erros distintos e nenhum retorna decisão válida;
- [x] payload enviado ao Jev não contém `expected`, `oracle`, GameState integral, secrets nem narrativa histórica desnecessária;
- [x] `JEVMODEL_API_KEY` não aparece em bundle web, Android, logs ou fixtures;
- [x] revisão Sol independente `APPROVED` em `handoffs/SPEC-177-SOL-independent-review.md`.

## Execução — 2026-10-03

Usuário autorizou expressamente Sol High como substituto de Terra High nesta
spec; o custo de modelo foi maior que o mínimo planejado. Revisão Sol High em
contexto independente retornou `APPROVED` após corrigir três gaps reproduzidos
offline: timeout total, coerção de tipos da resposta e mutação do request.

O adapter está em `services/jev_decision.py`, fixture sintética e 22 testes em
`tests/test_jev_decision_backend.py`. `httpx` é dependência direta. A suíte
completa passou em checkout isolado com basetemp ASCII: **1.920 passed,
35 skipped, 15 deselected**. Governance, Project Index e Ruff passaram.
Project Index foi regenerado exclusivamente para o CI verificar freshness do
source novo; não entrou no contexto/fluxo do produto e `eval_map` não mudou.
Sem chave local, o smoke real opcional não foi executado; nenhuma promoção
de Jev ou mudança de gameplay ocorreu. Evidência detalhada em
`docs/spec177/README.md`.

Commit de implementação `31ec7779570b13b746f52c3e5b1f00cfed2f6908`
publicado no [PR #13](https://github.com/Batatao343/rpg-ia-master/pull/13),
empilhado sobre o PR #12. GitHub `validate` run 37142521573 e `eval-gates`
run 37142521566 terminaram `success`. O protected-evaluator-review foi
`skipped` porque a SPEC-177 não alterou paths protegidos.
