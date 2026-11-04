# SPEC-372 — eval das criaturas de trama: Nova Arcádia

Gerado por `scripts/fauna/eval_tramas.py` (avaliador congelado na Etapa 1; não editar à mão).

- Região: `nova_arcadia` · seeds: 20 · dias por seed: 30
- Criaturas ligadas: 8 · tramas com criatura: 5
- Modos: `off` (flag desligada), `dormente` (flag ligada, nenhum sinal de trama), `maximo` (flag ligada, todo sinal de trama; estágio literal por trama abaixo).

| Teste | Valor | Limiar | Resultado |
|---|---|---|---|
| T1 portão: maior fatia antes do estágio | 0.0 | ≤ 0.0 | ok |
| T1 presenças de ligada (dormente) | 0 | ≤ 0 | ok |
| T1 escolhas no `track` (dormente) | 0 | ≤ 0 | ok |
| T2 puxão: menor razão on/off nos locais | 1.6293 | ≥ 1.5 | ok |
| T2 ligadas inalcançáveis | 0 | = 0 | ok |
| T3 presenças nos locais da trama (n=15) | 1.0 | ≥ 1.0 | ok |
| T3 `trama_id` com a flag off | 0 | = 0 | ok |
| T4 gatilhos off/dormente/maximo | {'off': 600, 'dormente': 600, 'maximo': 600} | iguais | ok |
| T4 Δ combates (dormente) | 0.0 | -0.1 a +0.05 | ok |
| T4 Δ combates (maximo) | -0.0101 | -0.1 a +0.05 | ok |
| T5 vazamento (segredo/núcleo) | 0 | ≤ 0 | ok |
| T8 estágio literal (16 casos) | 0 errados, 0 mutados | 0 | ok |
| T7 relatório da 360 com a flag off | True | idêntico | ok |

## Estágio do modo `maximo` (literal)

`{"tr_na_a_colecao": "investigada", "tr_na_aco_que_lembra": "revelada", "tr_na_corpos_marcados": "revelada", "tr_na_documento_da_legiao": "revelada", "tr_na_lista_de_fornalha": "investigada", "tr_na_o_que_o_lorde_trocou": "revelada", "tr_na_po_de_sonho": "revelada"}`

## Ligações

`{"mon_enxerto_da_fornalha": [{"desde": "investigada", "id": "tr_na_aco_que_lembra"}], "mon_escritura_rastejante": [{"desde": "investigada", "id": "tr_na_a_colecao"}], "mon_pavio_da_lista": [{"desde": "investigada", "id": "tr_na_lista_de_fornalha"}], "mon_porca_da_queda": [{"desde": "tocada", "id": "tr_na_po_de_sonho"}], "mon_quebrado_de_vitrine": [{"desde": "tocada", "id": "tr_na_a_colecao"}, {"desde": "tocada", "id": "tr_na_po_de_sonho"}], "mon_rosario_de_vertebras": [{"desde": "tocada", "id": "tr_na_corpos_marcados"}], "mon_sangrado_da_clinica": [{"desde": "investigada", "id": "tr_na_corpos_marcados"}], "mon_sorvedouro_do_codigo": [{"desde": "tocada", "id": "tr_na_lista_de_fornalha"}]}`

## Contagens

| Modo | Ações | Gatilhos | Combates de fauna | Conversões | Presenças | Presenças de ligada | Combates/100 |
|---|---|---|---|---|---|---|---|
| off | 2400 | 600 | 298 | 117 | 408 | 28 | 12.417 |
| dormente | 2400 | 600 | 298 | 115 | 405 | 0 | 12.417 |
| maximo | 2400 | 600 | 295 | 117 | 409 | 38 | 12.292 |

## Distribuição (contexto neutro, exata)

- T1 por criatura: {"mon_enxerto_da_fornalha": {"max_share": 0.0}, "mon_escritura_rastejante": {"max_share": 0.0}, "mon_pavio_da_lista": {"max_share": 0.0}, "mon_porca_da_queda": {"max_share": 0.0}, "mon_quebrado_de_vitrine": {"max_share": 0.0}, "mon_rosario_de_vertebras": {"max_share": 0.0}, "mon_sangrado_da_clinica": {"max_share": 0.0}, "mon_sorvedouro_do_codigo": {"max_share": 0.0}}
- T2 por criatura: {"mon_enxerto_da_fornalha": {"ratio": 1.6728, "share_off": 0.029259, "share_on": 0.048945, "threads": ["tr_na_aco_que_lembra"]}, "mon_escritura_rastejante": {"ratio": 1.6413, "share_off": 0.019376, "share_on": 0.031802, "threads": ["tr_na_a_colecao"]}, "mon_pavio_da_lista": {"ratio": 1.6341, "share_off": 0.018703, "share_on": 0.030563, "threads": ["tr_na_lista_de_fornalha"]}, "mon_porca_da_queda": {"ratio": 1.6785, "share_off": 0.018152, "share_on": 0.030467, "threads": ["tr_na_po_de_sonho"]}, "mon_quebrado_de_vitrine": {"ratio": 1.7164, "share_off": 0.03988, "share_on": 0.06845, "threads": ["tr_na_a_colecao", "tr_na_po_de_sonho"]}, "mon_rosario_de_vertebras": {"ratio": 1.6968, "share_off": 0.025904, "share_on": 0.043955, "threads": ["tr_na_corpos_marcados"]}, "mon_sangrado_da_clinica": {"ratio": 1.6293, "share_off": 0.026969, "share_on": 0.043942, "threads": ["tr_na_corpos_marcados"]}, "mon_sorvedouro_do_codigo": {"ratio": 1.6473, "share_off": 0.061573, "share_on": 0.101432, "threads": ["tr_na_lista_de_fornalha"]}}
- Inalcançáveis: []
