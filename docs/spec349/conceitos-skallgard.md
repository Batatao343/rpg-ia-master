# SPEC-349 · onda Skallgard e o Ermo Branco — conceitos (gerar 2× e cortar, R9)

Processo (Etapa 3, padrão das ondas 1 e 2): tabuleiro de 23 vagas com eixos fechados **antes** da
prosa (`data/bestiario/fichas/skallgard.yaml` → `vagas:`, verde com `lint.py --vagas` e conferido à
mão contra as 8 fichas retro), depois 56 conceitos de 1 linha, corte pelo autor (Opus) até 23, prosa,
e corte independente do revisor de unicidade (Opus).
Resultado do autor: **20 novas + 3 slots** (`enemy_lobo_invernal`, `enemy_yeti`, `mon_jotun_cinza`,
reinventados no slot, mantendo o id).

Comparado contra: as 8 retro de Skallgard (Guerreiro Bjorn, Titã de Gelo, Urso-Titã, Lobo de Vidro,
Verme do Gelo, Renegado do Ermo, Corvo de Gelo Negro, Lobo da Aurora Morta); os 44 docs `monsters/`
com a tag `skallgard` no Codex (Foca-Lâmina, Caribu-Cinza, Corvo-da-Aurora, Mamute-da-Névoa,
Raposa-de-Sal, Touro-Almiscarado-Negro, Cintilação, Sopro-Errante, Cristal-Sanguíneo, Eco-Congelado,
Chama-Fátua-Azul, Aurora-Viva, Espírito-Animal da Parede, O Que Volta do Branco, Lamento-de-Geada,
Guardião-Sem-Rosto, Coisa-da-Sala-Fria, Filho-do-Vento-Branco, Boca-no-Gelo, Caçadores-Cegos,
Clã-Sem-Fogo, Coruja-de-Osso, Doninha-Térmica, Alce-Espectral, Salmão-de-Ferro, Bússola-Morta,
Veia-de-Calor, Reflexo-da-Aurora, Procissão-Branca, O Frio que Lembra, Enxofre-Vivo, Costura-de-Pele,
Salteadores da Garganta, Mascateiros do Gelo, O Pastor-Branco, Filho-do-Frio, A Coisa-Sob-o-Gelo
Antigo, Mãe-das-Nevascas, Os Primeiros-Caçadores, O Que Restou do Gigante e os demais); as 27 de
Nova Arcádia e as 22 do rascunho do Pântano.

Âncoras usadas (lore pós-348, checkout principal): Rede Carmesim e Cristal-Sanguíneo
(`creatures.txt:25`, `:116`, `items.txt:66`); anti-luz do Farol, **sem** a ligação Farol → Rede, que é
segredo (`locations.txt:230`); Juramento do Fogo Alto e o assento vazio (`factions.txt:191`,
`locations.txt:232`); clãs de combate × tecnológicos e a especiação (`factions.txt:175-206`);
Ursos-Titãs com ganchos de osso na carne (`creatures.txt:70`, `races.txt:344`); Sopro de Vorr e as
estátuas conscientes (`npcs.txt:391`, `locations.txt:228`); a Landship que falta (E-08) só como
indício público — ferro anão rebitado sob o gelo e Anões que mudam de assunto (`races.txt:88`), nunca
o paradeiro.

Demônios da onda (Skallgard não tem demônio de lugar fixo, §3.8): Vhrak, Maalrek, Veth, Skarath e
Dorrhen, todos itinerantes. Nenhuma cria repete (plano, material) da cria do mesmo demônio na onda 1
ou na 2.

Inspirações externas (R12, só ideia, fonte registrada na ficha e no fim do doc de arte):
caranguejo-ermitão, carrapato-de-inverno do alce, lagarta-lanosa-do-ártico, mandriões
(cleptoparasitas), colêmbolos (pulgas-da-neve), corcova de bisão e camelo.

## 1. Os 56 conceitos

Legenda: **F** = ficou · **C-A** = cortado pelo autor (motivo) · **C-R** = cortado pelo revisor.

### Corpos reescritos (Reescritos)

| # | Conceito | Decisão |
|---|---|---|
| 1 | **Parado do Sopro** — caçador que um Sopro-Errante pegou de lado: o braço e o ombro presos num instante em gelo limpo, o resto envelhecido por dois | F |
| 2 | **Levantado de Rubi** — morto do Ermo com uma flor de Cristal-Sanguíneo no esterno; levanta de novo o primeiro inimigo que cai | F |
| 3 | **Queimado de Breu** — vigia que olhou para a chama negra do Farol; pele preta e fosca que não devolve luz; apaga a luz em volta | F |
| 4 | **Parelha Carmesim** — seis cães de trenó mortos atrelados, levantados sem desatrelar; atropelam a fila e fazem a volta | F |
| 5 | **Desfiado da Aurora** — tocado pela Aurora-Viva; a carne acesa se desfaz em luz; atira tiras da própria pele | F |
| 6 | **Crescido do Clã** — caçador em quem a especiação não parou: quatro metros, osso rompendo a pele, de pé numa armação de ferro dos tecnológicos | F (slot `mon_jotun_cinza`) |
| 7 | Mudo de Vorr — garganta e pulmões viraram fole de vidro sem som | C-A: silenciar a cena é a Traça do Sino Mudo (NA) |
| 8 | Torna-Sul — mercenário dos clãs que voltou do sul com a Ferrugem do Sangue, que congela nas veias | C-A: Praga de Ferro é âncora de NA; "ferida vira força" repete Banhado e Tritão |
| 9 | Aurorado que marca — a luz da Aurora gruda no alvo e o deixa à vista | C-A: marca que facilita acertos é o Rosário de Vértebras; a Aurora ficou com o Desfiado |
| 10 | Escaldado do Ventre — vítima de vapor com o músculo vidrado pelo frio | C-A: abraçar e beber calor repete o Arame Vivo (dreno por contato) |
| 11 | Pelado de Vidro — caçador cuja armadura de Lobo-de-Vidro enraizou na pele | C-A: variante meio-humana do Lobo-de-Vidro; corte de volta é do Pajem |
| 12 | Galhada da Parede — galhadas gravadas com nomes dos mortos, reanimadas | C-A: terceira reanimação da Rede; o Espírito-Animal da Parede já ocupa a Parede |
| 13 | Tripulante Anão preservado — anão de escafandro saindo do gelo | C-A: entrega o paradeiro da Landship que falta (E-08 é segredo) |
| 14 | Sucessor do Farol — andarilho atraído para a torre | C-A: segredo do ciclo do guardião (LEAK_PHRASES da 348) |

### Bestas da entropia (Bestas Tortas)

| # | Conceito | Decisão |
|---|---|---|
| 15 | **Ermitão de Elmo** (era Ermitão de Escotilha) — bicho de seis pernas morando num elmo de guerra das batalhas Cinzéus × Anões; fecha a viseira no pulso | F (R1: P0, a cúpula anã com vigia apontava a Landship) |
| 16 | **Carrapato de Mamute** (era de Montaria) — uma boca em cada ponta; bebe de um bicho e devolve a outro | F (R1: hospedeiro trocado; os ganchos são da Montaria) |
| 17 | **Lagarta de Sete Invernos** — congela e degela no meio da luta | F |
| 18 | **Mandrião de Dois Bicos** — ave das escadarias de Vorr com o bico rachado em dois; só desce sobre quem já foi ferido | F |
| 19 | **Pulga de Forquilha** — colêmbolo do tamanho de um cão; salta por cima de quem guarda | F (slot `enemy_lobo_invernal`) |
| 20 | **Corcova Fervente** — bisão do Ermo com a corcova de gordura que ferve e guarda calor | F (slot `enemy_yeti`) |
| 21 | Urso de Ganchos Soltos — Urso-Titã selvagem com os ganchos de cavaleiros mortos | C-A: variante do Urso-Titã (retro) |
| 22 | Arminho de Gola — arminho de espinha comprida que se enrosca no pescoço | C-A: mustelídeo de novo (Doninha-Térmica); enroscar é do Arame Vivo |
| 23 | Glutão de Despensa — guarda carne congelada nas bochechas e rouba consumíveis | C-A: segundo mustelídeo e terceiro ladrão da região |
| 24 | Maré de Lemingues — bola rolante de lemingues congelados por fora e vivos por dentro | C-A: "amontoados para se aquecer" é o Filho-do-Vento-Branco |
| 25 | Morsa de Presas de Âncora — finca as presas no gelo e arrasta para o buraco | C-A: arrastar para a água é da Foca-Lâmina e do Bagre de Varal |
| 26 | Narval de Rio Subglacial — a presa atravessa o gelo de baixo | C-A: ataque por baixo do gelo é do Verme-do-Gelo e da Boca-no-Gelo |
| 27 | Caribu de Rubi — galhada de Cristal-Sanguíneo | C-A: reskin do Alce-Espectral e do Caribu-Cinza |
| 28 | Fulmar de Óleo — ave que cospe óleo que congela e pesa | C-A: segunda ave marinha (fica o Mandrião); óleo que prende repete o Romeiro de Âmbar |
| 29 | Berne do Caribu — mosca que põe ovo no Ferimento e eclode em inimigo | C-A: semear na ferida é do Jardineiro de Tumores |
| 30 | Aranha-do-Mar do Buraco — picnogônida de oito pernas sob o gelo | C-A: puxar para a água repete; perder perna ao ser cortada espelha o Tritão de Sobra |
| 31 | Tardígrado do Degelo — vira barril seco e imune | C-A: mesmo estado alternado da Lagarta, que é fauna real do Ártico |
| 32 | Ouriço da Borda — espinhos que custam Fôlego | C-A: encarecer a Carta é a Escritura Rastejante |
| 33 | Lince de Anti-luz — some no escuro do Farol | C-A: segunda criatura da anti-luz; fica o Queimado de Breu |
| 34 | Lebre de Dentes Longos — incisivos que não param de crescer | C-A: identidade fraca, sem papel próprio |

### Humanoides que pagaram o preço (Cobrados)

| # | Conceito | Decisão |
|---|---|---|
| 35 | **Montaria Cravada** — cavaleiro e Urso-Titã em que os ganchos criaram raiz; um corpo só | F |
| 36 | **Ferreiro de Chama Fria** — mãos pretas da chama-fátua azul; desfaz a arma de quem entra na Fornalha | F |
| 37 | **Lascador Morno** — garimpeiro clandestino de Cristal-Sanguíneo; atira lascas que dão a morte de outro | F |
| 38 | **Escuta do Sinal** — leitor da Câmara com cornetas aparafusadas no crânio; chama pelo gelo | F |
| 39 | **Caldeira de Peito** — tecnológico com uma caldeira do Ventre no peito, dentro de uma armação a vapor | F |
| 40 | **Andas de Caribu** — Renegado sem pés sobre andas de osso cravadas nas canelas | F |
| 41 | Pescador de Buraco — braços mortos de frio, puxa para o buraco | C-A: puxar para a água repete a Foca-Lâmina e o Bagre |
| 42 | Domador de Ganchos — o clã que crava os ganchos | C-A: segundo portador de ganchos; fica a Montaria Cravada |
| 43 | Bebedor de Óleo de Leviatã — pele que verte óleo e arde | C-A: sem facção do grafo; queimar ao toque repete Pajem e Lençol |
| 44 | Aceso por Dentro — Renegado com Veias-de-Calor enxertadas | C-A: eixos batiam U3 com quatro humanos; enxerto repete o Enxerto da Fornalha |
| 45 | Jurado do Assento Vazio — quem sentou no assento do Gigante | C-A: narrativo, sem corpo torto |

### Crias de apetite (demônios encarnados)

| # | Conceito | Decisão |
|---|---|---|
| 46 | **Tição do Juramento** (Vhrak) — lenha, sebo e crânio de cabra da fogueira do Fogo Alto; atiça o rancor dos feridos | F |
| 47 | **Colecionador de Poses** (Maalrek) — corpo montado de estátuas conscientes da Fortaleza; guarda a pose do alvo | F (chefe) |
| 48 | **Feltro do Ventre** (Veth) — feltro e sebo dos canos com oito mãos; toma o reforço do jogador | F |
| 49 | **Aperto da Trégua** (Skarath; era Rosto nas Costas) — dois braços de clãs rivais presos num aperto de mãos; pune a rodada sem defesa | F (R1: o Rosto era o Vira-Costas de NA invertido) |
| 50 | **Enegrecido que Espera** (Dorrhen) — mãos e pés mortos de geada juntos num corpo; fecha a saída | F |
| 51 | Abraço Duplo do Juramento (Vhrak) — dois clãs fundidos se esfaqueando | C-A: é o Abraço Duplo cortado na onda 1 |
| 52 | Feixe de Ganchos (Maalrek) — quadrúpede de ganchos de osso | C-A: segundo corpo de ganchos (Montaria Cravada) |
| 53 | Troféus do Corredor (Maalrek) — dentes e garras dos ritos | C-A: é a Costura-de-Pele |
| 54 | Roda de Passos (Dorrhen) — anel de pernas que anda em círculo na Bússola-Morta | C-A: silhueta radial repete a Roda de Mandíbulas (NA) |
| 55 | Cavador de Neve (Dorrhen) — dedos que cavam | C-A: é a Cavadeira de Unhas, também de Dorrhen (NA) |
| 56 | Avesso da Corda (Skarath) — cordada de geleira que corta a corda | C-A: corda de novo para Skarath (Cordão de Medida, Pântano) |

## 2. Lista do autor (20 novas + 3 slots)

Reescritos (5 + slot): Parado do Sopro · Levantado de Rubi · Queimado de Breu · Parelha Carmesim ·
Desfiado da Aurora · *(slot)* Crescido do Clã.
Bestas Tortas (4 + 2 slots): Ermitão de Elmo · Carrapato de Mamute · Lagarta de Sete Invernos ·
Mandrião de Dois Bicos · *(slot)* Pulga de Forquilha · *(slot)* Corcova Fervente.
Cobrados (6): Montaria Cravada · Ferreiro de Chama Fria · Lascador Morno · Escuta do Sinal ·
Caldeira de Peito · Andas de Caribu.
Crias de Apetite (5): Tição do Juramento (Vhrak) · Colecionador de Poses (Maalrek, chefe) ·
Feltro do Ventre (Veth) · Aperto da Trégua (Skarath) · Enegrecido que Espera (Dorrhen).

Cotas (U12, `COTAS_PADRAO`, Skallgard não tem cota própria em `COTAS_ONDA`): famílias 6/6/6/5 (com
os slots); lacaio 7, padrão 9, elite 6, chefe 1; 12 papéis e 9 arquétipos; 5 demônios; habitat
Skallgard e o Ermo 20, Fortaleza de Vorr 4, Farol 5, Salão do Juramento 3.

## 3. Revisão de unicidade (Opus, `handoffs/SPEC-349-independent-review.md`)

Rodada 1: CHANGES_REQUIRED. 10 aprovadas, 13 com correção, nenhum corte (cortar deixaria a onda abaixo
de 20 novas). Aplicado:

- **P0 · Ermitão** — a cúpula anã com vigia e os "Anões que mudam de assunto" apontavam a Landship que
  falta (E-08). Agora é o **Ermitão de Elmo**: mora num elmo das batalhas Cinzéus × Anões nas passagens
  (público, `creatures.txt:25`). A mecânica mudou para a viseira presa no pulso, que ocupa um espaço da mão.
- **P1 · Parado do Sopro** — era variante do Colecionador (Sopro, estátuas, vidro). O lado parado
  agora é carne viva parada no tempo, sem casca. Material `carne_exposta`, e saiu da Fortaleza.
- **P1 · Queimado de Breu** — repetia os Caçadores-Cegos e insinuava o ciclo do guardião. Agora é um
  caçador que chegou perto demais do Farol e voltou, e enxerga só luz (`percepcao: luz`).
- **P1 · Carrapato** — a âncora dos ganchos ficou só com a Montaria. Agora é o **Carrapato de Mamute**,
  com uma boca em cada ponta (marca do Abismo), e a mecânica ficou.
- **P1 · Andas de Caribu** — o "rouba e foge com prazo" era o molde da Gralha (NA). Agora chuta de cima,
  por cima da defesa, e escolhe a distância na neve funda (`batedor_rapido`).
- **P1 · Feltro do Ventre** — sem as oito mãos (Fardo, Pântano) e sem cera (Convidado, NA). Agora é uma
  faixa de feltro com franjas de farpas de cobre (`serpentiforme`). A mecânica ficou.
- **P1 · Rosto nas Costas** — era o Vira-Costas (NA) invertido. Agora é o **Aperto da Trégua**: dois braços
  de clãs rivais presos num aperto de mãos (`acoplado`), que pune a rodada sem defesa.
- **P1 · Enegrecido que Espera** — deixou de ser um amálgama de mãos e pés. É um único amputado do frio,
  cujos cotos cresceram.
- **P1 · Crescido do Clã** — a armação de ferro ficou só com a Caldeira. Agora usa talas de osso de mamute
  com couro cru, e a mecânica passa a ser "enquanto as talas aguentam".
- **P2** — o Levantado não tem mais gancho que dê intenção à Rede; o Tição tem crânio de caribu; a Lagarta
  ganhou sete anéis mortos que não degelam; a Pulga tem a forquilha atravessando a própria barriga e
  vive junto às saídas de vapor do Ventre.

Rodada 2: ver o fim do parecer.
