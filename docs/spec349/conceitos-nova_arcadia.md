# SPEC-349 · onda 1 · Nova Arcádia — conceitos (gerar 2× e cortar, R9)

Processo seguido (Etapa 3): tabuleiro de vagas com eixos fechados **antes** de qualquer prosa
(`data/bestiario/fichas/nova_arcadia.yaml` → `vagas:`, verde em U2/U3/U12 com `lint.py --vagas`
e também contra os eixos das 12 fichas retro), depois ≥ 2× conceitos de 1 linha, corte pelo
autor (fable) até 24, prosa, e corte independente do revisor de unicidade (Opus,
`handoffs/SPEC-349-independent-review.md`). Resultado: **21 novas + 6 slots** (5 reinventados,
1 adotado). Em 28/10 o coordenador trocou duas adoções (Brasa Profunda e Polvo dos Destroços)
por reinvenções escritas pelo Opus (§4).

Fontes: só `lore_nova/` (branch da SPEC-348) e o Codex. Nenhuma inspiração externa registrada
(R12: a lista no fim do doc de arte está vazia de propósito). Referências que *não* foram
usadas de propósito: bestiários de manual (gárgula, golem, ooze, elemental, Frankenstein,
kraken), cuja silhueta o revisor ainda apanhou em 3 propostas e foram reescritas.

## 1. Os 48 conceitos (1 linha cada)

Legenda: **F** = ficou na lista do autor (24) · **C-A** = cortado pelo autor · **C-R** = cortado
ou substituído pelo revisor · **R** = reescrito após o revisor.

### Corpos reescritos (Reescritos)

| # | Conceito | Decisão |
|---|---|---|
| 1 | **Arame Vivo** — Praga de Ferro terminal: veias viradas em arame para fora da pele; drena por contato | F |
| 2 | **Fole de Costela** — Tosse de Ferro: costelas abertas em fole de escória que sopra fuligem | F |
| 3 | **Rosário de Vértebras** — Praga dos Ossos num afogado: medula costura vértebras de muitos mortos no rio | F |
| 4 | **Fila de Grilhões** — servos do Mercado de Carne soldados à própria corrente pela Praga | F |
| 5 | **Relicário de Osso** — medula da Praga dos Ossos cresce através do altar da Catedral | R → *Relicário da Catedral* (cristal de Éter, não medula: repetia o Rosário) |
| 6 | **Remendado de Vane** — paciente do Doutor costurado com cobre, fareja sangue | R → *Sangrado da Clínica* (sem Vane no público; mecânica própria) |
| 7 | Pajem de Obsidiana — servo do Palácio reescrito pelo que as paredes transpiram | F (virou o slot `enemy_sentinela_ferro`) |
| 8 | Carpa de Ferrugem — peixe dos rios que bebem o esgoto, escamas de óxido | C-A: fraco; peixe de rio não luta na cidade |
| 9 | Pulga de Grilhão — pulgas do Mercado de Carne que saltam e bebem ferro | C-A: segunda ideia de "grilhão"; miúda demais para vaga |
| 10 | Quebrado de Cristal — Elfo do Dourado cristalizado pelo Pó de Fada, exposto nos Jardins | C-A primeiro (sessil fraco); voltou como *Quebrado de Vitrine* na família Cobrados |
| 11 | Mastim de Escória — cão do Fosso mineralizado pela carne da Praga | C-A: reskin do Cão de Rebite (cão + ferro) |
| 12 | Cavalo de Carroça dos Corvos — cavalo que puxou mortos da Praga por anos, veias de ferro | C-A: reskin da Coisa-que-Foi-Cavalo (cavalo morto do pântano) |

### Bestas da entropia (Bestas Tortas)

| # | Conceito | Decisão |
|---|---|---|
| 13 | **Lençol de Chaminé** — baratas de escória soldadas numa placa com brasa presa dentro | F |
| 14 | **Traça do Sino Mudo** — mariposa que come o som dos sinos; em volta tudo fica surdo | F |
| 15 | **Gralha de Crematório** — corvídeo de cinza dos fornos dos Corvos, paira sem bater asa, rouba | F |
| 16 | **Porca da Queda** — porca que comeu A Queda do Pó de Sonho; pesa errado, o chão cede | F |
| 17 | **Centopeia da Torre Invertida** — vive nas paredes do Oubliette de cabeça para baixo, cai para cima | F |
| 18 | Pombo de Chumbo — pombos das cornijas de obsidiana com penas de chumbo, caem como pedra | C-R: gárgula disfarçada; 2ª ave; repetia o "peso errado" da Porca → *Rã de Lótus* |
| 19 | Rã de Lótus — rã dos tanques dos Jardins, cores que não existem, olhos adiantados meio segundo | F (slot `enemy_gargula_ferro`, 2ª rodada) |
| 20 | Lagartixa de Obsidiana — buraco de luz com patas, caça nos telhados do Dourado | C-A: colidia com o Pajem (obsidiana) |
| 21 | Aranha de Cornija — teias de fio que absorvem luz | C-A: sem física quebrada legível; teia = clichê |
| 22 | Gato de Pó — gato de casa nobre, ronrona sono | C-A: conceito mole; "sono" vira perigo conceitual |
| 23 | Morcego de Beiral — morcegos que ecoam o sino antes do toque | C-A: 2 criaturas de sino; Morcego já existe em outra região |
| 24 | Sanguessuga de Telhado — sanguessuga que sobe pela chuva ácida das chaminés | C-A: Sanguessuga-Braço já é do pântano vizinho |

### Humanoides que pagaram o preço (Cobrados)

| # | Conceito | Decisão |
|---|---|---|
| 25 | **Sorvedouro do Código** — Inquisidor com o funil de sugar Éter enxertado no esterno | F |
| 26 | **Pavio da Lista** — mago da Lista de Fornalha consumido como combustível | R: silhueta steampunk (caldeira de rodas) → gaiola nas costas de um carregador |
| 27 | **Enxerto da Fornalha** — Encapuzado com lâmina de Aço de Sangue enxertada no ombro | R: mecânica "ignora metal" repetia o Portão → "lâmina que puxa" |
| 28 | Vela da Chama Azul — fanático queimado por dentro, boca costurada, arde de uma vez | C-R: versão avançada do Iniciado retro; explosão repetia o Lençol |
| 29 | Costurador de Dentes — necromante amador com mandíbula de dentes comprados | C-R: é o Cortadores de Dente da lore com outra pele |
| 30 | **Quebrado de Vitrine** — Elfo de estimação virado vidro rachado; a luz que o atravessa ampara os outros | F (entrou na 2ª rodada no lugar de 28/29) |
| 31 | Varredor do Forno — coveiro dos Corvos que morreu e continua varrendo | C-A: morto-vivo de dívida = Refugo-do-Mercado |
| 32 | Informante Oco — agente da Mão Sombria sem memórias, rosto liso | C-A: Máscara-da-Casa cobre; "rosto liso" repetido |
| 33 | Legionário de Aço de Sangue — soldado cuja armadura ganhou vontade | C-A: reskin do Soldado retro + Sangue-de-Aço |
| 34 | Criança da Quadrilha viciada em Pó | C-A: criança como inimigo, não |
| 35 | Jardineiro de Lótus — mago dos Jardins que virou conduto | C-A: é o Servo-Iluminado do Codex |
| 36 | Capataz de Contrato — funcionário do Mercado que assinou a si mesmo | C-A: humano comum; sem corpo reescrito |

### Crias de apetite (demônios encarnados)

| # | Conceito | Decisão |
|---|---|---|
| 37 | **Vira-Costas da Praça** (Fehk) — corpo só de costas e cotovelos, só bate em quem o toca | F |
| 38 | **Roda de Mandíbulas** (Maalrek) — roda de doze cabeças de cão com cubo de mãos de apostadores | F (chefe) |
| 39 | **Cavadeira de Unhas** (Dorrhen) — bicho de dedos de osso que cava e sai por baixo | F |
| 40 | **Convidado de Cera** (Veth) — convidado de cera de candelabro, sem rosto, joias alheias | F |
| 41 | Abraço Duplo (Skarath) — dois homens costurados pelas costas, um cordial e um de facas | C-R: par com o Vira-Costas (dois "de costas"); traidor de duas caras |
| 42 | **Escritura Rastejante** (Daruun) — rolo de contratos de pele que rasteja e cobra | R: sem enroscar (repetia o Arame); só Anel de Ferro |
| 43 | **Portão que Morde** (Vhrak) — portão entre anéis com barras em presas e dentes cuspidos | F |
| 44 | Trouxa de Luto (Solvhara) — trouxa de lama com pertences de mortos que abraça | C-R: mesma silhueta/material da Coisa do Esgoto → *Velório de Sal* (slot `enemy_golem_lixo`) |
| 45 | Lenço Molhado (Fehk, lacaio) — mordaça de pano que rasteja e tapa bocas | C-A: 2ª cria de Fehk; só uma é obrigatória, e esta é mole |
| 46 | Martelo de Greve (Vhrak) — cabeças de martelo e capuzes fundidos num brigão | C-A: acoplado já estava no Abraço; Vhrak ficou com o Portão |
| 47 | Espelho de Vergonha (Veleth) — cria da Casa dos Espelhos de cacos e rostos | C-A: Eco-do-Espelho e Máscara-da-Casa já cobrem a Casa |
| 48 | Estátua de Orgulho (Urath) — estátua de obsidiana de nobre que se recusa a cair | C-A: estátua viva = gárgula/golem; Urath é de Zhur |

## 2. Cortes do revisor (rodada 1) e o que foi feito

| Corte/pedido | Aplicado |
|---|---|
| Costurador de Dentes: cortar (Cortadores de Dente) | cortado |
| Vela da Chama Azul: cortar (Iniciado avançado) | cortado; Quebrado de Vitrine entrou para manter `humanoide_preco` ≥ 4 e o Anel Dourado |
| Abraço Duplo: reescrever ou cortar | cortado (Skarath fica para outra onda) |
| Pombo de Chumbo: reescrever (gárgula) | substituído por Rã de Lótus no mesmo slot |
| Trouxa de Luto: reescrever (golem de lixo) | substituída por Velório de Sal no mesmo slot |
| Brasa Profunda e Polvo dos Destroços: trocar | aplicado em 28/10 pelo coordenador: os dois slots viraram reinvenção (Caído do Cadinho e Bagre de Varal, §4) |
| Remendado de Vane: reescrever (Frankenstein, vazamento) | reescrito duas vezes; virou Sangrado da Clínica (sangrado pela lanceta, branco e leve; sem retalhos, sem Vane); mecânica própria (age 2× se não ferido) |
| Relicário de Osso: reescrever (repete o Rosário) | reescrito: cristal de Éter da água da Catedral, sem medula, sem oração |
| Enxerto: ajustar mecânica | "lâmina que puxa" (arranca a defesa preparada) |
| Escritura × Arame: mudar uma | Escritura lê cláusulas à distância (custo dobrado), sem contato |
| Fila: gancho copia o Refugo | gancho trocado (corrente + pescoço endurecido) |
| Pavio: silhueta steampunk | gaiola de ferro nas costas de um carregador; anda |
| Refs "trocadas" (P1-2/P1-3) | **não aplicado**: as linhas são da lore da SPEC-348 (que pousa antes); ver §9 |

## 3. Lista final da onda (21 novas + 6 slots)

Reescritos (6): Arame Vivo · Fole de Costela · Rosário de Vértebras · Fila de Grilhões ·
Relicário da Catedral · Sangrado da Clínica · *(slots)* Pajem de Obsidiana · Caído do Cadinho.
Bestas Tortas (5): Lençol de Chaminé · Traça do Sino Mudo · Gralha de Crematório · Porca da Queda ·
Centopeia da Torre Invertida · *(slots)* Rã de Lótus · Coisa do Esgoto · Bagre de Varal.
Cobrados (4): Sorvedouro do Código · Pavio da Lista · Enxerto da Fornalha · Quebrado de Vitrine.
Crias de Apetite (6): Vira-Costas da Praça (Fehk) · Roda de Mandíbulas (Maalrek, chefe) ·
Cavadeira de Unhas (Dorrhen) · Convidado de Cera (Veth) · Escritura Rastejante (Daruun) ·
Portão que Morde (Vhrak) · *(slot)* Velório de Sal (Solvhara).

Cotas (U12): famílias 6/5/4/6 (≥ 4); lacaio 6, padrão 9, elite 5, chefe 1; 11 papéis táticos e
10 arquétipos distintos; 7 demônios distintos (Fehk obrigatório); cada anel com ≥ 5 habitats.

## 4. Os dois slots refeitos (28/10, autor Opus)

O revisor reprovou as adoções de `enemy_elemental_fogo_poluido` (Brasa Profunda: lore do Reino
Subterrâneo e, no corpo, o elemental de fogo de manual) e de `enemy_polvo_esgoto` (Polvo dos
Destroços: lore da costa, sem física quebrada). O coordenador decidiu reinventar os dois no mesmo
id. Foram 6 conceitos para 2 vagas (R9):

| # | Conceito | Decisão |
|---|---|---|
| 49 | **Caído do Cadinho** — fundidor com a Ferrugem do Sangue que caiu na panela de gusa; o ferro das veias chamou o metal, e ele saiu com placas de escória sobre músculo em brasa; esfria até travar e parte a crosta para voltar | F (slot `enemy_elemental_fogo_poluido`, família Reescritos) |
| 50 | **Bagre de Varal** — bagre sem pele, placas de osso sobre o músculo, que nada pelo ar do Anel de Lama dentro de um bolsão de água do Pântano que não cai; afoga de pé | F (slot `enemy_polvo_esgoto`, família Bestas Tortas) |
| 51 | Prisioneiro-do-Nível-Dez (adoção, sugestão do revisor) | C-A: o doc é um grupo ("magos selvagens e monstros"), sem anatomia; o Oubliette já é da Centopeia; fixar o que O Cego evita apagaria o mistério da lore |
| 52 | Pele de Rua — predador chato sob a crosta de lama rachada das ruas (as crianças andam pela borda) | C-A: "vem de baixo e prende o pé" repete a Cavadeira e a Porca |
| 53 | Enguia de Lixívia — enguia de pele cáustica dos canais das lavadeiras | C-A: a Enguia-da-Lama já existe no Codex; sem física quebrada |
| 54 | Lote Leve — o lingote de Aço de Sangue que saiu com a forma do homem | C-A: o Aço de Sangue já é do Enxerto e do Sangue-de-Aço |

Referência de acerto seguida nos dois: a do Lycan (placas sobre músculo exposto). No Caído, as placas
são de escória sobre carne em brasa. No Bagre, são placas de osso de peixe de fundo sobre o músculo que
o despejo deixou sem pele.
