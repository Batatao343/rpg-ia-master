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
