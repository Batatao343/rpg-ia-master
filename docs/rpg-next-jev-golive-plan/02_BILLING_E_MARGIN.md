# Billing, Estilhas de Éter e margem

## Escopos separados

- `gold`: economia do personagem dentro do `GameState`.
- `ether_shards`: saldo comercial da conta, fora do `GameState`.

Nunca converter Ouro em Estilhas ou persistir wallet dentro do save.

## Unidade

Ledger usa **subunidade inteira** para nunca depender de float (recomendação: `1 Estilha = 1000 shard_milli`). UI pode exibir duas casas decimais, mas cálculo/ledger usam inteiro + Decimal nas conversões monetárias.

## Meta econômica v1

Nesta primeira versão:

```text
target_margin_brl = gross_brl * 0.05
variable_budget_brl = gross_brl
                    - channel_fee_brl
                    - target_margin_brl
                    - tax_brl

tax_brl = 0  # somente nesta modelagem inicial
```

Custos fixos mensais de Vercel/Supabase ficam fora da margem por transação, mas aparecem separados no FinOps.

## Conversão compra -> Estilhas

Uma `pricing_version` define `shard_budget_unit_brl`, FX/rate-card/buffer e fees do canal.

```text
shards_granted = floor(variable_budget_brl / shard_budget_unit_brl)
```

Rounding restante é registrado; nunca conceder orçamento variável acima do disponível.

A mesma quantidade de Estilhas pode ter preço bruto diferente em Stripe e Google Play. Preço/SKU é server-side/store-authoritative, nunca enviado pelo client como autoridade.

## Conversão usage -> débito

```text
variable_cost_brl = normalized_provider_cost_usd * fx_versioned_with_buffer
shards_debited = ceil(variable_cost_brl / shard_budget_unit_brl)
```

Unknown/stale pricing não vira custo zero. Billing exato falha fechado ou usa reserva conservadora explicitamente marcada.

## Consumo normal

Não perguntar preço antes de cada turno. Backend cria reserva invisível e um spend ceiling para a operação; provider/fallback não pode exceder a reserva sem interromper/falhar de forma controlada.

Após usage final:

```text
reserve(max)
-> execute within spend ceiling
-> settle(actual)
-> release(remainder)
```

Saldo spendable nunca fica negativo.

## Imagem

Imagem é exceção de UX:

1. backend calcula quote em Estilhas;
2. UI mostra valor final/teto;
3. usuário confirma;
4. reserva exatamente o quote;
5. provider é chamado;
6. sucesso faz settlement; falha pré-provider libera;
7. efeito externo incerto vai para reconciliation, sem retry/refund automático cego;
8. se custo real exceder quote, usuário não é debitado além do valor confirmado; FinOps registra a perda/anomalia.

Triggers automáticos de arte podem criar oferta/placeholder, nunca provider call pago.

## Pacotes finais

Não definir valores comerciais finais antes de:

1. metering real;
2. fee real/config da conta Stripe;
3. fee/tier real da conta Google Play;
4. buffer FX aprovado;
5. baseline de turnos, voz e imagem.

## Transparência

- saldo discreto visível;
- Account mostra compras, saldo e consumo 24h/7d/30d;
- custo por turno sob demanda, ligado à operação real;
- mobile usa tap/focus, não hover obrigatório;
- detalhes provider/model/token ficam fora da narrativa padrão.
