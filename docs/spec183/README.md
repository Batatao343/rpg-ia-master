# SPEC-183 — evidência de pricing de Estilhas

## Contrato entregue

`services/shard_pricing.py` usa apenas `Decimal` para dinheiro e inteiro para
`shard_milli` (**1 Estilha = 1000 `shard_milli`**). A unidade
`shard_budget_unit_brl` é BRL **por `shard_milli`**. Ouro do personagem não entra
no cálculo nem no save da conta.

Compra: fee percentual + fee fixa são arredondadas **para cima** ao centavo;
5% do bruto são reservados como margem-alvo, também arredondados para cima.
Imposto é zero nesta versão. `floor(variable_budget / unit)` define exatamente
as unidades concedidas; um SKU publicado com outra quantidade é rejeitado.
`rounding_reserve_brl = variable_budget - units * unit` permanece explícito.
O relatório exibe `fixed_infra_brl` separadamente, sem subtraí-lo da margem
por transação.

Uso: somente eventos da SPEC-182 marcados `billing_exact` e originados de custo
reportado pelo provider ou rate card fixo instalado podem produzir quote.
`ceil(provider_cost_usd * fx_usd_brl * (1 + buffer) / unit)` determina o débito.
O resultado mantém IDs dos eventos, versão de pricing, versões de custo e
reserva de arredondamento. Custo estimado, card ausente/divergente, FX ou card
stale falham fechado. A SPEC-184 implementará reserva e settlement; esta spec
não debita ninguém.

Uma cotação nova exige o rate card instalado com **versão, SHA-256 e data de
observação** iguais aos da versão de pricing. Como o artefato contém só a data,
o instante canônico conservador é **00:00 UTC**; 23:59 do mesmo dia é rejeitado.
A auditoria histórica não recalcula
uma compra antiga com o card atual: consulta o recibo e o ledger originais,
as versões e os valores ali registrados. Arquivos antigos de rate card devem
ser preservados, nunca sobrescritos ao publicar uma versão nova.

## Persistência e autoridade

A migration `20261008160000_pricing_versions.sql` cria `app.pricing_versions`
e `app.purchase_skus` sem inserir versões, preços ou pacotes comerciais.
Triggers proíbem UPDATE/DELETE, inclusive por rotina privilegiada. O papel
`rpg_api` só recebe SELECT; clientes `anon`/`authenticated` não recebem acesso.
`infrastructure/pricing_catalog.py` lê o preço e a quantidade pelo `sku_id`
do banco antes de calcular; nenhum preço do cliente é autoridade. O schema
guarda fonte/instante/validade do FX, rate card, buffer, fees por canal e
versão/hash do rate card e versão do SKU. Compras futuras devem registrar os IDs da versão/SKU no ledger
da SPEC-184, e débitos futuros os IDs de versão/eventos de usage.

O Project Index foi consultado seletivamente: `player.gold` pertence ao domínio
`economy`, com writers de GameState. Não há owner prévio de Estilhas; a SPEC-184
é a dona planejada da wallet. O source de `state.py`, `services/usage_metering.py`
e das migrations confirmou essa separação.

## Calculadora de simulação

`uv run python -m scripts.pricing_report --version-json <versão.json>
--sku-json <sku.json> --at <ISO-8601> [--usage-usd 0.019]
[--fixed-infra-brl 37.25]`

A entrada é arquivo local e a saída marca `simulation_only: true`. Os vetores
`web`/`play` nos testes usam valores **sintéticos, não comerciais**: a mesma
quantidade 311 `shard_milli` resulta de brutos diferentes (10,50 e 11,00 BRL)
com fees de exemplo. Não há SKU publicado por esta spec. A opção `--usage-usd`
assume um custo sintético reportado para explorar a equação; não constitui
evidência faturável.

## Gates

- Vetores conhecidos: fee fixa + percentual, Play percentual, margem, reserva,
  FX/buffer e arredondamento de débito.
- 1.000 casos determinísticos de conservação de compra e 1.000 de débito.
- Postgres local: round-trip de versão/SKU, preço server-side, proibição de
  mutação, bloqueio de fees inválidas e `rpg_api` sem permissão de INSERT.
- Limite: sem FX verificado da conta, fee real por canal e baseline de uso, a
  migration permanece vazia; não há pricing comercial pronto para publicar.
