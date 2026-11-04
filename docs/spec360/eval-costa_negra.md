# SPEC-360 — eval da fauna viva: Costa Negra — Cemitério de Leviatãs

Gerado por `scripts/fauna/eval.py` (avaliador congelado na Etapa 1; não editar à mão).

- Região: `costa_negra` · seeds: 20 · dias por seed: 60
- Perfil sintético: 3 chegadas por dia entre os nós da região + 1 descanso; perigo forçado 4, nível 3.

| Métrica | Valor | Limiar | Resultado |
|---|---|---|---|
| M1 sinal antes (precedidos) | 0.8436 | ≥ 0.7 | ok |
| M1 aproximação | 1.0000 | ≥ 1.0 | ok |
| M2 horário (pior razão fora/dentro) | 0.273 | ≤ 0.35 | ok |
| M3 presa sobe (mínimo) | 1.7095 | ≥ 1.5 | ok |
| M3 predador cai (máximo) | 0.4749 | ≤ 0.6 | ok |
| M4 território | 0.9503 | ≥ 0.8 | ok |
| M5 combates por 100 ações (Δ on vs off) | -0.1950 | -0.2 a +0.05 | ok |
| M6 vazamento de nome | 0 | ≤ 0 | ok |

## Contagens

| Modo | Chegadas | Descansos | Gatilhos | Combates de fauna | Conversões | Sinais em cena |
|---|---|---|---|---|---|---|
| off | 3600 | 1200 | 1200 | 723 | 0 | 0 |
| on | 3600 | 1200 | 1200 | 582 | 207 | 1039 |

Combates por 100 ações: off 15.062 · on 12.125.

## Distribuição (contexto neutro, exata)

- M2 por criatura (fora/dentro): {"mon_acendedor_de_naufragios": 0.1818, "mon_andarilho_de_cracas": 0.273, "mon_baleia_ossario": 0.273, "mon_caldeireiro_de_oleo": 0.2491, "mon_carrapato_osso": 0.2095, "mon_contrabandista_vitreo": 0.193, "mon_esfolado_de_sal": 0.273, "mon_ferida_de_coral": 0.273, "mon_gaivota_ladra": 0.273, "mon_petrel_de_papo_cheio": 0.273, "mon_raspadeira_de_barbatana": 0.2491, "mon_saltador_de_poca": 0.273, "mon_saqueador_marfim": 0.2119, "mon_touro_de_banha": 0.273, "mon_ventre_partilhado": 0.2095}
- M3 presa sobe por predador: {"mon_caranguejo_mare": 1.909, "mon_estrela_de_alavanca": 1.7446, "mon_gaivota_ladra": 1.715, "mon_o_que_come_nas_praias": 1.7603, "mon_tubarao_de_casco": 1.7095}
- M3 predador cai: {"mon_caranguejo_mare": 0.471, "mon_estrela_de_alavanca": 0.4482, "mon_gaivota_ladra": 0.4749, "mon_tubarao_de_casco": 0.4631}
- M4 contextos com candidata territorial: 10

## SPEC-370 — por região, oráculo próprio do M1, M7 e M8

- Nós raiz na região: 2. N/A declarados no avaliador (R16).

| Métrica | Valor | Limiar | Resultado |
|---|---|---|---|
| M1 precedidos (oráculo próprio, R18) | 0.8162 | ≥ 0.7 | ok |
| M1 precedidos (oráculo antigo, `sinais_mostrados`) | 0.8436 | informativo | — |
| M1 aproximação | 1.0000 | ≥ 1.0 | ok |
| M2 horário | 0.273 | ≤ 0.35 | ok |
| M3 cadeia alimentar | sobe 1.7095 · cai 0.4749 | ≥ 1.5 / ≤ 0.6 | ok |
| M4 território | 0.9503 | ≥ 0.8 | ok |
| M5 por região (informativo, D5) | -0.1950 | alerta fora de -0.3 a +0.1 | ok |
| M6 vazamento de nome | 0 | ≤ 0 | ok |
| M7 determinismo (20 × 60) | `6336a6c050d9f496` × `6336a6c050d9f496` | hashes iguais | ok |
| M8 densidade de sinal novo | 0.2796 | ≤ 0.4 | ok |

### Oráculo do M1

- Combates de fauna com entrada (on): 582 · precedidos (oráculo próprio): 475 · (antigo): 491.
- Divergências: só o antigo conta 16 · só o próprio conta 0.
- Textos de sinal emitidos: 1342 · sem dono no arquivo de dados: 0 · com mais de um dono: 0.
- Ações com sinal novo (M8): 1342 de 4800.
- Gatilhos off = on (R9 da 360): ok.
