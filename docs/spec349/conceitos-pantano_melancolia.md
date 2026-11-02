# SPEC-359 · onda 2 · Pântano da Melancolia — conceitos (gerar 2× e cortar, R9)

Processo (Etapa 3, padrão da onda 1): tabuleiro de 22 vagas com eixos fechados **antes** da prosa
(`data/bestiario/fichas/pantano_melancolia.yaml` → `vagas:`, verde com `lint.py --vagas` e contra as
8 fichas retro), depois 46 conceitos de 1 linha, corte pelo autor (Opus) até 22, prosa, e corte
independente do revisor de unicidade (Opus, `handoffs/SPEC-359-independent-review.md`).
Resultado do autor: **21 novas + 1 slot** (`enemy_zumbi_blindado`, reinventado).

Comparado contra: as 8 retro do Pântano, os ~30 docs `monsters/` do Pântano no Codex (que levam a
tag `nova_arcadia`: Enguia-da-Lama, Garça-Pálida, Mosca-de-Cadáver, Fogo-Fátuo, Névoa-Pesada,
Lágrima-de-Éter, Reflexo-Afogado, General-Sem-Nome, Choro-na-Névoa, Carniça-Andante,
Flor-Carnívora, Tumor-do-Pântano, Saqueadores, Coletores, O Que Bebeu a Batalha, Raiz-Mãe,
Afogados-Antes, Névoa-Que-Pensa, Salgueiro-Chorão, Nenúfar-Devorador, Musgo-da-Lembrança,
Cipó-Pescador, Crocodilo-Cinzento, Libélula-Lâmina, Peixe-Cego, Sapo-Cantor, Coisa-que-Foi-Cavalo,
Verme-Sanguessuga-Mestre), as 27 de Nova Arcádia, e os docs de outras regiões que apareceram no
caminho (Mergulhadores-Saqueadores e Tartaruga-Ruína, de Aethelgard).

Inspirações externas (R12, só ideia, fonte registrada na ficha e no fim do doc de arte): corpos de
turfeira (Tollund, Grauballe), adipocera, âmbar com insetos, castores, insetos patinadores
(Gerridae), tartaruga-aligátor, peixe-arqueiro (Toxotes), regeneração de salamandras, musaranhos
de dente vermelho, arraias de rio e linguados.

## 1. Os 46 conceitos

Legenda: **F** = ficou · **C-A** = cortado pelo autor (motivo) · **C-R** = cortado pelo revisor.

### Corpos reescritos (Reescritos)

| # | Conceito | Decisão |
|---|---|---|
| 1 | **Estaqueiro Afogado** — afogado de pele de adipocera na Cripta, finca estacas e estica um cordão diante dos outros | F |
| 2 | **Romeiro de Âmbar** — doente da Praga que vive de chá há 20 anos; resina cor de âmbar em placas sobre a carne viva | F |
| 3 | **Banhado do Centro** — veterano banhado no sangue de Malagor; ferrugem negra cai em placas sobre músculo novo | F |
| 4 | **Curtido da Turfeira** — quem deitou na lama, curtido pela turfa, sem ossos | F (slot `enemy_zumbi_blindado`) |
| 5 | Enraizado do Tumor — infectado pelo Tumor cujas pernas viraram raiz | C-A: Tumor ficou com o Jardineiro; "gente que vira pântano" repete a Borda |
| 6 | Sentado do Salgueiro — quem sentou sob o Salgueiro-Chorão e virou casca | C-A: variante meio-humana do Salgueiro-Chorão |
| 7 | Cinzéu da Âncora — Cinzéu da coalizão afogado, correntes das costas presas à lama | C-A: Afogado-da-Batalha de outra raça |
| 8 | Lycan afogado no ciclo — Praga dos Ossos que continuou crescendo na água | C-A: nenhuma criatura nova é Lycan (fora de escopo); repete o Rosário |
| 9 | Pulmão de Turfa — coletor de pulmões tomados por musgo | C-A: repete o Fole de Costela |
| 10 | Corpo-Covo — costelas da Praga dos Ossos viradas em armadilha de peixe | C-A: Praga dos Ossos em afogado = Rosário de Vértebras |
| 11 | Escorrido — corpo dissolvendo da cintura para baixo | C-A: ooze disfarçado |
| 12 | Inchado de Névoa — cadáver cheio de gás da névoa que estoura | C-A: repete o "quem deitou" do Curtido e o estouro do Lençol |
| 13 | Boca de Peixe-Cego — pescador da borda que virou o peixe que comia | C-A: variante meio-humana do Peixe-Cego |
| 14 | Sombra de Lodo — sombra da guerra de Malagor com corpo de lama | C-A: perigo perto do conceitual |

### Bestas da entropia (Bestas Tortas)

| # | Conceito | Decisão |
|---|---|---|
| 15 | **Castor de Estacas** — rói as estacas de medição; a água que represa não desce | F |
| 16 | **Patinador de Óleo** — inseto de pernas de junco; a película de óleo e Éter o segura | F |
| 17 | **Cágado de Geada** — casco de geada que não derrete; mordida que gela | F |
| 18 | **Fundeiro da Poça** — peixe de boca em tubo; o jato de água oleosa bate como pedra | F |
| 19 | **Tritão de Sobra** — o ciclo acelerado regenera cada ferida como um membro a mais | F |
| 20 | **Musaranho de Dente Vermelho** — o Éter desfaz a comida antes de alimentar; come sem parar | F |
| 21 | **Borda que Anda** — barranco de turfa com as estacas de medição na espinha; o chão firme encolhe | F (chefe) |
| 22 | Ninfa de Máscara — larva gigante de Libélula-Lâmina com o lábio que dispara | C-A: filhote da Libélula-Lâmina (marcador de variante) |
| 23 | Caramujo de Retalho — concha de escamas e cascos colados que apara antes do golpe | C-A: casco de destroços = Tartaruga-Ruína; "adiantado" = Rã de Lótus |
| 24 | Percevejo de Ninhada — percevejo d'água com ovos nas costas que eclodem em lacaios | C-A: quarto inseto aquático; invocador sem física torta |
| 25 | Girino de Uma Noite — vive a vida inteira numa luta | C-A: terceiro anfíbio da região; o ciclo ficou com o Tritão |
| 26 | Boi de Turfa — boi de pele de turfa | C-A: reskin da Porca da Queda (quadrúpede de lama) |
| 27 | Lontra Afogadora — segura a presa debaixo da água | C-A: afogar de pé é do Bagre de Varal |
| 28 | Baiacu de Gás — peixe inflado de gás de pântano que flutua e explode | C-A: Fogo-Fátuo + estouro do Lençol |
| 29 | Peixe-Pulmão da Lama — dorme em casulo e morde quem pisa | C-A: emboscada por baixo = Cavadeira de Unhas |
| 30 | Lagostim de Ferro de Turfeira — carapaça de ferro do esgoto do Anel de Ferro | C-A: só material; sem física quebrada |

### Humanoides que pagaram o preço (Cobrados)

| # | Conceito | Decisão |
|---|---|---|
| 31 | **Podador do Ciclo** — druida cujos antebraços viraram podões de osso; corta o Ferimento e leva uma Carta | F |
| 32 | **Jardineiro de Tumores** — Renegado com Tumores plantados nas costas; semeia nas feridas | F |
| 33 | **Mula de Lágrimas** — contrabandista que engole Lágrimas-de-Éter; barriga translúcida | F |
| 34 | **Casaco de Sanguessugas** — saqueador que veste Sanguessugas-Braço para não sentir o Pântano | F |
| 35 | **Turno Vencido** — druida que ficou além do turno; a argila ritual fechou a cabeça num pote | F |
| 36 | Mergulhador de Espólio — saqueador de pulmão de sino que puxa para o fundo | C-A: é o Mergulhadores-Saqueadores de Aethelgard |
| 37 | Corvo de Vara — recolhedor de corpos da borda | C-A: Corvos já em NA; rumor dos corpos da Guilda roça segredo da 348 |
| 38 | Fumante de Ervas — druida de pele defumada pelo ritual | C-A: nuvem repete Fole/Arraia |
| 39 | Afundada — seguidora de Saelwen com líquen e olhos de água parada | C-A: é a descrição da própria Saelwen / retro Druida-Renegado |
| 40 | Ouvinte do Sapo-Cantor — Renegado que se deita para ouvir | C-A: perigo conceitual |

### Crias de apetite (demônios encarnados)

| # | Conceito | Decisão |
|---|---|---|
| 41 | **Regaço da Margem** (Solvhara) — massa sentada de turfa morna; embala, dá Fôlego, rouba a ação | F |
| 42 | **Cordão de Medida** (Skarath) — corda-guia de tendões e punhos; devolve a última jogada | F |
| 43 | **Mãos no Rosto** (Veleth) — braços a mais cobrindo o mesmo rosto; cala a Virtude | F |
| 44 | **Cisne de Pátina** (Morvath) — penas de seda de estandarte podre; o bico envelhece a defesa | F |
| 45 | **Arraia de Lodo** (Thessavar) — disco pardo que sopra lodo e turva o presságio dos outros | F |
| 46 | **Fardo de Espólio** (Daruun) — escudo de torre sobre oito braços de afogado; cobra pedágio | F |
| 47 | Estandarte do Orgulho (Urath) — haste de general cravada na lama | C-A: General-Sem-Nome cobre; Urath é de Zhur |
| 48 | Abraço de Rivais (Vhrak) — dois saqueadores fundidos se esfaqueando | C-A: é o Abraço Duplo cortado na onda 1 |

## 2. Lista do autor (21 novas + 1 slot)

Reescritos (3 + slot): Estaqueiro Afogado · Romeiro de Âmbar · Banhado do Centro · *(slot)* Curtido da Turfeira.
Bestas Tortas (7): Castor de Estacas · Patinador de Óleo · Cágado de Geada · Fundeiro da Poça ·
Tritão de Sobra · Musaranho de Dente Vermelho · Borda que Anda (chefe).
Cobrados (5): Podador do Ciclo · Jardineiro de Tumores · Mula de Lágrimas · Casaco de Sanguessugas · Turno Vencido.
Crias de Apetite (6): Regaço da Margem (Solvhara) · Cordão de Medida (Skarath) · Mãos no Rosto
(Veleth) · Cisne de Pátina (Morvath) · Arraia de Lodo (Thessavar) · Fardo de Espólio (Daruun).

Cotas (U12, `COTAS_ONDA["pantano_melancolia"]`): famílias 4/7/5/6; lacaio 6, padrão 9, elite 6,
chefe 1; 13 papéis e 9 arquétipos; 6 demônios (Solvhara obrigatória; 4 que a onda 1 não usou:
Skarath, Veleth, Morvath, Thessavar); habitat Borda 14, Profundezas 13, Cripta 4.

## 3. Cortes do revisor

Rodada 1: C-1 Estaqueiro (vazava o segredo da Cripta) e C-2 Banhado (reskin do Caído do Cadinho) reescritos; P2-5 do Curtido aplicado. Rodada 2: APPROVED_WITH_FOLLOWUPS. Detalhe em `handoffs/SPEC-359-independent-review.md` e na SPEC-359 §9.
