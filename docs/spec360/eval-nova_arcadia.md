# SPEC-360 — eval da fauna viva: Nova Arcádia

Gerado por `scripts/fauna/eval.py` (avaliador congelado na Etapa 1; não editar à mão).

- Região: `nova_arcadia` · seeds: 20 · dias por seed: 60
- Perfil sintético: 3 chegadas por dia entre os nós da região + 1 descanso; perigo forçado 4, nível 3.

| Métrica | Valor | Limiar | Resultado |
|---|---|---|---|
| M1 sinal antes (precedidos) | 0.8139 | ≥ 0.7 | ok |
| M1 aproximação | 1.0000 | ≥ 1.0 | ok |
| M2 horário (pior razão fora/dentro) | 0.2833 | ≤ 0.35 | ok |
| M3 presa sobe (mínimo) | 1.6944 | ≥ 1.5 | ok |
| M3 predador cai (máximo) | 0.5478 | ≤ 0.6 | ok |
| M4 território | 0.8167 | ≥ 0.8 | ok |
| M5 combates por 100 ações (Δ on vs off) | -0.1604 | -0.2 a +0.05 | ok |
| M6 vazamento de nome | 0 | ≤ 0 | ok |

## Contagens

| Modo | Chegadas | Descansos | Gatilhos | Combates de fauna | Conversões | Sinais em cena |
|---|---|---|---|---|---|---|
| off | 3600 | 1200 | 1200 | 723 | 0 | 0 |
| on | 3600 | 1200 | 1200 | 607 | 214 | 2367 |

Combates por 100 ações: off 15.062 · on 12.646.

## Distribuição (contexto neutro, exata)

- M2 por criatura (fora/dentro): {"enemy_degolador_mao_sombria": 0.2417, "enemy_elemental_fogo_poluido": 0.2352, "enemy_gargula_ferro": 0.2392, "enemy_horror_esgoto": 0.217, "enemy_iniciado_chama_azul": 0.2429, "enemy_polvo_esgoto": 0.2753, "enemy_rato_peste_anel_lama": 0.2543, "enemy_sentinela_ferro": 0.1893, "enemy_soldado_legiao_ferro": 0.1797, "mon_arame_vivo": 0.2833, "mon_cao_rebite": 0.1868, "mon_cavadeira_de_unhas": 0.217, "mon_centopeia_da_torre_invertida": 0.1709, "mon_convidado_de_cera": 0.2392, "mon_enxerto_da_fornalha": 0.1648, "mon_escritura_rastejante": 0.2427, "mon_fole_de_costela": 0.2352, "mon_gralha_de_crematorio": 0.1773, "mon_lencol_de_chamine": 0.1701, "mon_pavio_da_lista": 0.2427, "mon_porca_da_queda": 0.2753, "mon_quebrado_de_vitrine": 0.2113, "mon_rato_caldeira": 0.2352, "mon_rosario_de_vertebras": 0.2581, "mon_sangrado_da_clinica": 0.1648, "mon_sorvedouro_do_codigo": 0.1843, "mon_traca_do_sino_mudo": 0.2352, "mon_vira_costas_da_praca": 0.1835}
- M3 presa sobe por predador: {"enemy_gargula_ferro": 2.0639, "enemy_horror_esgoto": 1.7542, "enemy_polvo_esgoto": 1.8151, "enemy_soldado_legiao_ferro": 2.0537, "mon_arame_vivo": 1.8159, "mon_cao_rebite": 1.9799, "mon_centopeia_da_torre_invertida": 1.7918, "mon_enxerto_da_fornalha": 1.8135, "mon_gralha_de_crematorio": 1.8977, "mon_lencol_de_chamine": 1.9073, "mon_porca_da_queda": 1.8151, "mon_roda_de_mandibulas": 1.6944, "mon_rosario_de_vertebras": 1.8158, "mon_sangrado_da_clinica": 1.8757, "mon_sorvedouro_do_codigo": 1.9184}
- M3 predador cai: {"enemy_gargula_ferro": 0.4887, "enemy_horror_esgoto": 0.5318, "enemy_polvo_esgoto": 0.5478, "enemy_soldado_legiao_ferro": 0.4959, "mon_arame_vivo": 0.5397, "mon_cao_rebite": 0.5041, "mon_centopeia_da_torre_invertida": 0.4866, "mon_enxerto_da_fornalha": 0.4708, "mon_gralha_de_crematorio": 0.4649, "mon_lencol_de_chamine": 0.47, "mon_porca_da_queda": 0.5478, "mon_rosario_de_vertebras": 0.538, "mon_sangrado_da_clinica": 0.4564, "mon_sorvedouro_do_codigo": 0.4738}
- M4 contextos com candidata territorial: 20
