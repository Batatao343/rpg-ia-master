# SPEC-360 — eval da fauna viva: Skallgard

Gerado por `scripts/fauna/eval.py` (avaliador congelado na Etapa 1; não editar à mão).

- Região: `skallgard` · seeds: 20 · dias por seed: 60
- Perfil sintético: 3 chegadas por dia entre os nós da região + 1 descanso; perigo forçado 4, nível 3.

| Métrica | Valor | Limiar | Resultado |
|---|---|---|---|
| M1 sinal antes (precedidos) | 0.7726 | ≥ 0.7 | ok |
| M1 aproximação | 1.0000 | ≥ 1.0 | ok |
| M2 horário (pior razão fora/dentro) | 0.2841 | ≤ 0.35 | ok |
| M3 presa sobe (mínimo) | 1.7299 | ≥ 1.5 | ok |
| M3 predador cai (máximo) | 0.5152 | ≤ 0.6 | ok |
| M4 território | 0.8627 | ≥ 0.8 | ok |
| M5 combates por 100 ações (Δ on vs off) | -0.1549 | -0.2 a +0.05 | ok |
| M6 vazamento de nome | 0 | ≤ 0 | ok |

## Contagens

| Modo | Chegadas | Descansos | Gatilhos | Combates de fauna | Conversões | Sinais em cena |
|---|---|---|---|---|---|---|
| off | 3600 | 1200 | 1200 | 723 | 0 | 0 |
| on | 3600 | 1200 | 1200 | 611 | 198 | 1155 |

Combates por 100 ações: off 15.062 · on 12.729.

## Distribuição (contexto neutro, exata)

- M2 por criatura (fora/dentro): {"enemy_guerreiro_bjorn": 0.2047, "enemy_renegado_ermo": 0.1747, "enemy_yeti": 0.2436, "mon_andas_de_caribu": 0.2436, "mon_aperto_da_tregua": 0.2841, "mon_corvo_gelo": 0.1866, "mon_desfiado_da_aurora": 0.2289, "mon_ermitao_de_elmo": 0.2329, "mon_ferreiro_chama_fria": 0.2329, "mon_jotun_cinza": 0.2382, "mon_lagarta_sete_invernos": 0.2108, "mon_lascador_morno": 0.1868, "mon_levantado_de_rubi": 0.1868, "mon_lobo_aurora": 0.258, "mon_lobo_de_vidro": 0.2041, "mon_mandriao_dois_bicos": 0.2531, "mon_montaria_cravada": 0.1747, "mon_queimado_de_breu": 0.2722, "mon_ticao_do_juramento": 0.2841}
- M3 presa sobe por predador: {"mon_carrapato_de_mamute": 1.822, "mon_ermitao_de_elmo": 1.8063, "mon_lobo_aurora": 2.0372, "mon_lobo_de_vidro": 1.8617, "mon_mandriao_dois_bicos": 1.927, "mon_montaria_cravada": 1.9631, "mon_urso_tita": 1.7299, "mon_verme_do_gelo": 1.9705}
- M3 predador cai: {"mon_carrapato_de_mamute": 0.4769, "mon_ermitao_de_elmo": 0.4637, "mon_lobo_aurora": 0.4884, "mon_lobo_de_vidro": 0.5152, "mon_mandriao_dois_bicos": 0.5089, "mon_montaria_cravada": 0.491, "mon_verme_do_gelo": 0.4811}
- M4 contextos com candidata territorial: 15

## SPEC-370 — por região, oráculo próprio do M1, M7 e M8

- Nós raiz na região: 3. N/A declarados no avaliador (R16).

| Métrica | Valor | Limiar | Resultado |
|---|---|---|---|
| M1 precedidos (oráculo próprio, R18) | 0.7375 | ≥ 0.7 | ok |
| M1 precedidos (oráculo antigo, `sinais_mostrados`) | 0.7726 | informativo | — |
| M1 aproximação | 1.0000 | ≥ 1.0 | ok |
| M2 horário | 0.2841 | ≤ 0.35 | ok |
| M3 cadeia alimentar | sobe 1.7299 · cai 0.5152 | ≥ 1.5 / ≤ 0.6 | ok |
| M4 território | 0.8627 | ≥ 0.8 | ok |
| M5 por região (informativo, D5) | -0.1549 | alerta fora de -0.3 a +0.1 | ok |
| M6 vazamento de nome | 0 | ≤ 0 | ok |
| M7 determinismo (20 × 60) | `23c5b451caa58add` × `23c5b451caa58add` | hashes iguais | ok |
| M8 densidade de sinal novo | 0.3017 | ≤ 0.4 | ok |

### Oráculo do M1

- Combates de fauna com entrada (on): 598 · precedidos (oráculo próprio): 441 · (antigo): 462.
- Divergências: só o antigo conta 21 · só o próprio conta 0.
- Textos de sinal emitidos: 1448 · sem dono no arquivo de dados: 0 · com mais de um dono: 0.
- Ações com sinal novo (M8): 1448 de 4800.
- Gatilhos off = on (R9 da 360): ok.
