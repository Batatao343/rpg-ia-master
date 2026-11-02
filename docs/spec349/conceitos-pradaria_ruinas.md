# SPEC-349 · onda 3 · Pradaria das Ruínas — conceitos (gerar 2× e cortar, R9)

Processo (o mesmo da onda 1): tabuleiro de 22 vagas (21 novas + 1 slot) com eixos fechados **antes**
da prosa (`data/bestiario/fichas/pradaria_ruinas.yaml` → `vagas:`, verde em U2/U3/U12 com
`lint.py --vagas` e também contra os eixos das 11 fichas retro da região); depois 48 conceitos de
1 linha; corte do autor (Opus) até 22; prosa; corte independente do revisor de unicidade (Opus,
`spec-reviewer`).

Âncoras usadas (lore da SPEC-348, checkout principal): bioma "perigo MODERNO" e espectros só nas
ruínas isoladas (`creatures.txt:430`); fauna da Pradaria (`:434-456`); Pó-Sussurrante, Marco-Vivo,
Espectro-Élfico/Cinzéu, Soldado-Sem-Guerra (`:466-488`); Osso Pintado, Vrel, Cavaleiros-Cinza,
Desenterrados, Eremitas, Mercadores (`:496-518`); Coisa-nos-Alicerces e Semente-do-Vazio (`:527`,
`:535`); Elfos — pele de porcelana, ampulheta, dor (`races.txt:41-50`), inveja dos Cinzéus (`:75`);
Cinzéus — sem dor, correntes na pele, cauda (`:217-232`); Praga dos Ossos (`:516-529`); Colina Cinza
(`npcs.txt:35`, `timeline_completa.txt:378`); Vaelorn/Solvhen, Aerwen e Morvan (`factions.txt:348-354`);
Groth (`factions.txt:387`); Vesh (`npcs.txt:1037-1042`); vento que nunca para (`daily_life.txt:235`).

Segredos que **não** entram no texto público: Solvhen como sonho de Solvhara (por isso nenhuma
Cria de Apetite tem Solvhen como habitat e nenhuma liga a Tristeza à cidade), a Ampulheta de
Aerwen, a herdeira da Colina Cinza.

Inspiração externa registrada (R12): fulgurito/trinitita (Vidrado do Morro), pernaltas
(Pernalta das Colunas) e besouros-rinoceronte (Besouro de Alavanca); ver o doc de arte.

## 1. Os 48 conceitos (1 linha cada)

Legenda: **F** = ficou na lista do autor · **C-A** = cortado pelo autor (motivo) · **C-R** = cortado
ou reescrito pelo revisor (§2).

### Corpos reescritos (Reescritos)

| # | Conceito | Decisão |
|---|---|---|
| 1 | **Vertedor de Areia** — Elfo que morreu na hora da ampulheta e ficou de pé pelo Éter; escorre areia das rachaduras de porcelana e acelera até desabar sozinho | F |
| 2 | **Vidrado do Morro** — guarda no alto de um morro com a areia fundida em vidro sobre o corpo pelo fogo de Malagor | F |
| 3 | **Costas de Alicerce** — saqueador que dormiu encostado numa laje de fundação e acordou com ela crescida na espinha | F |
| 4 | Osso que Pegou — Andarilho do Osso Pintado que costurou à pele ossos de Lycan; as farpas pegaram e viraram placas sobre músculo | C-R (§2) → Vestido de Gafanhotos |
| 5 | **Fuçador da Semente** — javali de presa longa que engoliu a semente de um círculo morto; buraco seco no flanco, apodrece o que rasga | F |
| 6 | Carniceiro Esporado — falcão-carniceiro que comeu ossos de Lycan; asas viraram lanças de osso, não voa, corre e espeta | C-A: Praga dos Ossos em animal = variante do Lycan |
| 7 | Varrão de Ossada — javali com Praga dos Ossos, coroa de presas e placas sobre músculo | C-A: Lycan de quatro patas (variante da ideia de referência); javali já é do Fuçador |
| 8 | Cinzéu Recongelado — Cinzéu cuja estátua de gelo de nascimento voltou a fechar sobre metade do corpo | C-A: gelo não é da Pradaria; colide com o Vidrado (corpo dentro de casca) |
| 9 | Enraizado de Vaelorn — mago élfico cujas veias claras saíram da pele como raízes de Éter | C-A: reskin do Arame Vivo (Nova Arcádia: veias viradas para fora) |
| 10 | Cego do Céu Vermelho — veterano que olhou Malagor e ficou com os olhos de brasa | C-A: brasa no corpo = Caído do Cadinho (NA); sem silhueta própria |
| 11 | Jaula Viva — escravo com Ferrugem do Sangue fundido às barras da carroça-jaula de Groth | C-A: Fila de Grilhões (NA) com outra corrente |
| 12 | Fiel do Marco — peregrino que seguiu um Marco-Vivo e ficou com o rosto esculpido em relevo | C-A: perigo pouco físico; o Marco-Vivo já cobre o "seguir para onde algo espera" |

### Bestas da entropia (Bestas Tortas)

| # | Conceito | Decisão |
|---|---|---|
| 13 | **Nadador de Pedra** — bicho cego que nada dentro das fundações como em água; o chão ondula e derruba | F |
| 14 | **Cobra de Légua** — cobra que não afina e nunca acaba; cada rodada vem mais uma volta | F |
| 15 | **Rodante de Espinhos** — bola de espinhos de osso que rola contra o vento e morro acima | F |
| 16 | **Pernalta das Colunas** — ave de pernas de vareta altas como colunas, arpoa de cima | F |
| 17 | **Lagarto de Mudas** — lagarto em carne viva cujas peles trocadas andam e mordem | F |
| 18 | Bode sem Freio — bode cujo embalo não diminui; só para ao bater | C-R (§2) → Besouro de Alavanca |
| 19 | Lesma de Argamassa — lesma do tamanho de um boi que dissolve a cal das fundações | C-A: segunda criatura "pedra" com o Nadador; lenta demais para lutar |
| 20 | Cupinzeiro de Rostos — cupinzeiro que copia os relevos élficos e anda sobre pernas de cupim | C-A: composto difuso, arte ilegível; Marco-Vivo já tem o "relevo que se mexe" |
| 21 | Antílope Adiantado — antílope que chega um instante antes do próprio som | C-A: física quebrada só no conceito, sem corpo legível em arte |
| 22 | Coruja de Pescoço Inteiro — coruja que gira a cabeça sem fim e enrola o próprio pescoço | C-A: a Coruja-dos-Túmulos já existe no Codex; a do pescoço torcido virou a Égua de Costas |
| 23 | Besouro Rola-Crânio — besouro que empurra uma bola de ossos e couraças mais pesada que o mundo | C-A: "rolar" já é do Rodante; peso errado é da Porca da Queda (NA) |
| 24 | Potro de Oito Patas — cavalo selvagem cinza com patas a mais, rápido demais | C-A: Sleipnir de manual; Tritão de Sobra (Pântano) já tem membros a mais |
| 25 | Lebre de Rastro — lebre cujas pegadas aparecem antes dela | C-A: Lebre-de-Duas-Cabeças no Codex; perigo conceitual |
| 26 | Sapo de Poeira — sapo que bebe o vento e incha até estourar em poeira | C-A: Sapo-Boi Ácido (Pântano) e explosão (Lençol de Chaminé, NA) |

### Humanoides que pagaram o preço (Cobrados)

| # | Conceito | Decisão |
|---|---|---|
| 27 | **Carregador de Ganchos** — Cinzéu de Groth com dezenas de ganchos de açougue na pele; fisga e puxa | F |
| 28 | **Leitor de Cativos** — Vrel de Vesh que leu cativos demais; cabeça rachada, palpos que seguram crânios | F |
| 29 | **Profanador Cravejado** — Desenterrado com as joias élficas afundadas na carne; arranca o que você carrega | F |
| 30 | Pulmão de Frases — eremita das ruínas Cinzéus de peito em barril, frases surgindo por baixo da pele, tosse que paralisa | C-R (§2) → Cauda Emendada |
| 31 | **Desfiado de Vaelorn** — sentinela élfico que pagou para lhe puxarem os nervos; salta e luta partido | F |
| 32 | **Arqueiro de Tendão** — arqueiro dos Cavaleiros-Cinza com pedras de Éter no lugar dos olhos | F |
| 33 | Cavaleiro Enxertado — Cavaleiro-Cinza com as pernas crescidas nos flancos do cavalo | C-A: centauro de manual |
| 34 | Capataz de Coleira — Mercador de Groth com uma coleira de Éter que dá ordens | C-A: humano comum, o corpo não paga nada; o Capturador retro já é o "mercador que luta" |
| 35 | Mago Perdido de Illyan — aprendiz de Vaelorn que se perdeu no Abismo como o Magister | C-A: tocar Illyan expõe a tragédia de Aerwen; conjurador de manual |
| 36 | Pintor de Pele — Osso Pintado que tatua as vítimas com tinta de osso moído | C-A: o corpo dele não paga preço; gore |
| 37 | Andarilho de Sal — nômade que lambe o sal das fundações com os auroques e virou pedra salgada | C-A: sal já é do Velório (NA) e do Pântano |
| 38 | Arauto do Osso Pintado — pregoeiro de Kaarg que fala com voz de caveira | C-A: sem corpo reescrito; papel de NPC |

### Crias de apetite (demônios encarnados)

| # | Conceito | Decisão |
|---|---|---|
| 39 | **Égua de Costas** (Solvhara) — égua chorada que volta com a cabeça virada para trás e deita sobre quem chora | F |
| 40 | **Cabeça Acima** (Urath) — ossos de duelista élfico esticados, pescoço de vértebras nuas, nem sente golpe fraco | F |
| 41 | **Chifres Travados** (Vhrak) — dois auroques fundidos no nó dos chifres, cada corpo para um lado | F (chefe) |
| 42 | **Retalho das Duas Cidades** (Veth) — corpo costurado de lado élfico e lado Cinzéu, desfaz a sua guarda | F |
| 43 | Contemplador Sentado (Solvhara) — roda de Cinzéus sentados de costas, fundidos, que param quem olha | C-A: tocaria o segredo de Solvhen; radial repetia a Roda de Mandíbulas (NA) |
| 44 | Rolo de Pergaminho (Solvhara) — pergaminho do arquivo de Morvan que enrola quem lê | C-A: Escritura Rastejante (NA, Daruun) com outra tinta |
| 45 | Chicote Cru (Maalrek) — cauda de couro cru trançado com uma mão na ponta | C-A: serpentiforme colidia com a Cobra de Légua; Maalrek já tem chefe em NA |
| 46 | Muda de Kaarg (Skarath) — cria da Traição no bando que trai quando vantajoso | C-A: Skarath já tem cria no Pântano; sem anatomia própria |
| 47 | Toca sem Saída (Dorrhen) — corpo de túneis que se cava a si mesmo | C-A: Cavadeira de Unhas (NA, Dorrhen) cava |
| 48 | Tapeçaria Podre (Morvath) — tapeçaria élfica de veludo que apodrece bonito e abraça | C-A: perigo pouco físico; Morvath tem cria no Pântano |

## 2. Corte do revisor (rodada 1) e o que foi feito

Parecer: `handoffs/SPEC-349-pradaria_ruinas-uniqueness-review.md` (9 aprovadas, 10 mudanças, 3 cortes).

| Corte/pedido | Aplicado |
|---|---|
| Osso que Pegou: CORTE (Lycan por contágio; armadura que cresce = Caído do Cadinho) | cortado; vaga 4 virou **Vestido de Gafanhotos** (lavrador que o enxame de Gafanhotos-de-Bronze não terminou de comer, cascas vivas como armadura sobre o músculo roído; cada golpe solta uma revoada que morde quem bateu; fogo espanta sem pagar) |
| Bode sem Freio: CORTE (carneiro de manual; embalo = Rodante) | cortado; vaga 11 virou **Besouro de Alavanca** (chifre de pé de cabra que levanta lajes; arranca as placas da armadura, rachadura que dura a luta — diferente da Costura, que desfaz reforço temporário) |
| Pulmão de Frases: CORTE (Eremita + Pó-Sussurrante do Codex; fole = Fole de Costela) | cortado; vaga 15 virou **Cauda Emendada** (Cinzéu Andarilho com vértebras de mortos emendadas à cauda; varre os tornozelos e derruba sem prender, sugestão do revisor) |
| Vidrado: vaza a Colina Cinza; assinatura = Pajem | renomeado **Vidrado do Morro**; Colina Cinza fora de todo texto público e da paleta; assinatura nova = o sol no peito de vidro ofusca (golpe do ofuscado sai fraco); contra = sol nas costas, noite, nuvem |
| Vertedor: "quatro mãos" | corrigido para "mãos de quatro dedos" |
| Cobra de Légua: gancho = Serpente-da-Grama-Alta | gancho reescrito (o pastor que seguiu o corpo da manhã à tarde) |
| Rodante: assinatura = Rosário de Vértebras | espinho-marca removido; rola sempre para quem fez barulho por último; contra = ficar quieto e defender |
| Carregador: "puxa e prende" = Fila de Grilhões | um tranco só que arrasta para o meio dos caçadores, sem prender; tirado de Solvhen |
| Leitor: "desfaz a jogada" = Gralha | lê a próxima jogada e o agrupamento mostra a resposta no presságio; ele não toca na jogada |
| Profanador: roubar/fugir/devolver = Gralha; porcelana repetida | assinatura = pele cravejada (arrancar uma relíquia fere e devolve a peça); porcelana e gola de cristal removidas |
| Égua: deitar por cima = Regaço/Velório; égua morta = Corcel-Espectral | égua viva que ficou ao lado do dono morto; cabeça virada mantida; coice em quem recua ou passa por trás |
| Chifres Travados: giro = Roda de Mandíbulas | cabo de guerra: o nó vai para o corpo mais inteiro; ferir os dois por igual trava o nó |
| Costura: Solvhen como habitat de Cria | `pr_solvhen` → `pradaria_ruinas` (ficha e vaga 21) |
| Capim de Couraça: resistir a lâmina = Curtido; gancho = Soldado-Sem-Guerra | assinatura = o vento (só avança nas rajadas a favor); gancho trocado |
| Cabeça Acima (opcional) | "devolve com força maior" removido |

## 3. Lista final da onda (após a rodada 1)

Reescritos (5): Vertedor de Areia · Vidrado do Morro · Costas de Alicerce · Vestido de Gafanhotos ·
Fuçador da Semente · *(slot)* Capim de Couraça (`enemy_esqueleto_legiao_antiga`).
Bestas Tortas (6): Nadador de Pedra · Cobra de Légua · Rodante de Espinhos · Pernalta das Colunas ·
Lagarto de Mudas · Besouro de Alavanca.
Cobrados (6): Carregador de Ganchos (Groth) · Leitor de Cativos (Vesh) · Profanador Cravejado ·
Cauda Emendada · Desfiado de Vaelorn · Arqueiro de Tendão (Cavaleiros-Cinza).
Crias de Apetite (4): Égua de Costas (Solvhara) · Cabeça Acima (Urath) · Chifres Travados (Vhrak,
chefe) · Retalho das Duas Cidades (Veth).

Cotas (U12): 21 novas; famílias 6/6/6/4 (com o slot); lacaio 7 · padrão 9 · elite 5 · chefe 1;
12 papéis táticos e 9 arquétipos distintos; 4 demônios (Urath estreia no bestiário). Habitats:
Pradaria aberta 15, Ruínas Assombradas 11, Vaelorn 5, Solvhen 1 (nenhuma Cria em Solvhen).

## 4. O slot genérico

`enemy_esqueleto_legiao_antiga` (Esqueleto da Legião Antiga, lacaio, `morto_vivo_implacavel`,
`implacavel`/`absoluta`): o Afogado-da-Batalha não é adotável (já tem ficha, D4). Reinventado como
**Capim de Couraça**: um morto da Guerra do Céu Vermelho por onde o capim cresceu, raízes no lugar
dos tendões, que só avança quando a rajada vem a favor dele. Conceitos para a vaga: Capim de Couraça
(F); Soldado Salgado pelos auroques (C-A: sal); Lanceiro de Cupim (C-A: cupinzeiro já cortado);
Couraça Habitada por cão-da-pradaria (C-A: o perigo é o bicho, não o morto).
