# SPEC-395 - relatorio

## Etapa 0
`e208f189` so acrescentou `"abissal": {"muito_ferido": "flee", "sempre": "attack"}` em `tactical_profile.py`
(mais ajustes de teste/simulacao/validator). Teste motivador:
`test_todo_bestiario_curado_normaliza_para_action_keys_fechadas`.

## Conjunto A (prioridade `absoluta` com flee/surrender pela tabela): 8 ids
portao_que_morde (abissal), odre_de_oleo, sorvedouro_do_codigo, pavio_da_lista (conjurador),
fervente_de_ferrugem, porca_da_queda (bruto), dedos_de_colheita (covarde_oportunista),
lencol_de_chamine (predador). So o portao e abissal; os outros 7 caem na mesma regra.

## R3 - equivalencia
`base-snapshot.json` (main sem correcao, 373 ids) x `fix-snapshot.json` (correcao, `--excluir A`):
365 ids identicos; os 8 de A diferem (action_key). `final-snapshot.json` (excluindo A + 4 abissais
restantes = 12 ids, 361 ids) identico ao da correcao.

## R4/R6 - arena L3 off/on, sementes 0-39 (`base.json` -> `arena-final.json`)
| id | base off/on | final off/on |
|---|---|---|
| portao_que_morde | 61 / 63,5 | 61 / 63,5 |
| odre_de_oleo | 56,5 / 53 | 56,5 / 53 |
| sorvedouro_do_codigo | **8,5 / 12** | 59 / 59 |
| pavio_da_lista | **2 / 2,5** | 55 / 63,5 |
| fervente_de_ferrugem | 58,5 / 68 | igual |
| porca_da_queda | **7 / 11** | 70 / 74,5 |
| dedos_de_colheita | **8,5 / 11** | 57,5 / 59 |
| lencol_de_chamine | 60 / 60 | igual |
| estivador, lacrador, mastro, monte | em faixa | iguais (por R3) |

F = sorvedouro, pavio, porca, dedos (a fuga deixou de contar como vitoria do heroi). 1 execucao de
`calibrar.py` (3 rodadas), so corpo/dano/forca/sig dentro de +-7 (maior: corpo -5 no sorvedouro).
Dials no `_ajustes.yaml`, regenerados por `gerar_mecanica.py` (via calibrar): bestiary.json e
`data/cards/criaturas/nova_arcadia.json`.

## R7 - confirmacao sementes 40-119 (sem reajuste)
Todos `ok` exceto **mon_odre_de_oleo** (L3 off 37,2 % / on 45,8 %; nao recalibrado, estava 56,5/53 em 0-39:
variancia de amostra, ficou fora de F por R4). Demais: portao 53/52,7; sorvedouro 47,2/52; pavio 59,8/63;
fervente 57,3/64,7; porca 64/73; dedos 50,7/49,2; lencol 50,7/50,7; estivador 60,8/75,2;
lacrador 61,5/74,3; mastro 66,5/75,7; monte 62,5/73,8.
