# SPEC-180 — Expansão seletiva de Jev e decisão de promoção

> **Status:** `draft`
> **Depende de:** SPEC-179 `done`
> **EXECUTOR_MODEL obrigatório:** `Sol`
> **EXECUTOR_EFFORT obrigatório:** `High`
> **REVIEW_MODEL obrigatório:** `Sol`
> **REVIEW_EFFORT:** `High`
> **REVIEW_REQUIRED:** `true`
> **SUBSTITUIÇÃO DE MODELO:** proibida sem aprovação explícita do usuário; mismatch => `MODEL_HANDOFF_REQUIRED`
> **Delegação Luna permitida:** Luna: grep/inventário mecânico de callsites; classificação semântica e rollout ficam com Sol.
> **MODEL_BREAKDOWN:** `examples/spec-model-contract.yaml` → `SPEC-180` é source of truth para subtarefas/review focus

## Objetivo

Decidir, com evidência, quais callsites de `ModelTier.CLASSIFY` podem migrar para Jev. Não existe meta de substituir o tier inteiro.

## Requisitos

- **R1 — inventário real:** localizar callsites CLASSIFY por busca/source. Project Index é opcional e seletivo, nunca pré-requisito nem fonte de verdade.
- **R2 — buckets:** `bounded_decision`; `bounded_with_dynamic_candidates`; `mixed/free_form`.
- **R3 — free-form:** `TradeIntent.item_ref` e qualquer geração aberta permanecem no LLM salvo spec/eval própria que prove decomposição equivalente.
- **R4 — eval por callsite:** nenhuma migração adicional sem corpus/oráculo e A/B apropriado.
- **R5 — router:** decisão usa SPEC-178 + SPEC-179 e a regra pré-declarada abaixo; sem holdout privado, isso NÃO autoriza alegação de generalização.
- **R6 — rollout reversível:** `off | shadow | primary` por config. Começar em `shadow` quando tecnicamente possível; shadow nunca controla gameplay.
- **R7 — fallback:** em `primary`, erro/timeout/unrepresentable/threshold de confiança congelado cai para CLASSIFY atual e gera telemetry.
- **R8 — threshold:** calibrar antes do rollout primário usando apenas material permitido. Se exigir semântica/expected novo, `EVAL_AUTHORING_REQUIRED` em tarefa separada.
- **R9 — gates Python:** combate ativo/recovery/viagem e outras decisões determinísticas continuam em Python.
- **R10 — rollback:** voltar a `off`/CLASSIFY sem migração de dados e, quando possível, sem deploy.
- **R11 — metering hook:** preparar Jev para entrar no usage metering da SPEC-182 se promovido.
- **R12 — docs:** documentar Jev como decision backend, não LLM/chat provider.

## Saída obrigatória

`callsite | contract | Jev-fit | evidence | quality delta | p95 | cost | rollout decision`

## Critérios de aceite

- [ ] todos os callsites CLASSIFY do HEAD inventariados;
- [ ] nenhuma migração sem eval/evidência;
- [ ] free-form não convertido a Choice à força;
- [ ] rollout `off/shadow/primary` e fallback testados;
- [ ] regression routing protegida continua verde;
- [ ] paths protegidos byte-identical salvo tarefa de eval-authoring separada;
- [ ] revisão Sol independente aprovada;
- [ ] sem long-run.

## Regra de decisão pré-declarada

Classificar resultado como:

- `NO_GO`: existe qualquer regressão pareada não coberta por fallback seguro, leak/target inválido, ou candidate pipeline fica indisponível;
- `SHADOW`: qualidade é não-regressiva, mas cobertura confiante/target/benefício operacional ainda é insuficiente;
- `PRIMARY_WITH_FALLBACK`: somente se o pipeline Jev+fallback não perde nenhum caso que o CLASSIFY atual acerta nas réplicas confirmatórias, produz zero target/leak inválido, mantém 100% availability via fallback e Jev resolve **>=80%** dos casos elegíveis sem fallback; além disso, pelo menos um entre custo observado ou p95 melhora materialmente e o outro não piora mais que 10%.

A spec pode implementar os modos `off|shadow|primary`, mas o default pós-spec é `shadow` quando Jev passa. Alterar default para `primary` requer `PROMOTION_APPROVAL_REQUIRED` explícito do usuário após o relatório.

## Gate de fechamento

- [ ] todos os callsites CLASSIFY do HEAD foram listados por source search e classificados;
- [ ] nenhum `mixed/free_form` migrou;
- [ ] `shadow` não afeta gameplay nem duplica side effects;
- [ ] `primary` (quando manualmente habilitado) tem timeout/idempotency/fallback testados;
- [ ] rollback para `off` não exige migration nem recomputação de saves;
- [ ] review Sol independente aprova a decisão e o modo default.
