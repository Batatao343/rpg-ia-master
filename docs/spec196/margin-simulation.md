# SPEC-196 — Simulacao de margem (baseline real)

> Gerado por `scripts/finops_margin_sim.py`. **Nao e oferta comercial**: nenhum SKU/preco
> esta publicado; precos brutos sao entradas de simulacao. Imposto fora desta versao
> (`tax_rate = 0`). Infra fixa (Vercel/Supabase) fica FORA das margens por SKU.

## Premissas

- FX 5.40 BRL/USD, buffer de FX 10% no debito (premissa; real vem da `pricing_version`).
- Unidade de orcamento: R$ 0.001 por shard_milli (1 shard = R$ 1,00) (premissa).
- Meta de margem de contribuicao: 5% por SKU/canal/pricing_version.
- Imagem: ~US$ 0.05 por retrato (premissa; substituir pelo 1o uso real em staging).
- Taxas por canal:
  - `stripe`: Stripe BR cartao 3,99% + R$0,39 (assumido; confirmar contra a conta)
  - `google_play`: Google Play 15% (confirmar tier de servico pendente SPEC-198)

## Custo por turno (medido)

| Baseline | USD/turno |
|---|---|
| matriz B 28/09 (subcontado) | 0.000603 |
| 13x30 DeepSeek v4 | 0.000800 |
| comerciante real 20/08 | 0.000814 |

Fontes: `ESTADO_ATUAL.md` (matriz B, comerciante real 20/08, 13x30),
`playtest/pricing.py` (heuristica 1200 in/400 out). A matriz B esta SUBCONTADA
(achado de 28/09); por isso o cenario de estresse x3 e o que decide o guard.

## Cenario: matriz B 28/09 (subcontado) (0.000603 USD/turno)

| Canal | Preco | Taxa canal | Orcamento var. | Turnos/pacote | Custo real (todos consumidos) | Margem R$ | Margem % | Folga de custo | >=5%? |
|---|---|---|---|---|---|---|---|---|---|
| stripe | R$ 9.90 | R$ 0.79 | R$ 8.61 | 2404 | R$ 7.83 | R$ 1.28 | 13.0% | 1.10x | sim |
| stripe | R$ 19.90 | R$ 1.19 | R$ 17.71 | 4945 | R$ 16.10 | R$ 2.61 | 13.1% | 1.10x | sim |
| stripe | R$ 39.90 | R$ 1.99 | R$ 35.91 | 10027 | R$ 32.65 | R$ 5.26 | 13.2% | 1.10x | sim |
| stripe | R$ 79.90 | R$ 3.58 | R$ 72.32 | 20194 | R$ 65.75 | R$ 10.57 | 13.2% | 1.10x | sim |
| google_play | R$ 9.90 | R$ 1.49 | R$ 7.91 | 2209 | R$ 7.19 | R$ 1.22 | 12.3% | 1.10x | sim |
| google_play | R$ 19.90 | R$ 2.99 | R$ 15.91 | 4443 | R$ 14.46 | R$ 2.45 | 12.3% | 1.10x | sim |
| google_play | R$ 39.90 | R$ 5.99 | R$ 31.91 | 8910 | R$ 29.01 | R$ 4.90 | 12.3% | 1.10x | sim |
| google_play | R$ 79.90 | R$ 11.99 | R$ 63.91 | 17846 | R$ 58.10 | R$ 9.81 | 12.3% | 1.10x | sim |

## Cenario: 13x30 DeepSeek v4 (0.000800 USD/turno)

| Canal | Preco | Taxa canal | Orcamento var. | Turnos/pacote | Custo real (todos consumidos) | Margem R$ | Margem % | Folga de custo | >=5%? |
|---|---|---|---|---|---|---|---|---|---|
| stripe | R$ 9.90 | R$ 0.79 | R$ 8.61 | 1812 | R$ 7.83 | R$ 1.28 | 13.0% | 1.10x | sim |
| stripe | R$ 19.90 | R$ 1.19 | R$ 17.71 | 3727 | R$ 16.10 | R$ 2.61 | 13.1% | 1.10x | sim |
| stripe | R$ 39.90 | R$ 1.99 | R$ 35.91 | 7557 | R$ 32.65 | R$ 5.26 | 13.2% | 1.10x | sim |
| stripe | R$ 79.90 | R$ 3.58 | R$ 72.32 | 15219 | R$ 65.75 | R$ 10.57 | 13.2% | 1.10x | sim |
| google_play | R$ 9.90 | R$ 1.49 | R$ 7.91 | 1665 | R$ 7.19 | R$ 1.22 | 12.3% | 1.10x | sim |
| google_play | R$ 19.90 | R$ 2.99 | R$ 15.91 | 3348 | R$ 14.46 | R$ 2.45 | 12.3% | 1.10x | sim |
| google_play | R$ 39.90 | R$ 5.99 | R$ 31.91 | 6715 | R$ 29.01 | R$ 4.90 | 12.3% | 1.10x | sim |
| google_play | R$ 79.90 | R$ 11.99 | R$ 63.91 | 13449 | R$ 58.10 | R$ 9.81 | 12.3% | 1.10x | sim |

## Cenario: comerciante real 20/08 (0.000814 USD/turno)

| Canal | Preco | Taxa canal | Orcamento var. | Turnos/pacote | Custo real (todos consumidos) | Margem R$ | Margem % | Folga de custo | >=5%? |
|---|---|---|---|---|---|---|---|---|---|
| stripe | R$ 9.90 | R$ 0.79 | R$ 8.61 | 1780 | R$ 7.83 | R$ 1.28 | 13.0% | 1.10x | sim |
| stripe | R$ 19.90 | R$ 1.19 | R$ 17.71 | 3661 | R$ 16.10 | R$ 2.61 | 13.1% | 1.10x | sim |
| stripe | R$ 39.90 | R$ 1.99 | R$ 35.91 | 7424 | R$ 32.65 | R$ 5.26 | 13.2% | 1.10x | sim |
| stripe | R$ 79.90 | R$ 3.58 | R$ 72.32 | 14952 | R$ 65.75 | R$ 10.57 | 13.2% | 1.10x | sim |
| google_play | R$ 9.90 | R$ 1.49 | R$ 7.91 | 1635 | R$ 7.19 | R$ 1.22 | 12.3% | 1.10x | sim |
| google_play | R$ 19.90 | R$ 2.99 | R$ 15.91 | 3289 | R$ 14.46 | R$ 2.45 | 12.3% | 1.10x | sim |
| google_play | R$ 39.90 | R$ 5.99 | R$ 31.91 | 6597 | R$ 29.01 | R$ 4.90 | 12.3% | 1.10x | sim |
| google_play | R$ 79.90 | R$ 11.99 | R$ 63.91 | 13213 | R$ 58.10 | R$ 9.81 | 12.3% | 1.10x | sim |

## Deriva de custo do provider (baseline `comerciante real 20/08`, pacote R$ 19,90)

O debito usa o custo do rate card; se o provider encarecer sem o card ser atualizado,
a margem cai mesmo com o buffer. 'Deriva' = custo real / custo do card.

| Canal | Deriva | Margem R$ | Margem % | >=5%? |
|---|---|---|---|---|
| stripe | 1x | R$ 2.61 | 13.1% | sim |
| stripe | 1.05x | R$ 1.80 | 9.1% | sim |
| stripe | 1.10x | R$ 1.00 | 5.0% | sim |
| stripe | 1.25x | R$ -1.42 | -7.1% | **NAO** |
| stripe | 2x | R$ -13.49 | -67.8% | **NAO** |
| stripe | 3x | R$ -29.59 | -148.7% | **NAO** |
| google_play | 1x | R$ 2.45 | 12.3% | sim |
| google_play | 1.05x | R$ 1.72 | 8.7% | sim |
| google_play | 1.10x | R$ 1.00 | 5.0% | sim |
| google_play | 1.25x | R$ -1.17 | -5.9% | **NAO** |
| google_play | 2x | R$ -12.02 | -60.4% | **NAO** |
| google_play | 3x | R$ -26.48 | -133.1% | **NAO** |

## Imagem (retrato)

Debito por imagem: US$ 0.05 x FX 5.40 x (1+0.10) = R$ 0.30 (= 297 shard_milli). O guard de imagem (kill switch + rate card
fresco, 7 dias) impede nova venda de efeito caro com cartao stale.

## Leitura

- Escopo: dimensionamento de PRECO por compra no desenho (preco - taxa - meta), assumindo
  ZERO reembolso/disputa. O relatorio real (`services/finops.py`) usa receita LIQUIDA
  (bruto - reembolso - disputa) e a margem % e a meta de 5% sao calculadas sobre ela;
  taxas ja pagas e custo de uso nao sao devolvidos pelo canal. Esta simulacao NAO
  prova margem de producao: so mostra a folga do preco antes de publicar a versao.
- O pacote e dimensionado em ORCAMENTO, nao em turnos: a margem % e independente do custo
  por turno e so o numero de turnos/pacote muda. A unica protecao contra deriva de custo
  e o buffer de FX (10%): 'folga' ~1,10x. Acima disso, com todos os shards consumidos, a
  margem cai abaixo de 5% => rate card fresco/alertas/kill switches sao o guard real
  (SPEC-196 R3/R4/R5).
- A folga cai com a taxa do canal: Google Play (15%) tem folga menor que Stripe; preco baixo
  sofre mais com a taxa fixa de R$0,39 do Stripe.
- Linhas abaixo da meta nesta simulacao (inclui cenarios de deriva): **6**. Cada
  uma indica SKU/canal cujo preco deve subir (ou pacote reduzir) antes de publicar a
  `pricing_version`.
- Quebra (shards nao consumidos) so melhora a margem real; nao e creditada aqui.
