# Arena SPEC-349 - floresta_sussurros

40 seeds x 5 Posturas por célula; MockLLM; herói da esteira do playtest; bot `cartas`. Faixa 45-85 %; reinventadas com |delta| <= 8 pp contra o slot antes. Gerado por `scripts/bestiario/arena.py`.

| Criatura | Cat. | Status | L3|off | L3|on | L5|off | L5|on | Delta vs slot antes | OK |
|---|---|---|---|---|---|---|---|---|
| Lixado da Fronteira (`mon_lixado_da_fronteira`) | padrao | nova | 80% | 78% | - | - | - | sim |
| Abafador de Candeias (`mon_abafador_de_candeias`) | padrao | nova | 58% | 85% | - | - | - | sim |
| Fechado de Escápulas (`mon_fechado_de_escapulas`) | elite | nova | 56% | 57% | - | - | - | sim |
| Virado do Avesso (`mon_virado_do_avesso`) | padrao | nova | 62% | 68% | - | - | - | sim |
| Calado das Guelras (`mon_calado_das_guelras`) | lacaio | nova | 76% | 74% | - | - | - | sim |
| Saltão Desbotado (`enemy_aranha_lobo`) | lacaio | reinventada | 76% | 66% | - | - | L3|off: +2.5; L3|on: -5.0 | sim |
| Casuar de Elmo Fundo (`enemy_urso_coruja_mutante`) | elite | reinventada | 64% | 53% | - | - | L3|off: +20.0; L3|on: +3.5 | sim |
| Preguiça da Pradaria (`mon_ent_dormindo`) | elite | reinventada | 73% | 72% | - | - | L3|off: -1.5; L3|on: +15.5 | NAO: L3|on delta 15.5 pp > 8 |
| Morcego Rasteiro (`mon_morcego_rasteiro`) | lacaio | nova | 76% | 81% | - | - | - | sim |
| Besouro do Estalo (`mon_besouro_do_estalo`) | lacaio | nova | 75% | 86% | - | - | - | NAO: L3|on 86% fora de 45-85% |
| Onça Vazada (`mon_onca_vazada`) | elite | nova | 62% | 60% | - | - | - | sim |
| Lagarta de Visgo (`mon_lagarta_de_visgo`) | lacaio | nova | 70% | 78% | - | - | - | sim |
| Toldo das Clareiras (`mon_toldo_das_clareiras`) | chefe | nova | - | - | 46% | 48% | - | sim |
| Vespa Coveira (`mon_vespa_coveira`) | elite | nova | 66% | 63% | - | - | - | sim |
| Bugio Invertido (`mon_bugio_invertido`) | padrao | nova | 57% | 54% | - | - | - | sim |
| Dedos de Colheita (`mon_dedos_de_colheita`) | padrao | nova | 79% | 77% | - | - | - | sim |
| Olho de Pétala (`mon_olho_de_petala`) | padrao | nova | 68% | 82% | - | - | - | sim |
| Mapa de Cicatrizes (`mon_mapa_de_cicatrizes`) | padrao | nova | 41% | 46% | - | - | - | NAO: L3|off 41% fora de 45-85% |
| Ressecado da Travessia (`mon_ressecado_da_travessia`) | lacaio | nova | 74% | 76% | - | - | - | sim |
| Mascador de Raiz (`mon_mascador_de_raiz`) | padrao | nova | 66% | 63% | - | - | - | sim |
| Sombra Deitada (`enemy_sombra_espreitadora`) | lacaio | reinventada | 82% | 68% | - | - | L3|off: +0.0; L3|on: +0.5 | sim |
| Ermitão de Carcaça (`mon_ermitao_de_carcaca`) | padrao | nova | 80% | 68% | - | - | - | sim |
| Desafiante Rubro (`mon_desafiante_rubro`) | elite | nova | 70% | 74% | - | - | - | sim |
| Enrolado da Clareira (`mon_enrolado_da_clareira`) | padrao | nova | 59% | 66% | - | - | - | sim |
| Picanço de Espinheiro (`mon_picanco_de_espinheiro`) | elite | nova | 72% | 68% | - | - | - | sim |
