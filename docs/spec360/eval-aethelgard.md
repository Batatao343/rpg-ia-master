# SPEC-360 — eval da fauna viva: Margem de Aethelgard

Gerado por `scripts/fauna/eval.py` (avaliador congelado na Etapa 1; não editar à mão).

- Região: `aethelgard` · seeds: 20 · dias por seed: 60
- Perfil sintético: 3 chegadas por dia entre os nós da região + 1 descanso; perigo forçado 4, nível 3.

| Métrica | Valor | Limiar | Resultado |
|---|---|---|---|
| M1 sinal antes (precedidos) | 0.8099 | ≥ 0.7 | ok |
| M1 aproximação | 1.0000 | ≥ 1.0 | ok |
| M2 horário (pior razão fora/dentro) | 0.2753 | ≤ 0.35 | ok |
| M3 presa sobe (mínimo) | 1.6839 | ≥ 1.5 | ok |
| M3 predador cai (máximo) | 0.4744 | ≤ 0.6 | ok |
| M4 território | 0.9522 | ≥ 0.8 | ok |
| M5 combates por 100 ações (Δ on vs off) | -0.1632 | -0.2 a +0.05 | ok |
| M6 vazamento de nome | 0 | ≤ 0 | ok |

## Contagens

| Modo | Chegadas | Descansos | Gatilhos | Combates de fauna | Conversões | Sinais em cena |
|---|---|---|---|---|---|---|
| off | 3600 | 1200 | 1200 | 723 | 0 | 0 |
| on | 3600 | 1200 | 1200 | 605 | 186 | 1070 |

Combates por 100 ações: off 15.062 · on 12.604.

## Distribuição (contexto neutro, exata)

- M2 por criatura (fora/dentro): {"enemy_cultista_destilacao": 0.2018, "enemy_esqueleto_mago": 0.2131, "enemy_fantasma": 0.2514, "mon_bigua_de_vidro": 0.2326, "mon_comedor_de_alga": 0.2018, "mon_mergulhadores_saqueadores": 0.2514, "mon_peito_de_sino": 0.2514, "mon_pernalta_do_conselho": 0.2753, "mon_quimera_cristal": 0.2515, "mon_veu_faminto": 0.2018}
- M3 presa sobe por predador: {"enemy_fantasma": 1.866, "mon_aranha_de_bolha": 1.81, "mon_bigua_de_vidro": 1.998, "mon_cacao_de_lastro": 1.6839, "mon_novelo_de_anzois": 1.8155, "mon_quimera_cristal": 1.8707, "mon_veu_faminto": 1.8567}
- M3 predador cai: {"enemy_fantasma": 0.4564, "mon_aranha_de_bolha": 0.4654, "mon_bigua_de_vidro": 0.4719, "mon_novelo_de_anzois": 0.4744, "mon_quimera_cristal": 0.4676, "mon_veu_faminto": 0.4643}
- M4 contextos com candidata territorial: 10

## SPEC-370 — por região, oráculo próprio do M1, M7 e M8

- Nós raiz na região: 2. N/A declarados no avaliador (R16).

| Métrica | Valor | Limiar | Resultado |
|---|---|---|---|
| M1 precedidos (oráculo próprio, R18) | 0.8050 | ≥ 0.7 | ok |
| M1 precedidos (oráculo antigo, `sinais_mostrados`) | 0.8099 | informativo | — |
| M1 aproximação | 1.0000 | ≥ 1.0 | ok |
| M2 horário | 0.2753 | ≤ 0.35 | ok |
| M3 cadeia alimentar | sobe 1.6839 · cai 0.4744 | ≥ 1.5 / ≤ 0.6 | ok |
| M4 território | 0.9522 | ≥ 0.8 | ok |
| M5 por região (informativo, D5) | -0.1632 | alerta fora de -0.3 a +0.1 | ok |
| M6 vazamento de nome | 0 | ≤ 0 | ok |
| M7 determinismo (20 × 60) | `c07e3bc7a973faf4` × `c07e3bc7a973faf4` | hashes iguais | ok |
| M8 densidade de sinal novo | 0.2781 | ≤ 0.4 | ok |

### Oráculo do M1

- Combates de fauna com entrada (on): 605 · precedidos (oráculo próprio): 487 · (antigo): 490.
- Divergências: só o antigo conta 3 · só o próprio conta 0.
- Textos de sinal emitidos: 1335 · sem dono no arquivo de dados: 0 · com mais de um dono: 0.
- Ações com sinal novo (M8): 1335 de 4800.
- Gatilhos off = on (R9 da 360): ok.
