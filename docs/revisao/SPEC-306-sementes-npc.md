# SPEC-306 - Revisão das sementes de NPC

> Gerado por `scripts/npc_seed_review.py build` a partir de `data/npc_seed_tables.json`. **Não edite à mão.**
> Versão das tabelas: 2.

Marque `[x]` o que aprova e anote o que deve mudar. Para aprovar: diga "aprovo as sementes" (ou a lista de ids) e o coordenador roda `npc_seed_review.py approve`. Ids recusados são reescritos, nunca apagados.

## Totais

| Tabela | Total | Pendentes | universais | regionais | raça | facção |
|---|---|---|---|---|---|---|
| professions | 61 | 0 | 18 | 31 | 8 | 4 |
| desires | 45 | 0 | 22 | 14 | 7 | 2 |
| fears | 45 | 0 | 21 | 17 | 6 | 1 |
| secrets | 44 | 0 | 21 | 17 | 3 | 3 |
| contradictions | 42 | 0 | 25 | 10 | 6 | 1 |
| mannerisms | 45 | 0 | 23 | 14 | 7 | 1 |

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

## professions - pendentes de leitura (0)

_Nenhuma linha pendente._

## desires - pendentes de leitura (0)

_Nenhuma linha pendente._

## fears - pendentes de leitura (0)

_Nenhuma linha pendente._

## secrets - pendentes de leitura (0)

_Nenhuma linha pendente._

## contradictions - pendentes de leitura (0)

_Nenhuma linha pendente._

## mannerisms - pendentes de leitura (0)

_Nenhuma linha pendente._

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
