# SPEC-360 — eval da fauna viva: Nova Arcádia

Gerado por `scripts/fauna/eval.py` (avaliador congelado na Etapa 1; não editar à mão).

- Região: `nova_arcadia` · seeds: 20 · dias por seed: 60
- Perfil sintético: 3 chegadas por dia entre os nós da região + 1 descanso; perigo forçado 4, nível 3.

| Métrica | Valor | Limiar | Resultado |
|---|---|---|---|
| M1 sinal antes (precedidos) | 0.7542 | ≥ 0.7 | ok |
| M1 aproximação | 1.0000 | ≥ 1.0 | ok |
| M2 horário (pior razão fora/dentro) | 0.289 | ≤ 0.35 | ok |
| M3 presa sobe (mínimo) | 1.7459 | ≥ 1.5 | ok |
| M3 predador cai (máximo) | 0.5545 | ≤ 0.6 | ok |
| M4 território | 0.8544 | ≥ 0.8 | ok |
| M5 combates por 100 ações (Δ on vs off) | -0.1687 | -0.2 a +0.05 | ok |
| M6 vazamento de nome | 0 | ≤ 0 | ok |

## Contagens

| Modo | Chegadas | Descansos | Gatilhos | Combates de fauna | Conversões | Sinais em cena |
|---|---|---|---|---|---|---|
| off | 3600 | 1200 | 1200 | 723 | 0 | 0 |
| on | 3600 | 1200 | 1200 | 601 | 223 | 1205 |

Combates por 100 ações: off 15.062 · on 12.521.

## Distribuição (contexto neutro, exata)

- M2 por criatura (fora/dentro): {"enemy_degolador_mao_sombria": 0.2492, "enemy_elemental_fogo_poluido": 0.2359, "enemy_gargula_ferro": 0.2461, "enemy_horror_esgoto": 0.2184, "enemy_iniciado_chama_azul": 0.2508, "enemy_polvo_esgoto": 0.2815, "enemy_rato_peste_anel_lama": 0.2615, "enemy_sentinela_ferro": 0.1887, "enemy_soldado_legiao_ferro": 0.1742, "mon_arame_vivo": 0.289, "mon_cao_rebite": 0.1807, "mon_cavadeira_de_unhas": 0.2184, "mon_centopeia_da_torre_invertida": 0.1717, "mon_convidado_de_cera": 0.2461, "mon_enxerto_da_fornalha": 0.165, "mon_escritura_rastejante": 0.2425, "mon_fole_de_costela": 0.2359, "mon_gralha_de_crematorio": 0.1745, "mon_lencol_de_chamine": 0.1696, "mon_pavio_da_lista": 0.2425, "mon_porca_da_queda": 0.2815, "mon_quebrado_de_vitrine": 0.212, "mon_rato_caldeira": 0.2359, "mon_rosario_de_vertebras": 0.2608, "mon_sangrado_da_clinica": 0.165, "mon_sorvedouro_do_codigo": 0.1832, "mon_traca_do_sino_mudo": 0.2359, "mon_vira_costas_da_praca": 0.1813}
- M3 presa sobe por predador: {"enemy_gargula_ferro": 2.0702, "enemy_horror_esgoto": 1.7459, "enemy_polvo_esgoto": 1.8117, "enemy_soldado_legiao_ferro": 2.0933, "mon_arame_vivo": 1.8123, "mon_cao_rebite": 1.9898, "mon_centopeia_da_torre_invertida": 1.7877, "mon_enxerto_da_fornalha": 1.8758, "mon_gralha_de_crematorio": 1.9246, "mon_lencol_de_chamine": 1.9094, "mon_porca_da_queda": 1.8117, "mon_rosario_de_vertebras": 1.8123, "mon_sangrado_da_clinica": 1.8758, "mon_sorvedouro_do_codigo": 1.921}
- M3 predador cai: {"enemy_gargula_ferro": 0.4922, "enemy_horror_esgoto": 0.54, "enemy_polvo_esgoto": 0.5545, "enemy_soldado_legiao_ferro": 0.502, "mon_arame_vivo": 0.5462, "mon_cao_rebite": 0.5159, "mon_centopeia_da_torre_invertida": 0.4888, "mon_enxerto_da_fornalha": 0.4699, "mon_gralha_de_crematorio": 0.476, "mon_lencol_de_chamine": 0.4711, "mon_porca_da_queda": 0.5545, "mon_rosario_de_vertebras": 0.5447, "mon_sangrado_da_clinica": 0.4559, "mon_sorvedouro_do_codigo": 0.4755}
- M4 contextos com candidata territorial: 20
