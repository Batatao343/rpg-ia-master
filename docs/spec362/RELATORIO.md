# SPEC-362 - relatorio (executor)

Base nova 0-19 (main atual): Arcanista todas 44,4 / calibrado 55,4 / descoberto 40,6 / improvisador 55,8 (igual a 355 pos-bestiario).

Decomposicao (0-19, todas): atual 44,4 | raio_cinza de volta ao pool 46,7 | utilitarias na compra 42,3 (piora).
Logo a queda vem do R12 (raio_cinza fora), nao do R11; D4 nao ajuda.

Pacote (Delta por passo em `passos-0-19.json`): bomba_estopim (frequencia cena->turno, dano_base 4->5), truque (protecao 2->3), pulso_medido (dano_base 3->4); garganta tentada e revertida (-0,6).
Final 0-19: todas 46,5 (folga atingida); descoberto 40,6; improvisador 58,3 (padrao <= 75). Outras Posturas identicas a base.

Confirmacao 20-99 (uma vez): todas **44,8 %** (< 45,0): R12 FALHOU. calibrado 57,0 / descoberto 41,8 / improvisador 59,0.
Sem reajuste (R3). `EXCECOES_PISO` fica (comentario deve citar 362 e 44,8 %). Bandeira por Carta nao medida (confirmacao ja falhou).
Opcao ao dono (D4): aceitar a excecao, ou spec com carta nova/legada (raio_cinza no pool = +2,3 pp medido).

## Rodada 2 (decisao do dono, 02/11)
Alavancas: raio_cinza de volta ao pool (R12 da 355 era higiene, nao dominancia) + pulso_medido custo_folego 1->0. 0-19: 48,1 % (todas), descoberto 44,2, improvisador 59,4, calibrado 56,9; outras Posturas identicas a base.
Confirmacao 100-179 (uma vez): todas **44,4 %** (cal 56,0 / des 40,8 / imp 55,8) - FALHOU. 20-99 informativa: 46,1 %.
Leitura: queda 0-19 -> held-out de ~3,7 pp (SE ~1,1 pp por 1.920 lutas; 0-19 tem 480 lutas, SE ~2,3). Bandeira dominante nao medida. Parado (regra 4).
