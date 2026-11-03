# Arena SPEC-371 - a luta ensina (nova_arcadia)

26 criaturas x 5 Posturas x 20 seeds = 2600 pares; nivel 3; MockLLM; bot `leitor`; flags `RPG_ENEMY_DECKS`, `RPG_ENEMY_INTENT`, `RPG_FAUNA_SABER` = on. Gerado por `scripts/fauna/arena_saber.py` (avaliador congelado).

| Metrica | Resultado | Limiar | OK |
|---|---|---|---|
| E1 fracao revelada | 34.4% (895/2600) | >= 30% | OK |
| E2 ganho de vitoria (revelados) | +10.06 pp | >= +3 pp | OK |
| E3 Vitalidade perdida 2/1 (438 pares) | 0.842x | <= 0.92x | OK |
| E4 vitoria luta 2 / pior criatura | 67.5% / -3.0 pp | <= 92% e >= -2 pp | FALHA |

| Criatura | delta vitoria luta 2 - luta 1 (pp) |
|---|---|
| `enemy_elemental_fogo_poluido` | -3.0 |
| `enemy_gargula_ferro` | +14.0 |
| `enemy_golem_lixo` | -2.0 |
| `enemy_horror_esgoto` | +4.0 |
| `enemy_polvo_esgoto` | +0.0 |
| `enemy_sentinela_ferro` | +3.0 |
| `mon_arame_vivo` | +11.0 |
| `mon_cavadeira_de_unhas` | +2.0 |
| `mon_centopeia_da_torre_invertida` | +2.0 |
| `mon_convidado_de_cera` | +11.0 |
| `mon_enxerto_da_fornalha` | +1.0 |
| `mon_escritura_rastejante` | +2.0 |
| `mon_fila_de_grilhoes` | +1.0 |
| `mon_fole_de_costela` | -2.0 |
| `mon_gralha_de_crematorio` | +12.0 |
| `mon_lencol_de_chamine` | -3.0 |
| `mon_pavio_da_lista` | +6.0 |
| `mon_porca_da_queda` | -1.0 |
| `mon_portao_que_morde` | +4.0 |
| `mon_quebrado_de_vitrine` | +0.0 |
| `mon_relicario_de_osso` | +2.0 |
| `mon_rosario_de_vertebras` | +6.0 |
| `mon_sangrado_da_clinica` | +5.0 |
| `mon_sorvedouro_do_codigo` | +1.0 |
| `mon_traca_do_sino_mudo` | +4.0 |
| `mon_vira_costas_da_praca` | +10.0 |
