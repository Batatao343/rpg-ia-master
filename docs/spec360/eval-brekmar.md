# SPEC-360 — eval da fauna viva: Brekmar

Gerado por `scripts/fauna/eval.py` (avaliador congelado na Etapa 1; não editar à mão).

- Região: `brekmar` · seeds: 20 · dias por seed: 60
- Perfil sintético: 3 chegadas por dia entre os nós da região + 1 descanso; perigo forçado 4, nível 3.

| Métrica | Valor | Limiar | Resultado |
|---|---|---|---|
| M1 sinal antes (precedidos) | 0.8066 | ≥ 0.7 | ok |
| M1 aproximação | 1.0000 | ≥ 1.0 | ok |
| M2 horário (pior razão fora/dentro) | 0.3215 | ≤ 0.35 | ok |
| M3 presa sobe (mínimo) | 1.7015 | ≥ 1.5 | ok |
| M3 predador cai (máximo) | 0.5056 | ≤ 0.6 | ok |
| M4 território | 0.9556 | ≥ 0.8 | ok |
| M5 combates por 100 ações (Δ on vs off) | -0.1563 | -0.2 a +0.05 | ok |
| M6 vazamento de nome | 0 | ≤ 0 | ok |

## Contagens

| Modo | Chegadas | Descansos | Gatilhos | Combates de fauna | Conversões | Sinais em cena |
|---|---|---|---|---|---|---|
| off | 3600 | 1200 | 1200 | 723 | 0 | 0 |
| on | 3600 | 1200 | 1200 | 610 | 193 | 1043 |

Combates por 100 ações: off 15.062 · on 12.708.

## Distribuição (contexto neutro, exata)

- M2 por criatura (fora/dentro): {"enemy_arpoador_osshari": 0.1536, "enemy_pirata_brekmar": 0.3215, "mon_anzolado_da_casa": 0.2798, "mon_broca_de_costado": 0.27, "mon_capangas_do_poco": 0.2557, "mon_capita_corda": 0.27, "mon_cardume_coagulado": 0.2818, "mon_carranca_de_proa": 0.3021, "mon_cobrador_gancho": 0.2798, "mon_estivador_das_facas": 0.2798, "mon_mao_estendida": 0.3215, "mon_odre_de_oleo": 0.3215, "mon_penhorado_do_poco": 0.2131, "mon_pescador_de_lanterna": 0.2757, "mon_quilhado_do_estaleiro": 0.1834, "mon_rato_cais_brekmar": 0.2807, "mon_sangria_de_aluguel": 0.2557, "mon_sino_de_enlace": 0.3143, "mon_tambor_do_ossario": 0.2818, "mon_torcido_da_rinha": 0.2798}
- M3 presa sobe por predador: {"enemy_arpoador_osshari": 1.9158, "mon_boia_de_bracos": 1.8753, "mon_cardume_coagulado": 1.8928, "mon_casco_de_costelas": 1.7015, "mon_gato_de_lastro": 1.8771, "mon_pescador_de_lanterna": 1.8131, "mon_sino_de_enlace": 1.8123}
- M3 predador cai: {"enemy_arpoador_osshari": 0.4433, "mon_boia_de_bracos": 0.5056, "mon_cardume_coagulado": 0.473, "mon_gato_de_lastro": 0.4924, "mon_pescador_de_lanterna": 0.4451, "mon_sino_de_enlace": 0.4687}
- M4 contextos com candidata territorial: 10

## SPEC-370 — por região, oráculo próprio do M1, M7 e M8

- Nós raiz na região: 2. N/A declarados no avaliador (R16).

| Métrica | Valor | Limiar | Resultado |
|---|---|---|---|
| M1 precedidos (oráculo próprio, R18) | 0.8033 | ≥ 0.7 | ok |
| M1 precedidos (oráculo antigo, `sinais_mostrados`) | 0.8066 | informativo | — |
| M1 aproximação | 1.0000 | ≥ 1.0 | ok |
| M2 horário | 0.3215 | ≤ 0.35 | ok |
| M3 cadeia alimentar | sobe 1.7015 · cai 0.5056 | ≥ 1.5 / ≤ 0.6 | ok |
| M4 território | 0.9556 | ≥ 0.8 | ok |
| M5 por região (informativo, D5) | -0.1563 | alerta fora de -0.3 a +0.1 | ok |
| M6 vazamento de nome | 0 | ≤ 0 | ok |
| M7 determinismo (20 × 60) | `e16122ffb940d9ed` × `e16122ffb940d9ed` | hashes iguais | ok |
| M8 densidade de sinal novo | 0.2779 | ≤ 0.4 | ok |

### Oráculo do M1

- Combates de fauna com entrada (on): 610 · precedidos (oráculo próprio): 490 · (antigo): 492.
- Divergências: só o antigo conta 2 · só o próprio conta 0.
- Textos de sinal emitidos: 1334 · sem dono no arquivo de dados: 0 · com mais de um dono: 0.
- Ações com sinal novo (M8): 1334 de 4800.
- Gatilhos off = on (R9 da 360): ok.
