# Arena SPEC-371 - a luta ensina (nova_arcadia)

26 criaturas x 5 Posturas x 20 seeds = 2600 pares; nivel 3; MockLLM; bot `leitor`; flags `RPG_ENEMY_DECKS`, `RPG_ENEMY_INTENT`, `RPG_FAUNA_SABER` = on. Gerado por `scripts/fauna/arena_saber.py` (avaliador congelado).

| Metrica | Resultado | Limiar | OK |
|---|---|---|---|
| E1 fracao revelada | 34.4% (895/2600) | >= 30% | OK |
| E2 ganho de vitoria (revelados) | -25.59 pp | >= +3 pp | FALHA |
| E3 Vitalidade perdida 2/1 (213 pares) | 0.999x | <= 0.92x | FALHA |
| E4 vitoria luta 2 / pior criatura | 55.2% / -47.0 pp | <= 92% e >= -2 pp | FALHA |

| Criatura | delta vitoria luta 2 - luta 1 (pp) |
|---|---|
| `enemy_elemental_fogo_poluido` | -7.0 |
| `enemy_gargula_ferro` | -10.0 |
| `enemy_golem_lixo` | -6.0 |
| `enemy_horror_esgoto` | -2.0 |
| `enemy_polvo_esgoto` | -1.0 |
| `enemy_sentinela_ferro` | -6.0 |
| `mon_arame_vivo` | -27.0 |
| `mon_cavadeira_de_unhas` | -9.0 |
| `mon_centopeia_da_torre_invertida` | -5.0 |
| `mon_convidado_de_cera` | -2.0 |
| `mon_enxerto_da_fornalha` | -2.0 |
| `mon_escritura_rastejante` | -5.0 |
| `mon_fila_de_grilhoes` | +1.0 |
| `mon_fole_de_costela` | -12.0 |
| `mon_gralha_de_crematorio` | -47.0 |
| `mon_lencol_de_chamine` | -13.0 |
| `mon_pavio_da_lista` | -1.0 |
| `mon_porca_da_queda` | -3.0 |
| `mon_portao_que_morde` | -7.0 |
| `mon_quebrado_de_vitrine` | -5.0 |
| `mon_relicario_de_osso` | +0.0 |
| `mon_rosario_de_vertebras` | -23.0 |
| `mon_sangrado_da_clinica` | -7.0 |
| `mon_sorvedouro_do_codigo` | -18.0 |
| `mon_traca_do_sino_mudo` | -9.0 |
| `mon_vira_costas_da_praca` | -3.0 |
