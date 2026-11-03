# SPEC-360 — eval da fauna viva: Pântano da Melancolia

Gerado por `scripts/fauna/eval.py` (avaliador congelado na Etapa 1; não editar à mão).

- Região: `pantano_melancolia` · seeds: 20 · dias por seed: 60
- Perfil sintético: 3 chegadas por dia entre os nós da região + 1 descanso; perigo forçado 4, nível 3.

| Métrica | Valor | Limiar | Resultado |
|---|---|---|---|
| M1 sinal antes (precedidos) | 0.8620 | ≥ 0.7 | ok |
| M1 aproximação | 1.0000 | ≥ 1.0 | ok |
| M2 horário (pior razão fora/dentro) | 0.2691 | ≤ 0.35 | ok |
| M3 presa sobe (mínimo) | 1.7391 | ≥ 1.5 | ok |
| M3 predador cai (máximo) | 0.4732 | ≤ 0.6 | ok |
| M4 território | 0.9581 | ≥ 0.8 | ok |
| M5 combates por 100 ações (Δ on vs off) | -0.1784 | -0.2 a +0.05 | ok |
| M6 vazamento de nome | 0 | ≤ 0 | ok |

## Contagens

| Modo | Chegadas | Descansos | Gatilhos | Combates de fauna | Conversões | Sinais em cena |
|---|---|---|---|---|---|---|
| off | 3600 | 1200 | 1200 | 723 | 0 | 0 |
| on | 3600 | 1200 | 1200 | 594 | 212 | 1066 |

Combates por 100 ações: off 15.062 · on 12.375.

## Distribuição (contexto neutro, exata)

- M2 por criatura (fora/dentro): {"enemy_druida_renegado": 0.2294, "enemy_zumbi_blindado": 0.2691, "mon_casaco_de_sanguessugas": 0.2653, "mon_castor_de_estacas": 0.2691, "mon_cervo_afogado": 0.1951, "mon_cisne_de_patina": 0.2432, "mon_cordao_de_medida": 0.2691, "mon_fardo_de_espolio": 0.2653, "mon_fundeiro_da_poca": 0.2432, "mon_jardineiro_de_tumores": 0.2083, "mon_maos_no_rosto": 0.2691, "mon_mosquito_eter": 0.2524, "mon_mula_de_lagrimas": 0.2255, "mon_patinador_de_oleo": 0.2083, "mon_podador_do_ciclo": 0.1472, "mon_regaco_da_margem": 0.2565, "mon_romeiro_de_ambar": 0.1774, "mon_sapo_boi_acido": 0.2565, "mon_tritao_de_sobra": 0.1951, "mon_viuva_lodo": 0.2691}
- M3 presa sobe por predador: {"mon_cagado_de_geada": 1.8146, "mon_cisne_de_patina": 1.8135, "mon_fundeiro_da_poca": 1.8135, "mon_musaranho_de_dente_vermelho": 1.7443, "mon_patinador_de_oleo": 1.8964, "mon_regaco_da_margem": 1.873, "mon_sanguessuga_braco": 1.9503, "mon_sapo_boi_acido": 1.7391, "mon_tritao_de_sobra": 1.8148, "mon_viuva_lodo": 1.7442}
- M3 predador cai: {"mon_cagado_de_geada": 0.4717, "mon_cisne_de_patina": 0.4708, "mon_fundeiro_da_poca": 0.4499, "mon_musaranho_de_dente_vermelho": 0.4721, "mon_patinador_de_oleo": 0.4717, "mon_regaco_da_margem": 0.4692, "mon_sanguessuga_braco": 0.4714, "mon_sapo_boi_acido": 0.4723, "mon_tritao_de_sobra": 0.4732, "mon_viuva_lodo": 0.4498}
- M4 contextos com candidata territorial: 10

## SPEC-370 — por região, oráculo próprio do M1, M7 e M8

- Nós raiz na região: 2. N/A declarados no avaliador (R16).

| Métrica | Valor | Limiar | Resultado |
|---|---|---|---|
| M1 precedidos (oráculo próprio, R18) | 0.8586 | ≥ 0.7 | ok |
| M1 precedidos (oráculo antigo, `sinais_mostrados`) | 0.8620 | informativo | — |
| M1 aproximação | 1.0000 | ≥ 1.0 | ok |
| M2 horário | 0.2691 | ≤ 0.35 | ok |
| M3 cadeia alimentar | sobe 1.7391 · cai 0.4732 | ≥ 1.5 / ≤ 0.6 | ok |
| M4 território | 0.9581 | ≥ 0.8 | ok |
| M5 por região (informativo, D5) | -0.1784 | alerta fora de -0.3 a +0.1 | ok |
| M6 vazamento de nome | 0 | ≤ 0 | ok |
| M7 determinismo (20 × 60) | `547991ffa323e57f` × `547991ffa323e57f` | hashes iguais | ok |
| M8 densidade de sinal novo | 0.2829 | ≤ 0.4 | ok |

### Oráculo do M1

- Combates de fauna com entrada (on): 594 · precedidos (oráculo próprio): 510 · (antigo): 512.
- Divergências: só o antigo conta 2 · só o próprio conta 0.
- Textos de sinal emitidos: 1358 · sem dono no arquivo de dados: 0 · com mais de um dono: 0.
- Ações com sinal novo (M8): 1358 de 4800.
- Gatilhos off = on (R9 da 360): ok.
