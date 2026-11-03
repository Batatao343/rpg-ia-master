# SPEC-360 — eval da fauna viva: Nova Arcádia

Gerado por `scripts/fauna/eval.py` (avaliador congelado na Etapa 1; não editar à mão).

- Região: `nova_arcadia` · seeds: 20 · dias por seed: 60
- Perfil sintético: 3 chegadas por dia entre os nós da região + 1 descanso; perigo forçado 4, nível 3.

| Métrica | Valor | Limiar | Resultado |
|---|---|---|---|
| M1 sinal antes (precedidos) | 0.7433 | ≥ 0.7 | ok |
| M1 aproximação | 1.0000 | ≥ 1.0 | ok |
| M2 horário (pior razão fora/dentro) | 0.2891 | ≤ 0.35 | ok |
| M3 presa sobe (mínimo) | 1.75 | ≥ 1.5 | ok |
| M3 predador cai (máximo) | 0.5543 | ≤ 0.6 | ok |
| M4 território | 0.875 | ≥ 0.8 | ok |
| M5 combates por 100 ações (Δ on vs off) | -0.1757 | -0.2 a +0.05 | ok |
| M6 vazamento de nome | 0 | ≤ 0 | ok |

## Contagens

| Modo | Chegadas | Descansos | Gatilhos | Combates de fauna | Conversões | Sinais em cena |
|---|---|---|---|---|---|---|
| off | 3600 | 1200 | 1200 | 723 | 0 | 0 |
| on | 3600 | 1200 | 1200 | 596 | 218 | 1189 |

Combates por 100 ações: off 15.062 · on 12.417.

## Distribuição (contexto neutro, exata)

- M2 por criatura (fora/dentro): {"enemy_degolador_mao_sombria": 0.2495, "enemy_elemental_fogo_poluido": 0.2356, "enemy_gargula_ferro": 0.2462, "enemy_horror_esgoto": 0.2185, "enemy_iniciado_chama_azul": 0.2511, "enemy_polvo_esgoto": 0.2815, "enemy_rato_peste_anel_lama": 0.2622, "enemy_sentinela_ferro": 0.1893, "enemy_soldado_legiao_ferro": 0.174, "mon_arame_vivo": 0.2891, "mon_cao_rebite": 0.1805, "mon_cavadeira_de_unhas": 0.2185, "mon_centopeia_da_torre_invertida": 0.172, "mon_convidado_de_cera": 0.2462, "mon_enxerto_da_fornalha": 0.1653, "mon_escritura_rastejante": 0.242, "mon_fole_de_costela": 0.2356, "mon_gralha_de_crematorio": 0.1744, "mon_lencol_de_chamine": 0.1698, "mon_pavio_da_lista": 0.242, "mon_porca_da_queda": 0.2815, "mon_quebrado_de_vitrine": 0.2113, "mon_rato_caldeira": 0.2356, "mon_rosario_de_vertebras": 0.261, "mon_sangrado_da_clinica": 0.1653, "mon_sorvedouro_do_codigo": 0.183, "mon_traca_do_sino_mudo": 0.2356, "mon_vira_costas_da_praca": 0.1809}
- M3 presa sobe por predador: {"enemy_gargula_ferro": 2.0775, "enemy_horror_esgoto": 1.75, "enemy_polvo_esgoto": 1.8159, "mon_arame_vivo": 1.8168, "mon_cao_rebite": 1.9988, "mon_centopeia_da_torre_invertida": 1.7915, "mon_enxerto_da_fornalha": 1.8795, "mon_gralha_de_crematorio": 1.9294, "mon_lencol_de_chamine": 1.9133, "mon_porca_da_queda": 1.8159, "mon_rosario_de_vertebras": 1.8167, "mon_sangrado_da_clinica": 1.8795}
- M3 predador cai: {"enemy_gargula_ferro": 0.4918, "enemy_horror_esgoto": 0.5401, "enemy_polvo_esgoto": 0.5543, "mon_arame_vivo": 0.546, "mon_cao_rebite": 0.5154, "mon_centopeia_da_torre_invertida": 0.4887, "mon_enxerto_da_fornalha": 0.4698, "mon_gralha_de_crematorio": 0.4759, "mon_lencol_de_chamine": 0.4711, "mon_porca_da_queda": 0.5543, "mon_rosario_de_vertebras": 0.5445, "mon_sangrado_da_clinica": 0.4558}
- M4 contextos com candidata territorial: 20

## SPEC-370 — por região, oráculo próprio do M1, M7 e M8

- Nós raiz na região: 4. N/A declarados no avaliador (R16).

| Métrica | Valor | Limiar | Resultado |
|---|---|---|---|
| M1 precedidos (oráculo próprio, R18) | 0.7366 | ≥ 0.7 | ok |
| M1 precedidos (oráculo antigo, `sinais_mostrados`) | 0.7433 | informativo | — |
| M1 aproximação | 1.0000 | ≥ 1.0 | ok |
| M2 horário | 0.2891 | ≤ 0.35 | ok |
| M3 cadeia alimentar | sobe 1.75 · cai 0.5543 | ≥ 1.5 / ≤ 0.6 | ok |
| M4 território | 0.875 | ≥ 0.8 | ok |
| M5 por região (informativo, D5) | -0.1757 | alerta fora de -0.3 a +0.1 | ok |
| M6 vazamento de nome | 0 | ≤ 0 | ok |
| M7 determinismo (20 × 60) | `c2ae68a744a9212d` × `c2ae68a744a9212d` | hashes iguais | ok |
| M8 densidade de sinal novo | 0.3127 | ≤ 0.4 | ok |

### Oráculo do M1

- Combates de fauna com entrada (on): 596 · precedidos (oráculo próprio): 439 · (antigo): 443.
- Divergências: só o antigo conta 4 · só o próprio conta 0.
- Textos de sinal emitidos: 1501 · sem dono no arquivo de dados: 0 · com mais de um dono: 0.
- Ações com sinal novo (M8): 1501 de 4800.
- Gatilhos off = on (R9 da 360): ok.
