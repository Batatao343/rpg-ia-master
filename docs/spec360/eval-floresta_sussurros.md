# SPEC-360 — eval da fauna viva: Floresta dos Sussurros

Gerado por `scripts/fauna/eval.py` (avaliador congelado na Etapa 1; não editar à mão).

- Região: `floresta_sussurros` · seeds: 20 · dias por seed: 60
- Perfil sintético: 3 chegadas por dia entre os nós da região + 1 descanso; perigo forçado 4, nível 3.

| Métrica | Valor | Limiar | Resultado |
|---|---|---|---|
| M1 sinal antes (precedidos) | 0.7844 | ≥ 0.7 | ok |
| M1 aproximação | 1.0000 | ≥ 1.0 | ok |
| M2 horário (pior razão fora/dentro) | 0.3208 | ≤ 0.35 | ok |
| M3 presa sobe (mínimo) | 1.7153 | ≥ 1.5 | ok |
| M3 predador cai (máximo) | 0.5019 | ≤ 0.6 | ok |
| M4 território | 0.9589 | ≥ 0.8 | ok |
| M5 combates por 100 ações (Δ on vs off) | -0.1466 | -0.2 a +0.05 | ok |
| M6 vazamento de nome | 0 | ≤ 0 | ok |

## Contagens

| Modo | Chegadas | Descansos | Gatilhos | Combates de fauna | Conversões | Sinais em cena |
|---|---|---|---|---|---|---|
| off | 3600 | 1200 | 1200 | 723 | 0 | 0 |
| on | 3600 | 1200 | 1200 | 617 | 171 | 1082 |

Combates por 100 ações: off 15.062 · on 12.854.

## Distribuição (contexto neutro, exata)

- M2 por criatura (fora/dentro): {"enemy_aranha_lobo": 0.2284, "enemy_urso_coruja_mutante": 0.3208, "mon_abafador_de_candeias": 0.2284, "mon_besouro_do_estalo": 0.2637, "mon_bugio_invertido": 0.2098, "mon_calado_das_guelras": 0.2637, "mon_dedos_de_colheita": 0.2116, "mon_desafiante_rubro": 0.3208, "mon_enrolado_da_clareira": 0.2284, "mon_lagarta_de_visgo": 0.2284, "mon_mapa_de_cicatrizes": 0.2116, "mon_mariposa_sussurro": 0.1928, "mon_morcego_rasteiro": 0.2284, "mon_olho_de_petala": 0.2284, "mon_onca_vazada": 0.3208, "mon_picanco_de_espinheiro": 0.2637, "mon_ressecado_da_travessia": 0.3208, "mon_serpente_raiz": 0.1839, "mon_vespa_coveira": 0.2637}
- M3 presa sobe por predador: {"mon_lagarta_de_visgo": 1.8584, "mon_morcego_rasteiro": 1.8925, "mon_olho_de_petala": 1.8099, "mon_onca_vazada": 1.8156, "mon_picanco_de_espinheiro": 1.8804, "mon_serpente_raiz": 1.8942, "mon_toldo_das_clareiras": 1.7153, "mon_urso_de_espinha": 1.8743, "mon_vespa_coveira": 1.8988}
- M3 predador cai: {"mon_lagarta_de_visgo": 0.4643, "mon_morcego_rasteiro": 0.4646, "mon_olho_de_petala": 0.4649, "mon_onca_vazada": 0.5019, "mon_picanco_de_espinheiro": 0.4596, "mon_serpente_raiz": 0.4492, "mon_urso_de_espinha": 0.4832, "mon_vespa_coveira": 0.4678}
- M4 contextos com candidata territorial: 10

## SPEC-370 — por região, oráculo próprio do M1, M7 e M8

- Nós raiz na região: 2. N/A declarados no avaliador (R16).

| Métrica | Valor | Limiar | Resultado |
|---|---|---|---|
| M1 precedidos (oráculo próprio, R18) | 0.7828 | ≥ 0.7 | ok |
| M1 precedidos (oráculo antigo, `sinais_mostrados`) | 0.7844 | informativo | — |
| M1 aproximação | 1.0000 | ≥ 1.0 | ok |
| M2 horário | 0.3208 | ≤ 0.35 | ok |
| M3 cadeia alimentar | sobe 1.7153 · cai 0.5019 | ≥ 1.5 / ≤ 0.6 | ok |
| M4 território | 0.9589 | ≥ 0.8 | ok |
| M5 por região (informativo, D5) | -0.1466 | alerta fora de -0.3 a +0.1 | ok |
| M6 vazamento de nome | 0 | ≤ 0 | ok |
| M7 determinismo (20 × 60) | `ab02011ce821be1d` × `ab02011ce821be1d` | hashes iguais | ok |
| M8 densidade de sinal novo | 0.2796 | ≤ 0.4 | ok |

### Oráculo do M1

- Combates de fauna com entrada (on): 617 · precedidos (oráculo próprio): 483 · (antigo): 484.
- Divergências: só o antigo conta 1 · só o próprio conta 0.
- Textos de sinal emitidos: 1342 · sem dono no arquivo de dados: 0 · com mais de um dono: 0.
- Ações com sinal novo (M8): 1342 de 4800.
- Gatilhos off = on (R9 da 360): ok.
