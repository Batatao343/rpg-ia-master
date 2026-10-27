# SPEC-332 - arena por família, `RPG_ENEMY_DECKS` off x on (27/10, amostra pequena)

Script: `bash scripts/dev/py.sh docs/spec332/arena_familias.py 3 --levels 3,5 --per-family 3`
(MockLLM, seeded; 5 Posturas x 3 criaturas não-chefe por família x 3 seeds = 45 combates por célula/modo;
predador_apice tem só 5 criaturas não-chefe -> 15). Bot "cartas" da SPEC-285. Vitória = herói vence.
`abissal` não tem criatura no bestiário atual (só entra por criatura gerada/sinal explícito): sem célula.

| Família | L3 off | L3 on | Δpp | L5 off | L5 on | Δpp |
|---|---|---|---|---|---|---|
| predador | 53% | 51% | -2 | 13% | 20% | +7 |
| covarde_oportunista | 93% | 87% | -7 | 98% | 91% | -7 |
| conjurador | 73% | 80% | +7 | 53% | 62% | +9 |
| morto_vivo_implacavel | 42% | 38% | -4 | 11% | 18% | +7 |
| bruto | 56% | 38% | -18 | 38% | 31% | -7 |
| guardiao | 24% | 22% | -2 | 11% | 18% | +7 |
| predador_apice | 73% | 67% | -7 | 0% | 0% | 0 |
| tatico | 58% | 73% | +16 | 67% | 76% | +9 |
| lider_matilha | 51% | 36% | -16 | 69% | 38% | -31 |
| emboscador | 56% | 56% | 0 | 29% | 27% | -2 |

Leitura: com a calibragem (dano de carta de inimigo -3 com piso na arma, buffs -2, DoT -1; só a assinatura é
`turno`; resto `cena`; assinatura com desvio por criatura) 17 de 20 células ficam a ±10 pp do `off`.
Fora: `bruto` L3 (-18), `lider_matilha` L3/L5 (-16/-31: o perfil de apoio do líder agora também usa cartas do
baralho) - **calibrar antes de ligar `on`**. O `off` já está fora de 45-85 % em vários nichos (L5 de predador,
morto-vivo, guardião e apex; L3 de guardião): o critério absoluto da spec depende de decisão do dono sobre o alvo,
como já registrado na arena da SPEC-328. Iterações da calibragem (mesma amostra reduzida, 2 seeds): sem calibrar
a vitória média caía de 62 % para 45 % nas 6 famílias medidas; ablação mostrou o dano das cartas como o maior driver
(-11 pp), depois buffs e controle.

## Lote 2 (27/10) - amostra maior, facções + curadoria + calibragem de `lider_matilha`

Comando: `bash scripts/dev/py.sh docs/spec332/arena_familias.py 8 --levels 3,5 --per-family 5` (200 combates por célula
`off`/`on`; predador_apice 40). `on` agora inclui os baralhos de facção, a curadoria de `bst_bote_certeiro` e as fases
de chefe (chefes ficam fora da arena). Alvo usado (decisão do coordenador): 45-85 % de vitória do jogador; o delta
`on` - `off` fica registrado para o dono escolher o alvo depois.

| Família | L3 off | L3 on | Δpp | L5 off | L5 on | Δpp |
|---|---|---|---|---|---|---|
| predador | 52,0 | 48,5 | -3,5 | 23,5 | 30,5 | +7,0 |
| covarde_oportunista | 84,5 | 79,5 | -5,0 | 88,0 | 75,5 | -12,5 |
| conjurador | 57,0 | 51,5 | -5,5 | 45,5 | 40,5 | -5,0 |
| morto_vivo_implacavel | 40,5 | 25,5 | -15,0 | 16,0 | 9,5 | -6,5 |
| bruto | 75,5 | 70,5 | -5,0 | 39,5 | 35,0 | -4,5 |
| guardiao | 31,5 | 20,0 | -11,5 | 19,0 | 10,0 | -9,0 |
| predador_apice | 82,5 | 80,0 | -2,5 | 12,5 | 5,0 | -7,5 |
| tatico | 74,0 | 76,5 | +2,5 | 65,0 | 65,5 | +0,5 |
| lider_matilha | 62,0 | 65,5 | +3,5 | 72,0 | 65,0 | -7,0 |
| emboscador | 70,5 | 64,0 | -6,5 | 36,5 | 32,5 | -4,0 |

- `bruto`: o -18 pp da amostra pequena era ruído (3 seeds x 3 criaturas); com 200 combates o delta é -5/-4,5 pp e L3 fica
  dentro da faixa. Sem mudança de carta. L5 (off 39,5) já está abaixo de 45 % no `off`.
- `lider_matilha`: L5 caía -19,5 pp. Ablação: o responsável era `inf_lider_matilha_mordida_do_alfa` (pesada 8); trocada para marcial 5 (o validador exige base >= arma)
  (e `uivo_de_reuniao` 2 -> 1) o delta vai a +3,5/-7,0 pp, ambos dentro da faixa.
- Ainda fora de 45-85 % no `on`: predador L5, morto_vivo L3/L5, guardiao L3/L5, apex L5, emboscador L5, conjurador L5
  (40,5), bruto L5 - todos já fora (ou na borda) no `off`; piores deltas de `on`: morto_vivo L3 (-15), covarde L5
  (-12,5), guardiao L3 (-11,5). Decisão do dono: manter o `off` como régua ou subir o piso desses nichos.
