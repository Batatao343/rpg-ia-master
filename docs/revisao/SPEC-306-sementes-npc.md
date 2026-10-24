# SPEC-306 - Revisão das sementes de NPC

> Gerado por `scripts/npc_seed_review.py build` a partir de `data/npc_seed_tables.json`. **Não edite à mão.**
> Versão das tabelas: 2.

Marque `[x]` o que aprova e anote o que deve mudar. Para aprovar: diga "aprovo as sementes" (ou a lista de ids) e o coordenador roda `npc_seed_review.py approve`. Ids recusados são reescritos, nunca apagados.

## Totais

| Tabela | Total | Pendentes | universais | regionais | raça | facção |
|---|---|---|---|---|---|---|
| professions | 61 | 25 | 18 | 31 | 8 | 4 |
| desires | 45 | 25 | 22 | 14 | 7 | 2 |
| fears | 45 | 25 | 21 | 17 | 6 | 1 |
| secrets | 44 | 25 | 21 | 17 | 3 | 3 |
| contradictions | 42 | 25 | 25 | 10 | 6 | 1 |
| mannerisms | 45 | 25 | 23 | 14 | 7 | 1 |

## Cobertura regional (linhas sem facção por região)

| Região | professions | desires | fears | secrets | contradictions | mannerisms |
|---|---|---|---|---|---|---|
| Nova Arcádia | 3 | 2 | 2 | 3 | 1 | 1 |
| Pântano da Melancolia | 3 | 2 | 2 | 2 | 1 | 1 |
| Deserto de Zhur | 3 | 2 | 2 | 2 | 1 | 1 |
| Floresta dos Sussurros | 3 | 2 | 2 | 2 | 1 | 1 |
| Selva de Xylos | 3 | 2 | 2 | 2 | 1 | 1 |
| Skallgard | 3 | 2 | 2 | 2 | 1 | 1 |
| Aethelgard | 3 | 2 | 2 | 2 | 1 | 1 |
| Ophidia | 3 | 2 | 2 | 2 | 1 | 1 |
| Costa Negra | 3 | 2 | 2 | 2 | 1 | 1 |
| Montanhas Afiadas | 3 | 2 | 2 | 2 | 0 | 2 |
| Pradaria das Ruínas | 3 | 2 | 2 | 2 | 0 | 2 |
| Brekmar | 4 | 2 | 2 | 2 | 1 | 1 |

## professions - pendentes de leitura (25)

| OK | id | rótulo | filtros | fonte |
|---|---|---|---|---|
| [ ] | `prof_parteira_de_favores` | parteira que cobra em favores | universal | `lore_nova/daily_life.txt:71` |
| [ ] | `prof_criado_de_casa_rica` | criado de casa abastada | universal | `lore_nova/daily_life.txt:39` |
| [ ] | `prof_vendedor_de_raizes` | vendedor de raízes em carrinho de duas rodas | universal | `lore_nova/daily_life.txt:133` |
| [ ] | `prof_guarda_de_familia` | guarda pessoal de família rica | universal | `lore_nova/daily_life.txt:163` |
| [ ] | `prof_recolhedor_de_corpos` | recolhedor de corpos para o crematório | universal | `lore_nova/daily_life.txt:147` |
| [ ] | `prof_catador_de_metal` | catador de metal e pregos tortos | universal | `lore_nova/daily_life.txt:27` |
| [ ] | `prof_lavador_de_roupa` | lavador de roupa do bairro das fundições | regiões: Nova Arcádia | `lore_nova/daily_life.txt:100` |
| [ ] | `prof_medidor_de_borda` | medidor de borda com estacas e cordão | regiões: Pântano da Melancolia | `lore_nova/locations.txt:111` |
| [ ] | `prof_guia_noturno` | guia noturno de travessias pelo mar de vidro | regiões: Deserto de Zhur | `lore_nova/daily_life.txt:281` |
| [ ] | `prof_colhedor_de_fungos` | colhedor de fungos vermelhos da mata | regiões: Floresta dos Sussurros | `lore_nova/locations.txt:150` |
| [ ] | `prof_cacador_de_espinhos` | caçador de feras de espinhos de osso | regiões: Floresta dos Sussurros | `lore_nova/locations.txt:148` |
| [ ] | `prof_carregador_de_copas` | carregador de cordas e pontes das copas | regiões: Selva de Xylos | `lore_nova/locations.txt:201` |
| [ ] | `prof_cacador_de_caribu` | caçador de caribu-cinza do ermo | regiões: Skallgard | `lore_nova/daily_life.txt:197` |
| [ ] | `prof_leitor_de_cristais` | leitor de cristais e fios numa câmara de escuta | regiões: Skallgard | `lore_nova/daily_life.txt:209` |
| [ ] | `prof_pescador_do_lago` | pescador de peixes de escamas luminosas | regiões: Aethelgard | `lore_nova/locations.txt:246` |
| [ ] | `prof_barqueiro_do_lago` | barqueiro das bordas cristalinas do lago | regiões: Aethelgard | `lore_nova/locations.txt:241` |
| [ ] | `prof_comprador_de_relatos` | comprador de relatos sobre ilhas distantes | regiões: Ophidia, Brekmar | `lore_nova/locations.txt:293` |
| [ ] | `prof_capitao_endividado` | capitão endividado que aceita rotas perto de ilhas proibidas | regiões: Ophidia | `lore_nova/locations.txt:291` |
| [ ] | `prof_vendedor_de_altitude` | vendedor de equipamento de altitude | regiões: Montanhas Afiadas | `lore_nova/locations.txt:355` |
| [ ] | `prof_pastor_de_auroques` | pastor de auroques entre as ruínas | regiões: Pradaria das Ruínas | `lore_nova/daily_life.txt:235` |
| [ ] | `prof_andarilho_remendeiro` | andarilho que vive de consertos de tenda e cordame | raças: Humano | `lore_nova/races.txt:349` |
| [ ] | `prof_escriturario_de_bordo` | escriturário de bordo que registra cada decisão em protocolo | raças: Anão da Fuligem | `lore_nova/races.txt:124` |
| [ ] | `prof_tatuador_de_rotas` | tatuador de mapas de rota na pele | raças: Cinzéu | `lore_nova/daily_life.txt:221` |
| [ ] | `prof_carregador_de_contrabando` | carregador de contrabando entre os anéis | regiões: Nova Arcádia; facções: A Mão Sombria | `lore_nova/factions.txt:47` |
| [ ] | `prof_preparador_do_cha` | preparador do chá que atenua a praga | regiões: Pântano da Melancolia; facções: Os Druidas do Ciclo Cinzento | `lore_nova/locations.txt:114` |

## desires - pendentes de leitura (25)

| OK | id | rótulo | filtros | fonte |
|---|---|---|---|---|
| [ ] | `des_tirar_parente` | tirar um parente de um trabalho que o está consumindo | universal | `lore_nova/daily_life.txt:45` |
| [ ] | `des_casa_de_pedra` | ter uma casa de pedra para chamar de sua | universal | `lore_nova/daily_life.txt:23` |
| [ ] | `des_ser_chamado_pelo_nome` | ser chamado pelo nome por alguém que importa | universal | `lore_nova/daily_life.txt:165` |
| [ ] | `des_curar_quem_ninguem` | ter recursos para curar quem ninguém cura | universal | `lore_nova/daily_life.txt:79` |
| [ ] | `des_filhos_longe` | ver os filhos longe do trabalho que lhe feriu as mãos | universal | `lore_nova/daily_life.txt:109` |
| [ ] | `des_mesa_dos_ricos` | ser recebido à mesa dos que hoje o desprezam | universal | `lore_nova/daily_life.txt:89` |
| [ ] | `des_largar_o_vicio` | largar o vício antes do próximo inverno | universal | `lore_nova/daily_life.txt:179` |
| [ ] | `des_tripulacao_de_antes` | voltar a navegar com a tripulação de antes | universal | `lore_nova/daily_life.txt:257` |
| [ ] | `des_oficio_que_constroi` | trocar o posto vigiado por um ofício que construa algo | universal | `lore_nova/daily_life.txt:63` |
| [ ] | `des_achar_fonte` | achar uma fonte que dure mais de uma estação | regiões: Deserto de Zhur | `lore_nova/daily_life.txt:283` |
| [ ] | `des_ler_miragens` | provar que sabe ler as miragens e salvar um forasteiro | regiões: Deserto de Zhur | `lore_nova/locations.txt:129` |
| [ ] | `des_provar_ophidia` | provar a quem duvida que veio mesmo de Ophidia | regiões: Ophidia | `data/origins.json:126` |
| [ ] | `des_mapa_que_se_repita` | traçar um mapa de Ophidia que seja o mesmo em dois dias | regiões: Ophidia | `lore_nova/locations.txt:283` |
| [ ] | `des_ambar_suficiente` | juntar âmbar cinza o bastante para nunca mais entrar numa carcaça | regiões: Costa Negra | `lore_nova/locations.txt:327` |
| [ ] | `des_nome_no_cais` | fazer-se um nome no cais que valha mais que dinheiro | regiões: Brekmar | `lore_nova/locations.txt:447` |
| [ ] | `des_planta_no_pantano` | plantar algo que cresça no pântano sem ser tragado | regiões: Pântano da Melancolia | `lore_nova/locations.txt:111` |
| [ ] | `des_viver_nas_copas` | trocar a vida no chão pela vida nas copas | regiões: Selva de Xylos | `lore_nova/locations.txt:201` |
| [ ] | `des_aceito_pelos_clas` | ser aceito entre os clãs tecnológicos mesmo vindo de fora | regiões: Skallgard | `lore_nova/locations.txt:223` |
| [ ] | `des_mergulhar_fundo` | mergulhar mais fundo que qualquer outro e voltar para contar | regiões: Aethelgard | `lore_nova/locations.txt:239` |
| [ ] | `des_passagem_segura` | abrir uma passagem segura que dure uma estação inteira | regiões: Montanhas Afiadas | `lore_nova/locations.txt:353` |
| [ ] | `des_osshari_cacada` | liderar a próxima grande caçada do vilarejo | regiões: Costa Negra; raças: Osshari | `lore_nova/races.txt:296` |
| [ ] | `des_vrel_navio_proprio` | comandar um navio afinado só com a própria tripulação | regiões: Brekmar; raças: Vrel | `lore_nova/races.txt:185` |
| [ ] | `des_elfo_memorias` | gravar numa cidade élfica as memórias de quem partiu | regiões: Pradaria das Ruínas; raças: Elfo | `lore_nova/locations.txt:386` |
| [ ] | `des_registros_do_reino` | recuperar os registros perdidos do reino antes de morrer | regiões: Montanhas Afiadas; facções: Os Últimos Anões do Reino | `lore_nova/factions.txt:418` |
| [ ] | `des_nome_na_parede` | ter o nome gravado entre os que alimentaram a cidade | regiões: Skallgard; facções: Os Clãs de Combate de Skallgard | `lore_nova/factions.txt:160` |

## fears - pendentes de leitura (25)

| OK | id | rótulo | filtros | fonte |
|---|---|---|---|---|
| [ ] | `fear_batida_na_porta` | uma batida na porta de madrugada | universal | `lore_nova/daily_life.txt:137` |
| [ ] | `fear_perder_sustento` | ficar sem forças para trabalhar e perder o sustento | universal | `lore_nova/daily_life.txt:109` |
| [ ] | `fear_perder_filho` | perder alguém por falta de remédio | universal | `lore_nova/daily_life.txt:77` |
| [ ] | `fear_mentira_antiga` | ser desmascarado por uma mentira antiga | universal | `lore_nova/daily_life.txt:89` |
| [ ] | `fear_preco_da_comida` | o dia em que a comida subir mais que o ganho | universal | `lore_nova/daily_life.txt:139` |
| [ ] | `fear_esquecer_o_rosto` | esquecer o próprio rosto aos poucos | universal | `lore_nova/daily_life.txt:91` |
| [ ] | `fear_ser_numero` | virar apenas um número aos olhos de quem o emprega | universal | `lore_nova/daily_life.txt:165` |
| [ ] | `fear_ficar_para_tras` | ficar para trás quando todos partem | universal | `lore_nova/daily_life.txt:23` |
| [ ] | `fear_fora_das_muralhas` | ser empurrado para fora das muralhas | regiões: Nova Arcádia | `lore_nova/locations.txt:17` |
| [ ] | `fear_parar_de_andar` | perder a vontade de continuar andando | regiões: Pântano da Melancolia | `lore_nova/locations.txt:101` |
| [ ] | `fear_tempestade_navalha` | ser pego pelas tempestades de navalha em campo aberto | regiões: Deserto de Zhur | `lore_nova/locations.txt:127` |
| [ ] | `fear_silencio_escolhe` | o silêncio que parece escolher quem vai ouvir | regiões: Floresta dos Sussurros | `lore_nova/locations.txt:146` |
| [ ] | `fear_raizes_nos_pes` | parar num ponto e sentir raízes subindo pelos pés | regiões: Selva de Xylos | `lore_nova/locations.txt:171` |
| [ ] | `fear_ser_forasteiro` | ser tratado como forasteiro pelos que considera seus | regiões: Skallgard | `lore_nova/locations.txt:223` |
| [ ] | `fear_afogado_repete` | ver um afogado repetir o caminho que fazia em vida | regiões: Aethelgard | `lore_nova/locations.txt:248` |
| [ ] | `fear_conhecer_de_ophidia` | encontrar alguém que de fato veio de Ophidia | regiões: Ophidia | `data/origins.json:126` |
| [ ] | `fear_gas_nas_ossadas` | o gás das ossadas que acende ao menor ruído | regiões: Costa Negra | `lore_nova/daily_life.txt:305` |
| [ ] | `fear_sem_equipamento` | ficar sem equipamento acima das passagens | regiões: Montanhas Afiadas | `lore_nova/locations.txt:355` |
| [ ] | `fear_luzes_nas_ruinas` | as luzes que se movem entre as ruínas ao anoitecer | regiões: Pradaria das Ruínas | `lore_nova/daily_life.txt:237` |
| [ ] | `fear_nome_sujo` | ser conhecido como quem não paga o que deve | regiões: Brekmar | `lore_nova/locations.txt:447` |
| [ ] | `fear_anao_sem_protocolo` | agir sem protocolo e causar um erro sem volta | raças: Anão da Fuligem | `lore_nova/races.txt:116` |
| [ ] | `fear_vrel_memoria` | acordar sem saber qual das memórias é a sua | raças: Vrel | `lore_nova/races.txt:176` |
| [ ] | `fear_osshari_trono` | o grande crânio que ainda não terminou de morrer | regiões: Costa Negra; raças: Osshari | `lore_nova/locations.txt:338` |
| [ ] | `fear_humano_sem_lugar` | não ter um lugar que seja seu por origem | raças: Humano | `lore_nova/races.txt:320` |
| [ ] | `fear_estacas_arrancadas` | encontrar as estacas de medição arrancadas pela manhã | regiões: Pântano da Melancolia; facções: Os Druidas do Ciclo Cinzento | `lore_nova/factions.txt:459` |

## secrets - pendentes de leitura (25)

| OK | id | rótulo | filtros | fonte |
|---|---|---|---|---|
| [ ] | `sec_paga_calar` | paga todo mês a alguém que sabe o que ele fez | universal | `lore_nova/daily_life.txt:89` |
| [ ] | `sec_id_de_morto` | carrega a identificação de um morto para passar pelos portões | universal | `lore_nova/locations.txt:19` |
| [ ] | `sec_fica_com_objetos` | fica com objetos dos mortos que deveria declarar | universal | `lore_nova/daily_life.txt:153` |
| [ ] | `sec_sustenta_irmao` | divide a própria ração com um parente doente e esconde isso | universal | `lore_nova/daily_life.txt:23` |
| [ ] | `sec_dilui_mercadoria` | dilui o que vende para esticar o lucro | universal | `lore_nova/daily_life.txt:133` |
| [ ] | `sec_perdeu_quem_salvaria` | perdeu quem poderia ter salvado e nunca conta a ninguém | universal | `lore_nova/daily_life.txt:77` |
| [ ] | `sec_recebeu_para_calar` | recebeu pagamento para calar sobre um crime que testemunhou | universal | `lore_nova/daily_life.txt:59` |
| [ ] | `sec_cha_em_excesso` | toma o chá dos druidas além da dose e diz que é por causa da tosse | regiões: Pântano da Melancolia | `lore_nova/locations.txt:114` |
| [ ] | `sec_vende_espolio` | vende armas do espólio da guerra como se fossem herança de família | regiões: Pântano da Melancolia | `lore_nova/locations.txt:116` |
| [ ] | `sec_frasco_de_agua` | guarda um frasco de água que nunca dividiu com a caravana | regiões: Deserto de Zhur | `lore_nova/daily_life.txt:283` |
| [ ] | `sec_seguiu_miragem` | seguiu por um trecho o rosto de um parente morto na miragem | regiões: Deserto de Zhur | `lore_nova/daily_life.txt:285` |
| [ ] | `sec_fungo_vermelho` | usa o fungo vermelho da mata e esconde a dependência | regiões: Floresta dos Sussurros | `lore_nova/locations.txt:150` |
| [ ] | `sec_planta_proibida` | colhe em segredo uma planta proibida e vende a quem não pergunta | regiões: Floresta dos Sussurros, Selva de Xylos | `lore_nova/locations.txt:192` |
| [ ] | `sec_raiz_no_corpo` | esconde sob a roupa uma raiz que começou a crescer quando parou demais | regiões: Selva de Xylos | `lore_nova/locations.txt:171` |
| [ ] | `sec_ficha_falsa` | guarda uma ficha de quota falsificada para não passar fome | regiões: Skallgard | `lore_nova/daily_life.txt:201` |
| [ ] | `sec_cristal_nao_declarado` | guarda um cristal tirado das ruínas submersas e nunca o declarou | regiões: Aethelgard | `lore_nova/daily_life.txt:297` |
| [ ] | `sec_caminho_seco` | conhece o caminho seco até as ruínas e nega a quem pergunta | regiões: Aethelgard | `lore_nova/locations.txt:253` |
| [ ] | `sec_origem_inventada` | nunca esteve em Ophidia e inventou a origem para ser levado a sério | regiões: Ophidia | `data/origins.json:126` |
| [ ] | `sec_vende_atalhos` | se faz passar por guia Cinzéu sem nunca ter atravessado as montanhas | regiões: Montanhas Afiadas | `lore_nova/locations.txt:357` |
| [ ] | `sec_nome_do_espectro` | reconheceu um espectro das ruínas e nunca contou à família | regiões: Pradaria das Ruínas | `lore_nova/locations.txt:405` |
| [ ] | `sec_elfo_ampulheta` | sabe que a ampulheta está quase no fim e escondeu isso da família | regiões: Pradaria das Ruínas; raças: Elfo | `lore_nova/factions.txt:323` |
| [ ] | `sec_osshari_finge` | finge sentir o êxtase da caçada que o seu povo exibe | regiões: Costa Negra; raças: Osshari | `lore_nova/races.txt:289` |
| [ ] | `sec_legiao_ficha` | falsificou uma ficha de prisão para poupar um conhecido | regiões: Nova Arcádia; facções: A Legião de Ferro | `lore_nova/factions.txt:20` |
| [ ] | `sec_mao_vende_rede` | vende em segredo informações da rede em que trabalha | regiões: Nova Arcádia; facções: A Mão Sombria | `lore_nova/factions.txt:47` |
| [ ] | `sec_deve_ao_navio` | deve uma decisão ao navio das docas centrais e ainda não pagou | regiões: Brekmar; facções: O Poder de Kahen | `lore_nova/locations.txt:431` |

## contradictions - pendentes de leitura (25)

| OK | id | rótulo | filtros | fonte |
|---|---|---|---|---|
| [ ] | `con_cobra_mas_perdoa` | cobra cada favor que faz, mas perdoa promessas que sabe vazias | universal | `lore_nova/daily_life.txt:71` |
| [ ] | `con_obediente_rebelde` | obediente no serviço, rebelde apenas nos pensamentos | universal | `lore_nova/daily_life.txt:45` |
| [ ] | `con_relaxado_atento` | relaxado à vista de todos, atento a cada detalhe que ninguém notou | universal | `lore_nova/daily_life.txt:59` |
| [ ] | `con_sorri_e_deve` | sorri a quem lhe deve e evita quem ele próprio deve | universal | `lore_nova/daily_life.txt:89` |
| [ ] | `con_pergunta_tudo_menos` | pergunta sobre tudo, menos sobre o que preferiria não saber | universal | `lore_nova/daily_life.txt:107` |
| [ ] | `con_respeita_cobra` | trata os mortos com respeito e cobra taxa por cada objeto | universal | `lore_nova/daily_life.txt:153` |
| [ ] | `con_nome_e_numero` | aceita ser chamado por número, mas guarda o nome de cada protegido | universal | `lore_nova/daily_life.txt:165` |
| [ ] | `con_ritual_caos` | rigoroso nos rituais do vício e desordenado em todo o resto | universal | `lore_nova/daily_life.txt:185` |
| [ ] | `con_reclama_primeiro` | reclama do trabalho e faz questão de ser o primeiro a chegar | universal | `lore_nova/daily_life.txt:9` |
| [ ] | `con_vitoria_e_preco` | conta as vitórias do passado e evita falar do que pagou por elas | universal | `lore_nova/daily_life.txt:257` |
| [ ] | `con_lei_dos_aneis` | recita as leis dos anéis na rua e as desobedece em casa | regiões: Nova Arcádia | `lore_nova/locations.txt:28` |
| [ ] | `con_alegre_pesado` | alegre em voz alta, tomado por um peso que não sabe explicar | regiões: Pântano da Melancolia | `lore_nova/locations.txt:101` |
| [ ] | `con_agua_e_dadiva` | guarda a água como ouro e a oferece a quem está à beira da morte | regiões: Deserto de Zhur | `lore_nova/daily_life.txt:283` |
| [ ] | `con_teme_silencio` | teme o silêncio da mata e desconfia de quem faz barulho | regiões: Floresta dos Sussurros | `lore_nova/locations.txt:146` |
| [ ] | `con_ama_a_selva` | ama a selva viva e desconfia de tudo que cresce depressa demais | regiões: Selva de Xylos | `lore_nova/locations.txt:169` |
| [ ] | `con_orgulho_do_frio` | orgulhoso de aguentar o frio e viciado no calor dos túneis | regiões: Skallgard | `lore_nova/daily_life.txt:199` |
| [ ] | `con_destemido_tremulo` | destemido debaixo d'água e trêmulo em terra firme | regiões: Aethelgard | `lore_nova/daily_life.txt:293` |
| [ ] | `con_jura_ophidia` | jura ter nascido em Ophidia e se atrapalha quando pedem detalhes | regiões: Ophidia | `data/origins.json:126` |
| [ ] | `con_osso_sem_chama` | revira carcaças de leviatã sem receio, mas evita acender qualquer chama | regiões: Costa Negra | `lore_nova/daily_life.txt:305` |
| [ ] | `con_sem_lei_regras` | jura que não há lei e cobra respeito às regras que inventa | regiões: Brekmar | `lore_nova/locations.txt:436` |
| [ ] | `con_osshari_metodo` | violento por método, nunca por prazer | raças: Osshari | `lore_nova/races.txt:291` |
| [ ] | `con_vrel_solitario` | prefere a solidão, mas sente falta do ruído das memórias alheias | raças: Vrel | `lore_nova/races.txt:195` |
| [ ] | `con_anao_afeto` | chama de ineficiência aquilo que faz por afeto | raças: Anão da Fuligem | `lore_nova/races.txt:114` |
| [ ] | `con_cinzeu_cuidadoso` | não sente dor, mas trata cada ferida alheia com cuidado exagerado | raças: Cinzéu | `lore_nova/races.txt:235` |
| [ ] | `con_cumpre_quota` | cumpre a quota de prisões e diz preferir perdoar | regiões: Nova Arcádia; facções: A Legião de Ferro | `lore_nova/factions.txt:20` |

## mannerisms - pendentes de leitura (25)

| OK | id | rótulo | filtros | fonte |
|---|---|---|---|---|
| [ ] | `man_pesa_moedas` | pesa cada moeda na palma antes de aceitá-la | universal | `lore_nova/locations.txt:28` |
| [ ] | `man_conta_nos_dedos` | conta nos dedos antes de dar qualquer resposta | universal | `lore_nova/daily_life.txt:57` |
| [ ] | `man_esfrega_maos` | esfrega as mãos como quem sente frio mesmo no calor | universal | `lore_nova/daily_life.txt:109` |
| [ ] | `man_confere_faca` | confere onde está a faca antes de se sentar | universal | `lore_nova/daily_life.txt:93` |
| [ ] | `man_mastiga_raiz` | mastiga raiz amarga entre uma frase e outra | universal | `lore_nova/daily_life.txt:61` |
| [ ] | `man_evita_olhar` | evita os olhos e fita as mãos de quem fala | universal | `lore_nova/daily_life.txt:39` |
| [ ] | `man_lenco_molhado` | leva um lenço molhado ao rosto mesmo longe das fundições | regiões: Nova Arcádia | `lore_nova/locations.txt:59` |
| [ ] | `man_conta_passos_lama` | conta os passos até a água toda vez que para | regiões: Pântano da Melancolia | `lore_nova/daily_life.txt:117` |
| [ ] | `man_desvia_brilho` | desvia o olhar de qualquer ponto distante e brilhante | regiões: Deserto de Zhur | `lore_nova/daily_life.txt:285` |
| [ ] | `man_inclina_cabeca` | inclina a cabeça como quem ouve um chamado e ri sem graça | regiões: Floresta dos Sussurros | `lore_nova/locations.txt:146` |
| [ ] | `man_nao_para` | troca de lugar a cada poucos minutos e nunca fica parado | regiões: Selva de Xylos | `lore_nova/locations.txt:171` |
| [ ] | `man_estende_maos_ao_fogo` | estende as mãos a qualquer chama antes de começar a falar | regiões: Skallgard | `lore_nova/daily_life.txt:199` |
| [ ] | `man_prende_folego` | prende a respiração por um instante antes de cada frase | regiões: Aethelgard | `lore_nova/daily_life.txt:293` |
| [ ] | `man_anota_deve` | anota em silêncio o nome de quem lhe deve algo | regiões: Brekmar | `lore_nova/locations.txt:436` |
| [ ] | `man_desenha_ilhas` | desenha ilhas diferentes no ar toda vez que conta de onde veio | regiões: Ophidia | `lore_nova/locations.txt:283` |
| [ ] | `man_cheira_o_ar` | cheira o ar antes de entrar em qualquer lugar fechado | regiões: Costa Negra | `lore_nova/daily_life.txt:307` |
| [ ] | `man_gestos_curtos` | fala por gestos curtos para poupar o fôlego | regiões: Montanhas Afiadas | `lore_nova/daily_life.txt:221` |
| [ ] | `man_toca_a_rocha` | toca a rocha com a palma antes de apoiar o peso | regiões: Montanhas Afiadas | `lore_nova/daily_life.txt:221` |
| [ ] | `man_olha_por_cima` | olha o horizonte por cima do ombro de quem fala | regiões: Pradaria das Ruínas | `lore_nova/daily_life.txt:237` |
| [ ] | `man_le_pedras` | passa a mão nas pedras antigas como quem reconhece letras | regiões: Pradaria das Ruínas | `lore_nova/locations.txt:379` |
| [ ] | `man_exibe_escamas` | exibe o padrão das escamas ao entrar numa sala | raças: Osshari | `lore_nova/races.txt:286` |
| [ ] | `man_pisca_devagar` | pisca devagar como quem recebe lembranças que não são suas | raças: Vrel | `lore_nova/races.txt:176` |
| [ ] | `man_assina_tudo` | assina e data tudo o que entrega, até um copo d'água | raças: Anão da Fuligem | `lore_nova/races.txt:116` |
| [ ] | `man_risca_frases` | risca frases curtas na superfície mais próxima enquanto fala | raças: Cinzéu | `lore_nova/races.txt:240` |
| [ ] | `man_de_frente_ao_mar` | prefere sentar-se de frente para a porta e para o mar | regiões: Brekmar; facções: Os Grupos Piratas Rivais | `lore_nova/factions.txt:258` |

## Exemplos sorteados (game_id `review-306`, turnos 0 a 9)

### Nova Arcádia

1. Elfo (Os Filhos da Chama Azul) - recolhedor de corpos para o crematório; quer ter recursos para curar quem ninguém cura; teme o que o Abismo faz com quem ouve demais; segredo: armazena comida e a nega aos vizinhos; contradição: generoso com estranhos, sovina com a família; maneirismo: mastiga raiz amarga entre uma frase e outra
2. Elfo (sem facção) - curandeiro de feridas e febres; quer deixar algo que dure depois de si; teme ficar para trás quando todos partem; segredo: esconde que a Tosse de Ferro já o alcançou; contradição: obsessivo com limpeza do corpo, descuidado com o ambiente; maneirismo: agacha para falar, como quem examina o chão
3. Humano (sem facção) - guarda de portão; quer fugir da lei de onde veio; teme perder alguém por falta de remédio; segredo: mantém um relacionamento escondido; contradição: cobra cada favor que faz, mas perdoa promessas que sabe vazias; maneirismo: numera tudo que diz
4. Cinzéu (sem facção) - coveiro; quer dominar seu ofício até a perfeição; teme passar fome de novo; segredo: carrega a identificação de um morto para passar pelos portões; contradição: frio em público, caloroso com animais; maneirismo: corrige a fala dos outros
5. Cinzéu (A Mão Sombria) - vendedor de pó de sonho no beco; quer largar o vício antes do próximo inverno; teme ficar para trás quando todos partem; segredo: guarda uma carta que nunca entregou; contradição: honesto em tudo menos no jogo; maneirismo: fala sempre muito baixo, quase sussurrando
6. Cinzéu (Os Filhos da Chama Azul) - mercador ambulante; quer viver em paz longe das guerras de facção; teme ficar sem forças para trabalhar e perder o sustento; segredo: dilui o que vende para esticar o lucro; contradição: fala pouco, mas conta tudo a quem sabe ouvir; maneirismo: deixa silêncios longos antes de responder
7. Humano (A Mão Sombria) - caçador de recompensas menores; quer reencontrar um irmão desaparecido; teme ficar sem forças para trabalhar e perder o sustento; segredo: roubou algo valioso uma única vez e nunca confessou; contradição: ri nos momentos tristes e chora nos felizes; maneirismo: cospe de lado ao discordar
8. Elfo (sem facção) - dono de estalagem; quer tirar um parente de um trabalho que o está consumindo; teme ficar para trás quando todos partem; segredo: enterrou suas economias num esconderijo; contradição: calmo em crise, explosivo com ninharias; maneirismo: olha as próprias mãos, contando os anos
9. Vrel (sem facção) - operário das fundições; quer reencontrar um irmão desaparecido; teme multidões e gritaria; segredo: finge saber ler; contradição: obsessivo com limpeza do corpo, descuidado com o ambiente; maneirismo: numera tudo que diz
10. Humano (sem facção) - escriba de contratos; quer ser reconhecido por algum feito; teme adoecer longe de casa; segredo: deve um favor perigoso a alguém influente; contradição: generoso com estranhos, sovina com a família; maneirismo: confere onde está a faca antes de se sentar

### Pântano da Melancolia

1. Humano (sem facção) - catador de sucata de guerra; quer vingar um parente perdido; teme o escuro total; segredo: falsifica pequenos documentos; contradição: obediente no serviço, rebelde apenas nos pensamentos; maneirismo: evita os olhos e fita as mãos de quem fala
2. Anão da Fuligem (sem facção) - catador de sucata de guerra; quer voltar a navegar com a tripulação de antes; teme passar fome de novo; segredo: vende armas do espólio da guerra como se fossem herança de família; contradição: pobre, mas vaidoso com a aparência; maneirismo: cospe de lado ao discordar
3. Elfo (sem facção) - mercador ambulante; quer vingar um parente perdido; teme adoecer longe de casa; segredo: fica com objetos dos mortos que deveria declarar; contradição: reza todo dia mas não acredita que alguém ouça; maneirismo: pergunta o nome de cada pessoa duas vezes
4. Cinzéu (Os Druidas do Ciclo Cinzento) - cartógrafo de rotas incertas; quer plantar algo que cresça no pântano sem ser tragado; teme o escuro total; segredo: ouve algo que ninguém mais ouve e não conta; contradição: pergunta sobre tudo, menos sobre o que preferiria não saber; maneirismo: pesa cada moeda na palma antes de aceitá-la
5. Cinzéu (Os Druidas-Renegados) - guarda de portão; quer ganhar poder e voz no local onde vive; teme perder a vontade de continuar andando; segredo: desertou de um grupo armado e usa outro nome; contradição: reclama do trabalho e faz questão de ser o primeiro a chegar; maneirismo: conta os passos até a água toda vez que para
6. Vrel (Os Druidas-Renegados) - dono de estalagem; quer largar o vício antes do próximo inverno; teme vozes de mortos chamando pelo nome; segredo: ouve algo que ninguém mais ouve e não conta; contradição: corajoso na briga, covarde nas conversas difíceis; maneirismo: cobre a boca ao sorrir
7. Vrel (sem facção) - dono de estalagem; quer juntar ouro para sair da região; teme fogo descontrolado; segredo: divide a própria ração com um parente doente e esconde isso; contradição: fala pouco, mas conta tudo a quem sabe ouvir; maneirismo: pisca devagar como quem recebe lembranças que não são suas
8. Anão da Fuligem (Os Druidas-Renegados) - mensageiro de estrada; quer ser chamado pelo nome por alguém que importa; teme o dia em que a comida subir mais que o ganho; segredo: recebeu pagamento para calar sobre um crime que testemunhou; contradição: defende a ordem e vive na bagunça; maneirismo: assina e data tudo o que entrega, até um copo d'água
9. Anão da Fuligem (Os Druidas-Renegados) - catador de metal e pregos tortos; quer tirar um parente de um trabalho que o está consumindo; teme o dia em que a comida subir mais que o ganho; segredo: esconde uma cicatriz ou marca de origem; contradição: reclama do trabalho e faz questão de ser o primeiro a chegar; maneirismo: conta os passos até a água toda vez que para
10. Humano (sem facção) - coveiro; quer ganhar poder e voz no local onde vive; teme cobradores e dívidas; segredo: roubou algo valioso uma única vez e nunca confessou; contradição: relaxado à vista de todos, atento a cada detalhe que ninguém notou; maneirismo: corrige a fala dos outros

### Deserto de Zhur

1. Cinzéu (sem facção) - tatuador de mapas de rota na pele; quer recuperar um registro perdido do seu povo; teme ficar para trás quando todos partem; segredo: abandonou um filho em outra cidade; contradição: sábio no ofício, ingênuo com gente; maneirismo: evita os olhos e fita as mãos de quem fala
2. Osshari (sem facção) - guarda pessoal de família rica; quer trocar o posto vigiado por um ofício que construa algo; teme ser pego pelas tempestades de navalha em campo aberto; segredo: fica com objetos dos mortos que deveria declarar; contradição: honesto em tudo menos no jogo; maneirismo: esfrega as mãos como quem sente frio mesmo no calor
3. Cinzéu (As Tribos dos Devoradores de Sol) - dono de estalagem; quer voltar a navegar com a tripulação de antes; teme água funda e sem fundo; segredo: perdeu quem poderia ter salvado e nunca conta a ninguém; contradição: aceita ser chamado por número, mas guarda o nome de cada protegido; maneirismo: esfrega as mãos como quem sente frio mesmo no calor
4. Humano (sem facção) - cartógrafo de rotas incertas; quer vingar um parente perdido; teme ser traído por quem confia; segredo: abandonou um filho em outra cidade; contradição: lembra de dívidas antigas, mas esquece favores recentes; maneirismo: cobre a boca ao sorrir
5. Cinzéu (As Tribos dos Devoradores de Sol) - catador de metal e pregos tortos; quer voltar a navegar com a tripulação de antes; teme multidões e gritaria; segredo: guarda um frasco de água que nunca dividiu com a caravana; contradição: planeja tudo e abandona o plano ao primeiro susto; maneirismo: oferece uma bebida a todo recém-chegado
6. Osshari (As Tribos dos Devoradores de Sol) - ferreiro de aldeia; quer quitar uma dívida antiga; teme uma batida na porta de madrugada; segredo: sabota em silêncio um rival de ofício; contradição: guarda a água como ouro e a oferece a quem está à beira da morte; maneirismo: toca o próprio ombro antes de mentir
7. Vrel (As Tribos dos Devoradores de Sol) - guarda pessoal de família rica; quer largar o vício antes do próximo inverno; teme água funda e sem fundo; segredo: guarda uma carta que nunca entregou; contradição: cobra cada favor que faz, mas perdoa promessas que sabe vazias; maneirismo: evita os olhos e fita as mãos de quem fala
8. Anão da Fuligem (As Tribos dos Devoradores de Sol) - guarda pessoal de família rica; quer achar uma fonte que dure mais de uma estação; teme ficar para trás quando todos partem; segredo: paga todo mês a alguém que sabe o que ele fez; contradição: chama de ineficiência aquilo que faz por afeto; maneirismo: esfrega as mãos como quem sente frio mesmo no calor
9. Anão da Fuligem (As Tribos dos Devoradores de Sol) - escriturário de bordo que registra cada decisão em protocolo; quer ter uma casa de pedra para chamar de sua; teme o escuro total; segredo: guarda um frasco de água que nunca dividiu com a caravana; contradição: jura não ferir ninguém e carrega uma lâmina; maneirismo: oferece uma bebida a todo recém-chegado
10. Elfo (sem facção) - curandeiro de feridas e febres; quer ser reconhecido por algum feito; teme fogo descontrolado; segredo: deve um favor perigoso a alguém influente; contradição: generoso com estranhos, sovina com a família; maneirismo: corrige a fala dos outros

### Floresta dos Sussurros

1. Humano (sem facção) - vendedor de raízes em carrinho de duas rodas; quer reencontrar um irmão desaparecido; teme fogo descontrolado; segredo: ouve algo que ninguém mais ouve e não conta; contradição: aceita ser chamado por número, mas guarda o nome de cada protegido; maneirismo: pesa cada moeda na palma antes de aceitá-la
2. Elfo (sem facção) - guarda pessoal de família rica; quer fugir da lei de onde veio; teme adoecer longe de casa; segredo: carrega a identificação de um morto para passar pelos portões; contradição: fala pouco, mas conta tudo a quem sabe ouvir; maneirismo: inclina a cabeça como quem ouve um chamado e ri sem graça
3. Osshari (sem facção) - caçador de recompensas menores; quer descobrir o que realmente aconteceu no passado do lugar; teme cobradores e dívidas; segredo: ouve algo que ninguém mais ouve e não conta; contradição: calmo em crise, explosivo com ninharias; maneirismo: olha para a porta a cada poucos segundos
4. Humano (sem facção) - recolhedor de corpos para o crematório; quer dominar seu ofício até a perfeição; teme vozes de mortos chamando pelo nome; segredo: desertou de um grupo armado e usa outro nome; contradição: defende a ordem e vive na bagunça; maneirismo: mastiga raiz amarga entre uma frase e outra
5. Anão da Fuligem (sem facção) - ferreiro de aldeia; quer quitar uma dívida antiga; teme água funda e sem fundo; segredo: usa o fungo vermelho da mata e esconde a dependência; contradição: planeja tudo e abandona o plano ao primeiro susto; maneirismo: assina e data tudo o que entrega, até um copo d'água
6. Cinzéu (sem facção) - caçador de feras de espinhos de osso; quer reencontrar um irmão desaparecido; teme água funda e sem fundo; segredo: vende pequenas informações a quem pagar; contradição: conta as vitórias do passado e evita falar do que pagou por elas; maneirismo: cospe de lado ao discordar
7. Anão da Fuligem (sem facção) - guarda pessoal de família rica; quer quitar uma dívida antiga; teme o silêncio que parece escolher quem vai ouvir; segredo: ouve algo que ninguém mais ouve e não conta; contradição: conta as vitórias do passado e evita falar do que pagou por elas; maneirismo: bate o dedo na mesa ao pensar
8. Anão da Fuligem (sem facção) - escriturário de bordo que registra cada decisão em protocolo; quer viver em paz longe das guerras de facção; teme ficar sem forças para trabalhar e perder o sustento; segredo: colhe em segredo uma planta proibida e vende a quem não pergunta; contradição: obediente no serviço, rebelde apenas nos pensamentos; maneirismo: faz um gesto de juramento antes de prometer
9. Vrel (sem facção) - caçador de recompensas menores; quer proteger a vila onde vive; teme multidões e gritaria; segredo: carrega a identificação de um morto para passar pelos portões; contradição: leal até aparecer uma oferta melhor; maneirismo: toca o próprio ombro antes de mentir
10. Vrel (sem facção) - herborista de bosque; quer achar a cura de uma doença que o consome; teme multidões e gritaria; segredo: enterrou suas economias num esconderijo; contradição: teme o silêncio da mata e desconfia de quem faz barulho; maneirismo: tosse seca antes de falar de dinheiro

### Selva de Xylos

1. Elfo (A Colmeia dos Hospedeiros) - guarda de portão; quer fazer valer o tempo que lhe resta; teme multidões e gritaria; segredo: perdeu quem poderia ter salvado e nunca conta a ninguém; contradição: corajoso na briga, covarde nas conversas difíceis; maneirismo: faz um gesto de juramento antes de prometer
2. Osshari (A Colmeia dos Hospedeiros) - cartógrafo de rotas incertas; quer voltar a viver sob a luz do dia; teme adoecer longe de casa; segredo: recebeu pagamento para calar sobre um crime que testemunhou; contradição: violento por método, nunca por prazer; maneirismo: tosse seca antes de falar de dinheiro
3. Anão da Fuligem (A Colmeia dos Hospedeiros) - guia de trilhas; quer viver em paz longe das guerras de facção; teme passar fome de novo; segredo: carrega a identificação de um morto para passar pelos portões; contradição: cobra cada favor que faz, mas perdoa promessas que sabe vazias; maneirismo: esfrega as mãos como quem sente frio mesmo no calor
4. Anão da Fuligem (sem facção) - herborista de bosque; quer quitar uma dívida antiga; teme ver sangue de gente conhecida; segredo: sabota em silêncio um rival de ofício; contradição: leal até aparecer uma oferta melhor; maneirismo: agacha para falar, como quem examina o chão
5. Vrel (A Colmeia dos Hospedeiros) - vendedor de raízes em carrinho de duas rodas; quer descobrir o que realmente aconteceu no passado do lugar; teme a lei e seus oficiais; segredo: dilui o que vende para esticar o lucro; contradição: defende a ordem e vive na bagunça; maneirismo: confere onde está a faca antes de se sentar
6. Cinzéu (A Colmeia dos Hospedeiros) - dono de estalagem; quer achar a cura de uma doença que o consome; teme ficar sem forças para trabalhar e perder o sustento; segredo: carrega a identificação de um morto para passar pelos portões; contradição: calmo em crise, explosivo com ninharias; maneirismo: cantarola enquanto trabalha
7. Cinzéu (sem facção) - escriba de contratos; quer ganhar poder e voz no local onde vive; teme ficar para trás quando todos partem; segredo: sabota em silêncio um rival de ofício; contradição: não sente dor, mas trata cada ferida alheia com cuidado exagerado; maneirismo: olha para a porta a cada poucos segundos
8. Osshari (A Colmeia dos Hospedeiros) - guarda pessoal de família rica; quer vingar um parente perdido; teme o contágio que cresce dentro de gente viva; segredo: esconde uma cicatriz ou marca de origem; contradição: aceita ser chamado por número, mas guarda o nome de cada protegido; maneirismo: troca de lugar a cada poucos minutos e nunca fica parado
9. Anão da Fuligem (sem facção) - criado de casa abastada; quer juntar ouro para sair da região; teme fogo descontrolado; segredo: fica com objetos dos mortos que deveria declarar; contradição: pergunta sobre tudo, menos sobre o que preferiria não saber; maneirismo: evita os olhos e fita as mãos de quem fala
10. Vrel (A Colmeia dos Hospedeiros) - curandeiro de feridas e febres; quer descobrir o que realmente aconteceu no passado do lugar; teme ficar para trás quando todos partem; segredo: perdeu quem poderia ter salvado e nunca conta a ninguém; contradição: pergunta sobre tudo, menos sobre o que preferiria não saber; maneirismo: pisca devagar como quem recebe lembranças que não são suas

### Skallgard

1. Elfo (Os Clãs de Combate de Skallgard) - caçador de recompensas menores; quer ganhar poder e voz no local onde vive; teme adoecer longe de casa; segredo: ouve algo que ninguém mais ouve e não conta; contradição: obediente no serviço, rebelde apenas nos pensamentos; maneirismo: oferece uma bebida a todo recém-chegado
2. Cinzéu (sem facção) - catador de metal e pregos tortos; quer ter uma casa de pedra para chamar de sua; teme ficar para trás quando todos partem; segredo: dilui o que vende para esticar o lucro; contradição: conta as vitórias do passado e evita falar do que pagou por elas; maneirismo: olha para a porta a cada poucos segundos
3. Elfo (sem facção) - ferreiro de aldeia; quer ganhar poder e voz no local onde vive; teme perder alguém por falta de remédio; segredo: falsifica pequenos documentos; contradição: trata os mortos com respeito e cobra taxa por cada objeto; maneirismo: pergunta o nome de cada pessoa duas vezes
4. Vrel (sem facção) - catador de metal e pregos tortos; quer reencontrar um irmão desaparecido; teme ser desmascarado por uma mentira antiga; segredo: guarda uma ficha de quota falsificada para não passar fome; contradição: obediente no serviço, rebelde apenas nos pensamentos; maneirismo: esfrega as mãos como quem sente frio mesmo no calor
5. Anão da Fuligem (sem facção) - caçador de caribu-cinza do ermo; quer ver o mar antes de morrer; teme o frio que não passa; segredo: sabota em silêncio um rival de ofício; contradição: pergunta sobre tudo, menos sobre o que preferiria não saber; maneirismo: agacha para falar, como quem examina o chão
6. Vrel (sem facção) - guarda pessoal de família rica; quer largar o vício antes do próximo inverno; teme o que o Abismo faz com quem ouve demais; segredo: esconde uma cicatriz ou marca de origem; contradição: trata os mortos com respeito e cobra taxa por cada objeto; maneirismo: bate o dedo na mesa ao pensar
7. Vrel (sem facção) - contrabandista de pequenas cargas; quer quitar uma dívida antiga; teme ficar sozinho; segredo: finge saber ler; contradição: defende a ordem e vive na bagunça; maneirismo: cospe de lado ao discordar
8. Elfo (sem facção) - técnico de clã tecnológico; quer ver o mar antes de morrer; teme adoecer longe de casa; segredo: perdeu quem poderia ter salvado e nunca conta a ninguém; contradição: orgulhoso de aguentar o frio e viciado no calor dos túneis; maneirismo: pergunta o nome de cada pessoa duas vezes
9. Elfo (Os Renegados do Ermo) - cronista de memórias élficas; quer deixar algo que dure depois de si; teme cobradores e dívidas; segredo: foi criado por um povo que não é o seu; contradição: rigoroso nos rituais do vício e desordenado em todo o resto; maneirismo: corrige a fala dos outros
10. Humano (Os Renegados do Ermo) - mercador ambulante; quer achar a cura de uma doença que o consome; teme o frio que não passa; segredo: finge saber ler; contradição: fala pouco, mas conta tudo a quem sabe ouvir; maneirismo: toca o próprio ombro antes de mentir

### Aethelgard

1. Elfo (sem facção) - curandeiro de feridas e febres; quer ver os filhos longe do trabalho que lhe feriu as mãos; teme o dia em que o tempo acabar de repente; segredo: desertou de um grupo armado e usa outro nome; contradição: leal até aparecer uma oferta melhor; maneirismo: tosse seca antes de falar de dinheiro
2. Humano (sem facção) - mercador ambulante; quer viver em paz longe das guerras de facção; teme cobradores e dívidas; segredo: sabota em silêncio um rival de ofício; contradição: planeja tudo e abandona o plano ao primeiro susto; maneirismo: pesa cada moeda na palma antes de aceitá-la
3. Anão da Fuligem (sem facção) - curandeiro de feridas e febres; quer tirar um parente de um trabalho que o está consumindo; teme passar fome de novo; segredo: paga todo mês a alguém que sabe o que ele fez; contradição: sábio no ofício, ingênuo com gente; maneirismo: evita os olhos e fita as mãos de quem fala
4. Vrel (sem facção) - catador de metal e pregos tortos; quer voltar a viver sob a luz do dia; teme uma batida na porta de madrugada; segredo: paga todo mês a alguém que sabe o que ele fez; contradição: generoso com estranhos, sovina com a família; maneirismo: faz um gesto de juramento antes de prometer
5. Anão da Fuligem (sem facção) - caçador de recompensas menores; quer ganhar poder e voz no local onde vive; teme o que o Abismo faz com quem ouve demais; segredo: abandonou um filho em outra cidade; contradição: reza todo dia mas não acredita que alguém ouça; maneirismo: corrige a fala dos outros
6. Elfo (sem facção) - parteira que cobra em favores; quer ser recebido à mesa dos que hoje o desprezam; teme vozes de mortos chamando pelo nome; segredo: abandonou um filho em outra cidade; contradição: destemido debaixo d'água e trêmulo em terra firme; maneirismo: agacha para falar, como quem examina o chão
7. Anão da Fuligem (sem facção) - pescador de peixes de escamas luminosas; quer proteger a vila onde vive; teme ficar para trás quando todos partem; segredo: guarda um cristal tirado das ruínas submersas e nunca o declarou; contradição: sábio no ofício, ingênuo com gente; maneirismo: numera tudo que diz
8. Elfo (Os Cultistas da Destilação) - guia de trilhas; quer achar a cura de uma doença que o consome; teme a lei e seus oficiais; segredo: desertou de um grupo armado e usa outro nome; contradição: cobra cada favor que faz, mas perdoa promessas que sabe vazias; maneirismo: corrige a fala dos outros
9. Humano (sem facção) - catador de metal e pregos tortos; quer ter uma casa de pedra para chamar de sua; teme multidões e gritaria; segredo: mantém um relacionamento escondido; contradição: generoso com estranhos, sovina com a família; maneirismo: cospe de lado ao discordar
10. Humano (sem facção) - barqueiro das bordas cristalinas do lago; quer viver em paz longe das guerras de facção; teme fogo descontrolado; segredo: ouve algo que ninguém mais ouve e não conta; contradição: sorri a quem lhe deve e evita quem ele próprio deve; maneirismo: pergunta o nome de cada pessoa duas vezes

### Ophidia

1. Osshari (sem facção) - mercador ambulante; quer ganhar poder e voz no local onde vive; teme ficar sozinho; segredo: divide a própria ração com um parente doente e esconde isso; contradição: sábio no ofício, ingênuo com gente; maneirismo: evita os olhos e fita as mãos de quem fala
2. Humano (sem facção) - dono de estalagem; quer ser chamado pelo nome por alguém que importa; teme o escuro total; segredo: enterrou suas economias num esconderijo; contradição: curioso por tudo e cansado de tudo; maneirismo: gira um anel de cobre no dedo
3. Osshari (sem facção) - carpinteiro de barcos; quer deixar algo que dure depois de si; teme morrer sem que ninguém lembre; segredo: perdeu quem poderia ter salvado e nunca conta a ninguém; contradição: pergunta sobre tudo, menos sobre o que preferiria não saber; maneirismo: conta nos dedos antes de dar qualquer resposta
4. Vrel (sem facção) - criado de casa abastada; quer fugir da lei de onde veio; teme o que o Abismo faz com quem ouve demais; segredo: armazena comida e a nega aos vizinhos; contradição: jura não ferir ninguém e carrega uma lâmina; maneirismo: agacha para falar, como quem examina o chão
5. Humano (sem facção) - criado de casa abastada; quer ganhar poder e voz no local onde vive; teme água funda e sem fundo; segredo: finge saber ler; contradição: obsessivo com limpeza do corpo, descuidado com o ambiente; maneirismo: confere onde está a faca antes de se sentar
6. Osshari (sem facção) - parteira que cobra em favores; quer descobrir o que realmente aconteceu no passado do lugar; teme ficar sem forças para trabalhar e perder o sustento; segredo: paga todo mês a alguém que sabe o que ele fez; contradição: fala pouco, mas conta tudo a quem sabe ouvir; maneirismo: esfrega as mãos como quem sente frio mesmo no calor
7. Cinzéu (sem facção) - mercador ambulante; quer tirar um parente de um trabalho que o está consumindo; teme ver sangue de gente conhecida; segredo: armazena comida e a nega aos vizinhos; contradição: planeja tudo e abandona o plano ao primeiro susto; maneirismo: cospe de lado ao discordar
8. Humano (sem facção) - capitão endividado que aceita rotas perto de ilhas proibidas; quer descobrir o que realmente aconteceu no passado do lugar; teme esquecer o próprio rosto aos poucos; segredo: vende pequenas informações a quem pagar; contradição: generoso com estranhos, sovina com a família; maneirismo: ri alto de piadas que ninguém contou
9. Osshari (sem facção) - criado de casa abastada; quer ter recursos para curar quem ninguém cura; teme esquecer o próprio rosto aos poucos; segredo: tem parte num barco que não deveria navegar; contradição: planeja tudo e abandona o plano ao primeiro susto; maneirismo: ri alto de piadas que ninguém contou
10. Cinzéu (sem facção) - cartógrafo de rotas incertas; quer proteger a vila onde vive; teme o que o Abismo faz com quem ouve demais; segredo: dilui o que vende para esticar o lucro; contradição: sorri a quem lhe deve e evita quem ele próprio deve; maneirismo: oferece uma bebida a todo recém-chegado

### Costa Negra

1. Vrel (sem facção) - contrabandista de pequenas cargas; quer vingar um parente perdido; teme morrer sem que ninguém lembre; segredo: tem parte num barco que não deveria navegar; contradição: corajoso na briga, covarde nas conversas difíceis; maneirismo: pesa cada moeda na palma antes de aceitá-la
2. Humano (sem facção) - criado de casa abastada; quer ser chamado pelo nome por alguém que importa; teme ser desmascarado por uma mentira antiga; segredo: abandonou um filho em outra cidade; contradição: honesto em tudo menos no jogo; maneirismo: ri alto de piadas que ninguém contou
3. Anão da Fuligem (sem facção) - catador de metal e pregos tortos; quer descobrir o que realmente aconteceu no passado do lugar; teme o dia em que a comida subir mais que o ganho; segredo: mantém um relacionamento escondido; contradição: revira carcaças de leviatã sem receio, mas evita acender qualquer chama; maneirismo: numera tudo que diz
4. Anão da Fuligem (sem facção) - vendedor de raízes em carrinho de duas rodas; quer vingar um parente perdido; teme ficar para trás quando todos partem; segredo: finge saber ler; contradição: reclama do trabalho e faz questão de ser o primeiro a chegar; maneirismo: responde a toda pergunta com uma história
5. Osshari (sem facção) - escriba de contratos; quer juntar âmbar cinza o bastante para nunca mais entrar numa carcaça; teme o momento em que voltar a sentir dor; segredo: desertou de um grupo armado e usa outro nome; contradição: corajoso na briga, covarde nas conversas difíceis; maneirismo: corrige a fala dos outros
6. Anão da Fuligem (sem facção) - engenheiro de túneis; quer viver em paz longe das guerras de facção; teme adoecer longe de casa; segredo: fica com objetos dos mortos que deveria declarar; contradição: conta as vitórias do passado e evita falar do que pagou por elas; maneirismo: numera tudo que diz
7. Elfo (sem facção) - guarda pessoal de família rica; quer ter uma casa de pedra para chamar de sua; teme cobradores e dívidas; segredo: divide a própria ração com um parente doente e esconde isso; contradição: pergunta sobre tudo, menos sobre o que preferiria não saber; maneirismo: ri alto de piadas que ninguém contou
8. Cinzéu (sem facção) - coveiro; quer proteger a vila onde vive; teme passar fome de novo; segredo: enterrou suas economias num esconderijo; contradição: corajoso na briga, covarde nas conversas difíceis; maneirismo: cantarola enquanto trabalha
9. Osshari (sem facção) - ferreiro de aldeia; quer ser chamado pelo nome por alguém que importa; teme o momento em que voltar a sentir dor; segredo: dilui o que vende para esticar o lucro; contradição: jura não ferir ninguém e carrega uma lâmina; maneirismo: pergunta o nome de cada pessoa duas vezes
10. Anão da Fuligem (sem facção) - mercador ambulante; quer quitar uma dívida antiga; teme agir sem protocolo e causar um erro sem volta; segredo: sabota em silêncio um rival de ofício; contradição: trata os mortos com respeito e cobra taxa por cada objeto; maneirismo: ri alto de piadas que ninguém contou

### Montanhas Afiadas

1. Elfo (sem facção) - dono de estalagem; quer ver o mar antes de morrer; teme passar fome de novo; segredo: ouve algo que ninguém mais ouve e não conta; contradição: jura não ferir ninguém e carrega uma lâmina; maneirismo: fala por gestos curtos para poupar o fôlego
2. Elfo (Os Bandos Orc das Saídas Baixas) - catador de metal e pregos tortos; quer ver o mar antes de morrer; teme cobradores e dívidas; segredo: perdeu quem poderia ter salvado e nunca conta a ninguém; contradição: obsessivo com limpeza do corpo, descuidado com o ambiente; maneirismo: olha as próprias mãos, contando os anos
3. Humano (Os Bandos Orc das Saídas Baixas) - coveiro; quer quitar uma dívida antiga; teme o que o Abismo faz com quem ouve demais; segredo: conhece uma passagem pouco usada; contradição: curioso por tudo e cansado de tudo; maneirismo: cantarola enquanto trabalha
4. Elfo (Os Goblins-Mineiros) - dono de estalagem; quer ter uma casa de pedra para chamar de sua; teme o que o Abismo faz com quem ouve demais; segredo: armazena comida e a nega aos vizinhos; contradição: leal até aparecer uma oferta melhor; maneirismo: numera tudo que diz
5. Humano (Os Bandos Orc das Saídas Baixas) - escriba de contratos; quer viver em paz longe das guerras de facção; teme o dia em que a comida subir mais que o ganho; segredo: divide a própria ração com um parente doente e esconde isso; contradição: corajoso na briga, covarde nas conversas difíceis; maneirismo: tosse seca antes de falar de dinheiro
6. Elfo (Os Últimos Anões do Reino) - coveiro; quer ver os filhos longe do trabalho que lhe feriu as mãos; teme multidões e gritaria; segredo: vende pequenas informações a quem pagar; contradição: fala pouco, mas conta tudo a quem sabe ouvir; maneirismo: cantarola enquanto trabalha
7. Cinzéu (sem facção) - contrabandista de pequenas cargas; quer proteger a vila onde vive; teme uma batida na porta de madrugada; segredo: mantém um relacionamento escondido; contradição: conta as vitórias do passado e evita falar do que pagou por elas; maneirismo: evita os olhos e fita as mãos de quem fala
8. Humano (sem facção) - mensageiro de estrada; quer voltar a navegar com a tripulação de antes; teme uma batida na porta de madrugada; segredo: esconde uma cicatriz ou marca de origem; contradição: generoso com estranhos, sovina com a família; maneirismo: numera tudo que diz
9. Cinzéu (sem facção) - guarda de portão; quer ser reconhecido por algum feito; teme o que o Abismo faz com quem ouve demais; segredo: enterrou suas economias num esconderijo; contradição: cobra cada favor que faz, mas perdoa promessas que sabe vazias; maneirismo: cantarola enquanto trabalha
10. Cinzéu (Os Bandos Orc das Saídas Baixas) - guarda de portão; quer ser recebido à mesa dos que hoje o desprezam; teme a lei e seus oficiais; segredo: armazena comida e a nega aos vizinhos; contradição: obediente no serviço, rebelde apenas nos pensamentos; maneirismo: numera tudo que diz

### Pradaria das Ruínas

1. Anão da Fuligem (sem facção) - escriba de contratos; quer trocar o posto vigiado por um ofício que construa algo; teme perder alguém por falta de remédio; segredo: roubou algo valioso uma única vez e nunca confessou; contradição: corajoso na briga, covarde nas conversas difíceis; maneirismo: gira um anel de cobre no dedo
2. Humano (Os Mercadores de Escravos da Pradaria) - guarda de portão; quer dominar seu ofício até a perfeição; teme a lei e seus oficiais; segredo: roubou algo valioso uma única vez e nunca confessou; contradição: obsessivo com limpeza do corpo, descuidado com o ambiente; maneirismo: passa a mão nas pedras antigas como quem reconhece letras
3. Humano (sem facção) - mercador ambulante; quer trocar o posto vigiado por um ofício que construa algo; teme virar apenas um número aos olhos de quem o emprega; segredo: reconheceu um espectro das ruínas e nunca contou à família; contradição: calmo em crise, explosivo com ninharias; maneirismo: toca o próprio ombro antes de mentir
4. Osshari (Os Mercadores de Escravos da Pradaria) - vendedor de raízes em carrinho de duas rodas; quer dominar seu ofício até a perfeição; teme ser desmascarado por uma mentira antiga; segredo: recebeu pagamento para calar sobre um crime que testemunhou; contradição: rigoroso nos rituais do vício e desordenado em todo o resto; maneirismo: corrige a fala dos outros
5. Osshari (sem facção) - vendedor de raízes em carrinho de duas rodas; quer sentir algo de verdade, nem que seja uma vez; teme esquecer o próprio rosto aos poucos; segredo: reconheceu um espectro das ruínas e nunca contou à família; contradição: lembra de dívidas antigas, mas esquece favores recentes; maneirismo: cospe de lado ao discordar
6. Cinzéu (sem facção) - coveiro; quer vingar um parente perdido; teme ficar para trás quando todos partem; segredo: dilui o que vende para esticar o lucro; contradição: ri nos momentos tristes e chora nos felizes; maneirismo: pesa cada moeda na palma antes de aceitá-la
7. Vrel (As Cidades-Estado Sobreviventes) - catador de metal e pregos tortos; quer quitar uma dívida antiga; teme ser traído por quem confia; segredo: mantém um relacionamento escondido; contradição: jura não ferir ninguém e carrega uma lâmina; maneirismo: pesa cada moeda na palma antes de aceitá-la
8. Osshari (Os Mercadores de Escravos da Pradaria) - coveiro; quer juntar ouro para sair da região; teme ver sangue de gente conhecida; segredo: desertou de um grupo armado e usa outro nome; contradição: sorri a quem lhe deve e evita quem ele próprio deve; maneirismo: fala sempre muito baixo, quase sussurrando
9. Vrel (As Cidades-Estado Sobreviventes) - escriba de contratos; quer deixar algo que dure depois de si; teme ser traído por quem confia; segredo: mantém um relacionamento escondido; contradição: generoso com estranhos, sovina com a família; maneirismo: mastiga raiz amarga entre uma frase e outra
10. Osshari (sem facção) - parteira que cobra em favores; quer achar a cura de uma doença que o consome; teme ficar sem forças para trabalhar e perder o sustento; segredo: mantém um relacionamento escondido; contradição: frio em público, caloroso com animais; maneirismo: evita os olhos e fita as mãos de quem fala

### Brekmar

1. Elfo (Os Osshari de Brekmar) - coveiro; quer reencontrar um irmão desaparecido; teme esquecer o próprio rosto aos poucos; segredo: guarda uma carta que nunca entregou; contradição: ri nos momentos tristes e chora nos felizes; maneirismo: gira um anel de cobre no dedo
2. Humano (sem facção) - guarda pessoal de família rica; quer ser reconhecido por algum feito; teme ser desmascarado por uma mentira antiga; segredo: recebeu pagamento para calar sobre um crime que testemunhou; contradição: jura não ferir ninguém e carrega uma lâmina; maneirismo: confere onde está a faca antes de se sentar
3. Cinzéu (Os Osshari de Brekmar) - contrabandista de pequenas cargas; quer vingar um parente perdido; teme a lei e seus oficiais; segredo: sabota em silêncio um rival de ofício; contradição: ri nos momentos tristes e chora nos felizes; maneirismo: agacha para falar, como quem examina o chão
4. Anão da Fuligem (Os Grupos Piratas Rivais) - curandeiro de feridas e febres; quer ver os filhos longe do trabalho que lhe feriu as mãos; teme a lei e seus oficiais; segredo: armazena comida e a nega aos vizinhos; contradição: sorri a quem lhe deve e evita quem ele próprio deve; maneirismo: oferece uma bebida a todo recém-chegado
5. Vrel (Os Grupos Piratas Rivais) - guarda pessoal de família rica; quer achar a cura de uma doença que o consome; teme ser traído por quem confia; segredo: esconde uma cicatriz ou marca de origem; contradição: obsessivo com limpeza do corpo, descuidado com o ambiente; maneirismo: mastiga raiz amarga entre uma frase e outra
6. Vrel (sem facção) - curandeiro de feridas e febres; quer ser reconhecido por algum feito; teme adoecer longe de casa; segredo: divide a própria ração com um parente doente e esconde isso; contradição: sábio no ofício, ingênuo com gente; maneirismo: esfrega as mãos como quem sente frio mesmo no calor
7. Vrel (O Poder de Kahen) - guarda pessoal de família rica; quer ser reconhecido por algum feito; teme virar apenas um número aos olhos de quem o emprega; segredo: conhece uma passagem pouco usada; contradição: reclama do trabalho e faz questão de ser o primeiro a chegar; maneirismo: fala como se duas vozes respondessem juntas
8. Anão da Fuligem (Os Osshari de Brekmar) - coveiro; quer proteger a vila onde vive; teme agir sem protocolo e causar um erro sem volta; segredo: deve um favor perigoso a alguém influente; contradição: aceita ser chamado por número, mas guarda o nome de cada protegido; maneirismo: ri alto de piadas que ninguém contou
9. Osshari (Os Osshari de Brekmar) - vendedor de raízes em carrinho de duas rodas; quer sentir algo de verdade, nem que seja uma vez; teme ser apagado do registro das coisas; segredo: falsifica pequenos documentos; contradição: relaxado à vista de todos, atento a cada detalhe que ninguém notou; maneirismo: conta nos dedos antes de dar qualquer resposta
10. Humano (sem facção) - carpinteiro de barcos; quer ser chamado pelo nome por alguém que importa; teme o dia em que a comida subir mais que o ganho; segredo: recebeu pagamento para calar sobre um crime que testemunhou; contradição: fala pouco, mas conta tudo a quem sabe ouvir; maneirismo: agacha para falar, como quem examina o chão
