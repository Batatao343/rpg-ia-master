# SPEC-196 — FinOps, margin guard e observabilidade comercial

> **Status:** `draft`
> **Depende de:** SPEC-195 `done`
> **EXECUTOR_MODEL obrigatório:** `Terra`
> **EXECUTOR_EFFORT obrigatório:** `High`
> **REVIEW_MODEL obrigatório:** `Sol`
> **REVIEW_EFFORT:** `High`
> **REVIEW_REQUIRED:** `true`
> **SUBSTITUIÇÃO DE MODELO:** proibida sem aprovação explícita do usuário; mismatch => `MODEL_HANDOFF_REQUIRED`
> **Delegação Luna permitida:** Luna: agregação de séries e relatórios FinOps; kill switches/equações ficam com Terra.
> **MODEL_BREAKDOWN:** `examples/spec-model-contract.yaml` → `SPEC-196` é source of truth para subtarefas/review focus

## Objetivo

Dar visibilidade de custo/margem e impedir que provider/pricing drift torne o beta silenciosamente deficitário.

## Requisitos

- **R1** — dashboard/admin: gross, channel fees, variable cost, contribution margin, fixed infra separado.
- **R2** — margem por SKU/canal/coorte e custo por turn/image/voice.
- **R3** — alerts para unknown pricing, cost spike, fallback caro, wallet mismatch, webhook backlog, provider failure.
- **R4** — kill switches: desabilitar imagem, STT fallback caro, modelo específico ou novas compras sem quebrar leitura de campanhas.
- **R5** — pricing/rate cards têm freshness check.
- **R6** — nenhum ID de usuário como metric label de alta cardinalidade.

### Fora de escopo

BI sofisticado; forecasting de receita.

## Plano

1. Agregadores server-side.
2. Métricas/alerts.
3. Margin simulation sobre baseline real.
4. Kill-switch tests.
5. Runbook de preço/provider.

## Critérios de aceite

- [ ] target margin calculável por canal.
- [ ] mismatch financeiro alerta.
- [ ] kill switch testado.
- [ ] fixed infra aparece separado, não “some” da análise.

## Gates / evidência

Synthetic financial load + staging metrics.

## Gate de fechamento

- [ ] dashboard separa gross, channel fee, variable cost, contribution margin e fixed infra;
- [ ] meta de 5% é calculada por SKU/canal/pricing_version e não misturada com imposto nesta versão;
- [ ] unknown/stale rate card gera alerta e pode bloquear nova venda/efeito caro, nunca assume custo zero;
- [ ] kill switches são server-side, auditáveis e testados para imagem, STT fallback e modelo/decision backend;
- [ ] alerta financeiro não usa user_id/game_id como label de métrica;
- [ ] review Sol independente aprova fórmulas/guards.
