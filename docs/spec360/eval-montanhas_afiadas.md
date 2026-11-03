# SPEC-360 — eval da fauna viva: Montanhas Afiadas

Gerado por `scripts/fauna/eval.py` (avaliador congelado na Etapa 1; não editar à mão).

- Região: `montanhas_afiadas` · seeds: 20 · dias por seed: 60
- Perfil sintético: 3 chegadas por dia entre os nós da região + 1 descanso; perigo forçado 4, nível 3.

| Métrica | Valor | Limiar | Resultado |
|---|---|---|---|
| M1 sinal antes (precedidos) | 0.8158 | ≥ 0.7 | ok |
| M1 aproximação | 1.0000 | ≥ 1.0 | ok |
| M2 horário (pior razão fora/dentro) | 0.3232 | ≤ 0.35 | ok |
| M3 presa sobe (mínimo) | 1.7072 | ≥ 1.5 | ok |
| M3 predador cai (máximo) | 0.5007 | ≤ 0.6 | ok |
| M4 território | 0.9249 | ≥ 0.8 | ok |
| M5 combates por 100 ações (Δ on vs off) | -0.2490 | -0.2 a +0.05 | FALHOU |
| M6 vazamento de nome | 0 | ≤ 0 | ok |

## Contagens

| Modo | Chegadas | Descansos | Gatilhos | Combates de fauna | Conversões | Sinais em cena |
|---|---|---|---|---|---|---|
| off | 3600 | 1200 | 1200 | 723 | 0 | 0 |
| on | 3600 | 1200 | 1200 | 543 | 296 | 1068 |

Combates por 100 ações: off 15.062 · on 11.312.

## Distribuição (contexto neutro, exata)

- M2 por criatura (fora/dentro): {"enemy_morcego_vampiro": 0.2483, "enemy_orc_saidas_baixas": 0.2066, "enemy_wyvern_jovem": 0.2878, "mon_cabra_labirinto": 0.3232, "mon_cabra_navalha": 0.2756, "mon_geodo_da_praga": 0.184, "mon_mao_da_borda": 0.3232, "mon_marco_que_aponta": 0.2878, "mon_queimado_de_frio": 0.1644, "mon_rolador_de_escarpa": 0.2756, "mon_tesoura_de_cordada": 0.2878}
- M3 presa sobe por predador: {"enemy_basilisco_caverna": 1.7235, "enemy_morcego_vampiro": 1.8147, "enemy_wyvern_jovem": 1.7072, "mon_chicote_de_fenda": 1.7522}
- M3 predador cai: {"enemy_basilisco_caverna": 0.4687, "enemy_morcego_vampiro": 0.4729, "enemy_wyvern_jovem": 0.5007, "mon_chicote_de_fenda": 0.4968}
- M4 contextos com candidata territorial: 15

## SPEC-370 — por região, oráculo próprio do M1, M7 e M8

- Nós raiz na região: 3. N/A declarados no avaliador (R16).

| Métrica | Valor | Limiar | Resultado |
|---|---|---|---|
| M1 precedidos (oráculo próprio, R18) | 0.7993 | ≥ 0.7 | ok |
| M1 precedidos (oráculo antigo, `sinais_mostrados`) | 0.8158 | informativo | — |
| M1 aproximação | 1.0000 | ≥ 1.0 | ok |
| M2 horário | 0.3232 | ≤ 0.35 | ok |
| M3 cadeia alimentar | sobe 1.7072 · cai 0.5007 | ≥ 1.5 / ≤ 0.6 | ok |
| M4 território | 0.9249 | ≥ 0.8 | ok |
| M5 por região (informativo, D5) | -0.2490 | alerta fora de -0.3 a +0.1 | ok |
| M6 vazamento de nome | 0 | ≤ 0 | ok |
| M7 determinismo (20 × 60) | `a2f8d4909ab79652` × `a2f8d4909ab79652` | hashes iguais | ok |
| M8 densidade de sinal novo | 0.3040 | ≤ 0.4 | ok |

### Oráculo do M1

- Combates de fauna com entrada (on): 543 · precedidos (oráculo próprio): 434 · (antigo): 443.
- Divergências: só o antigo conta 9 · só o próprio conta 0.
- Textos de sinal emitidos: 1459 · sem dono no arquivo de dados: 0 · com mais de um dono: 0.
- Ações com sinal novo (M8): 1459 de 4800.
- Gatilhos off = on (R9 da 360): ok.
