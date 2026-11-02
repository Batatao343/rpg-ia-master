# Arena SPEC-349 - montanhas_afiadas

40 seeds x 5 Posturas por célula; MockLLM; herói da esteira do playtest; bot `cartas`. Faixa 45-85 %; reinventadas com |delta| <= 8 pp contra o slot antes. Gerado por `scripts/bestiario/arena.py`.

| Criatura | Cat. | Status | L3|off | L3|on | L5|off | L5|on | Delta vs slot antes | OK |
|---|---|---|---|---|---|---|---|---|
| Deitado na Parede (`mon_deitado_na_parede`) | padrao | nova | 82% | 74% | - | - | - | sim |
| Geodo da Praga (`mon_geodo_da_praga`) | lacaio | nova | 79% | 63% | - | - | - | sim |
| Cauda de Atalaia (`mon_cauda_de_atalaia`) | padrao | nova | 72% | 75% | - | - | - | sim |
| Queimado de Frio (`mon_queimado_de_frio`) | padrao | nova | 57% | 75% | - | - | - | sim |
| Olhos em Volta (`enemy_observador_menor`) | lacaio | reinventada | 68% | 60% | - | - | L3|off: -3.5; L3|on: -3.5 | sim |
| Leque de Costelas (`enemy_wyvern_jovem`) | elite | reinventada | 56% | 72% | - | - | L3|off: +25.0; L3|on: +40.0 | sim |
| Boi de Canga (`enemy_minotauro_esqueleto`) | elite | reinventada | 82% | 18% | - | - | L3|off: +62.0; L3|on: +0.5 | NAO: L3|on 18% fora de 45-85% |
| Morador do Caldeirão (`enemy_mimico_bau`) | elite | reinventada | 57% | 89% | - | - | L3|off: -19.0; L3|on: +19.0 | NAO: L3|off delta 19.0 pp > 8; L3|on 89% fora de 45-85%; L3|on delta 19.0 pp > 8 |
| Caramujo de Estalagmite (`enemy_basilisco_caverna`) | elite | reinventada | 50% | 66% | - | - | L3|off: -12.0; L3|on: +15.0 | NAO: L3|off delta 12.0 pp > 8; L3|on delta 15.0 pp > 8 |
| Lenço do Desfiladeiro (`enemy_morcego_vampiro`) | lacaio | reinventada | 82% | 72% | - | - | L3|off: +4.5; L3|on: +9.0 | NAO: L3|on delta 9.0 pp > 8 |
| Bexiga de Respiro (`mon_bexiga_de_respiro`) | lacaio | nova | 84% | 76% | - | - | - | sim |
| Saltão de Galeria (`mon_saltao_de_galeria`) | lacaio | nova | 75% | 74% | - | - | - | sim |
| Rolador de Escarpa (`mon_rolador_de_escarpa`) | padrao | nova | 84% | 79% | - | - | - | sim |
| Chicote de Fenda (`mon_chicote_de_fenda`) | padrao | nova | 76% | 82% | - | - | - | sim |
| Ladrão de Lume (`mon_ladrao_de_lume`) | lacaio | nova | 76% | 82% | - | - | - | sim |
| Ponte de Ombros (`enemy_troll_ponte`) | elite | reinventada | 46% | 55% | - | - | L3|off: +2.0; L3|on: +17.5 | sim |
| Braços de Tenaz (`mon_bracos_de_tenaz`) | elite | nova | 62% | 74% | - | - | - | sim |
| Marco que Aponta (`mon_marco_que_aponta`) | padrao | nova | 59% | 80% | - | - | - | sim |
| Armador de Fosso (`mon_armador_de_fosso`) | lacaio | nova | 78% | 77% | - | - | - | sim |
| Vedado de Piche (`mon_vedado_de_piche`) | padrao | nova | 64% | 66% | - | - | - | sim |
| Peso dos Vencidos (`mon_peso_dos_vencidos`) | chefe | nova | - | - | 65% | 26% | - | NAO: L5|on 26% fora de 45-85% |
| Tampão da Câmara (`mon_tampao_da_camara`) | padrao | nova | 59% | 78% | - | - | - | sim |
| Tesoura de Cordada (`mon_tesoura_de_cordada`) | lacaio | nova | 83% | 80% | - | - | - | sim |
| Mastro de Troféus (`mon_mastro_de_trofeus`) | elite | nova | 52% | 64% | - | - | - | sim |
| Mão da Borda (`mon_mao_da_borda`) | padrao | nova | 76% | 68% | - | - | - | sim |
| Língua de Lima (`mon_lingua_de_lima`) | lacaio | nova | 62% | 81% | - | - | - | sim |
| Pisador do Salão (`mon_pisador_do_salao`) | elite | nova | 48% | 62% | - | - | - | sim |
