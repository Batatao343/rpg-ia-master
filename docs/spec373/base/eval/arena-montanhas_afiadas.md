# Arena SPEC-349 - montanhas_afiadas

40 seeds x 5 Posturas por célula; MockLLM; herói da esteira do playtest; bot `cartas`. Faixa 45-85 %; reinventadas com |delta| <= 8 pp contra o slot antes. Gerado por `scripts/bestiario/arena.py`.

| Criatura | Cat. | Status | L3|off | L3|on | L5|off | L5|on | Delta vs slot antes | OK |
|---|---|---|---|---|---|---|---|---|
| Deitado na Parede (`mon_deitado_na_parede`) | padrao | nova | 82% | 74% | - | - | - | sim |
| Geodo da Praga (`mon_geodo_da_praga`) | lacaio | nova | 74% | 61% | - | - | - | sim |
| Cauda de Atalaia (`mon_cauda_de_atalaia`) | padrao | nova | 76% | 77% | - | - | - | sim |
| Queimado de Frio (`mon_queimado_de_frio`) | padrao | nova | 56% | 74% | - | - | - | sim |
| Olhos em Volta (`enemy_observador_menor`) | lacaio | reinventada | 66% | 58% | - | - | L3|off: -7.0; L3|on: -8.0 | sim |
| Leque de Costelas (`enemy_wyvern_jovem`) | elite | reinventada | 61% | 72% | - | - | L3|off: +24.0; L3|on: +33.5 | sim |
| Boi de Canga (`enemy_minotauro_esqueleto`) | elite | reinventada | 82% | 14% | - | - | L3|off: +62.0; L3|on: -4.5 | NAO: L3|on 14% fora de 45-85% |
| Morador do Caldeirão (`enemy_mimico_bau`) | elite | reinventada | 60% | 87% | - | - | L3|off: -18.0; L3|on: +17.0 | NAO: L3|off delta 18.0 pp > 8; L3|on 87% fora de 45-85%; L3|on delta 17.0 pp > 8 |
| Caramujo de Estalagmite (`enemy_basilisco_caverna`) | elite | reinventada | 50% | 66% | - | - | L3|off: -18.0; L3|on: +11.5 | NAO: L3|off delta 18.0 pp > 8; L3|on delta 11.5 pp > 8 |
| Lenço do Desfiladeiro (`enemy_morcego_vampiro`) | lacaio | reinventada | 81% | 60% | - | - | L3|off: +5.0; L3|on: -4.5 | sim |
| Bexiga de Respiro (`mon_bexiga_de_respiro`) | lacaio | nova | 84% | 76% | - | - | - | sim |
| Saltão de Galeria (`mon_saltao_de_galeria`) | lacaio | nova | 77% | 74% | - | - | - | sim |
| Rolador de Escarpa (`mon_rolador_de_escarpa`) | padrao | nova | 84% | 79% | - | - | - | sim |
| Chicote de Fenda (`mon_chicote_de_fenda`) | padrao | nova | 74% | 80% | - | - | - | sim |
| Ladrão de Lume (`mon_ladrao_de_lume`) | lacaio | nova | 76% | 82% | - | - | - | sim |
| Ponte de Ombros (`enemy_troll_ponte`) | elite | reinventada | 44% | 51% | - | - | L3|off: +2.0; L3|on: +13.5 | NAO: L3|off 44% fora de 45-85% |
| Braços de Tenaz (`mon_bracos_de_tenaz`) | elite | nova | 60% | 87% | - | - | - | NAO: L3|on 87% fora de 45-85% |
| Marco que Aponta (`mon_marco_que_aponta`) | padrao | nova | 57% | 78% | - | - | - | sim |
| Armador de Fosso (`mon_armador_de_fosso`) | lacaio | nova | 78% | 96% | - | - | - | NAO: L3|on 96% fora de 45-85% |
| Vedado de Piche (`mon_vedado_de_piche`) | padrao | nova | 63% | 65% | - | - | - | sim |
| Peso dos Vencidos (`mon_peso_dos_vencidos`) | chefe | nova | - | - | 68% | 28% | - | NAO: L5|on 28% fora de 45-85% |
| Tampão da Câmara (`mon_tampao_da_camara`) | padrao | nova | 57% | 77% | - | - | - | sim |
| Tesoura de Cordada (`mon_tesoura_de_cordada`) | lacaio | nova | 82% | 78% | - | - | - | sim |
| Mastro de Troféus (`mon_mastro_de_trofeus`) | elite | nova | 66% | 84% | - | - | - | sim |
| Mão da Borda (`mon_mao_da_borda`) | padrao | nova | 74% | 69% | - | - | - | sim |
| Língua de Lima (`mon_lingua_de_lima`) | lacaio | nova | 64% | 82% | - | - | - | sim |
| Pisador do Salão (`mon_pisador_do_salao`) | elite | nova | 51% | 62% | - | - | - | sim |
