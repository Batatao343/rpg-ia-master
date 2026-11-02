# SPEC-349 · esteira · Costa Negra (Cemitério de Leviatãs) — conceitos (gerar 2× e cortar, R9)

Processo (Etapa 3, padrão das ondas 1 e 2): tabuleiro de 22 vagas com eixos fechados **antes** da
prosa (`data/bestiario/fichas/costa_negra.yaml` → `vagas:`, verde com `lint.py --vagas` e contra as
7 fichas retro), depois 46 conceitos de 1 linha, corte pelo autor (Opus) até 22, prosa, e corte
independente do revisor de unicidade (Opus).
Resultado do autor: **22 novas**. A curadoria (`curadoria_legado.yaml`) não tem slot genérico com
`regiao_onda: costa_negra`: as 7 entradas da região são `classe: valoria` e entram como retro (R6).

Comparado contra: as 7 retro da Costa (Tubarão de Casco, Caranguejeiro da Maré, Gaivota-Ladra, O Que
Come nas Praias, Carrapato de Osso, Saqueador de Marfim, Filhote de Baleia-Ossário); os 44 docs
`monsters/` com a tag `costa_negra` (Caranguejeiro, Caranguejo-Rei-de-Carcaça, Verme-de-Osso,
Verme-Luminoso-de-Osso, Ave-Perfuradora, Rapina-de-Osso, Gaivota-Carniceira-Gigante,
Serpente-de-Maré, Charadeiro-de-Âmbar, Polvo-de-Crânio, Polvo-dos-Destroços, Enguia-do-Cais,
Sombra-de-Cardume, Sombra-de-Leviatã, Eco-de-Caçada, Coração-Que-Bate-Ainda, Canto-do-Trono,
O Que Se Vestiu de Leviatã, Comedores-de-Deus-Morto, O Leviatã-Que-Não-Foi-Caçado, Primeiro-Osshari-
Afogado, Maré-Que-Lembra, Coletores-de-Âmbar, Náufragos-do-Cemitério, Âmbar-Vivo, Coral-de-Osso,
Cogumelo-de-Carniça, Afogados-do-Porto, Capitão-Sem-Porto, Tripulação-Amaldiçoada e os de Brekmar);
as 27 de Nova Arcádia e as 22 do Pântano.

Crias de demônio: Lyss (a vizinha de Brekmar, nunca usada), Dorrhen, Maalrek, Veth e Vhrak, todas
com anatomia (`plano_corporal`, `material`) diferente das crias do mesmo demônio nas ondas 1–2 (R29).
Urath fica para Zhur; Daruun e Solvhara já têm duas crias cada.

Inspirações externas (R12, só ideia, fonte registrada na ficha): hidropisia de peixes (escamas em
pinha), cortes de coral, *ectopia cordis*, Jonas e os relatos de baleeiros engolidos, isópode gigante
(*Bathynomus*), estrelas-do-mar que abrem mexilhões, cracas e *Sacculina*, elefante-marinho,
saltador-do-lodo, peixe-bruxa, iguana-marinha, raqueiros da Cornualha (*wreckers*), galés a remo,
ganchos de esfola da caça à baleia, barbas de baleia.

## 1. Os 46 conceitos

Legenda: **F** = ficou · **C-A** = cortado pelo autor (motivo) · **C-R** = cortado pelo revisor.

### Corpos reescritos (Reescritos)

| # | Conceito | Decisão |
|---|---|---|
| 1 | **Escama Revirada** — Osshari dos canais antigos com as escamas arrepiadas e soltas; espirra lascas em quem o acerta | F |
| 2 | **Ferida de Coral** — coletor cortado no Coral-de-Osso; o coral cresce no braço e planta galho na ferida de quem ele corta | F |
| 3 | **Compassado do Trono** — dormiu no Trono; peito aberto, coração exposto no ciclo do Trono; para morto e dispara | F |
| 4 | **Forrado de Leviatã** — vestiu placas cruas de osso de leviatã; o osso enraizou e cresce sobre músculo exposto | F |
| 5 | **Hóspede do Estômago** — arpoador fechado num estômago vivo do Trono; anda dentro dele, e o estômago digere o que ele agarra | F (chefe) |
| 6 | Respirador do Trono — costelas viraram fole no ritmo do Trono e sopram gás de carcaça | C-A: é o Fole de Costela (NA); o ritmo do Trono ficou com o Compassado |
| 7 | Garganta de Âmbar — comedor de âmbar cinza com nódulos de resina saindo da barriga | C-A: resina em placas = Romeiro de Âmbar (Pântano) |
| 8 | Caiado de Sal — náufrago que cristalizou em sal de Éter | C-A: Velório de Sal (NA) |
| 9 | Tutanoso — Lycan que comeu tutano de leviatã e travou no meio do ciclo | C-A: nenhuma criatura nova é Lycan (regra da onda 2) |
| 10 | Inchado de Gás — cadáver cheio do gás das câmaras que estoura | C-A: estouro de gás já cortado no Pântano; perigo de cenário, não de criatura |
| 11 | Fumado de Esporos — prateleira de fungo saindo do rosto; revive a morte do leviatã | C-A: visões = perigo conceitual; fungo em gente = Jardineiro de Tumores |
| 12 | Bebedor de Óleo — óleo de leviatã no lugar do sangue; acende-se | C-A: corpo que queima = Pavio da Lista (NA) |

### Bestas da entropia (Bestas Tortas)

| # | Conceito | Decisão |
|---|---|---|
| 13 | **Barata das Costelas** — isópode gigante do fundo; enrola em bola e desce a encosta de ossos como barril | F |
| 14 | **Estrela de Alavanca** — estrela-do-mar de braços de vértebra; agarra o escudo pelas bordas e abre como mexilhão | F |
| 15 | **Andarilho de Cracas** — lobo-marinho coberto e guiado por uma colônia de cracas que cimenta larvas na armadura | F |
| 16 | **Touro de Banha** — elefante-marinho de banha de carcaça; a tromba virou aríete de cartilagem e osso | F |
| 17 | **Saltador de Poça** — saltador-do-lodo de olhos em haste de osso; espera na borda, morde e volta para a poça | F |
| 18 | **Bruxa de Carcaça** — peixe-bruxa do tamanho de um homem dentro da carne podre; o muco entope boca e nariz | F |
| 19 | **Petrel de Papo Cheio** — iguana-marinha de glândulas de sal inchadas em bolsas de cristal; espirra salmoura que cega | F |
| 20 | Lampreia de Medula — lampreia que fura osso e gente | C-A: drenador que gruda = Sanguessuga-Braço (retro Pântano); furar osso = Verme-de-Osso |
| 21 | Pescador de Crânio — peixe-pescador nas câmaras do crânio, isca de luz | C-A: luz nas câmaras = Verme-Luminoso; crânio alagado = Polvo-de-Crânio |
| 22 | Caramujo de Gás — fermenta gás de carcaça na concha e acende | C-A: Baiacu de Gás cortado no Pântano; gás é cenário |
| 23 | Saltão de Areia — anfípode do tamanho de um cão, em enxame, limpa corpos | C-A: é o Caranguejo-Maré (creatures.txt:1448), "desencarna um corpo em horas" |
| 24 | Pepino de Fios — pepino-do-mar que dispara fios brancos que colam | C-A: segundo bicho de gosma na mesma praia; a Bruxa tem âncora melhor (vive dentro da carcaça) |
| 25 | Ouriço de Vértebra — ouriço séssil de espinhos de osso nas poças | C-A: segundo equinoderme; a Estrela tem mecânica (abrir defesa) e o ouriço só fere quem pisa |
| 26 | Sino de Geleia — água-viva encalhada que cobre e envolve | C-A: segundo radial; envolver = Ventre Partilhado |
| 27 | Morcego de Costela — morcegos nas costelas que lambem sangue | C-A: morcego-vampiro de manual |
| 28 | Ostra de Olho — ostra gigante com pérola de Éter que fecha na perna | C-A: armadilha de baú (mimico) com concha |
| 29 | Ermitão de Crânio — caranguejo-ermitão que veste crânio humano | C-A: quarto caranguejo da região; vestir ossos = Carrapato de Osso (retro) |
| 30 | Hiena de Costela — cão de praia de gengiva óssea | C-A: Cão de Rebite (NA) de praia |

### Humanoides que pagaram o preço (Cobrados)

| # | Conceito | Decisão |
|---|---|---|
| 31 | **Esfolado de Sal** — Osshari que arranca as escamas para sentir o sal na carne; bebe a dor de quem fere | F |
| 32 | **Contrabandista Vítreo** — da Mão Sombria, prova os venenos de Ophidia; pele vítrea em placas coloridas; cospe | F |
| 33 | **Caldeireiro de Óleo** — derrete banha para os Sindicatos; braços crostados de sebo; o chão em volta vira óleo quente | F |
| 34 | **Acendedor de Naufrágios** — raqueiro dos piratas com um cristal de Éter no lugar do olho e lanterna falsa | F |
| 35 | **Remo Acorrentado** — remador de galé pirata que naufragou acorrentado; a argola afundou no pulso; gira o remo partido | F |
| 36 | Quilheiro de Osso — do Estaleiro das Almas; pó de osso de leviatã calcificou as juntas | C-A: osso de leviatã no corpo = Forrado de Leviatã |
| 37 | Mascador de Âmbar — masca âmbar cinza cru; maxilar de resina | C-A: âmbar no corpo = Romeiro de Âmbar (Pântano) |
| 38 | Carregador de Costela — espinha torta de carregar costelas | C-A: preço sem física torta; deformação de trabalho já é o Remo |
| 39 | Mergulhador de Ophidia — voltou de Ophidia | C-A: ninguém volta de Ophidia (locations.txt:291); abriria mistério |
| 40 | Remendado da Casa das Marés — servo de Lyss preso a outro pela mão | C-A: virou a cria de Lyss (Ventre Partilhado), que é o lugar certo para isso |

### Crias de apetite (demônios encarnados)

| # | Conceito | Decisão |
|---|---|---|
| 41 | **Ventre Partilhado** (Lyss) — dois afogados achados abraçados; um afunda na barriga do outro e os braços livres puxam | F |
| 42 | **Balsa de Último Dia** (Dorrhen) — jangada de tábuas e ossos de náufragos que se arranca as tábuas para bater | F |
| 43 | **Gancho de Esfola** (Maalrek) — seis ganchos de esfolar e tiras de banha; anda pelas costelas e crava o gancho que fica | F |
| 44 | **Raspadeira de Barbatana** (Veth) — bicho de barbas de baleia que raspa e estraga o que brilha | F |
| 45 | **Rancor de Pinças** (Vhrak) — monte de carapaças das guerras de carcaça; devolve cada golpe a quem bateu | F |
| 46 | Pança de Âmbar (Daruun) — barriga que engole âmbar e cobra pedágio | C-A: Daruun já tem duas crias; cobrar pedágio = Fardo de Espólio |
| 47 | Mão Estendida (Skarath) — escada de antebraços que ajuda a subir e solta na câmara de gás | C-A: corda de membros = Cordão de Medida (Skarath, Pântano) |
| 48 | Estandarte de Urath — arpão de general cravado num crânio | C-A: Urath é de Zhur; estátua que não luta |

## 2. Lista do autor (22 novas)

Reescritos (5): Escama Revirada · Ferida de Coral · Compassado do Trono · Forrado de Leviatã ·
Hóspede do Estômago (chefe).
Bestas Tortas (7): Barata das Costelas · Estrela de Alavanca · Andarilho de Cracas · Touro de Banha ·
Saltador de Poça · Bruxa de Carcaça · Petrel de Papo Cheio.
Cobrados (5): Esfolado de Sal · Contrabandista Vítreo · Caldeireiro de Óleo · Acendedor de Naufrágios ·
Remo Acorrentado.
Crias de Apetite (5): Ventre Partilhado (Lyss) · Balsa de Último Dia (Dorrhen) · Gancho de Esfola
(Maalrek) · Raspadeira de Barbatana (Veth) · Rancor de Pinças (Vhrak).

Cotas (U12, `COTAS_PADRAO`; a Costa não tem entrada em `COTAS_ONDA`): famílias 5/7/5/5; lacaio 7,
padrão 9, elite 5, chefe 1; 12 papéis e 9 arquétipos; 5 demônios; habitat Cemitério 19, Trono 7.
Proposta para a spec-filha: `demonios_min: 4` e `habitat_min: {costa_negra: 8, cn_o_trono: 5}`.

## 3. Cortes do revisor

Parecer: `handoffs/SPEC-349-costa_negra-independent-review.md` (revisor Opus, independente do autor).
Rodada 1: **nenhum corte**; 9 aprovadas e 13 com mudança, todas aplicadas na ficha:

- Escama Revirada: deixou de devolver o golpe (era o Pajem de Obsidiana e o Rancor); as escamas caem e o raso vira chão de lascas.
- Ferida de Coral: deixou de "plantar e regar" (Jardineiro de Tumores); a muda trava a junta: perde a Reação, depois a arma daquele braço.
- Compassado do Trono: o ritmo é o do coração que o Canto deixou lento, não o ciclo de seis horas do Trono; `evitar` cita o Sorvedouro do Código.
- Hóspede do Estômago: o estômago é um pedaço refeito pelo Coração-Que-Bate-Ainda (lore ancorada; não é segundo órgão sobrevivente).
- Andarilho de Cracas: a crosta não custa Fôlego (Velório de Sal); na 3ª camada a colônia move o alvo (Sacculina).
- Esfolado de Sal: sem roubo de vida (Hóspede, Musaranho); o Ferimento salgado conta em dobro até lavar. Papel: `perseguidor_marca`.
- Caldeireiro de Óleo: sem caldeirão nas costas (3ª silhueta de carga às costas); o sebo dos braços derrete no fogo e vira a poça.
- Remo Acorrentado: sem varrer a linha (Touro); golpe de alvo único que sobe um grau por rodada seguida, zerado por barulho fora do ritmo.
- Ventre Partilhado: sem puxar para o ventre (Hóspede, Regaço); costura de pele com dano partilhado; silhueta "um homem carregando outro no colo".
- Gancho de Esfola: sem marca que escala com Ferimentos (Roda de Mandíbulas); dilema: mover-se rasga, ficar parado custa Fôlego.
- Raspadeira de Barbatana: não inutiliza Carta (Convidado de Cera, Podador); degrada a arma física até ser afiada.
- Acendedor de Naufrágios, Rancor de Pinças ("bandos", não "tribos") e Forrado ("mais resistente"): só texto.
