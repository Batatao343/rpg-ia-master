# SPEC-360 — eval da fauna viva: Pradaria das Ruínas

Gerado por `scripts/fauna/eval.py` (avaliador congelado na Etapa 1; não editar à mão).

- Região: `pradaria_ruinas` · seeds: 20 · dias por seed: 60
- Perfil sintético: 3 chegadas por dia entre os nós da região + 1 descanso; perigo forçado 4, nível 3.

| Métrica | Valor | Limiar | Resultado |
|---|---|---|---|
| M1 sinal antes (precedidos) | 0.7576 | ≥ 0.7 | ok |
| M1 aproximação | 1.0000 | ≥ 1.0 | ok |
| M2 horário (pior razão fora/dentro) | 0.2832 | ≤ 0.35 | ok |
| M3 presa sobe (mínimo) | 1.7353 | ≥ 1.5 | ok |
| M3 predador cai (máximo) | 0.4846 | ≤ 0.6 | ok |
| M4 território | 0.8922 | ≥ 0.8 | ok |
| M5 combates por 100 ações (Δ on vs off) | -0.1840 | -0.2 a +0.05 | ok |
| M6 vazamento de nome | 0 | ≤ 0 | ok |

## Contagens

| Modo | Chegadas | Descansos | Gatilhos | Combates de fauna | Conversões | Sinais em cena |
|---|---|---|---|---|---|---|
| off | 3600 | 1200 | 1200 | 723 | 0 | 0 |
| on | 3600 | 1200 | 1200 | 590 | 216 | 1242 |

Combates por 100 ações: off 15.062 · on 12.292.

## Distribuição (contexto neutro, exata)

- M2 por criatura (fora/dentro): {"enemy_assassino_cinzeu": 0.2522, "enemy_bandido_capitao": 0.2829, "enemy_capturador_groth": 0.2829, "enemy_espectro_lamento": 0.2035, "enemy_necromante_renegado": 0.2157, "enemy_nomade_canibal": 0.2291, "mon_arqueiro_de_tendao": 0.2435, "mon_auroque_ruinas": 0.2167, "mon_besouro_de_alavanca": 0.2615, "mon_cabeca_acima": 0.2192, "mon_carregador_de_ganchos": 0.2832, "mon_cauda_emendada": 0.2829, "mon_cobra_de_legua": 0.2832, "mon_espectro_elfico": 0.2076, "mon_fucador_da_semente": 0.1807, "mon_gafanhoto_runa": 0.2227, "mon_lagarto_de_mudas": 0.2213, "mon_leitor_de_cativos": 0.2078, "mon_lobo_da_pradaria": 0.1999, "mon_pernalta_das_colunas": 0.1966, "mon_profanador_cravejado": 0.2076, "mon_retalho_das_duas_cidades": 0.2494, "mon_rodante_de_espinhos": 0.159, "mon_vestido_de_gafanhotos": 0.2832, "mon_vidrado_do_morro": 0.2516}
- M3 presa sobe por predador: {"mon_cobra_de_legua": 1.8553, "mon_fucador_da_semente": 1.9214, "mon_lagarto_de_mudas": 1.8668, "mon_lobo_da_pradaria": 1.9319, "mon_pernalta_das_colunas": 1.7353, "mon_rodante_de_espinhos": 1.9203}
- M3 predador cai: {"mon_cobra_de_legua": 0.4492, "mon_fucador_da_semente": 0.4627, "mon_lagarto_de_mudas": 0.4697, "mon_lobo_da_pradaria": 0.4846, "mon_pernalta_das_colunas": 0.4596, "mon_rodante_de_espinhos": 0.4721}
- M4 contextos com candidata territorial: 20

## SPEC-370 — por região, oráculo próprio do M1, M7 e M8

- Nós raiz na região: 4. N/A declarados no avaliador (R16).

| Métrica | Valor | Limiar | Resultado |
|---|---|---|---|
| M1 precedidos (oráculo próprio, R18) | 0.7492 | ≥ 0.7 | ok |
| M1 precedidos (oráculo antigo, `sinais_mostrados`) | 0.7576 | informativo | — |
| M1 aproximação | 1.0000 | ≥ 1.0 | ok |
| M2 horário | 0.2832 | ≤ 0.35 | ok |
| M3 cadeia alimentar | sobe 1.7353 · cai 0.4846 | ≥ 1.5 / ≤ 0.6 | ok |
| M4 território | 0.8922 | ≥ 0.8 | ok |
| M5 por região (informativo, D5) | -0.1840 | alerta fora de -0.3 a +0.1 | ok |
| M6 vazamento de nome | 0 | ≤ 0 | ok |
| M7 determinismo (20 × 60) | `fc7ff3ef09ea6301` × `fc7ff3ef09ea6301` | hashes iguais | ok |
| M8 densidade de sinal novo | 0.3194 | ≤ 0.4 | ok |

### Oráculo do M1

- Combates de fauna com entrada (on): 590 · precedidos (oráculo próprio): 442 · (antigo): 447.
- Divergências: só o antigo conta 5 · só o próprio conta 0.
- Textos de sinal emitidos: 1533 · sem dono no arquivo de dados: 0 · com mais de um dono: 0.
- Ações com sinal novo (M8): 1533 de 4800.
- Gatilhos off = on (R9 da 360): ok.
