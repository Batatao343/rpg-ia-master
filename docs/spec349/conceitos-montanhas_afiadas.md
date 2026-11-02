# SPEC-349 · onda 7 · Montanhas Afiadas — conceitos (gerar 2× e cortar, R9)

Processo (Etapa 3, padrão das ondas 1 e 2): tabuleiro de 27 vagas com eixos fechados **antes** da
prosa (`data/bestiario/fichas/montanhas_afiadas.yaml` → `vagas:`, verde com `lint.py --vagas` e,
num script à parte, contra as 6 fichas retro), depois 61 conceitos de 1 linha, corte pelo autor
(Opus) até 27, prosa, e corte independente do revisor de unicidade (Opus, seção 3).
Resultado do autor: **20 novas + 7 slots reinventados** (`enemy_observador_menor`,
`enemy_wyvern_jovem`, `enemy_minotauro_esqueleto`, `enemy_mimico_bau`, `enemy_basilisco_caverna`,
`enemy_morcego_vampiro`, `enemy_troll_ponte`).

Âncoras usadas: os Últimos Anões na Forja Profunda (bigornas quentes; só as pistas públicas), o Rei
Subterrâneo como presença e peso (Poço-de-Gravidade, "algo imenso em qualquer direção"), os Orcs e
Goblins como um povo só que divergiu (G-17, só como fala de acampamento), os Cinzéus guias e
guerreiros das passagens, a Praga de Ferro dos fugitivos de Nova Arcádia, o labirinto que muda com
os deslizamentos. O Verme-Primordial e o contrato da Forja não aparecem em texto público.

Comparado contra: as 6 retro da região (Orc das Saídas Baixas, Cabra-Navalha, Anão-Eco, Goblin de
Eco, Cabra do Labirinto, Guardião de Basalto), os 33 docs `monsters/` com a tag `montanhas_afiadas`
(Águia-das-Lascas, Amálgama-de-Minério, Aranha-de-Pedra, Aranha-Lanterna, Brasa-Profunda,
Carneiro-Trovão, Cogumelo-Cego, Coro-Soterrado, Cria-do-Rei, Cristal-Cantante, Eco-de-Profundidade,
Eco-Predador, Escavadores-Loucos, Espelho-de-Pedra, Filho-do-Rei, Flor-de-Profundidade,
Goblins-Mineiros, Líquen-de-Brasa, Morcego-Bússola, Morcego-de-Ferro, O Sino-Que-Não-Foi-Forjado,
Orcs das Saídas Baixas, Os Que Já Estavam Cavando, Poço-de-Gravidade, Rato-de-Pedra-Cinzento,
Refugiados-Bandidos, Salamandra-de-Forja, Toupeira-Gigante-Cega, Trepadeira-de-Ferro, Tribo-do-Eco,
Última-Sentinela, Verme-Mastigador-de-Rocha, Verme-Primordial), as 27 de Nova Arcádia e as 22 do
Pântano. Crias de demônio: Vhrak, Dorrhen, Veth, Maalrek, Skarath, Veleth e Urath (a primeira cria
de Urath da esteira), cada uma com plano corporal e material diferentes das crias do mesmo demônio
nas ondas 1 e 2.

Inspirações externas (R12, só ideia, fonte registrada na ficha e no fim do doc de arte): lagartos
do gênero Draco, pôneis de mina, caranguejo-ermitão, poço petrificante de Knaresborough,
caravela-portuguesa, grilos de caverna, pangolim e tatu-bola, amblipígios, lóris-lento,
ofiuroides, rádula dos caramujos, geodos e geladura.

## 1. Os 61 conceitos

Legenda: **F** = ficou · **C-A** = cortado pelo autor (motivo) · **C-R** = cortado pelo revisor.

### Corpos reescritos (Reescritos)

| # | Conceito | Decisão |
|---|---|---|
| 1 | **Deitado na Parede** — explorador que dormiu numa câmara de peso torto e cai para o lado; anda nas paredes | F |
| 2 | **Geodo da Praga** — fugitivo da Praga de Ferro em quem o ferro do sangue, no frio, virou nós de cristal que estouram | F |
| 3 | **Cauda de Atalaia** — guerreiro Cinzéu morto na guerra das passagens, pendurado pela cauda de osso que não parou de crescer | F |
| 4 | **Queimado de Frio** — viajante que a geada não terminou de matar; carvão por fora, músculo vivo por dentro, caça calor | F |
| 5 | **Olhos em Volta** — explorador que voltou do fundo com olhos em volta da cabeça, no pescoço e nas mãos | F (slot `enemy_observador_menor`) |
| 6 | Prensado da Boca — explorador comprimido pelo peso do Rei, costelas sobrepostas como telhas | C-A: mesmo mecanismo do Deitado (peso do Rei) e do Poço-de-Gravidade |
| 7 | Lycan preso no gelo — transformação congelada no meio do ciclo | C-A: nenhuma criatura nova é Lycan (regra da onda 2) |
| 8 | Barba de Cobre — anão morto cujos fios de cobre da barba viraram raízes que chicoteiam | C-A: fios saindo do corpo repetem o Arame Vivo (NA) |
| 9 | Tremido do Fundo — saco de pele com os ossos moídos pelo tremor das profundezas | C-A: corpo sem ossos repete o Curtido da Turfeira (Pântano) e encosta no segredo do Verme |
| 10 | Calcificado de Gotejamento — corpo coberto de calcário que anda dentro da crosta | C-A: corpo mineral repete a Amálgama-de-Minério; a pedra que cresce foi para o Caramujo |
| 11 | Cantor de Veio — Goblin com Cristal-Cantante nos ossos, que zune quando golpeado | C-A: segundo corpo mineral depois do Geodo; o Cristal-Cantante já é alarme |
| 12 | Respirado — pulmões crescidos para fora das costelas no ar fundo dos respiros | C-A: repete o Fole de Costela (NA) |
| 13 | Carregador Corcunda — carregador com a armação de carga fundida à espinha | C-A: silhueta do Pavio da Lista (NA, homem com gaiola nas costas) |
| 14 | Despencado da Fenda — caído em fenda, ossos emendados em ângulo de aranha | C-A: "articulação errada" de manual; repete Arame Vivo e Sangrado da Clínica |
| 15 | Simétrico das Câmaras — corpo espelhado, sem costas, de rosto dos dois lados | C-A: "visto de todos os lados" é o Vira-Costas da Praça (NA) |

### Bestas da entropia (Bestas Tortas)

| # | Conceito | Decisão |
|---|---|---|
| 16 | **Leque de Costelas** — lagarto dos picos de costelas abertas em leque de pele, afiadas pelo vento; plana rente às trilhas | F (slot `enemy_wyvern_jovem`) |
| 17 | **Boi de Canga** — boi de tração dos Anões deixado no Reino; cego, sem pelo, canga coberta de carne; arremete pelo trilho | F (slot `enemy_minotauro_esqueleto`) |
| 18 | **Morador do Caldeirão** — crustáceo de ventre mole que mora num caldeirão de forja anão, como um ermitão | F (slot `enemy_mimico_bau`) |
| 19 | **Caramujo de Estalagmite** — caramujo de casca de estalagmite cuja gosma vira pedra e prende os pés | F (slot `enemy_basilisco_caverna`) |
| 20 | **Lenço do Desfiladeiro** — faixa de couro com mãozinhas nas bordas que gruda na cara e bebe o fôlego | F (slot `enemy_morcego_vampiro`) |
| 21 | **Bexiga de Respiro** — saco de ar quente que flutua nos respiros dos Anões com fios que amortecem | F |
| 22 | **Saltão de Galeria** — grilo de caverna cego do tamanho de um cão que salta em bando no bafo | F |
| 23 | **Rolador de Escarpa** — bicho de placas de pederneira que se enrola e desce a encosta contra a trilha | F |
| 24 | **Chicote de Fenda** — bicho achatado das fendas verticais, de patas-chicote e braços de espinhos | F |
| 25 | **Ladrão de Lume** — bicho pelado de olhos enormes que rouba a lanterna e foge para o alto | F |
| 26 | Laje Falsa — bicho chato que imita uma laje do piso polido e se fecha nas pernas | C-A: segundo disfarce de objeto depois do Morador do Caldeirão |
| 27 | Preguiça de Corrente — bicho pesado pendurado nas correntes dos elevadores anões, cai como contrapeso | C-A: ataque de cima repete Leque de Costelas e Cauda de Atalaia |
| 28 | Pastador de Líquen — tatuzinho gigante que brilha do Líquen-de-Brasa que come | C-A: bola que rola repete o Rolador; não luta |
| 29 | Carrapato de Mula — carrapato do tamanho de uma cabeça que cai do teto | C-A: drenador pequeno genérico; repete Musaranho e Sanguessuga-Braço |
| 30 | Corça de Presas — cervo de presas de sabre que caça na encosta | C-A: quarto ungulado da região (duas cabras, Carneiro-Trovão, Boi de Canga) |
| 31 | Proteu da Cisterna — salamandra cega gigante das cisternas anãs | C-A: salamandra repete o Tritão de Sobra (Pântano) e a Salamandra-de-Forja |
| 32 | Escaravelho de Guano — besouros sob as colônias de Morcego-de-Ferro | C-A: enxame sem identidade de luta própria |
| 33 | Lince de Cascalho — felino da neve com ossos rompendo o pelo | C-A: repete o Urso-de-Espinha e o Lycan |
| 34 | Abutre Quebra-Osso — solta ossos e pedras sobre as presas | C-A: repete a Águia-das-Lascas |
| 35 | Formiga de Veio — formigas que comem minério e derrubam galerias | C-A: enxame; repete o Verme-Mastigador-de-Rocha |

### Humanoides que pagaram o preço (Cobrados)

| # | Conceito | Decisão |
|---|---|---|
| 36 | **Ponte de Ombros** — Orc de Gruumsha deitado sobre a fenda mais estreita, mãos e pés presos na pedra; o pedágio é passar por cima | F (slot `enemy_troll_ponte`) |
| 37 | **Braços de Tenaz** — ferreiro dos Últimos Anões com tenazes de forja rebitadas aos ossos dos antebraços | F |
| 38 | **Marco que Aponta** — guia Cinzéu cujas tatuagens de rota viraram cordões de cicatriz; o mapa já não leva à saída | F |
| 39 | **Armador de Fosso** — Goblin-mineiro que trocou os dedos perdidos nas armadilhas por ganchos e molas | F |
| 40 | **Vedado de Piche** (era Cosido do Fundo) — Orc que fechou os olhos com piche para descer ao Reino; fareja sangue | F (renomeado na rodada 1 do revisor) |
| 41 | Ouvidor de Parede — Goblin trepanado com uma corneta de latão no crânio, ouve pela pedra | C-A: vigia que avisa repete Olhos em Volta e o Cristal-Cantante |
| 42 | Cravado das Saídas — Orc com pregos de ferro pelo corpo para aguentar o fundo | C-A: mesmo preço do Vedado de Piche (Orc que se mutila pelo fundo); o slot do troll ficou com a Ponte de Ombros |
| 43 | Pedágio de Carne — Orc que costura no próprio corpo a pele que cobra | C-A: enxerto de pele alheia repete o Enxerto da Fornalha (NA) |
| 44 | Engolidor de Brasa — carregador que engole Brasa-Profunda e brilha pela barriga | C-A: barriga que brilha repete a Mula de Lágrimas (Pântano) |
| 45 | Selado de Protocolo — anão de boca rebitada que guarda o silêncio da Forja | C-A: sentinela anã repete Guardião de Basalto e Última-Sentinela; encosta no segredo da Forja |
| 46 | Livro de Pele — escriba anão que talhou os registros da queda na própria pele | C-A: corpo riscado como livro é o Sangrado da Clínica (NA) |
| 47 | Ventre de Relíquias — Goblin contrabandista que engole relíquias anãs | C-A: carregador de barriga cheia repete a Mula de Lágrimas |
| 48 | Cordada Costurada — escaladores costurados uns aos outros pela pele | C-A: fileira de corpos presos repete a Fila de Grilhões (NA) |

### Crias de apetite (demônios encarnados)

| # | Conceito | Decisão |
|---|---|---|
| 49 | **Peso dos Vencidos** (Vhrak) — tronco de Orc costurado sobre um monte de Goblins mortos; as partes se odeiam | F (chefe) |
| 50 | **Tampão da Câmara** (Dorrhen) — porta entupida dos corpos de quem morreu cavando a saída | F |
| 51 | **Tesoura de Cordada** (Veth) — costelas encaixadas como elos, com mandíbulas de tesoura; corta corda e correia | F |
| 52 | **Mastro de Troféus** (Maalrek) — mastro de troféus dos Orcs que anda sobre as mãos pregadas e segura o ferido | F |
| 53 | **Mão da Borda** (Skarath) — disco de couro sob a beira com braços de ventosa e uma mão humana limpa de isca | F |
| 54 | **Língua de Lima** (Veleth) — bicho de pó que apaga, lambendo, as inscrições da queda do Reino | F |
| 55 | **Pisador do Salão** (Urath) — quatro pernas de ossos de braço anão emendados; pisa em quem está mais baixo | F |
| 56 | Bolso Fundo (Daruun) — estômago de moedas que engole os itens do grupo | C-A: Daruun saqueador repete o Fardo de Espólio (Pântano) |
| 57 | Grito Engolido (Fehk) — o pavor que os Orcs escondem tomando carne | C-A: conceitual; e entregaria a fraqueza oculta dos Orcs |
| 58 | Muleta de Carne (Maalrek) — falso ferido que manca e pede socorro | C-A: a isca de quem ajuda é a Mão da Borda |
| 59 | Rolha de Gente (Dorrhen) — tubo de carne que se enfia nos túneis | C-A: tubo de carne nos túneis repete o Verme-Mastigador-de-Rocha; virou o Tampão |
| 60 | Passagem que Não Estava (Thessavar) — corredor que se fecha atrás do grupo | C-A: conceitual; o labirinto que muda já é a Cabra do Labirinto |
| 61 | Trono de Ombros (Urath) — degraus feitos de ombros onde o capataz se senta | C-A: conceitual, sem luta; virou o Pisador do Salão |

## 2. Lista do autor (20 novas + 7 slots)

| Família | Criaturas |
|---|---|
| Reescritos | Deitado na Parede, Geodo da Praga, Cauda de Atalaia, Queimado de Frio, Olhos em Volta (slot) |
| Bestas Tortas | Leque de Costelas (slot), Boi de Canga (slot), Morador do Caldeirão (slot), Caramujo de Estalagmite (slot), Lenço do Desfiladeiro (slot), Bexiga de Respiro, Saltão de Galeria, Rolador de Escarpa, Chicote de Fenda, Ladrão de Lume |
| Cobrados | Ponte de Ombros (slot), Braços de Tenaz, Marco que Aponta, Armador de Fosso, Vedado de Piche |
| Crias de Apetite | Peso dos Vencidos (chefe), Tampão da Câmara, Tesoura de Cordada, Mastro de Troféus, Mão da Borda, Língua de Lima, Pisador do Salão |

Categorias: lacaio 9 · padrão 9 · elite 8 · chefe 1. Papéis táticos: 13 de 13. Arquétipos: 10.
Habitat: A Boca 12 · Passagens 11 · Saídas Baixas 10 · Forja Profunda 5.

## 3. Cortes do revisor

Revisor de unicidade: Opus (`opus-spec-reviewer`), parecer em `handoffs/SPEC-349-independent-review.md`.
Rodada 1: 10 aprovadas, 17 com mudança, nenhuma cortada sem conserto. O autor aplicou tudo:

| Criatura | Motivo do revisor | O que mudou |
|---|---|---|
| Geodo da Praga | eixos e explosão na morte da Mula de Lágrimas (PM) | nós amadurecem perto do fogo e viram soco de cristal; `bipede_curvado`, `bruto_de_linha` |
| Queimado de Frio | placas pretas sobre músculo e busca de calor do Caído do Cadinho (NA); frio por contato do Cágado | pele cerosa com bolhas de geladura e barba presa no gelo; pune quem para; `cera_sebo`, `calor`, `controlador` |
| Morador do Caldeirão | mímico de manual (objeto que morde) | caldeirão em brasa que inutiliza arma de metal e esfria longe das bigornas; sem disfarce |
| Caramujo de Estalagmite | prender no lugar repete o Romeiro de Âmbar; jardim de estátuas do basilisco | a gosma prende a lâmina, não o pé; ferramentas presas no rastro no lugar das estátuas |
| Lenço do Desfiladeiro | dreno por rodada do Casaco de Sanguessugas; manto de manual sem R12 | cega, e o risco é a queda na trilha; fonte registrada; `emboscador` |
| Braços de Tenaz | braço de ferro longo do Enxerto da Fornalha; "nem para quem" apontava o contrato | braços de tamanho anão vitrificados pelo calor, desarme quente; frase removida; `bipede_ereto` |
| Tampão da Câmara | origem (cavar com as unhas) da Cavadeira de Unhas | grupo esmagado na porta quando o teto cedeu |
| Tesoura de Cordada | corrente de ossos do Rosário; silhueta do Cordão de Medida | corpo curto de escápulas e maxilares em tesoura sobre patas de costela; `hexapode_ou_mais` |
| Mão da Borda | origem igual à do Cordão de Medida (Skarath) | guia que cobrou e largou o cliente na borda |
| Deitado na Parede | silhueta do Pajem de Obsidiana | silhueta do corpo tombado de lado |
| Olhos em Volta | mecânica da Rã de Lótus | a Carta preparada do jogador fica à mostra para os inimigos |
| Marco que Aponta | corpo inteiro riscado do Sangrado da Clínica | relevo só no braço rígido que aponta |
| Cosido do Fundo → Vedado de Piche | "costura" e núcleo de nome da Peso dos Vencidos | olhos fechados com piche; nome e id novos (`mon_vedado_de_piche`) |
| Mastro de Troféus | excesso de mãos de mortos nas crias | anda cravando a estaca, laça com tendão |
| Pisador do Salão | pés de mãos anãs (mesmo motivo) | pés de crânio anão |
| Língua de Lima | terceiro "tira proteção"; Cisne de Pátina | apaga o último efeito a favor do alvo |
| Saltão de Galeria | bate-e-volta do Leque e do Patinador; contra-jogo do Lenço; nada torto | pousa de patas no teto (cai para cima), o bando derruba pelo peso; `vibracao` |

Ajustes opcionais aplicados: o Chicote puxa o alvo contra a parede; a arte do Rolador se afasta da
Roda de Mandíbulas.

Rodada 2 (final): 12 aprovadas; 5 correções mínimas e exatas aplicadas ao pé da letra (Deitado na
Parede tombado em todos os campos; contra-jogo do Geodo é partir o nó verde; Queimado agarra as
pernas e bloqueia defesa/Reação; Saltão pesa ao contrário; Morador derrama brasa no chão e o
Caramujo faz largar a arma ou ser arrastado). Veredito final: **APPROVED** para as 27.
