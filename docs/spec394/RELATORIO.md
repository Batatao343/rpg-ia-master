# SPEC-394 - relatorio

Base: `main` `55b85c2c` (SPEC-373 pousada). Medicao L3 off/on, sementes 0-39 (`base.json`).
F (sem `ok` na base) = anzolado, armador, portao, escuta. Lacrador, bracos e carregador voltaram
sozinhos para a faixa com a 373 (D1: nao recalibrados).

## R3 - causa da deriva (portao e lacrador)

Bisecao no motor com a arena congelada (worktree descartavel, `docs/spec394/diagnostico.py`):

| commit | portao off/on | lacrador off/on |
|---|---|---|
| `a1751163` (SPEC-349 final) | 61 / 63 | 56 / 81,5 |
| `cb2d3555` | 61 / 63 | 56 / 81,5 |
| `e208f189` | **91** / 93,5 | 64,5 / 89 |
| `b6e84030` ... `03d457dc` (371, 387) | 91 / 93,5 | 64,5 / 89 |

- O salto vem de `e208f189` ("full-suite failures after SPEC-349", 02/11 13:29), nao da SPEC-387.
  Ele acrescentou `"abissal": {"muito_ferido": "flee", "sempre": "attack"}` em
  `services/tactical_profile.py:_ENEMY_ARCHETYPE_ACTIONS` para fazer um teste passar.
- `normalize_runtime_profile` preenche o `action_key` de toda prioridade sem chave com essa tabela,
  ignorando `resistance: absoluta`. O Portao tem `arquetipo: abissal`, `nao_foge: true` e a prioridade
  autoral `muito_ferido` = "Nao sai do batente" (`resistance: absoluta`): agora FOGE ferido e a
  fuga conta como vitoria do heroi.
- Braco de diagnostico: com `abissal` sem `muito_ferido`, portao volta a **61 / 63,5** (igual a 349).
  Mesmo braco no lacrador (tambem abissal): 0,5 % / 1 %, ou seja, o lacrador so fica na faixa porque
  foge; nao ha ajuste de dial que o conserte sem decidir a regra de fuga.
- Braco `_can_act` da 387 (`1e208ac9`) revertido por patch em processo: **sem efeito** (portao 91/90,
  lacrador 64,5/79,5, os outros 3 identicos); 0 acionamentos do ramo em 5 sementes de portao.
  Os commits de dados do bestiario de 349 a hoje nao tocam portao/lacrador (so 373 em outras criaturas).
- Conclusao (D3): **defeito de motor/tabela** (a tabela de arquetipo sobrepoe `nao_foge`/`resistance:
  absoluta`; vale para as 5 criaturas `abissal`: estivador_das_facas, lacrador_de_saidas,
  mastro_de_trofeus, portao_que_morde, monte_de_alheios). Fora do escopo desta spec: spec propria
  (Risco alto). O portao fica como excecao nominal porque qualquer dial calibrado hoje seria
  desfeito pela correcao.

## Recalibracao (R4/R5)

Duas execucoes de `calibrar.py` (a 2a nao achou nada melhor que o melhor da 1a). Dials em `_ajustes.yaml`.

| criatura | antes (off/on) | dials antes | depois (off/on) | dials depois | ok |
|---|---|---|---|---|---|
| mon_anzolado_da_casa | 72,5 / 91 | c2 d1 f1 s0 | 57,5 / 76 | c2 d2 f1 s1 | sim |
| mon_armador_de_fosso | 78,5 / 95,5 | c1 d0 f0 s0 | 49,5 / 86 | c2 d2 f0 s4 | **nao** |
| mon_escuta_do_sinal | 46,5 / 89,5 | c1 d1 f0 s2 | 41,5 / 87,5 | c1 d1 f1 s3 | **nao** |
| mon_portao_que_morde | 91 / 90 | c-2 d-1 | 91 / 90 (intocado) | c-2 d-1 | **nao** |

Armador e escuta: o `on` fica 36-46 pp acima do `off`, e os dials movem os dois modos juntos;
melhor ajuste visto e mantido (D2).

EXCECAO mon_armador_de_fosso
EXCECAO mon_escuta_do_sinal
EXCECAO mon_portao_que_morde

## R6 - as outras criaturas

`base-snapshot.json` x `final-snapshot.json` (369 ids, hash off + baralho on, sementes 0-11): identicos.

## R7 - confirmacao (sementes 40-119, uma rodada, sem reajuste)

| criatura | off / on | ok |
|---|---|---|
| mon_anzolado_da_casa | 56,8 / 71 | sim |
| mon_armador_de_fosso | 41,7 / 79,5 | nao (off 3,3 pp abaixo do piso; `on` entrou) |
| mon_escuta_do_sinal | 42,7 / 82 | nao (off 2,3 pp abaixo do piso) |
| mon_portao_que_morde | 90,7 / 91 | nao (bug de motor, spec propria) |

Veredito cheio: `N_373 + 1` (so o anzolado voltou). Armador e escuta estao a 2-3 pp da faixa em
sementes novas; o ajuste em 0-39 sobreajustou o `off`. Sem reajuste (D5).
