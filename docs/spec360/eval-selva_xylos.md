# SPEC-360 — eval da fauna viva: Selva de Xylos

Gerado por `scripts/fauna/eval.py` (avaliador congelado na Etapa 1; não editar à mão).

- Região: `selva_xylos` · seeds: 20 · dias por seed: 60
- Perfil sintético: 3 chegadas por dia entre os nós da região + 1 descanso; perigo forçado 4, nível 3.

| Métrica | Valor | Limiar | Resultado |
|---|---|---|---|
| M1 sinal antes (precedidos) | 0.7977 | ≥ 0.7 | ok |
| M1 aproximação | 1.0000 | ≥ 1.0 | ok |
| M2 horário (pior razão fora/dentro) | 0.2308 | ≤ 0.35 | ok |
| M3 presa sobe (mínimo) | 1.7618 | ≥ 1.5 | ok |
| M3 predador cai (máximo) | 0.4798 | ≤ 0.6 | ok |
| M4 território | 0.9314 | ≥ 0.8 | ok |
| M5 combates por 100 ações (Δ on vs off) | -0.1729 | -0.2 a +0.05 | ok |
| M6 vazamento de nome | 0 | ≤ 0 | ok |

## Contagens

| Modo | Chegadas | Descansos | Gatilhos | Combates de fauna | Conversões | Sinais em cena |
|---|---|---|---|---|---|---|
| off | 3600 | 1200 | 1200 | 723 | 0 | 0 |
| on | 3600 | 1200 | 1200 | 598 | 188 | 1206 |

Combates por 100 ações: off 15.062 · on 12.458.

## Distribuição (contexto neutro, exata)

- M2 por criatura (fora/dentro): {"mon_coandu_de_rebrota": 0.1969, "mon_enxertadora_da_uniao": 0.2248, "mon_lacado_de_hifas": 0.1927, "mon_lagarta_da_hora": 0.2248, "mon_larva_hospedeira": 0.2188, "mon_macaco_esporo": 0.2221, "mon_mascador_de_nectar": 0.2308, "mon_monte_de_alheios": 0.2207, "mon_predador_crescido": 0.2188, "mon_pressa_da_seiva": 0.2106, "mon_provador_de_cores": 0.2281, "mon_rainha_cipo": 0.2075, "mon_remendado_de_osso": 0.2308, "mon_vespa_oleira": 0.2298, "mon_viuvo_do_esporo": 0.2276}
- M3 presa sobe por predador: {"enemy_vinha_estranguladora": 1.7618, "mon_predador_crescido": 1.7762, "mon_remendado_de_osso": 1.9487, "mon_tamandua_de_ponte": 1.8684, "mon_vipera_flora": 1.8235}
- M3 predador cai: {"enemy_vinha_estranguladora": 0.4798, "mon_predador_crescido": 0.4796, "mon_remendado_de_osso": 0.4757, "mon_tamandua_de_ponte": 0.4762, "mon_vipera_flora": 0.4635}
- M4 contextos com candidata territorial: 15

## SPEC-370 — por região, oráculo próprio do M1, M7 e M8

- Nós raiz na região: 3. N/A declarados no avaliador (R16).

| Métrica | Valor | Limiar | Resultado |
|---|---|---|---|
| M1 precedidos (oráculo próprio, R18) | 0.7910 | ≥ 0.7 | ok |
| M1 precedidos (oráculo antigo, `sinais_mostrados`) | 0.7977 | informativo | — |
| M1 aproximação | 1.0000 | ≥ 1.0 | ok |
| M2 horário | 0.2308 | ≤ 0.35 | ok |
| M3 cadeia alimentar | sobe 1.7618 · cai 0.4798 | ≥ 1.5 / ≤ 0.6 | ok |
| M4 território | 0.9314 | ≥ 0.8 | ok |
| M5 por região (informativo, D5) | -0.1729 | alerta fora de -0.3 a +0.1 | ok |
| M6 vazamento de nome | 0 | ≤ 0 | ok |
| M7 determinismo (20 × 60) | `702e5bbb4a51d74b` × `702e5bbb4a51d74b` | hashes iguais | ok |
| M8 densidade de sinal novo | 0.3071 | ≤ 0.4 | ok |

### Oráculo do M1

- Combates de fauna com entrada (on): 598 · precedidos (oráculo próprio): 473 · (antigo): 477.
- Divergências: só o antigo conta 4 · só o próprio conta 0.
- Textos de sinal emitidos: 1474 · sem dono no arquivo de dados: 0 · com mais de um dono: 0.
- Ações com sinal novo (M8): 1474 de 4800.
- Gatilhos off = on (R9 da 360): ok.
