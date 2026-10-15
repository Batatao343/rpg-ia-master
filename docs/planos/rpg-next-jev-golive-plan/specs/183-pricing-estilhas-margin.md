# SPEC-183 — Pricing de Estilhas e margem por canal

> **Status:** `draft`
> **Depende de:** SPEC-182 `done`
> **EXECUTOR_MODEL obrigatório:** `Terra`
> **EXECUTOR_EFFORT obrigatório:** `High`
> **REVIEW_MODEL obrigatório:** `Sol`
> **REVIEW_EFFORT:** `High`
> **REVIEW_REQUIRED:** `true`
> **SUBSTITUIÇÃO DE MODELO:** proibida sem aprovação explícita do usuário; mismatch => `MODEL_HANDOFF_REQUIRED`
> **Delegação Luna permitida:** Luna: coleta de taxas/rate cards versionados e geração de relatórios; equações/rounding ficam com Terra e revisão Sol.
> **MODEL_BREAKDOWN:** `examples/spec-model-contract.yaml` → `SPEC-183` é source of truth para subtarefas/review focus

## Objetivo

Criar o pricing engine versionado que converte compras BRL em Estilhas e usage em débito, preservando 5% de margem-alvo sobre a compra depois de fee do canal e custos variáveis mensuráveis.

## Requisitos

- **R1** — unidade canônica `ether_shard` independente de Ouro; ledger usa subunidade inteira (ex.: `shard_milli`, 1000 = 1 Estilha) e UI apenas formata.
- **R2** — `pricing_versions` imutáveis com FX source/time, buffers e rate cards.
- **R3** — `purchase_skus` por canal; mesma quantidade de Estilhas pode ter preço bruto diferente web/Play.
- **R4** — fórmula audita gross, fee, target_margin, variable_budget e rounding.
- **R5** — tax = 0 nesta versão, campo existe para futuro.
- **R6** — fixed infra não entra no per-transaction margin, mas é reportável.
- **R7** — não definir pacotes finais até baseline de usage; usar exemplos claramente não comerciais.
- **R8** — preços nunca vêm do client.

### Fora de escopo

Cobrar usuário; subscriptions; promo/free credits.

## Plano

1. Implementar Decimal/fixed-point, jamais float financeiro.
2. Property tests de conservação/margem/rounding.
3. Simular Stripe fee e Play fee como configs versionadas.
4. Produzir calculadora/report CLI.
5. Sol revisa equações e edge cases.

## Critérios de aceite

- [ ] margem nunca fica abaixo do target por erro de rounding.
- [ ] fee fixa de canal é contemplada.
- [ ] Google fee tier não é hardcoded como verdade eterna.
- [ ] pacote impossível é rejeitado.
- [ ] pricing version de compra/usage é auditável.

## Gates / evidência

Property tests + golden financial vectors. Não alterar golden para passar implementação.

## Fórmula canônica desta versão

Para compra: `variable_budget_brl = gross_brl - channel_fee_brl - target_margin_brl - tax_brl`, com `target_margin_brl = gross_brl * 0.05` e `tax_brl = 0` nesta versão. Estilhas concedidas são `floor(variable_budget_brl / shard_budget_unit_brl)`; o restante fica registrado como rounding reserve, nunca distribuído silenciosamente.

Para uso: custo variável normalizado é convertido para BRL usando FX/version + buffer; débito é `ceil(variable_cost_brl / shard_budget_unit_brl)`. Valores financeiros usam Decimal/fixed-point.

## Gate de fechamento

- [ ] property tests provam que rounding nunca concede orçamento variável maior que o disponível após fee+margem;
- [ ] fee percentual + fee fixa e Play percentage-only/configurável são cobertas;
- [ ] FX/rate-card ausente ou stale falha fechado para pricing comercial;
- [ ] nenhum preço/pacote final é publicado nesta spec;
- [ ] review Sol independente valida equações, units e rounding.
