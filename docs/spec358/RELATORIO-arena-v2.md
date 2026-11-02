# SPEC-358 - Reprocessamento da arena: v1 (remocao) x v2 (substituicao)

Sementes 0-19, protocolo de lote (padrao, `level_req`, 20 sementes). Nenhuma Carta, limiar ou relatorio antigo foi alterado. `[F]` = fato medido; `[H]` = hipotese.

Bandeiras v1 derivadas do mesmo relatorio v2 (mesmas regras do `sim.py`). Conferencia contra o v1 de verdade: {'arquivo': 'sangromante_avaro.json', 'cartas': 12, 'iguais': True}.

## 0. Leitura (escrita a mao sobre os numeros abaixo; regerar o relatorio com `--fase relatorio` a apaga)

- [F] Itens: 308 (180 Cartas de subclasse + 16 de tronco x 3 subclasses + 40 neutras x 2 baralhos). O v1 recusa 76; o v2 recusa 2 (`dev1_con_cicatriz_votiva` +15,0 pp e `med1_tri_respiro_forcado` +8,8 pp, esta SEM referencia: delta por remocao).
- [F] Motivos das 76 recusas do v1 (um item pode ter mais de um, entao 40 + 9 + 32 nao soma 76): 40 `dominante` por uso e 9 `em_branco` (artefato do bot, agora aviso) e 32 `dominante` por delta de remocao. No total, 75 das 76 recusas do v1 passam no v2 (secao 2); 1 item entra so no v2 (`dev1_con_cicatriz_votiva`).
- [F] Confirmacao 20-99 (320 lutas, 77 itens): os dois `dominante` do v2 caem para +3,4 e +3,1 pp (ruido); nenhum item fica `dominante` nessa rodada. [H] Ou seja, o `dominante` do v2 nas sementes 0-19 e, nesta amostra, ruido de 80 lutas, nao Carta forte.
- [F] Muitos deltas por substituicao saem NEGATIVOS (ex.: Bencao do Aco -5,0; Corte sem Aviso 0,0; Pinca de Aco -17,5). [H] A referencia no ponto medio da faixa de orcamento e mais forte para o bot que boa parte das Cartas reais, que gastam poder em efeitos que a arena nao mede (condicoes, Chamado, Torpor...). O v2 e um filtro de "inflacao por Carta vazia", nao de "Carta fraca"; um v2 sem bandeira nao prova que a Carta e boa.
- [F] R15 (controle `ctl_ferro_dano4_marcial`, dano 4 marcial puro, 320 lutas): remocao +10,6 pp; substituicao -11,2 pp (a referencia e dano 7). O criterio literal "|delta v2| < |delta v1|" NAO se confirma (11,2 > 10,6), embora o sinal mostre o que se queria: o controle fraco deixa de parecer forte. Por D6, o v2 fica disponivel e NAO e recomendado como default sem decisao do dono.
- [F] Motor: todos os dados foram regerados em `motor_sha` b145f4ba8ade4acaf792d798cd60b55e6479eb40 (carimbo em `arena-v2*.json`); os numeros bateram com a rodada anterior. Equivalencia v1 refeita nesse motor (15/15).
- [F] Verificacao interna: o delta por remocao do v2 e as bandeiras v1 derivadas bateram exatamente com o v1 real em `sangromante_avaro.json`.


## 1. Contagem de bandeiras

Itens (Carta x variante): 308.

| | v1 | v2 |
|---|---|---|
| bandeiras (total) | 76 | 2 |
| itens recusados | 76 | 2 |
| por uso (em_branco / dominante por uso; motivos se sobrepoem) | 9 / 40 | 0 (viram aviso) |
| por delta (dominante; motivos se sobrepoem) | 32 | 2 |

Itens sem referencia (reacao/passiva/etc.): 17.

## 2. Divergencias de veredito (v1 x v2)

76 itens. Liberados pelo v2: 75; recusados so no v2: 1.

| Carta | uso | delta v1 (remocao) | delta v2 | X ref | vitoria_base | vitoria_ref | bandeiras v1 -> v2 | avisos v2 |
|---|---|---|---|---|---|---|---|---|
| arc1_cal_rede | 51% | +8.8 | -8.8 (sub) | 9 | 0.212 | 0.388 | dominante -> - | - |
| arc1_cal_segunda_medicao | 28% | +10.0 | -1.3 (sub) | 10 | 0.212 | 0.325 | dominante -> - | - |
| arc1_cal_folga | 21% | +12.5 | -1.3 (sub) | 11 | 0.450 | 0.588 | dominante -> - | - |
| arc1_cal_impacto | 26% | +13.8 | -1.2 (sub) | 8 | 0.450 | 0.600 | dominante -> - | - |
| arc1_des_dedos | 0% | +5.0 | -2.5 (sub) | 7 | 0.700 | 0.775 | em_branco -> - | uso_baixo |
| arc1_des_corrente | 0% | +5.0 | -2.5 (sub) | 6 | 0.700 | 0.775 | em_branco -> - | uso_baixo |
| arc1_imp_orquestra | 4% | +5.0 | -2.5 (sub) | 19 | 0.738 | 0.812 | em_branco -> - | uso_baixo |
| cor1_alm_lembranca_errada | 62% | +3.7 | -5.0 (sub) | 9 | 0.463 | 0.550 | dominante -> - | uso_alto |
| cor1_alm_corredor_sem_eco | 0% | +0.0 | -8.8 (sub) | 18 | 0.575 | 0.662 | em_branco -> - | uso_baixo |
| cor1_bio_raiz_na_pele | 76% | +3.8 | -10.0 (sub) | 5 | 0.762 | 0.900 | dominante -> - | uso_alto |
| cor1_bio_mordida_do_bolor | 75% | +6.2 | -1.3 (sub) | 5 | 0.762 | 0.838 | dominante -> - | uso_alto |
| cor1_bio_golpe_de_mofo | 64% | +7.5 | +5.0 (sub) | 8 | 0.500 | 0.525 | dominante -> - | uso_alto |
| cor1_ino_medir_a_fadiga | 2% | -6.2 | -3.8 (sub) | 5 | 0.825 | 0.800 | em_branco -> - | uso_baixo |
| cor1_ino_colapso_programado | 67% | -1.2 | -3.7 (sub) | 18 | 0.688 | 0.713 | dominante -> - | uso_alto |
| cor1_ino_geometria_da_ruina | 3% | +1.2 | -5.0 (sub) | 18 | 0.588 | 0.650 | em_branco -> - | uso_baixo |
| dev1_con_veu_de_incenso | 90% | +11.2 | +0.0 (sub) | 6 | 0.775 | 0.887 | dominante -> - | uso_alto |
| dev1_con_cajado_votivo | 89% | +8.8 | +1.3 (sub) | 4 | 0.775 | 0.850 | dominante -> - | uso_alto |
| dev1_con_cicatriz_votiva | 31% | +5.0 | +15.0 (sub) | 11 | 0.475 | 0.375 | - -> dominante | - |
| dev1_enl_nome_repetido | 60% | +2.5 | +0.0 (sub) | 5 | 0.825 | 0.850 | dominante -> - | uso_alto |
| dev1_enl_peso_dos_ausentes | 52% | +11.3 | +0.0 (sub) | 9 | 0.725 | 0.838 | dominante -> - | - |
| dev1_enl_luto_que_aquece | 20% | +12.5 | +3.7 (sub) | 11 | 0.725 | 0.812 | dominante -> - | - |
| dev1_enl_cortejo_de_cinzas | 35% | +11.2 | +0.0 (sub) | 18 | 0.713 | 0.825 | dominante -> - | - |
| dev1_enl_missa_dos_ausentes | 0% | -7.5 | -3.7 (sub) | 18 | 0.738 | 0.700 | em_branco -> - | uso_baixo |
| med1_bot_agulha_envenenada | 35% | +8.8 | +2.5 (sub) | 8 | 0.287 | 0.350 | dominante -> - | - |
| med1_fer_garra_de_protese | 55% | +10.0 | +0.0 (sub) | 4 | 0.775 | 0.875 | dominante -> - | - |
| med1_tri_remendo_rapido | 15% | +10.0 | -1.2 (sub) | 5 | 0.762 | 0.875 | dominante -> - | - |
| med1_tri_maca_erguida | 48% | +10.0 | -2.5 (sub) | 6 | 0.762 | 0.887 | dominante -> - | - |
| med1_tri_no_desfeito | 60% | +8.8 | -5.0 (sub) | 7 | 0.762 | 0.900 | dominante -> - | - |
| med1_tri_sedativo_seco | 59% | +8.8 | -2.5 (sub) | 5 | 0.762 | 0.875 | dominante -> - | - |
| med1_tri_pancada_de_cabo | 44% | +11.3 | -1.2 (sub) | 5 | 0.762 | 0.887 | dominante -> - | - |
| san1_ava_juros_do_primeiro | 5% | -2.5 | -2.5 (sub) | 7 | 0.475 | 0.475 | em_branco -> - | uso_baixo |
| san1_ava_poupar_ferida | 5% | -2.5 | -1.2 (sub) | 5 | 0.900 | 0.887 | em_branco -> - | uso_baixo |
| san1_ava_execucao_da_divida | 62% | -6.2 | -1.2 (sub) | 18 | 0.688 | 0.637 | dominante -> - | uso_alto |
| san1_ava_cofre_sem_fundo | 79% | +2.5 | +0.0 (sub) | 18 | 0.750 | 0.775 | dominante -> - | uso_alto |
| san1_exp_cicatriz_aberta | 81% | +10.0 | -1.2 (sub) | 7 | 0.762 | 0.875 | dominante -> - | uso_alto |
| san1_exp_gole_rubro | 9% | +8.8 | +0.0 (sub) | 5 | 0.762 | 0.850 | dominante -> - | - |
| san1_exp_selo_de_dor | 83% | +8.8 | -2.5 (sub) | 5 | 0.762 | 0.875 | dominante -> - | uso_alto |
| san1_sil_corte_sem_aviso | 46% | +13.8 | +0.0 (sub) | 8 | 0.537 | 0.675 | dominante -> - | - |
| san1_sil_arterial_fina | 26% | +11.2 | -3.7 (sub) | 8 | 0.613 | 0.762 | dominante -> - | - |
| san1_sil_cirurgia_sem_testemunha | 63% | -2.5 | -1.3 (sub) | 17 | 0.688 | 0.675 | dominante -> - | uso_alto |
| san1_sil_ultima_gota | 73% | +8.8 | +0.0 (sub) | 18 | 0.700 | 0.787 | dominante -> - | uso_alto |
| arc1_tro_marca_de_giz [calibrado] | 26% | +8.8 | +0.0 (sub) | 7 | 0.787 | 0.875 | dominante -> - | - |
| arc1_tro_lance_calculado [descoberto] | 32% | +8.7 | -2.5 (sub) | 11 | 0.263 | 0.375 | dominante -> - | - |
| arc1_tro_lance_calculado [improvisador] | 31% | +20.0 | -1.2 (sub) | 11 | 0.300 | 0.512 | dominante -> - | - |
| arc1_tro_contrassinal [calibrado] | 76% | +5.0 | -5.0 (sub) | 5 | 0.787 | 0.887 | dominante -> - | uso_alto |
| arc1_tro_contrassinal [descoberto] | 67% | +3.7 | -3.7 (sub) | 5 | 0.738 | 0.812 | dominante -> - | uso_alto |
| arc1_tro_contrassinal [improvisador] | 69% | +0.0 | -3.7 (sub) | 5 | 0.812 | 0.850 | dominante -> - | uso_alto |
| dev1_tro_vigilia_de_cinza [zeloso] | 16% | +10.0 | -2.5 (sub) | 7 | 0.700 | 0.825 | dominante -> - | - |
| dev1_tro_palavra_que_corta [consagrado] | 68% | +5.0 | -2.5 (sub) | 5 | 0.800 | 0.875 | dominante -> - | uso_alto |
| dev1_tro_palavra_que_corta [zeloso] | 52% | +12.5 | -2.5 (sub) | 5 | 0.700 | 0.850 | dominante -> - | - |
| dev1_tro_dedo_de_sentenca [zeloso] | 45% | +8.8 | -3.7 (sub) | 6 | 0.700 | 0.825 | dominante -> - | - |
| san1_tro_corte_de_penitencia [exposto] | 77% | +3.7 | +1.2 (sub) | 6 | 0.812 | 0.838 | dominante -> - | uso_alto |
| san1_tro_corte_de_penitencia [silencioso] | 72% | -1.2 | -3.7 (sub) | 6 | 0.887 | 0.912 | dominante -> - | uso_alto |
| san1_tro_eco_de_ferida [exposto] | 63% | +5.0 | +0.0 (sub) | 6 | 0.812 | 0.863 | dominante -> - | uso_alto |
| neu1_na_espada_da_legiao [devoto] | 71% | +1.2 | +0.0 (sub) | 5 | 0.800 | 0.812 | dominante -> - | uso_alto |
| neu1_na_espada_da_legiao [arcanista] | 72% | +5.0 | +1.3 (sub) | 5 | 0.787 | 0.825 | dominante -> - | uso_alto |
| neu1_na_fuligem_das_chamines [devoto] | 66% | +1.2 | +0.0 (sub) | 5 | 0.800 | 0.812 | dominante -> - | uso_alto |
| neu1_na_fuligem_das_chamines [arcanista] | 70% | +0.0 | -7.5 (sub) | 5 | 0.787 | 0.863 | dominante -> - | uso_alto |
| neu1_na_gazua_dos_telhados [devoto] | 71% | +3.7 | +1.3 (sub) | 6 | 0.800 | 0.825 | dominante -> - | uso_alto |
| neu1_na_gazua_dos_telhados [arcanista] | 72% | +2.5 | -5.0 (sub) | 6 | 0.787 | 0.863 | dominante -> - | uso_alto |
| neu1_na_salvo_conduto_falso [devoto] | 65% | +1.2 | +0.0 (sub) | 5 | 0.800 | 0.812 | dominante -> - | uso_alto |
| neu1_na_salvo_conduto_falso [arcanista] | 71% | +5.0 | -2.5 (sub) | 5 | 0.787 | 0.863 | dominante -> - | uso_alto |
| neu1_er_emboscada_dos_renegados [arcanista] | 43% | +10.0 | -6.2 (sub) | 8 | 0.362 | 0.525 | dominante -> - | - |
| neu1_er_machado_de_vorr [devoto] | 61% | -3.7 | -1.2 (sub) | 9 | 0.838 | 0.812 | dominante -> - | uso_alto |
| neu1_br_sabre_de_pirata [devoto] | 68% | +0.0 | +0.0 (sub) | 5 | 0.800 | 0.800 | dominante -> - | uso_alto |
| neu1_br_sabre_de_pirata [arcanista] | 73% | +5.0 | +1.3 (sub) | 5 | 0.787 | 0.825 | dominante -> - | uso_alto |
| neu1_br_grogue_do_porto [devoto] | 73% | +2.5 | -1.3 (sub) | 7 | 0.800 | 0.838 | dominante -> - | uso_alto |
| neu1_br_grogue_do_porto [arcanista] | 73% | +5.0 | -3.7 (sub) | 7 | 0.787 | 0.875 | dominante -> - | uso_alto |
| neu1_br_arpao_de_osso [arcanista] | 51% | +8.8 | -6.2 (sub) | 9 | 0.362 | 0.512 | dominante -> - | - |
| neu1_sb_pedagio_de_sangue [devoto] | 73% | +1.2 | +0.0 (sub) | 5 | 0.800 | 0.812 | dominante -> - | uso_alto |
| neu1_sb_pedagio_de_sangue [arcanista] | 74% | +2.5 | -1.2 (sub) | 5 | 0.787 | 0.825 | dominante -> - | uso_alto |
| neu1_sb_martelo_de_guerra_anao [arcanista] | 66% | +0.0 | +0.0 (sub) | 10 | 0.787 | 0.787 | dominante -> - | uso_alto |
| neu1_sb_corda_de_aranha [devoto] | 69% | +3.7 | +0.0 (sub) | 7 | 0.800 | 0.838 | dominante -> - | uso_alto |
| neu1_sb_corda_de_aranha [arcanista] | 70% | +3.7 | -5.0 (sub) | 7 | 0.787 | 0.875 | dominante -> - | uso_alto |
| neu1_ge_nectar_da_furia [arcanista] | 62% | +6.2 | -2.5 (sub) | 11 | 0.362 | 0.450 | dominante -> - | uso_alto |
| neu1_ge_ampulheta_de_vaelorn [arcanista] | 23% | +8.7 | +0.0 (sub) | 19 | 0.675 | 0.762 | dominante -> - | - |

## 3. Confirmacao com sementes 20-99 (320 lutas por braco, uma vez)

Itens com `dominante` no v2 ou com veredito v1 != v2. `delta v1` = remocao, `delta v2` = substituicao.

| Carta | delta v1 0-19 | delta v2 0-19 | delta v1 20-99 | delta v2 20-99 | bandeiras v1 -> v2 (20-99) |
|---|---|---|---|---|---|
| arc1_cal_rede | +8.8 | -8.8 | +5.9 | -10.3 | - -> - |
| arc1_cal_segunda_medicao | +10.0 | -1.3 | +4.4 | -3.7 | - -> - |
| arc1_cal_folga | +12.5 | -1.3 | -4.1 | +1.6 | - -> - |
| arc1_cal_impacto | +13.8 | -1.2 | +0.0 | +0.0 | - -> - |
| arc1_des_dedos | +5.0 | -2.5 | +3.7 | +2.2 | em_branco -> - |
| arc1_des_corrente | +5.0 | -2.5 | +3.7 | +2.2 | em_branco -> - |
| arc1_imp_orquestra | +5.0 | -2.5 | +0.6 | -4.4 | em_branco -> - |
| cor1_alm_lembranca_errada | +3.7 | -5.0 | +1.3 | -6.6 | - -> - |
| cor1_alm_corredor_sem_eco | +0.0 | -8.8 | +0.0 | -3.4 | em_branco -> - |
| cor1_bio_raiz_na_pele | +3.8 | -10.0 | +0.0 | -6.9 | dominante -> - |
| cor1_bio_mordida_do_bolor | +6.2 | -1.3 | -0.6 | -3.4 | dominante -> - |
| cor1_bio_golpe_de_mofo | +7.5 | +5.0 | +5.3 | +0.0 | - -> - |
| cor1_ino_medir_a_fadiga | -6.2 | -3.8 | -1.9 | -2.5 | em_branco -> - |
| cor1_ino_colapso_programado | -1.2 | -3.7 | +0.3 | -9.4 | - -> - |
| cor1_ino_geometria_da_ruina | +1.2 | -5.0 | -2.8 | -6.6 | - -> - |
| dev1_con_veu_de_incenso | +11.2 | +0.0 | +1.2 | -1.3 | dominante -> - |
| dev1_con_cajado_votivo | +8.8 | +1.3 | +5.3 | +0.9 | dominante -> - |
| dev1_con_cicatriz_votiva | +5.0 | +15.0 | +3.4 | +3.4 | - -> - |
| dev1_enl_nome_repetido | +2.5 | +0.0 | +0.3 | -0.3 | dominante -> - |
| dev1_enl_peso_dos_ausentes | +11.3 | +0.0 | +0.0 | -2.2 | - -> - |
| dev1_enl_luto_que_aquece | +12.5 | +3.7 | +5.9 | +5.6 | - -> - |
| dev1_enl_cortejo_de_cinzas | +11.2 | +0.0 | -3.7 | -0.3 | - -> - |
| dev1_enl_missa_dos_ausentes | -7.5 | -3.7 | +0.3 | -3.4 | - -> - |
| med1_bot_agulha_envenenada | +8.8 | +2.5 | +6.9 | -12.8 | - -> - |
| med1_fer_garra_de_protese | +10.0 | +0.0 | -0.3 | -4.4 | - -> - |
| med1_tri_remendo_rapido | +10.0 | -1.2 | +3.4 | -0.6 | - -> - |
| med1_tri_maca_erguida | +10.0 | -2.5 | +5.9 | -0.9 | - -> - |
| med1_tri_no_desfeito | +8.8 | -5.0 | +1.3 | -4.4 | - -> - |
| med1_tri_sedativo_seco | +8.8 | -2.5 | +0.0 | -7.2 | - -> - |
| med1_tri_pancada_de_cabo | +11.3 | -1.2 | +2.2 | -4.1 | - -> - |
| med1_tri_respiro_forcado | +8.8 | +8.8 | +3.1 | +3.1 | uso_nao_medido -> - |
| san1_ava_juros_do_primeiro | -2.5 | -2.5 | -3.4 | -5.6 | - -> - |
| san1_ava_poupar_ferida | -2.5 | -1.2 | +0.0 | +0.3 | em_branco -> - |
| san1_ava_execucao_da_divida | -6.2 | -1.2 | +9.1 | +1.9 | dominante -> - |
| san1_ava_cofre_sem_fundo | +2.5 | +0.0 | +2.2 | +0.3 | - -> - |
| san1_exp_cicatriz_aberta | +10.0 | -1.2 | -0.3 | -3.1 | dominante -> - |
| san1_exp_gole_rubro | +8.8 | +0.0 | +0.6 | -1.6 | - -> - |
| san1_exp_selo_de_dor | +8.8 | -2.5 | -2.5 | -5.3 | dominante -> - |
| san1_sil_corte_sem_aviso | +13.8 | +0.0 | +1.9 | -0.9 | - -> - |
| san1_sil_arterial_fina | +11.2 | -3.7 | +3.4 | -0.6 | - -> - |
| san1_sil_cirurgia_sem_testemunha | -2.5 | -1.3 | +3.7 | -0.6 | - -> - |
| san1_sil_ultima_gota | +8.8 | +0.0 | -0.9 | -2.2 | - -> - |
| arc1_tro_marca_de_giz [calibrado] | +8.8 | +0.0 | +0.3 | -1.6 | - -> - |
| arc1_tro_lance_calculado [descoberto] | +8.7 | -2.5 | -1.6 | -3.1 | - -> - |
| arc1_tro_lance_calculado [improvisador] | +20.0 | -1.2 | -5.6 | -5.0 | - -> - |
| arc1_tro_contrassinal [calibrado] | +5.0 | -5.0 | +1.2 | -1.3 | dominante -> - |
| arc1_tro_contrassinal [descoberto] | +3.7 | -3.7 | +5.6 | -1.3 | dominante -> - |
| arc1_tro_contrassinal [improvisador] | +0.0 | -3.7 | +3.7 | -1.9 | dominante -> - |
| dev1_tro_vigilia_de_cinza [zeloso] | +10.0 | -2.5 | -1.2 | -0.9 | - -> - |
| dev1_tro_palavra_que_corta [consagrado] | +5.0 | -2.5 | +0.0 | -1.6 | - -> - |
| dev1_tro_palavra_que_corta [zeloso] | +12.5 | -2.5 | +3.1 | -1.3 | dominante -> - |
| dev1_tro_dedo_de_sentenca [zeloso] | +8.8 | -3.7 | -3.7 | -8.8 | - -> - |
| san1_tro_corte_de_penitencia [exposto] | +3.7 | +1.2 | -2.2 | -4.4 | dominante -> - |
| san1_tro_corte_de_penitencia [silencioso] | -1.2 | -3.7 | -0.3 | -0.6 | dominante -> - |
| san1_tro_eco_de_ferida [exposto] | +5.0 | +0.0 | +3.4 | +0.3 | - -> - |
| neu1_na_espada_da_legiao [devoto] | +1.2 | +0.0 | +3.4 | -0.6 | dominante -> - |
| neu1_na_espada_da_legiao [arcanista] | +5.0 | +1.3 | +0.6 | -0.6 | dominante -> - |
| neu1_na_fuligem_das_chamines [devoto] | +1.2 | +0.0 | -1.9 | -4.4 | dominante -> - |
| neu1_na_fuligem_das_chamines [arcanista] | +0.0 | -7.5 | +1.9 | -4.4 | dominante -> - |
| neu1_na_gazua_dos_telhados [devoto] | +3.7 | +1.3 | -3.7 | -4.7 | dominante -> - |
| neu1_na_gazua_dos_telhados [arcanista] | +2.5 | -5.0 | +1.2 | -2.5 | dominante -> - |
| neu1_na_salvo_conduto_falso [devoto] | +1.2 | +0.0 | -3.4 | -6.9 | dominante -> - |
| neu1_na_salvo_conduto_falso [arcanista] | +5.0 | -2.5 | +3.4 | -1.9 | dominante -> - |
| neu1_er_emboscada_dos_renegados [arcanista] | +10.0 | -6.2 | +4.1 | -10.0 | - -> - |
| neu1_er_machado_de_vorr [devoto] | -3.7 | -1.2 | +2.5 | -3.4 | - -> - |
| neu1_br_sabre_de_pirata [devoto] | +0.0 | +0.0 | +0.3 | -0.3 | dominante -> - |
| neu1_br_sabre_de_pirata [arcanista] | +5.0 | +1.3 | +1.6 | -0.6 | dominante -> - |
| neu1_br_grogue_do_porto [devoto] | +2.5 | -1.3 | +0.0 | -1.9 | dominante -> - |
| neu1_br_grogue_do_porto [arcanista] | +5.0 | -3.7 | +0.9 | -4.1 | dominante -> - |
| neu1_br_arpao_de_osso [arcanista] | +8.8 | -6.2 | +2.2 | -11.2 | - -> - |
| neu1_sb_pedagio_de_sangue [devoto] | +1.2 | +0.0 | +3.4 | -0.6 | dominante -> - |
| neu1_sb_pedagio_de_sangue [arcanista] | +2.5 | -1.2 | -1.9 | -3.1 | dominante -> - |
| neu1_sb_martelo_de_guerra_anao [arcanista] | +0.0 | +0.0 | -0.6 | +0.0 | dominante -> - |
| neu1_sb_corda_de_aranha [devoto] | +3.7 | +0.0 | +0.0 | -1.9 | dominante -> - |
| neu1_sb_corda_de_aranha [arcanista] | +3.7 | -5.0 | +4.4 | -0.6 | dominante -> - |
| neu1_ge_nectar_da_furia [arcanista] | +6.2 | -2.5 | +8.1 | +0.6 | dominante -> - |
| neu1_ge_ampulheta_de_vaelorn [arcanista] | +8.7 | +0.0 | +1.6 | -1.6 | - -> - |

## 4. Casos de controle

| Carta | uso | delta v1 (remocao) | delta v2 | X ref | vitoria_base | vitoria_ref | bandeiras v1 -> v2 | avisos v2 |
|---|---|---|---|---|---|---|---|---|
| dev1_con_bencao_do_aco | 50% | +1.3 | -5.0 (sub) | 8 | 0.475 | 0.537 | - -> - | - |
| san1_sil_corte_sem_aviso | 46% | +13.8 | +0.0 (sub) | 8 | 0.537 | 0.675 | dominante -> - | - |
| cor1_alm_culpa_antiga | 30% | -12.5 | -16.2 (sub) | 9 | 0.350 | 0.388 | - -> - | - |
| med1_bot_agulha_envenenada | 35% | +8.8 | +2.5 (sub) | 8 | 0.287 | 0.350 | dominante -> - | - |
| med1_fer_cotovelo_de_aco | 43% | +0.0 | -13.8 (sub) | 8 | 0.263 | 0.400 | - -> - | - |
| med1_fer_pinca_de_aco | 45% | +1.3 | -17.5 (sub) | 9 | 0.263 | 0.450 | - -> - | - |
| arc1_tro_centelha_ressoante [calibrado] | 41% | +5.0 | -5.0 (sub) | 5 | 0.787 | 0.887 | - -> - | - |
| arc1_tro_centelha_ressoante [descoberto] | 21% | +5.0 | -2.5 (sub) | 5 | 0.738 | 0.812 | - -> - | - |
| arc1_tro_centelha_ressoante [improvisador] | 52% | +2.5 | -1.2 (sub) | 5 | 0.812 | 0.850 | - -> - | - |

### R15 - controle sintetico `ctl_ferro_dano4_marcial` (sementes 20-99)

delta por remocao +10.6 pp; delta por substituicao -11.2 pp; `vitoria_sem` 0.287, `vitoria_ref` 0.506, `vitoria_com` 0.394; ref {'id': 'ctl_ferro_dano4_marcial~ref', 'efeito': {'kind': 'dano', 'dano_base': 7, 'categoria_arma': 'marcial'}, 'power_score': 6.0, 'faixa': [-3.0, 16.0]}.

[F] |delta v2| >= |delta v1|: a hipotese R15 NAO se confirmou (D6: o v2 nao e recomendado como default sem decisao do dono).

## 5. Tabelas por conjunto


### arquivo:arcanista_cinzento_calibrado.json

| Carta | uso | delta v1 (remocao) | delta v2 | X ref | vitoria_base | vitoria_ref | bandeiras v1 -> v2 | avisos v2 |
|---|---|---|---|---|---|---|---|---|
| arc1_cal_leitura | 33% | +1.3 | -5.0 (sub) | 5 | 0.825 | 0.887 | - -> - | - |
| arc1_cal_pulso_medido | 58% | +3.8 | -2.5 (sub) | 5 | 0.825 | 0.887 | - -> - | - |
| arc1_cal_prumo | 21% | -1.2 | +0.0 (sub) | 6 | 0.825 | 0.812 | - -> - | - |
| arc1_cal_compasso | 14% | -2.5 | -1.2 (sub) | 5 | 0.825 | 0.812 | - -> - | - |
| arc1_cal_gabarito | 14% | -2.5 | -1.2 (sub) | 5 | 0.825 | 0.812 | - -> - | - |
| arc1_cal_estilhaco | 47% | +3.8 | -8.8 (sub) | 8 | 0.212 | 0.338 | - -> - | - |
| arc1_cal_rede | 51% | +8.8 | -8.8 (sub) | 9 | 0.212 | 0.388 | dominante -> - | - |
| arc1_cal_segunda_medicao | 28% | +10.0 | -1.3 (sub) | 10 | 0.212 | 0.325 | dominante -> - | - |
| arc1_cal_folga | 21% | +12.5 | -1.3 (sub) | 11 | 0.450 | 0.588 | dominante -> - | - |
| arc1_cal_impacto | 26% | +13.8 | -1.2 (sub) | 8 | 0.450 | 0.600 | dominante -> - | - |
| arc1_cal_quadrante | 33% | -5.0 | -1.3 (sub) | 18 | 0.713 | 0.675 | - -> - | - |
| arc1_cal_mares | 19% | -3.7 | -1.2 (sub) | 21 | 0.775 | 0.750 | - -> - | - |

### arquivo:arcanista_cinzento_descoberto.json

| Carta | uso | delta v1 (remocao) | delta v2 | X ref | vitoria_base | vitoria_ref | bandeiras v1 -> v2 | avisos v2 |
|---|---|---|---|---|---|---|---|---|
| arc1_des_faisca | 11% | +6.2 | -3.8 (sub) | 4 | 0.700 | 0.800 | - -> - | - |
| arc1_des_dedos | 0% | +5.0 | -2.5 (sub) | 7 | 0.700 | 0.775 | em_branco -> - | uso_baixo |
| arc1_des_palma | 11% | +7.5 | -1.2 (sub) | 5 | 0.700 | 0.787 | - -> - | - |
| arc1_des_corrente | 0% | +5.0 | -2.5 (sub) | 6 | 0.700 | 0.775 | em_branco -> - | uso_baixo |
| arc1_des_brasa | 0% | +5.0 | +5.0 (rem) | - | 0.700 | - | uso_nao_medido -> - | uso_nao_medido,sem_referencia |
| arc1_des_garganta | 11% | +6.2 | -3.8 (sub) | 4 | 0.700 | 0.800 | - -> - | - |
| arc1_des_sobrecarga | 41% | +1.3 | -3.7 (sub) | 10 | 0.312 | 0.362 | - -> - | - |
| arc1_des_vazao_selvagem | 50% | +0.0 | -7.5 (sub) | 8 | 0.312 | 0.388 | - -> - | - |
| arc1_des_raio_livre | 35% | +6.2 | -3.8 (sub) | 10 | 0.450 | 0.550 | - -> - | - |
| arc1_des_estouro_contido | 20% | -1.3 | -5.0 (sub) | 9 | 0.312 | 0.350 | - -> - | - |
| arc1_des_fenda | 39% | +6.2 | -3.7 (sub) | 18 | 0.600 | 0.700 | - -> - | - |
| arc1_des_caldeira_sem_fundo | 59% | +7.5 | -2.5 (sub) | 19 | 0.650 | 0.750 | - -> - | - |

### arquivo:arcanista_cinzento_improvisador.json

| Carta | uso | delta v1 (remocao) | delta v2 | X ref | vitoria_base | vitoria_ref | bandeiras v1 -> v2 | avisos v2 |
|---|---|---|---|---|---|---|---|---|
| arc1_imp_parafuso | 34% | -2.5 | -6.2 (sub) | 5 | 0.850 | 0.887 | - -> - | - |
| arc1_imp_gambiarra | 50% | -2.5 | -3.7 (sub) | 9 | 0.300 | 0.312 | - -> - | - |
| arc1_imp_carretel | 35% | +1.3 | -2.5 (sub) | 5 | 0.850 | 0.887 | - -> - | - |
| arc1_imp_olho_latao | 33% | +0.0 | -3.7 (sub) | 5 | 0.850 | 0.887 | - -> - | - |
| arc1_imp_mola | 0% | -2.5 | -2.5 (rem) | - | 0.850 | - | uso_nao_medido -> - | uso_nao_medido,sem_referencia |
| arc1_imp_remendo_cobre | 17% | -3.7 | -1.2 (sub) | 5 | 0.850 | 0.825 | - -> - | - |
| arc1_imp_bomba_estopim | 46% | +7.5 | +0.0 (sub) | 8 | 0.300 | 0.375 | - -> - | - |
| arc1_imp_truque | 49% | -2.5 | -3.7 (sub) | 9 | 0.300 | 0.312 | - -> - | - |
| arc1_imp_arame | 44% | +1.3 | -11.3 (sub) | 9 | 0.487 | 0.613 | - -> - | - |
| arc1_imp_terceiro_dia | 31% | +1.3 | -8.8 (sub) | 18 | 0.637 | 0.738 | - -> - | - |
| arc1_imp_orquestra | 4% | +5.0 | -2.5 (sub) | 19 | 0.738 | 0.812 | em_branco -> - | uso_baixo |
| arc1_imp_ultima_gambiarra | 28% | +7.5 | -3.7 (sub) | 19 | 0.512 | 0.625 | - -> - | - |

### arquivo:corruptor_alma.json

| Carta | uso | delta v1 (remocao) | delta v2 | X ref | vitoria_base | vitoria_ref | bandeiras v1 -> v2 | avisos v2 |
|---|---|---|---|---|---|---|---|---|
| cor1_alm_semente_de_culpa | 35% | +3.7 | +3.7 (sub) | 5 | 0.750 | 0.750 | - -> - | - |
| cor1_alm_sussurro_rouco | 35% | +1.2 | +1.2 (sub) | 5 | 0.750 | 0.750 | - -> - | - |
| cor1_alm_voz_que_falta | 36% | +0.0 | -7.5 (sub) | 6 | 0.750 | 0.825 | - -> - | - |
| cor1_alm_rosto_do_pavor | 35% | +1.2 | -2.5 (sub) | 6 | 0.750 | 0.787 | - -> - | - |
| cor1_alm_pe_no_vazio | 35% | +2.5 | +2.5 (sub) | 5 | 0.750 | 0.750 | - -> - | - |
| cor1_alm_ler_a_culpa | 35% | +1.2 | +1.2 (sub) | 5 | 0.750 | 0.750 | - -> - | - |
| cor1_alm_duvida_reflexa | 0% | +3.7 | +3.7 (rem) | - | 0.750 | - | uso_nao_medido -> - | uso_nao_medido,sem_referencia |
| cor1_alm_culpa_antiga | 30% | -12.5 | -16.2 (sub) | 9 | 0.350 | 0.388 | - -> - | - |
| cor1_alm_cerco_de_vozes | 20% | -1.3 | -8.7 (sub) | 8 | 0.463 | 0.537 | - -> - | - |
| cor1_alm_lembranca_errada | 62% | +3.7 | -5.0 (sub) | 9 | 0.463 | 0.550 | dominante -> - | uso_alto |
| cor1_alm_corredor_sem_eco | 0% | +0.0 | -8.8 (sub) | 18 | 0.575 | 0.662 | em_branco -> - | uso_baixo |
| cor1_alm_nome_apagado | 17% | +0.0 | -10.0 (sub) | 19 | 0.650 | 0.750 | - -> - | - |

### arquivo:corruptor_biologia.json

| Carta | uso | delta v1 (remocao) | delta v2 | X ref | vitoria_base | vitoria_ref | bandeiras v1 -> v2 | avisos v2 |
|---|---|---|---|---|---|---|---|---|
| cor1_bio_mofo_quente | 43% | +3.8 | -3.7 (sub) | 5 | 0.762 | 0.838 | - -> - | - |
| cor1_bio_febre_lenta | 28% | +0.0 | -7.5 (sub) | 5 | 0.762 | 0.838 | - -> - | - |
| cor1_bio_raiz_na_pele | 76% | +3.8 | -10.0 (sub) | 5 | 0.762 | 0.900 | dominante -> - | uso_alto |
| cor1_bio_ler_a_carne | 28% | -2.5 | -10.0 (sub) | 5 | 0.762 | 0.838 | - -> - | - |
| cor1_bio_mordida_do_bolor | 75% | +6.2 | -1.3 (sub) | 5 | 0.762 | 0.838 | dominante -> - | uso_alto |
| cor1_bio_pele_podre | 0% | +3.8 | +3.8 (rem) | - | 0.762 | - | uso_nao_medido -> - | uso_nao_medido,sem_referencia |
| cor1_bio_nariz_de_coveiro | 16% | +2.5 | -3.7 (sub) | 5 | 0.762 | 0.825 | - -> - | - |
| cor1_bio_carne_tenra | 14% | -6.2 | -6.2 (sub) | 8 | 0.487 | 0.487 | - -> - | - |
| cor1_bio_golpe_de_mofo | 64% | +7.5 | +5.0 (sub) | 8 | 0.500 | 0.525 | dominante -> - | uso_alto |
| cor1_bio_colheita_podre | 23% | +2.5 | -1.2 (sub) | 9 | 0.500 | 0.537 | - -> - | - |
| cor1_bio_metastase_viva | 44% | +7.5 | -2.5 (sub) | 18 | 0.675 | 0.775 | - -> - | - |
| cor1_bio_banquete_de_vermes | 54% | +3.7 | +0.0 (sub) | 19 | 0.688 | 0.725 | - -> - | - |

### arquivo:corruptor_inorganica.json

| Carta | uso | delta v1 (remocao) | delta v2 | X ref | vitoria_base | vitoria_ref | bandeiras v1 -> v2 | avisos v2 |
|---|---|---|---|---|---|---|---|---|
| cor1_ino_gancho_de_ferro | 31% | -5.0 | -3.7 (sub) | 5 | 0.825 | 0.812 | - -> - | - |
| cor1_ino_junta_emperrada | 31% | -5.0 | -3.7 (sub) | 5 | 0.825 | 0.812 | - -> - | - |
| cor1_ino_estalo_de_viga | 55% | -3.7 | -2.5 (sub) | 5 | 0.825 | 0.812 | - -> - | - |
| cor1_ino_medir_a_fadiga | 2% | -6.2 | -3.8 (sub) | 5 | 0.825 | 0.800 | em_branco -> - | uso_baixo |
| cor1_ino_estilhaco_de_ferro | 0% | -6.2 | -6.2 (rem) | - | 0.825 | - | uso_nao_medido -> - | uso_nao_medido,sem_referencia |
| cor1_ino_carapaca_de_ferrugem | 13% | -2.5 | +0.0 (sub) | 6 | 0.825 | 0.800 | - -> - | - |
| cor1_ino_oxido_no_gume | 8% | -2.5 | -16.3 (sub) | 9 | 0.325 | 0.463 | - -> - | - |
| cor1_ino_peso_morto | 8% | -1.3 | -15.0 (sub) | 9 | 0.325 | 0.463 | - -> - | - |
| cor1_ino_estrutura_cansada | 47% | -1.2 | -6.2 (sub) | 8 | 0.537 | 0.588 | - -> - | - |
| cor1_ino_dobra_forcada | 6% | +0.0 | -5.0 (sub) | 9 | 0.537 | 0.588 | - -> - | - |
| cor1_ino_colapso_programado | 67% | -1.2 | -3.7 (sub) | 18 | 0.688 | 0.713 | dominante -> - | uso_alto |
| cor1_ino_geometria_da_ruina | 3% | +1.2 | -5.0 (sub) | 18 | 0.588 | 0.650 | em_branco -> - | uso_baixo |

### arquivo:devoto_consagrado.json

| Carta | uso | delta v1 (remocao) | delta v2 | X ref | vitoria_base | vitoria_ref | bandeiras v1 -> v2 | avisos v2 |
|---|---|---|---|---|---|---|---|---|
| dev1_con_cinza_no_peito | 23% | +1.2 | -3.7 (sub) | 6 | 0.775 | 0.825 | - -> - | - |
| dev1_con_veu_de_incenso | 90% | +11.2 | +0.0 (sub) | 6 | 0.775 | 0.887 | dominante -> - | uso_alto |
| dev1_con_cajado_votivo | 89% | +8.8 | +1.3 (sub) | 4 | 0.775 | 0.850 | dominante -> - | uso_alto |
| dev1_con_uncao_curta | 7% | +1.2 | +0.0 (sub) | 5 | 0.775 | 0.787 | - -> - | - |
| dev1_con_selo_contra_o_abismo | 0% | +0.0 | +0.0 (rem) | - | 0.775 | - | uso_nao_medido -> - | uso_nao_medido,sem_referencia |
| dev1_con_postura_de_oracao | 26% | +0.0 | -2.5 (sub) | 4 | 0.775 | 0.800 | - -> - | - |
| dev1_con_marca_votiva | 52% | +2.5 | -5.0 (sub) | 5 | 0.775 | 0.850 | - -> - | - |
| dev1_con_cicatriz_votiva | 31% | +5.0 | +15.0 (sub) | 11 | 0.475 | 0.375 | - -> dominante | - |
| dev1_con_bencao_do_aco | 50% | +1.3 | -5.0 (sub) | 8 | 0.475 | 0.537 | - -> - | - |
| dev1_con_hora_canonica | 39% | -2.5 | +2.5 (sub) | 11 | 0.825 | 0.775 | - -> - | - |
| dev1_con_missa_fechada | 13% | +7.5 | -2.5 (sub) | 18 | 0.750 | 0.850 | - -> - | - |
| dev1_con_sacramento_do_vazio | 34% | +6.2 | +1.2 (sub) | 19 | 0.787 | 0.838 | - -> - | - |

### arquivo:devoto_enlutado.json

| Carta | uso | delta v1 (remocao) | delta v2 | X ref | vitoria_base | vitoria_ref | bandeiras v1 -> v2 | avisos v2 |
|---|---|---|---|---|---|---|---|---|
| dev1_enl_braco_de_chumbo | 28% | +0.0 | -2.5 (sub) | 5 | 0.825 | 0.850 | - -> - | - |
| dev1_enl_pranto_lento | 39% | +0.0 | -2.5 (sub) | 5 | 0.825 | 0.850 | - -> - | - |
| dev1_enl_nome_repetido | 60% | +2.5 | +0.0 (sub) | 5 | 0.825 | 0.850 | dominante -> - | uso_alto |
| dev1_enl_consolo_da_lembranca | 6% | -1.2 | -3.7 (sub) | 5 | 0.825 | 0.850 | - -> - | - |
| dev1_enl_rosto_do_morto | 0% | -1.2 | -1.2 (rem) | - | 0.825 | - | uso_nao_medido -> - | uso_nao_medido,sem_referencia |
| dev1_enl_ler_o_luto | 28% | -2.5 | -5.0 (sub) | 5 | 0.825 | 0.850 | - -> - | - |
| dev1_enl_nome_gravado | 49% | -2.5 | -5.0 (sub) | 9 | 0.500 | 0.525 | - -> - | - |
| dev1_enl_consolo_roubado | 36% | +0.0 | -1.2 (sub) | 8 | 0.500 | 0.512 | - -> - | - |
| dev1_enl_peso_dos_ausentes | 52% | +11.3 | +0.0 (sub) | 9 | 0.725 | 0.838 | dominante -> - | - |
| dev1_enl_luto_que_aquece | 20% | +12.5 | +3.7 (sub) | 11 | 0.725 | 0.812 | dominante -> - | - |
| dev1_enl_cortejo_de_cinzas | 35% | +11.2 | +0.0 (sub) | 18 | 0.713 | 0.825 | dominante -> - | - |
| dev1_enl_missa_dos_ausentes | 0% | -7.5 | -3.7 (sub) | 18 | 0.738 | 0.700 | em_branco -> - | uso_baixo |

### arquivo:devoto_zeloso.json

| Carta | uso | delta v1 (remocao) | delta v2 | X ref | vitoria_base | vitoria_ref | bandeiras v1 -> v2 | avisos v2 |
|---|---|---|---|---|---|---|---|---|
| dev1_zel_mao_na_frente | 51% | +1.3 | +1.3 (sub) | 5 | 0.825 | 0.825 | - -> - | - |
| dev1_zel_dedo_apontado | 42% | -6.2 | -6.2 (sub) | 5 | 0.825 | 0.825 | - -> - | - |
| dev1_zel_mao_no_peito | 47% | +0.0 | +1.2 (sub) | 4 | 0.825 | 0.812 | - -> - | - |
| dev1_zel_ciume_subito | 0% | +1.3 | +1.3 (rem) | - | 0.825 | - | uso_nao_medido -> - | uso_nao_medido,sem_referencia |
| dev1_zel_anteparo_ciumento | 0% | +1.3 | +1.3 (rem) | - | 0.825 | - | uso_nao_medido -> - | uso_nao_medido,sem_referencia |
| dev1_zel_olhar_fixo | 10% | +1.3 | -1.2 (sub) | 5 | 0.825 | 0.850 | - -> - | - |
| dev1_zel_zelo_em_brasa | 10% | +1.3 | -1.2 (sub) | 4 | 0.825 | 0.850 | - -> - | - |
| dev1_zel_ciume_aberto | 55% | +0.0 | -3.7 (sub) | 8 | 0.400 | 0.438 | - -> - | - |
| dev1_zel_ninguem_toca | 32% | -1.3 | -2.5 (sub) | 11 | 0.400 | 0.412 | - -> - | - |
| dev1_zel_ferro_antes_do_ferro | 48% | +1.3 | +1.3 (sub) | 9 | 0.787 | 0.787 | - -> - | - |
| dev1_zel_corpo_entre | 18% | -2.5 | +0.0 (sub) | 22 | 0.738 | 0.713 | - -> - | - |
| dev1_zel_ninguem_mais | 50% | -6.2 | +0.0 (sub) | 19 | 0.850 | 0.787 | - -> - | - |

### arquivo:medico_boticario.json

| Carta | uso | delta v1 (remocao) | delta v2 | X ref | vitoria_base | vitoria_ref | bandeiras v1 -> v2 | avisos v2 |
|---|---|---|---|---|---|---|---|---|
| med1_bot_emplasto_espesso | 55% | -6.2 | -2.5 (sub) | 6 | 0.850 | 0.812 | - -> - | - |
| med1_bot_sal_na_sombra | 52% | -7.5 | -1.2 (sub) | 6 | 0.850 | 0.787 | - -> - | - |
| med1_bot_po_nos_olhos | 50% | +1.3 | +0.0 (sub) | 5 | 0.850 | 0.863 | - -> - | - |
| med1_bot_visco_de_raiz | 51% | -5.0 | -8.7 (sub) | 6 | 0.850 | 0.887 | - -> - | - |
| med1_bot_gota_de_veneno | 55% | +0.0 | -1.3 (sub) | 5 | 0.850 | 0.863 | - -> - | - |
| med1_bot_giz_vermelho | 52% | -3.7 | -5.0 (sub) | 5 | 0.850 | 0.863 | - -> - | - |
| med1_bot_frasco_aos_pes | 0% | -11.2 | -11.2 (rem) | - | 0.850 | - | uso_nao_medido -> - | uso_nao_medido,sem_referencia |
| med1_bot_antidoto_de_cinza | 30% | -2.5 | +1.3 (sub) | 11 | 0.287 | 0.250 | - -> - | - |
| med1_bot_agulha_envenenada | 35% | +8.8 | +2.5 (sub) | 8 | 0.287 | 0.350 | dominante -> - | - |
| med1_bot_amargo_forte | 38% | +2.5 | -2.5 (sub) | 12 | 0.388 | 0.438 | - -> - | - |
| med1_bot_fumigacao_geral | 21% | -2.5 | -6.2 (sub) | 18 | 0.688 | 0.725 | - -> - | - |
| med1_bot_elixir_imperfeito | 14% | +0.0 | +1.3 (sub) | 19 | 0.675 | 0.662 | - -> - | - |

### arquivo:medico_cirurgiao_ferro.json

| Carta | uso | delta v1 (remocao) | delta v2 | X ref | vitoria_base | vitoria_ref | bandeiras v1 -> v2 | avisos v2 |
|---|---|---|---|---|---|---|---|---|
| med1_fer_tala_rigida | 44% | +3.7 | -3.7 (sub) | 7 | 0.775 | 0.850 | - -> - | - |
| med1_fer_lente_de_protese | 44% | +3.7 | -3.7 (sub) | 7 | 0.775 | 0.850 | - -> - | - |
| med1_fer_pistao_de_campo | 38% | +2.5 | -8.7 (sub) | 6 | 0.775 | 0.887 | - -> - | - |
| med1_fer_cravo_na_junta | 46% | +5.0 | -7.5 (sub) | 5 | 0.775 | 0.900 | - -> - | - |
| med1_fer_garra_de_protese | 55% | +10.0 | +0.0 (sub) | 4 | 0.775 | 0.875 | dominante -> - | - |
| med1_fer_placa_no_peito | 0% | +1.2 | +1.2 (rem) | - | 0.775 | - | uso_nao_medido -> - | uso_nao_medido,sem_referencia |
| med1_fer_cotovelo_de_aco | 43% | +0.0 | -13.8 (sub) | 8 | 0.263 | 0.400 | - -> - | - |
| med1_fer_armadura_de_campo | 27% | +1.3 | +1.3 (sub) | 11 | 0.263 | 0.263 | - -> - | - |
| med1_fer_pinca_de_aco | 45% | +1.3 | -17.5 (sub) | 9 | 0.263 | 0.450 | - -> - | - |
| med1_fer_braco_de_colosso | 26% | +6.2 | -2.5 (sub) | 12 | 0.412 | 0.500 | - -> - | - |
| med1_fer_ancora_de_ferro | 21% | +3.7 | +3.7 (sub) | 22 | 0.613 | 0.613 | - -> - | - |
| med1_fer_cirurgia_no_ferro | 15% | +3.7 | +0.0 (sub) | 18 | 0.675 | 0.713 | - -> - | - |

### arquivo:medico_cirurgiao_trincheira.json

| Carta | uso | delta v1 (remocao) | delta v2 | X ref | vitoria_base | vitoria_ref | bandeiras v1 -> v2 | avisos v2 |
|---|---|---|---|---|---|---|---|---|
| med1_tri_remendo_rapido | 15% | +10.0 | -1.2 (sub) | 5 | 0.762 | 0.875 | dominante -> - | - |
| med1_tri_maca_erguida | 48% | +10.0 | -2.5 (sub) | 6 | 0.762 | 0.887 | dominante -> - | - |
| med1_tri_ordem_curta | 59% | +7.5 | -3.7 (sub) | 6 | 0.762 | 0.875 | - -> - | - |
| med1_tri_no_desfeito | 60% | +8.8 | -5.0 (sub) | 7 | 0.762 | 0.900 | dominante -> - | - |
| med1_tri_sedativo_seco | 59% | +8.8 | -2.5 (sub) | 5 | 0.762 | 0.875 | dominante -> - | - |
| med1_tri_pancada_de_cabo | 44% | +11.3 | -1.2 (sub) | 5 | 0.762 | 0.887 | dominante -> - | - |
| med1_tri_respiro_forcado | 0% | +8.8 | +8.8 (rem) | - | 0.762 | - | uso_nao_medido,dominante -> dominante | uso_nao_medido,sem_referencia |
| med1_tri_sutura_sob_fogo | 15% | +5.0 | +0.0 (sub) | 9 | 0.287 | 0.338 | - -> - | - |
| med1_tri_golpe_e_pulso | 36% | +7.5 | -6.2 (sub) | 8 | 0.287 | 0.425 | - -> - | - |
| med1_tri_sedar_e_remendar | 15% | +7.5 | +1.3 (sub) | 9 | 0.450 | 0.512 | - -> - | - |
| med1_tri_hospital_de_lona | 10% | +6.2 | +0.0 (sub) | 18 | 0.662 | 0.725 | - -> - | - |
| med1_tri_pulso_emprestado | 16% | +1.2 | +1.2 (sub) | 19 | 0.688 | 0.688 | - -> - | - |

### arquivo:sangromante_avaro.json

| Carta | uso | delta v1 (remocao) | delta v2 | X ref | vitoria_base | vitoria_ref | bandeiras v1 -> v2 | avisos v2 |
|---|---|---|---|---|---|---|---|---|
| san1_ava_moeda_guardada | 29% | +0.0 | +0.0 (sub) | 5 | 0.900 | 0.900 | - -> - | - |
| san1_ava_cofre_estreito | 12% | -6.2 | -3.7 (sub) | 6 | 0.900 | 0.875 | - -> - | - |
| san1_ava_juros_do_primeiro | 5% | -2.5 | -2.5 (sub) | 7 | 0.475 | 0.475 | em_branco -> - | uso_baixo |
| san1_ava_poupar_ferida | 5% | -2.5 | -1.2 (sub) | 5 | 0.900 | 0.887 | em_branco -> - | uso_baixo |
| san1_ava_livro_de_dividas | 19% | -3.7 | -3.7 (sub) | 5 | 0.900 | 0.900 | - -> - | - |
| san1_ava_gota_contada | 18% | -3.7 | -1.2 (sub) | 3 | 0.900 | 0.875 | - -> - | - |
| san1_ava_mao_fechada | 0% | -6.2 | -6.2 (rem) | - | 0.900 | - | uso_nao_medido -> - | uso_nao_medido,sem_referencia |
| san1_ava_cobranca_adiada | 38% | +7.5 | +1.3 (sub) | 9 | 0.475 | 0.537 | - -> - | - |
| san1_ava_penhor_de_carne | 60% | -3.7 | -3.7 (sub) | 5 | 0.900 | 0.900 | - -> - | - |
| san1_ava_hipoteca_de_sangue | 26% | -5.0 | +0.0 (sub) | 11 | 0.575 | 0.525 | - -> - | - |
| san1_ava_execucao_da_divida | 62% | -6.2 | -1.2 (sub) | 18 | 0.688 | 0.637 | dominante -> - | uso_alto |
| san1_ava_cofre_sem_fundo | 79% | +2.5 | +0.0 (sub) | 18 | 0.750 | 0.775 | dominante -> - | uso_alto |

### arquivo:sangromante_exposto.json

| Carta | uso | delta v1 (remocao) | delta v2 | X ref | vitoria_base | vitoria_ref | bandeiras v1 -> v2 | avisos v2 |
|---|---|---|---|---|---|---|---|---|
| san1_exp_talho_publico | 59% | +7.5 | -3.7 (sub) | 5 | 0.762 | 0.875 | - -> - | - |
| san1_exp_veia_a_mostra | 39% | +1.3 | -11.2 (sub) | 8 | 0.475 | 0.600 | - -> - | - |
| san1_exp_cicatriz_aberta | 81% | +10.0 | -1.2 (sub) | 7 | 0.762 | 0.875 | dominante -> - | uso_alto |
| san1_exp_aplauso_de_ferro | 0% | +5.0 | +5.0 (rem) | - | 0.762 | - | uso_nao_medido -> - | uso_nao_medido,sem_referencia |
| san1_exp_segundo_ato | 60% | +7.5 | -3.7 (sub) | 5 | 0.762 | 0.875 | - -> - | - |
| san1_exp_sangue_na_areia | 50% | +3.8 | -7.5 (sub) | 5 | 0.762 | 0.875 | - -> - | - |
| san1_exp_gole_rubro | 9% | +8.8 | +0.0 (sub) | 5 | 0.762 | 0.850 | dominante -> - | - |
| san1_exp_selo_de_dor | 83% | +8.8 | -2.5 (sub) | 5 | 0.762 | 0.875 | dominante -> - | uso_alto |
| san1_exp_plateia_cega | 34% | +2.5 | -11.3 (sub) | 9 | 0.475 | 0.613 | - -> - | - |
| san1_exp_bis_de_cicatriz | 46% | -5.0 | +1.2 (sub) | 8 | 0.625 | 0.562 | - -> - | - |
| san1_exp_teatro_de_facas | 26% | -3.7 | -6.2 (sub) | 18 | 0.650 | 0.675 | - -> - | - |
| san1_exp_ultima_cortina | 42% | -1.3 | -5.0 (sub) | 19 | 0.775 | 0.812 | - -> - | - |

### arquivo:sangromante_silencioso.json

| Carta | uso | delta v1 (remocao) | delta v2 | X ref | vitoria_base | vitoria_ref | bandeiras v1 -> v2 | avisos v2 |
|---|---|---|---|---|---|---|---|---|
| san1_sil_fio_de_barbeiro | 42% | +6.2 | +0.0 (sub) | 5 | 0.875 | 0.938 | - -> - | - |
| san1_sil_veneno_vermelho | 17% | +3.7 | -2.5 (sub) | 5 | 0.875 | 0.938 | - -> - | - |
| san1_sil_pe_de_pluma | 0% | +5.0 | +5.0 (rem) | - | 0.875 | - | uso_nao_medido -> - | uso_nao_medido,sem_referencia |
| san1_sil_olho_no_pulso | 16% | +3.7 | -2.5 (sub) | 5 | 0.875 | 0.938 | - -> - | - |
| san1_sil_estancar_calado | 17% | +5.0 | +0.0 (sub) | 7 | 0.875 | 0.925 | - -> - | - |
| san1_sil_marca_de_unha | 16% | +2.5 | -3.7 (sub) | 5 | 0.875 | 0.938 | - -> - | - |
| san1_sil_corte_sem_aviso | 46% | +13.8 | +0.0 (sub) | 8 | 0.537 | 0.675 | dominante -> - | - |
| san1_sil_ponto_cego | 12% | +5.0 | -8.8 (sub) | 8 | 0.537 | 0.675 | - -> - | - |
| san1_sil_arterial_fina | 26% | +11.2 | -3.7 (sub) | 8 | 0.613 | 0.762 | dominante -> - | - |
| san1_sil_silencio_cobrado | 42% | +7.5 | -8.8 (sub) | 9 | 0.613 | 0.775 | - -> - | - |
| san1_sil_cirurgia_sem_testemunha | 63% | -2.5 | -1.3 (sub) | 17 | 0.688 | 0.675 | dominante -> - | uso_alto |
| san1_sil_ultima_gota | 73% | +8.8 | +0.0 (sub) | 18 | 0.700 | 0.787 | dominante -> - | uso_alto |

### tronco

| Carta | uso | delta v1 (remocao) | delta v2 | X ref | vitoria_base | vitoria_ref | bandeiras v1 -> v2 | avisos v2 |
|---|---|---|---|---|---|---|---|---|
| arc1_tro_centelha_ressoante [calibrado] | 41% | +5.0 | -5.0 (sub) | 5 | 0.787 | 0.887 | - -> - | - |
| arc1_tro_centelha_ressoante [descoberto] | 21% | +5.0 | -2.5 (sub) | 5 | 0.738 | 0.812 | - -> - | - |
| arc1_tro_centelha_ressoante [improvisador] | 52% | +2.5 | -1.2 (sub) | 5 | 0.812 | 0.850 | - -> - | - |
| arc1_tro_marca_de_giz [calibrado] | 26% | +8.8 | +0.0 (sub) | 7 | 0.787 | 0.875 | dominante -> - | - |
| arc1_tro_marca_de_giz [descoberto] | 34% | +2.5 | -2.5 (sub) | 7 | 0.738 | 0.787 | - -> - | - |
| arc1_tro_marca_de_giz [improvisador] | 23% | +1.2 | +0.0 (sub) | 7 | 0.812 | 0.825 | - -> - | - |
| arc1_tro_lance_calculado [calibrado] | 35% | +6.2 | +0.0 (sub) | 11 | 0.362 | 0.425 | - -> - | - |
| arc1_tro_lance_calculado [descoberto] | 32% | +8.7 | -2.5 (sub) | 11 | 0.263 | 0.375 | dominante -> - | - |
| arc1_tro_lance_calculado [improvisador] | 31% | +20.0 | -1.2 (sub) | 11 | 0.300 | 0.512 | dominante -> - | - |
| arc1_tro_contrassinal [calibrado] | 76% | +5.0 | -5.0 (sub) | 5 | 0.787 | 0.887 | dominante -> - | uso_alto |
| arc1_tro_contrassinal [descoberto] | 67% | +3.7 | -3.7 (sub) | 5 | 0.738 | 0.812 | dominante -> - | uso_alto |
| arc1_tro_contrassinal [improvisador] | 69% | +0.0 | -3.7 (sub) | 5 | 0.812 | 0.850 | dominante -> - | uso_alto |
| cor1_tro_fresta_no_osso [biologia] | 31% | +3.7 | -6.2 (sub) | 6 | 0.750 | 0.850 | - -> - | - |
| cor1_tro_fresta_no_osso [alma] | 22% | -2.5 | -3.7 (sub) | 6 | 0.762 | 0.775 | - -> - | - |
| cor1_tro_fresta_no_osso [inorganica] | 46% | -5.0 | -11.2 (sub) | 6 | 0.787 | 0.850 | - -> - | - |
| cor1_tro_peso_na_alma [biologia] | 31% | +3.7 | -6.2 (sub) | 5 | 0.750 | 0.850 | - -> - | - |
| cor1_tro_peso_na_alma [alma] | 21% | +0.0 | +0.0 (sub) | 5 | 0.762 | 0.762 | - -> - | - |
| cor1_tro_peso_na_alma [inorganica] | 46% | -3.7 | -8.8 (sub) | 5 | 0.787 | 0.838 | - -> - | - |
| cor1_tro_sinal_do_abismo [biologia] | 31% | +3.7 | -6.2 (sub) | 6 | 0.750 | 0.850 | - -> - | - |
| cor1_tro_sinal_do_abismo [alma] | 22% | +0.0 | -1.3 (sub) | 6 | 0.762 | 0.775 | - -> - | - |
| cor1_tro_sinal_do_abismo [inorganica] | 46% | -5.0 | -11.2 (sub) | 6 | 0.787 | 0.850 | - -> - | - |
| dev1_tro_vigilia_de_cinza [consagrado] | 19% | +2.5 | +1.2 (sub) | 7 | 0.800 | 0.812 | - -> - | - |
| dev1_tro_vigilia_de_cinza [zeloso] | 16% | +10.0 | -2.5 (sub) | 7 | 0.700 | 0.825 | dominante -> - | - |
| dev1_tro_vigilia_de_cinza [enlutado] | 17% | -3.8 | -2.5 (sub) | 7 | 0.863 | 0.850 | - -> - | - |
| dev1_tro_palavra_que_corta [consagrado] | 68% | +5.0 | -2.5 (sub) | 5 | 0.800 | 0.875 | dominante -> - | uso_alto |
| dev1_tro_palavra_que_corta [zeloso] | 52% | +12.5 | -2.5 (sub) | 5 | 0.700 | 0.850 | dominante -> - | - |
| dev1_tro_palavra_que_corta [enlutado] | 48% | -1.3 | +0.0 (sub) | 5 | 0.863 | 0.850 | - -> - | - |
| dev1_tro_dedo_de_sentenca [consagrado] | 50% | -1.3 | -7.5 (sub) | 6 | 0.800 | 0.863 | - -> - | - |
| dev1_tro_dedo_de_sentenca [zeloso] | 45% | +8.8 | -3.7 (sub) | 6 | 0.700 | 0.825 | dominante -> - | - |
| dev1_tro_dedo_de_sentenca [enlutado] | 21% | -5.0 | -3.7 (sub) | 6 | 0.863 | 0.850 | - -> - | - |
| med1_tro_faixa_bem_dada [cirurgiao_trincheira] | 7% | -5.0 | +0.0 (sub) | 5 | 0.838 | 0.787 | - -> - | - |
| med1_tro_faixa_bem_dada [boticario] | 8% | +3.7 | +0.0 (sub) | 5 | 0.738 | 0.775 | - -> - | - |
| med1_tro_faixa_bem_dada [cirurgiao_ferro] | 7% | +5.0 | -2.5 (sub) | 5 | 0.725 | 0.800 | - -> - | - |
| med1_tro_dose_de_torpor [cirurgiao_trincheira] | 49% | -2.5 | -10.0 (sub) | 6 | 0.838 | 0.912 | - -> - | - |
| med1_tro_dose_de_torpor [boticario] | 43% | +2.5 | -3.8 (sub) | 6 | 0.738 | 0.800 | - -> - | - |
| med1_tro_dose_de_torpor [cirurgiao_ferro] | 40% | +3.7 | -7.5 (sub) | 6 | 0.725 | 0.838 | - -> - | - |
| med1_tro_plantao_curto [cirurgiao_trincheira] | 41% | -6.2 | -3.7 (sub) | 7 | 0.838 | 0.812 | - -> - | - |
| med1_tro_plantao_curto [boticario] | 45% | +6.2 | +0.0 (sub) | 7 | 0.738 | 0.800 | - -> - | - |
| med1_tro_plantao_curto [cirurgiao_ferro] | 36% | +6.2 | -2.5 (sub) | 7 | 0.725 | 0.812 | - -> - | - |
| san1_tro_corte_de_penitencia [exposto] | 77% | +3.7 | +1.2 (sub) | 6 | 0.812 | 0.838 | dominante -> - | uso_alto |
| san1_tro_corte_de_penitencia [avaro] | 59% | -2.5 | -2.5 (sub) | 6 | 0.900 | 0.900 | - -> - | - |
| san1_tro_corte_de_penitencia [silencioso] | 72% | -1.2 | -3.7 (sub) | 6 | 0.887 | 0.912 | dominante -> - | uso_alto |
| san1_tro_veia_aberta [exposto] | 33% | +1.2 | -7.5 (sub) | 6 | 0.812 | 0.900 | - -> - | - |
| san1_tro_veia_aberta [avaro] | 18% | -3.7 | -6.2 (sub) | 6 | 0.900 | 0.925 | - -> - | - |
| san1_tro_veia_aberta [silencioso] | 31% | +3.8 | -1.2 (sub) | 6 | 0.887 | 0.938 | - -> - | - |
| san1_tro_eco_de_ferida [exposto] | 63% | +5.0 | +0.0 (sub) | 6 | 0.812 | 0.863 | dominante -> - | uso_alto |
| san1_tro_eco_de_ferida [avaro] | 37% | +0.0 | -1.2 (sub) | 6 | 0.900 | 0.912 | - -> - | - |
| san1_tro_eco_de_ferida [silencioso] | 43% | +3.8 | +0.0 (sub) | 6 | 0.887 | 0.925 | - -> - | - |

### neutras

| Carta | uso | delta v1 (remocao) | delta v2 | X ref | vitoria_base | vitoria_ref | bandeiras v1 -> v2 | avisos v2 |
|---|---|---|---|---|---|---|---|---|
| neu1_na_espada_da_legiao [devoto] | 71% | +1.2 | +0.0 (sub) | 5 | 0.800 | 0.812 | dominante -> - | uso_alto |
| neu1_na_espada_da_legiao [arcanista] | 72% | +5.0 | +1.3 (sub) | 5 | 0.787 | 0.825 | dominante -> - | uso_alto |
| neu1_na_fuligem_das_chamines [devoto] | 66% | +1.2 | +0.0 (sub) | 5 | 0.800 | 0.812 | dominante -> - | uso_alto |
| neu1_na_fuligem_das_chamines [arcanista] | 70% | +0.0 | -7.5 (sub) | 5 | 0.787 | 0.863 | dominante -> - | uso_alto |
| neu1_na_gazua_dos_telhados [devoto] | 71% | +3.7 | +1.3 (sub) | 6 | 0.800 | 0.825 | dominante -> - | uso_alto |
| neu1_na_gazua_dos_telhados [arcanista] | 72% | +2.5 | -5.0 (sub) | 6 | 0.787 | 0.863 | dominante -> - | uso_alto |
| neu1_na_salvo_conduto_falso [devoto] | 65% | +1.2 | +0.0 (sub) | 5 | 0.800 | 0.812 | dominante -> - | uso_alto |
| neu1_na_salvo_conduto_falso [arcanista] | 71% | +5.0 | -2.5 (sub) | 5 | 0.787 | 0.863 | dominante -> - | uso_alto |
| neu1_na_selo_da_legiao [devoto] | 23% | +3.8 | -1.2 (sub) | 11 | 0.575 | 0.625 | - -> - | - |
| neu1_na_selo_da_legiao [arcanista] | 36% | +3.8 | -2.5 (sub) | 11 | 0.362 | 0.425 | - -> - | - |
| neu1_na_elixir_do_doutor_vane [devoto] | 14% | +2.5 | -1.2 (sub) | 8 | 0.838 | 0.875 | - -> - | - |
| neu1_na_elixir_do_doutor_vane [arcanista] | 33% | +5.0 | -6.2 (sub) | 8 | 0.575 | 0.688 | - -> - | - |
| neu1_na_lembranca_do_aco [devoto] | 19% | -1.2 | -5.0 (sub) | 17 | 0.825 | 0.863 | - -> - | - |
| neu1_na_lembranca_do_aco [arcanista] | 43% | -5.0 | +0.0 (sub) | 17 | 0.725 | 0.675 | - -> - | - |
| neu1_er_lanca_de_gancho [devoto] | 22% | +0.0 | -1.2 (sub) | 5 | 0.800 | 0.812 | - -> - | - |
| neu1_er_lanca_de_gancho [arcanista] | 18% | +1.3 | -2.5 (sub) | 5 | 0.787 | 0.825 | - -> - | - |
| neu1_er_traje_branco [devoto] | 20% | +5.0 | +0.0 (sub) | 7 | 0.800 | 0.850 | - -> - | - |
| neu1_er_traje_branco [arcanista] | 16% | +3.7 | -1.3 (sub) | 7 | 0.787 | 0.838 | - -> - | - |
| neu1_er_aguardente_de_liquen [devoto] | 11% | +5.0 | -2.5 (sub) | 6 | 0.800 | 0.875 | - -> - | - |
| neu1_er_aguardente_de_liquen [arcanista] | 6% | +3.7 | -2.5 (sub) | 6 | 0.787 | 0.850 | - -> - | - |
| neu1_er_luvas_de_veia_de_calor [devoto] | 8% | +1.2 | -3.7 (sub) | 7 | 0.800 | 0.850 | - -> - | - |
| neu1_er_luvas_de_veia_de_calor [arcanista] | 8% | +3.7 | -1.3 (sub) | 7 | 0.787 | 0.838 | - -> - | - |
| neu1_er_emboscada_dos_renegados [devoto] | 42% | +5.0 | +0.0 (sub) | 8 | 0.575 | 0.625 | - -> - | - |
| neu1_er_emboscada_dos_renegados [arcanista] | 43% | +10.0 | -6.2 (sub) | 8 | 0.362 | 0.525 | dominante -> - | - |
| neu1_er_machado_de_vorr [devoto] | 61% | -3.7 | -1.2 (sub) | 9 | 0.838 | 0.812 | dominante -> - | uso_alto |
| neu1_er_machado_de_vorr [arcanista] | 48% | +0.0 | -2.5 (sub) | 9 | 0.575 | 0.600 | - -> - | - |
| neu1_er_cerco_do_branco [devoto] | 18% | -3.8 | -3.8 (sub) | 18 | 0.800 | 0.800 | - -> - | - |
| neu1_er_cerco_do_branco [arcanista] | 46% | +3.7 | -1.2 (sub) | 18 | 0.738 | 0.787 | - -> - | - |
| neu1_br_sabre_de_pirata [devoto] | 68% | +0.0 | +0.0 (sub) | 5 | 0.800 | 0.800 | dominante -> - | uso_alto |
| neu1_br_sabre_de_pirata [arcanista] | 73% | +5.0 | +1.3 (sub) | 5 | 0.787 | 0.825 | dominante -> - | uso_alto |
| neu1_br_grogue_do_porto [devoto] | 73% | +2.5 | -1.3 (sub) | 7 | 0.800 | 0.838 | dominante -> - | uso_alto |
| neu1_br_grogue_do_porto [arcanista] | 73% | +5.0 | -3.7 (sub) | 7 | 0.787 | 0.875 | dominante -> - | uso_alto |
| neu1_br_tinta_de_polvo [devoto] | 22% | -1.3 | -1.3 (sub) | 6 | 0.800 | 0.800 | - -> - | - |
| neu1_br_tinta_de_polvo [arcanista] | 18% | +2.5 | -2.5 (sub) | 6 | 0.787 | 0.838 | - -> - | - |
| neu1_br_madeira_de_naufragio [devoto] | 20% | +5.0 | +0.0 (sub) | 7 | 0.800 | 0.850 | - -> - | - |
| neu1_br_madeira_de_naufragio [arcanista] | 16% | +3.7 | -1.3 (sub) | 7 | 0.787 | 0.838 | - -> - | - |
| neu1_br_arpao_de_osso [devoto] | 56% | +5.0 | -5.0 (sub) | 9 | 0.575 | 0.675 | - -> - | - |
| neu1_br_arpao_de_osso [arcanista] | 51% | +8.8 | -6.2 (sub) | 9 | 0.362 | 0.512 | dominante -> - | - |
| neu1_br_doce_de_mare [devoto] | 14% | +1.2 | -2.5 (sub) | 9 | 0.838 | 0.875 | - -> - | - |
| neu1_br_doce_de_mare [arcanista] | 33% | +5.0 | -7.5 (sub) | 9 | 0.575 | 0.700 | - -> - | - |
| neu1_br_pistola_de_pederneira [devoto] | 19% | -1.2 | -3.7 (sub) | 18 | 0.825 | 0.850 | - -> - | - |
| neu1_br_pistola_de_pederneira [arcanista] | 43% | -5.0 | -5.0 (sub) | 18 | 0.725 | 0.725 | - -> - | - |
| neu1_ka_residuo_sanguineo [devoto] | 23% | +0.0 | +0.0 (sub) | 5 | 0.800 | 0.800 | - -> - | - |
| neu1_ka_residuo_sanguineo [arcanista] | 18% | +2.5 | -2.5 (sub) | 5 | 0.787 | 0.838 | - -> - | - |
| neu1_ka_divida_gravada [devoto] | 22% | -2.5 | -2.5 (sub) | 5 | 0.800 | 0.800 | - -> - | - |
| neu1_ka_divida_gravada [arcanista] | 18% | +1.3 | -2.5 (sub) | 5 | 0.787 | 0.825 | - -> - | - |
| neu1_ka_guarda_de_sangue [devoto] | 25% | +5.0 | +0.0 (sub) | 11 | 0.575 | 0.625 | - -> - | - |
| neu1_ka_guarda_de_sangue [arcanista] | 38% | +2.5 | -3.7 (sub) | 11 | 0.362 | 0.425 | - -> - | - |
| neu1_ka_equilibrio_de_kahen [devoto] | 30% | -3.8 | -2.5 (sub) | 22 | 0.800 | 0.787 | - -> - | - |
| neu1_ka_equilibrio_de_kahen [arcanista] | 12% | +5.0 | +0.0 (sub) | 22 | 0.738 | 0.787 | - -> - | - |
| neu1_ka_xadrez_com_lyss [devoto] | 16% | +1.2 | +0.0 (sub) | 24 | 0.863 | 0.875 | - -> - | - |
| neu1_ka_xadrez_com_lyss [arcanista] | 21% | +3.7 | +1.3 (sub) | 24 | 0.675 | 0.700 | - -> - | - |
| neu1_sb_pedagio_de_sangue [devoto] | 73% | +1.2 | +0.0 (sub) | 5 | 0.800 | 0.812 | dominante -> - | uso_alto |
| neu1_sb_pedagio_de_sangue [arcanista] | 74% | +2.5 | -1.2 (sub) | 5 | 0.787 | 0.825 | dominante -> - | uso_alto |
| neu1_sb_martelo_de_guerra_anao [devoto] | 52% | -1.3 | +0.0 (sub) | 10 | 0.800 | 0.787 | - -> - | - |
| neu1_sb_martelo_de_guerra_anao [arcanista] | 66% | +0.0 | +0.0 (sub) | 10 | 0.787 | 0.787 | dominante -> - | uso_alto |
| neu1_sb_corda_de_aranha [devoto] | 69% | +3.7 | +0.0 (sub) | 7 | 0.800 | 0.838 | dominante -> - | uso_alto |
| neu1_sb_corda_de_aranha [arcanista] | 70% | +3.7 | -5.0 (sub) | 7 | 0.787 | 0.875 | dominante -> - | uso_alto |
| neu1_sb_emboscada_de_gruumsha [devoto] | 31% | +5.0 | -2.5 (sub) | 8 | 0.575 | 0.650 | - -> - | - |
| neu1_sb_emboscada_de_gruumsha [arcanista] | 43% | +7.5 | -5.0 (sub) | 8 | 0.362 | 0.487 | - -> - | - |
| neu1_sb_pavor_do_fundo [devoto] | 32% | -3.7 | +1.3 (sub) | 9 | 0.838 | 0.787 | - -> - | - |
| neu1_sb_pavor_do_fundo [arcanista] | 25% | +3.8 | -1.2 (sub) | 9 | 0.575 | 0.625 | - -> - | - |
| neu1_sb_reliquia_arma_ana [devoto] | 19% | -1.2 | -5.0 (sub) | 18 | 0.825 | 0.863 | - -> - | - |
| neu1_sb_reliquia_arma_ana [arcanista] | 43% | -6.2 | -3.7 (sub) | 18 | 0.725 | 0.700 | - -> - | - |
| neu1_ge_lanterna_de_aranha [devoto] | 24% | -1.3 | -3.7 (sub) | 3 | 0.800 | 0.825 | - -> - | - |
| neu1_ge_lanterna_de_aranha [arcanista] | 22% | +1.3 | -3.7 (sub) | 3 | 0.787 | 0.838 | - -> - | - |
| neu1_ge_talisma_de_lebre [devoto] | 0% | +1.2 | +1.2 (rem) | - | 0.800 | - | uso_nao_medido -> - | uso_nao_medido,sem_referencia |
| neu1_ge_talisma_de_lebre [arcanista] | 0% | +3.7 | +3.7 (rem) | - | 0.787 | - | uso_nao_medido -> - | uso_nao_medido,sem_referencia |
| neu1_ge_flecha_de_cristal [devoto] | 22% | +0.0 | +0.0 (sub) | 5 | 0.800 | 0.800 | - -> - | - |
| neu1_ge_flecha_de_cristal [arcanista] | 18% | +1.3 | -2.5 (sub) | 5 | 0.787 | 0.825 | - -> - | - |
| neu1_ge_nectar_da_furia [devoto] | 57% | +5.0 | -5.0 (sub) | 11 | 0.575 | 0.675 | - -> - | - |
| neu1_ge_nectar_da_furia [arcanista] | 62% | +6.2 | -2.5 (sub) | 11 | 0.362 | 0.450 | dominante -> - | uso_alto |
| neu1_ge_armadura_de_quitina [devoto] | 36% | -2.5 | -1.2 (sub) | 11 | 0.838 | 0.825 | - -> - | - |
| neu1_ge_armadura_de_quitina [arcanista] | 36% | +5.0 | +1.2 (sub) | 11 | 0.575 | 0.613 | - -> - | - |
| neu1_ge_cataplasma_de_resina [devoto] | 14% | +3.8 | -6.2 (sub) | 8 | 0.575 | 0.675 | - -> - | - |
| neu1_ge_cataplasma_de_resina [arcanista] | 14% | +6.2 | -5.0 (sub) | 8 | 0.362 | 0.475 | - -> - | - |
| neu1_ge_lamina_de_vidro_negro [devoto] | 18% | -2.5 | -1.2 (sub) | 18 | 0.800 | 0.787 | - -> - | - |
| neu1_ge_lamina_de_vidro_negro [arcanista] | 46% | +5.0 | +0.0 (sub) | 18 | 0.738 | 0.787 | - -> - | - |
| neu1_ge_ampulheta_de_vaelorn [devoto] | 16% | +2.5 | +0.0 (sub) | 19 | 0.863 | 0.887 | - -> - | - |
| neu1_ge_ampulheta_de_vaelorn [arcanista] | 23% | +8.7 | +0.0 (sub) | 19 | 0.675 | 0.762 | dominante -> - | - |

## 6. Limitacoes

- [F] Reacoes, passivas, virtudes e utilitarias nao tem referencia: ficam com delta por remocao e aviso `sem_referencia` (o bot nao as declara).
- [F] "Outro suporte" (purga, ganhar Folego etc.) usa referencia de `protecao` (D3): o delta dessas Cartas mede suporte contra protecao, nao contra um efeito equivalente.
- [F] A referencia e uma Carta de efeito unico no ponto medio da faixa; Cartas com varios efeitos (area, Chamado, Torpor...) so tem o efeito principal comparado.
- [H] Uma Carta no topo da faixa de orcamento tera delta positivo legitimo; o v2 mede poder acima do esperado para o custo, nao ausencia de poder.
- [F] Nenhuma Carta foi alterada; as divergencias e os `dominante` do v2 sao apenas candidatas a uma spec de balanco futura.

