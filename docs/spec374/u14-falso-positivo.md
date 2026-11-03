# SPEC-374 — U14 (coerência eixo × corpo): taxa de falso positivo

Regra: `services/axis_text.py`, ligada ao `creature_gen.lint_runtime` (e por isso à correção curta e ao
`reparar_eixos`). Medida sobre as **281 fichas aprovadas** (`creature_gen.fichas_aprovadas()`: curadoria
da 349 + pool), sem LLM.

## O que a regra cobra (e o que não)

- **Material, dominância:** o material declarado tem <= 1 raiz distinta no corpo (léxico amplo) e **outro**
  material tem >= 3 raízes distintas do léxico forte (sal, osso, ferro, cristal, cera, lama, cinza, madeira,
  quitina). Genéricos (couro, pele, casca, fibra) ficam fora do léxico forte.
- **Locomoção `nada`, ausência:** nenhuma raiz de água/nado no corpo.
- **Não cobra:** `percepcao`, `plano_corporal`, `escala`, nem as demais locomoções. Primeira versão com
  ausência/dominância nos três eixos reprovava **45,6 %** das aprovadas (128/281): o texto das fichas boas
  não nomeia a percepção nem o jeito de andar de forma verificável. Limitação assumida: a percepção
  `respiracao` do "Ouvido de Sal" (a terceira contradição do curador) **não** é pega; material e
  locomoção são.

## Resultado

- **Falso positivo: 7 / 281 = 2,5 %** (teto do teste: 4 %).
- "Ouvido de Sal" reprova em 2 eixos: `material carne_exposta` (domina `sal_mineral`) e `locomocao nada` (ausente).

Fichas aprovadas que a regra marca (todas discutíveis; a maioria é mistura real de matérias):

```
mon_lesma_de_penacho [('material', 'carne_exposta', 'domina:eter_cristalizado')]
mon_esfolado_de_sal [('locomocao', 'nada', 'ausente')]
enemy_polvo_esgoto [('material', 'carne_exposta', 'domina:lama_turfa')]
mon_ossada_de_pomes [('material', 'cinza', 'domina:osso')]
mon_turno_vencido [('material', 'sal_mineral', 'domina:lama_turfa')]
enemy_vinha_estranguladora [('material', 'couro_tecido', 'domina:madeira_fibra')]
mon_ticao_do_juramento [('material', 'madeira_fibra', 'domina:osso')]
```
