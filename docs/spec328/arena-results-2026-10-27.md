# SPEC-328 Etapa 6 - arena `off` x `on` (27/10, amostra pequena)

Script: `bash scripts/dev/py.sh docs/spec328/arena_deck.py 3 --levels 1,3,5 --categories padrao,elite --per-cat 4 --folego N`
(MockLLM, seeded, 5 Posturas x 4 criaturas x 3 seeds = 12 combates por classe/célula; 360 combates por modo).
Bot `off` = "cartas" da SPEC-285 (1 ação/rodada). Bot `on` = joga da mão enquanto houver Fôlego, sem tomar emprestado.

| Fôlego | Mão | Célula | Vitória off | Vitória on | Rodadas off | Rodadas on |
|---|---|---|---|---|---|---|
| 3 | 5 | L1 padrão | 57% | 98% | 3.7 | 1.9 |
| 3 | 5 | L3 padrão | 73% | 85% | 4.1 | 2.5 |
| 3 | 5 | todas (L1/3/5 x padrão/elite) | 42% | 73% | 4.5 | 3.1 |
| 2 | 5 | L1 padrão | 57% | 95% | 3.7 | 2.4 |
| 2 | 5 | L3 padrão | 73% | 73% | 4.1 | 2.9 |
| 2 | 5 | todas | 42% | 63% | 4.5 | 3.6 |
| 1 | 5 | L1 padrão | 57% | 67% | 3.7 | 3.5 |
| 1 | 5 | L3 padrão | 73% | 70% | 4.1 | 4.2 |
| 1 | 5 | todas | 42% | 43% | 4.5 | 4.3 |
| 3 | 4 | todas | 42% | 64% | 4.5 | 3.3 |

Leitura: com os padrões do dono (Fôlego 3 / mão 5) o herói passa a jogar ~2-3 cartas por rodada e o
combate encurta ~30-50% com vitória bem acima do `off` (fora do critério de ±15 pp). Fôlego 1 reproduz o `off`
(sem jogo de cartas); Fôlego 2 é o ponto intermediário (ainda +20 pp nas células fáceis, ~par em L3).
Observação: o próprio `off` já fica fora de 35-80% nesta arena (L1 Sangromante/Corruptor 25%, L5 0-50%), então o
critério "35-80% por classe" precisa de decisão do dono sobre o alvo (calibrar com SPEC-329/inimigos ou Fôlego 2).
Nenhuma constante foi alterada: `FOLEGO_BASE=3` / `MAO_BASE=5` (padrões aprovados). Flag permanece `off`.

## Rodada 2 (revisão Sol) - derivação R6: custo 2 a partir de `dano_base >= 5` (em vez de 8)

`--dano2 5` x `--dano2 8`, mesma amostra (360 combates/modo), Fôlego 3 e 2, mão 5:

| Fôlego | `dano2` | Célula | Vitória off | Vitória on | Rodadas off | Rodadas on |
|---|---|---|---|---|---|---|
| 3 | 8 | todas | 42% | 73% | 4.5 | 3.1 |
| 3 | 5 | todas | 42% | 73% | 4.5 | 3.1 |
| 2 | 8 | todas | 42% | 63% | 4.5 | 3.6 |
| 2 | 5 | todas | 42% | 63% | 4.5 | 3.6 |

Resultado idêntico: o bot joga as básicas (`custo_folego: 1` explícito) e nenhuma carta do baralho inicial tem
`dano_base` entre 5 e 7 que mude a mão. A derivação 5 **não** aproxima do `off` (+31 pp continua); mantida a atual (8).
A alavanca real é a economia de ações (Fôlego), não a derivação. O Pacto (agora +2 Entropia/+1 Carga) não entra
nesta arena porque o bot nunca toma emprestado.
