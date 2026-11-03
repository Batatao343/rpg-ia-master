# SPEC-360 — eval da fauna viva: Skallgard

Gerado por `scripts/fauna/eval.py` (avaliador congelado na Etapa 1; não editar à mão).

- Região: `skallgard` · seeds: 20 · dias por seed: 60
- Perfil sintético: 3 chegadas por dia entre os nós da região + 1 descanso; perigo forçado 4, nível 3.

| Métrica | Valor | Limiar | Resultado |
|---|---|---|---|
| M1 sinal antes (precedidos) | 0.7867 | ≥ 0.7 | ok |
| M1 aproximação | 1.0000 | ≥ 1.0 | ok |
| M2 horário (pior razão fora/dentro) | 0.2831 | ≤ 0.35 | ok |
| M3 presa sobe (mínimo) | 1.73 | ≥ 1.5 | ok |
| M3 predador cai (máximo) | 0.5152 | ≤ 0.6 | ok |
| M4 território | 0.8896 | ≥ 0.8 | ok |
| M5 combates por 100 ações (Δ on vs off) | -0.1701 | -0.2 a +0.05 | ok |
| M6 vazamento de nome | 0 | ≤ 0 | ok |

## Contagens

| Modo | Chegadas | Descansos | Gatilhos | Combates de fauna | Conversões | Sinais em cena |
|---|---|---|---|---|---|---|
| off | 3600 | 1200 | 1200 | 723 | 0 | 0 |
| on | 3600 | 1200 | 1200 | 600 | 213 | 1173 |

Combates por 100 ações: off 15.062 · on 12.5.

## Distribuição (contexto neutro, exata)

- M2 por criatura (fora/dentro): {"enemy_guerreiro_bjorn": 0.2056, "enemy_renegado_ermo": 0.1756, "enemy_yeti": 0.2439, "mon_andas_de_caribu": 0.2439, "mon_aperto_da_tregua": 0.2831, "mon_corvo_gelo": 0.1856, "mon_desfiado_da_aurora": 0.2278, "mon_ermitao_de_elmo": 0.2333, "mon_ferreiro_chama_fria": 0.2333, "mon_jotun_cinza": 0.2395, "mon_lagarta_sete_invernos": 0.2111, "mon_lascador_morno": 0.1866, "mon_levantado_de_rubi": 0.1866, "mon_lobo_aurora": 0.2564, "mon_lobo_de_vidro": 0.2032, "mon_mandriao_dois_bicos": 0.2543, "mon_montaria_cravada": 0.1756, "mon_queimado_de_breu": 0.2702, "mon_ticao_do_juramento": 0.2831}
- M3 presa sobe por predador: {"mon_carrapato_de_mamute": 1.8251, "mon_ermitao_de_elmo": 1.8091, "mon_lobo_aurora": 2.0469, "mon_lobo_de_vidro": 1.869, "mon_mandriao_dois_bicos": 1.9371, "mon_montaria_cravada": 1.9702, "mon_urso_tita": 1.73, "mon_verme_do_gelo": 1.9775}
- M3 predador cai: {"mon_carrapato_de_mamute": 0.4769, "mon_ermitao_de_elmo": 0.4637, "mon_lobo_aurora": 0.4883, "mon_lobo_de_vidro": 0.5152, "mon_mandriao_dois_bicos": 0.5087, "mon_montaria_cravada": 0.4908, "mon_verme_do_gelo": 0.4809}
- M4 contextos com candidata territorial: 15

## SPEC-370 — por região, oráculo próprio do M1, M7 e M8

- Nós raiz na região: 3. N/A declarados no avaliador (R16).

| Métrica | Valor | Limiar | Resultado |
|---|---|---|---|
| M1 precedidos (oráculo próprio, R18) | 0.7517 | ≥ 0.7 | ok |
| M1 precedidos (oráculo antigo, `sinais_mostrados`) | 0.7867 | informativo | — |
| M1 aproximação | 1.0000 | ≥ 1.0 | ok |
| M2 horário | 0.2831 | ≤ 0.35 | ok |
| M3 cadeia alimentar | sobe 1.73 · cai 0.5152 | ≥ 1.5 / ≤ 0.6 | ok |
| M4 território | 0.8896 | ≥ 0.8 | ok |
| M5 por região (informativo, D5) | -0.1701 | alerta fora de -0.3 a +0.1 | ok |
| M6 vazamento de nome | 0 | ≤ 0 | ok |
| M7 determinismo (20 × 60) | `08e7f1daf44eaaa8` × `08e7f1daf44eaaa8` | hashes iguais | ok |
| M8 densidade de sinal novo | 0.3088 | ≤ 0.4 | ok |

### Oráculo do M1

- Combates de fauna com entrada (on): 600 · precedidos (oráculo próprio): 451 · (antigo): 472.
- Divergências: só o antigo conta 21 · só o próprio conta 0.
- Textos de sinal emitidos: 1482 · sem dono no arquivo de dados: 0 · com mais de um dono: 0.
- Ações com sinal novo (M8): 1482 de 4800.
- Gatilhos off = on (R9 da 360): ok.
