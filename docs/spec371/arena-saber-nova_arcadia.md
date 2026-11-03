# Arena SPEC-371 - a luta ensina (nova_arcadia)

26 criaturas x 5 Posturas x 20 seeds = 2600 pares; nivel 3; MockLLM; bot `leitor`; flags `RPG_ENEMY_DECKS`, `RPG_ENEMY_INTENT`, `RPG_FAUNA_SABER` = on. Gerado por `scripts/fauna/arena_saber.py` (avaliador congelado).

| Metrica | Resultado | Limiar | OK |
|---|---|---|---|
| E1 fracao revelada | 34.4% (895/2600) | >= 30% | OK |
| E2 ganho de vitoria (revelados) | -12.85 pp | >= +3 pp | FALHA |
| E3 Vitalidade perdida 2/1 (321 pares) | 0.928x | <= 0.92x | FALHA |
| E4 vitoria luta 2 / pior criatura | 59.6% / -31.0 pp | <= 92% e >= -2 pp | FALHA |

| Criatura | delta vitoria luta 2 - luta 1 (pp) |
|---|---|
| `enemy_elemental_fogo_poluido` | -6.0 |
| `enemy_gargula_ferro` | -1.0 |
| `enemy_golem_lixo` | -7.0 |
| `enemy_horror_esgoto` | +1.0 |
| `enemy_polvo_esgoto` | -1.0 |
| `enemy_sentinela_ferro` | -6.0 |
| `mon_arame_vivo` | -15.0 |
| `mon_cavadeira_de_unhas` | -4.0 |
| `mon_centopeia_da_torre_invertida` | -4.0 |
| `mon_convidado_de_cera` | +1.0 |
| `mon_enxerto_da_fornalha` | -2.0 |
| `mon_escritura_rastejante` | -1.0 |
| `mon_fila_de_grilhoes` | +1.0 |
| `mon_fole_de_costela` | -9.0 |
| `mon_gralha_de_crematorio` | -31.0 |
| `mon_lencol_de_chamine` | -8.0 |
| `mon_pavio_da_lista` | +3.0 |
| `mon_porca_da_queda` | -3.0 |
| `mon_portao_que_morde` | -2.0 |
| `mon_quebrado_de_vitrine` | -1.0 |
| `mon_relicario_de_osso` | +0.0 |
| `mon_rosario_de_vertebras` | -14.0 |
| `mon_sangrado_da_clinica` | -6.0 |
| `mon_sorvedouro_do_codigo` | -4.0 |
| `mon_traca_do_sino_mudo` | -2.0 |
| `mon_vira_costas_da_praca` | +6.0 |
