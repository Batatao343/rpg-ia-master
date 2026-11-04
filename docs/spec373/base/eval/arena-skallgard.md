# Arena SPEC-349 - skallgard

40 seeds x 5 Posturas por célula; MockLLM; herói da esteira do playtest; bot `cartas`. Faixa 45-85 %; reinventadas com |delta| <= 8 pp contra o slot antes. Gerado por `scripts/bestiario/arena.py`.

| Criatura | Cat. | Status | L3|off | L3|on | L5|off | L5|on | Delta vs slot antes | OK |
|---|---|---|---|---|---|---|---|---|
| Parado do Sopro (`mon_parado_do_sopro`) | padrao | nova | 78% | 76% | - | - | - | sim |
| Levantado de Rubi (`mon_levantado_de_rubi`) | padrao | nova | 64% | 70% | - | - | - | sim |
| Queimado de Breu (`mon_queimado_de_breu`) | padrao | nova | 62% | 76% | - | - | - | sim |
| Parelha Carmesim (`mon_parelha_carmesim`) | elite | nova | 56% | 60% | - | - | - | sim |
| Desfiado da Aurora (`mon_desfiado_da_aurora`) | lacaio | nova | 80% | 76% | - | - | - | sim |
| Ermitão de Elmo (`mon_ermitao_de_elmo`) | lacaio | nova | 66% | 82% | - | - | - | sim |
| Carrapato de Mamute (`mon_carrapato_de_mamute`) | lacaio | nova | 70% | 72% | - | - | - | sim |
| Lagarta de Sete Invernos (`mon_lagarta_sete_invernos`) | padrao | nova | 72% | 81% | - | - | - | sim |
| Mandrião de Dois Bicos (`mon_mandriao_dois_bicos`) | lacaio | nova | 66% | 61% | - | - | - | sim |
| Montaria Cravada (`mon_montaria_cravada`) | elite | nova | 57% | 82% | - | - | - | sim |
| Ferreiro de Chama Fria (`mon_ferreiro_chama_fria`) | padrao | nova | 76% | 79% | - | - | - | sim |
| Lascador Morno (`mon_lascador_morno`) | padrao | nova | 80% | 82% | - | - | - | sim |
| Escuta do Sinal (`mon_escuta_do_sinal`) | lacaio | nova | 46% | 90% | - | - | - | NAO: L3|on 90% fora de 45-85% |
| Caldeira de Peito (`mon_caldeira_de_peito`) | elite | nova | 53% | 56% | - | - | - | sim |
| Andas de Caribu (`mon_andas_de_caribu`) | padrao | nova | 69% | 80% | - | - | - | sim |
| Tição do Juramento (`mon_ticao_do_juramento`) | lacaio | nova | 42% | 77% | - | - | - | NAO: L3|off 42% fora de 45-85% |
| Colecionador de Poses (`mon_colecionador_de_poses`) | chefe | nova | - | - | 64% | 47% | - | sim |
| Feltro do Ventre (`mon_feltro_do_ventre`) | padrao | nova | 72% | 76% | - | - | - | sim |
| Aperto da Trégua (`mon_aperto_da_tregua`) | padrao | nova | 78% | 74% | - | - | - | sim |
| Enegrecido que Espera (`mon_enegrecido_que_espera`) | padrao | nova | 46% | 70% | - | - | - | sim |
| Pulga de Forquilha (`enemy_lobo_invernal`) | lacaio | reinventada | 46% | 44% | - | - | L3|off: -2.5; L3|on: -13.0 | NAO: L3|on 44% fora de 45-85%; L3|on delta 13.0 pp > 8 |
| Corcova Fervente (`enemy_yeti`) | elite | reinventada | 67% | 50% | - | - | L3|off: +33.0; L3|on: +13.5 | sim |
| Crescido do Clã (`mon_jotun_cinza`) | elite | reinventada | 78% | 67% | - | - | L3|off: +0.5; L3|on: -10.0 | NAO: L3|on delta 10.0 pp > 8 |
