# SPEC-360 — eval da fauna viva: Deserto de Zhur

Gerado por `scripts/fauna/eval.py` (avaliador congelado na Etapa 1; não editar à mão).

- Região: `deserto_zhur` · seeds: 20 · dias por seed: 60
- Perfil sintético: 3 chegadas por dia entre os nós da região + 1 descanso; perigo forçado 4, nível 3.

| Métrica | Valor | Limiar | Resultado |
|---|---|---|---|
| M1 sinal antes (precedidos) | 0.8230 | ≥ 0.7 | ok |
| M1 aproximação | 1.0000 | ≥ 1.0 | ok |
| M2 horário (pior razão fora/dentro) | 0.2487 | ≤ 0.35 | ok |
| M3 presa sobe (mínimo) | 1.7833 | ≥ 1.5 | ok |
| M3 predador cai (máximo) | 0.4841 | ≤ 0.6 | ok |
| M4 território | 0.9406 | ≥ 0.8 | ok |
| M5 combates por 100 ações (Δ on vs off) | -0.1715 | -0.2 a +0.05 | ok |
| M6 vazamento de nome | 0 | ≤ 0 | ok |

## Contagens

| Modo | Chegadas | Descansos | Gatilhos | Combates de fauna | Conversões | Sinais em cena |
|---|---|---|---|---|---|---|
| off | 3600 | 1200 | 1200 | 723 | 0 | 0 |
| on | 3600 | 1200 | 1200 | 599 | 205 | 1091 |

Combates por 100 ações: off 15.062 · on 12.479.

## Distribuição (contexto neutro, exata)

- M2 por criatura (fora/dentro): {"enemy_devorador_sol_zhur": 0.2487, "enemy_djinn_menor": 0.2224, "enemy_escorpiao_cristal": 0.2118, "mon_aguadeiro_de_bucho": 0.2487, "mon_altivo_do_vidro": 0.2487, "mon_cacador_sem_calor": 0.2318, "mon_costurado_de_lentes": 0.1991, "mon_couro_pegado": 0.2487, "mon_despenseiro_de_espinhos": 0.237, "mon_escaravelho_vidro": 0.237, "mon_fervente_de_ferrugem": 0.2009, "mon_furador_de_odres": 0.1726, "mon_guia_avesso": 0.198, "mon_hiena_sol": 0.2053, "mon_lacrador_de_saidas": 0.2165, "mon_lambedor_de_halito": 0.1726, "mon_lastreiro_da_cratera": 0.1991, "mon_maos_de_cinzel": 0.2318, "mon_peito_de_geodo": 0.2135, "mon_saltador_de_palafita": 0.1991, "mon_tatu_de_navalha": 0.2487, "mon_varano_vidrado": 0.2318}
- M3 presa sobe por predador: {"enemy_devorador_sol_zhur": 1.824, "enemy_escorpiao_cristal": 1.905, "enemy_verme_areia_jovem": 1.8239, "mon_cavador_de_funil": 1.7833, "mon_hiena_sol": 1.8674, "mon_lastreiro_da_cratera": 1.8295, "mon_varano_vidrado": 1.9011}
- M3 predador cai: {"enemy_devorador_sol_zhur": 0.4522, "enemy_escorpiao_cristal": 0.4841, "enemy_verme_areia_jovem": 0.4635, "mon_cavador_de_funil": 0.464, "mon_hiena_sol": 0.4729, "mon_lastreiro_da_cratera": 0.4441, "mon_varano_vidrado": 0.4717}
- M4 contextos com candidata territorial: 10

## SPEC-370 — por região, oráculo próprio do M1, M7 e M8

- Nós raiz na região: 2. N/A declarados no avaliador (R16).

| Métrica | Valor | Limiar | Resultado |
|---|---|---|---|
| M1 precedidos (oráculo próprio, R18) | 0.8114 | ≥ 0.7 | ok |
| M1 precedidos (oráculo antigo, `sinais_mostrados`) | 0.8230 | informativo | — |
| M1 aproximação | 1.0000 | ≥ 1.0 | ok |
| M2 horário | 0.2487 | ≤ 0.35 | ok |
| M3 cadeia alimentar | sobe 1.7833 · cai 0.4841 | ≥ 1.5 / ≤ 0.6 | ok |
| M4 território | 0.9406 | ≥ 0.8 | ok |
| M5 por região (informativo, D5) | -0.1715 | alerta fora de -0.3 a +0.1 | ok |
| M6 vazamento de nome | 0 | ≤ 0 | ok |
| M7 determinismo (20 × 60) | `9ad322b93702d86c` × `9ad322b93702d86c` | hashes iguais | ok |
| M8 densidade de sinal novo | 0.2885 | ≤ 0.4 | ok |

### Oráculo do M1

- Combates de fauna com entrada (on): 599 · precedidos (oráculo próprio): 486 · (antigo): 493.
- Divergências: só o antigo conta 7 · só o próprio conta 0.
- Textos de sinal emitidos: 1385 · sem dono no arquivo de dados: 0 · com mais de um dono: 0.
- Ações com sinal novo (M8): 1385 de 4800.
- Gatilhos off = on (R9 da 360): ok.
