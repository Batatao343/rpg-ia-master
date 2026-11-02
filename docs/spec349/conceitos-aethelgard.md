# Bestiário de Valoria · onda Aethelgard — conceitos (gerar 2× e cortar, R9)

Processo (o da onda 1): tabuleiro de 25 vagas (21 novas + 4 slots) com eixos fechados **antes** da
prosa (`data/bestiario/fichas/aethelgard.yaml` → `vagas:`, verde com `lint.py --vagas` e conferido
contra as 5 fichas retro: nenhum par passa de 3 eixos iguais), depois 50 conceitos de 1 linha, corte
pelo autor (Opus) até 25, prosa, e corte independente do revisor de unicidade (Opus).
Resultado do autor: **21 novas + 4 slots** (`enemy_esqueleto_mago`, `enemy_fantasma`,
`enemy_golem_carne` e `mon_quimera_cristal`, reinventados no slot).

Comparado contra: as 5 retro da região (Afogado de Aethelgard, Mergulhador Saqueador, Cultista da
Destilação, Faísca da Destilação, Vigia de Caco); os 30 docs `monsters/` de Aethelgard no Codex
(Peixe-de-Padrão, Enguia-de-Éter, Planta-Vertical, Caranguejo-Relíquia, Memória-de-Parede,
Corrente-de-Éter, Cristal-de-Oghma, Luz-Afogada, Conselheiro-Afogado, Eco-do-Aprendiz,
Amálgama-Submerso, Voz-de-Thessrak, Guardiões-da-Entrada-Seca, Bocas-Filhas de Thessrak, O Que
Estava no Fundo, Corrente-Primordial, Peixe-Que-Sonha-a-Cidade, Alga-Luminosa, Lírio-d'Água-Afogado,
Coral-de-Memória, Junco-Sussurrante, Enguia-Elétrica, Tartaruga-Ruína, Cardume-Espelho,
Bibliotecário-Afogado, Reflexo-na-Água-Parada, Última-Chama-Submersa); as 27 de Nova Arcádia e as 22
do Pântano.

Âncoras usadas: o lago de cratera que o mar invadiu pela garganta da Era 6 (sal, bichos do mar);
Oghma e a pressão que empurra de dentro para fora; as câmaras da Destilação e os voluntários; os
cristais de contenção que o aprendiz apagou; as bocas de Thessrak; Morvath nas Ruínas; o Povo-Recife
(coral na carne, calcificação); as Correntes-de-Éter, a Alga-Luminosa e o Cristal-de-Oghma; os
mergulhadores veteranos (Yera); Silas Vane comprando partes (âncora obrigatória do slot do Golem).

Inspirações externas (R12, só ideia, fonte registrada na ficha e no fim do doc de arte): aranha-de-sino
(*Argyroneta aquatica*), nudibrânquios e cleptocnidos, camarões-limpadores, peixe-vidro
(*Kryptopterus*), pernaltas.

## 1. Os 50 conceitos

Legenda: **F** = ficou · **C-A** = cortado pelo autor (motivo) · **C-R** = cortado pelo revisor.

### Corpos reescritos (Reescritos)

| # | Conceito | Decisão |
|---|---|---|
| 1 | **Doador Inacabado** — voluntário élfico da Destilação que não terminou de ser consumido; veias de cristal vazias, bebe o que falta | F |
| 2 | **Dentado de Eras** — mergulhador que ouviu as bocas do selo; a mandíbula dá dentes de todas as eras, que descem em placas pelo pescoço | F |
| 3 | **Avesso de Oghma** — virado do avesso pela pressão perto de Oghma; anda de barriga para cima com a gaiola de costelas aberta, que estoura | F |
| 4 | **Fervido da Corrente** — mago que atravessou uma Corrente-de-Éter: pele inteira sobre cinza fervente; escalda quem bate | F |
| 5 | **Iniciado Refratado** — iniciado do conselho com a medula em cristal; prismas furam a pele e devolvem a luz num feixe | F (slot `enemy_esqueleto_mago`) |
| 6 | **Nadador Transparente** — afogado de carne clara como água; na borda, só se vê o esqueleto nadando | F (slot `enemy_fantasma`) |
| 7 | **Encomenda Costurada** — três afogados conservados, costurados para caber num caixote de embarque; guarda a remessa | F (slot `enemy_golem_carne`) |
| 8 | Casco de Cracas — afogado coberto de cracas que cortam quem bate | C-A: crosta viva na carne fica com o Aspirante de Coral; reação a golpe fica com o Fervido |
| 9 | Salgado da Garganta — afogado coberto de sal onde o mar entra | C-A: sal em corpo morto = Velório de Sal (NA) |
| 10 | Mortalha de Ar — afogado envolto numa bolha prateada | C-A: ar preso é da Aranha de Bolha; o "fantasma" virou o Nadador |
| 11 | Ouvinte de Bocas — mergulhador com bocas novas abrindo no pescoço | C-A: variante meio-humana das Bocas-Filhas; virou o Dentado (dentes, não bocas) |
| 12 | Molde de Câmara — corpo atravessado pela grade de cristal da câmara | C-A: cristal saindo do corpo = Iniciado |
| 13 | Pescador de Padrão — escamas nos olhos de tanto olhar o Peixe-de-Padrão | C-A: transe é perigo conceitual; variante do Peixe-de-Padrão |
| 14 | Conselheiro de Gola — conselheiro preservado pelo Éter | C-A: o Conselheiro-Afogado já existe no Codex |

### Bestas da entropia (Bestas Tortas)

| # | Conceito | Decisão |
|---|---|---|
| 15 | **Cação de Lastro** — cação do mar leve demais para a água; engole pedras das Ruínas e sobe quando perde o lastro | F (chefe) |
| 16 | **Biguá de Vidro** — ave de mergulho de penas vidradas pelo Éter; mergulha, corta e volta à estaca | F |
| 17 | **Aranha de Bolha** — aranha d'água do tamanho de um homem com sino de ar entre os arcos; prende nos fios | F |
| 18 | **Lesma de Penacho** — lesma do mar que come Éter e o guarda nas pontas do penacho; rouba o feitiço da mão | F |
| 19 | **Ouriço de Lajedo** — ouriço do mar cujos espinhos continuam crescendo na carne | F |
| 20 | **Cupinzeiro de Vidro** — cupins que comem os cristais de contenção apagados e cospem paredes de vidro | F |
| 21 | **Camarão Faxineiro** — enxame que limpa os Afogados e fecha as feridas deles com quitina | F |
| 22 | **Ariranha de Arcada** — ariranha de bigodes de cristal que monta as Correntes-de-Éter para dar o bote | F (slot `mon_quimera_cristal`) |
| 23 | Ostra Nacarada — cobre de nácar o que a toca | C-A: imobilizar por crosta repete o Aspirante; sésil de mineral = Cupinzeiro |
| 24 | Lagostim de Chumbo — fica pesado e puxa para o fundo | C-A: a física do peso é do Cação, mais legível em arte |
| 25 | Garoupa de Arco — suga a presa para dentro da boca | C-A: puxar o alvo repete a Aranha |
| 26 | Moreia de Arcada — enguia que mora nos arcos | C-A: o Codex já tem duas enguias na região |
| 27 | Salamandra Cega da Entrada — anfíbio translúcido da Câmara Seca | C-A: anfíbio de caverna = Tritão de Sobra (Pântano) e Nadador |
| 28 | Morcego de Prisma — grito que volta dos cristais | C-A: ataque de som sem corpo novo; fraco em arte |
| 29 | Siri da Maré Morta — sai nas três horas de maré baixa | C-A: crustáceo de ninho = Caranguejo-Relíquia |
| 30 | Cardume de Lâminas — peixes que cortam em uníssono | C-A: o Cardume-Espelho já existe |

### Humanoides que pagaram o preço (Cobrados)

| # | Conceito | Decisão |
|---|---|---|
| 31 | **Peito de Sino** — mergulhador veterano com o peito alargado pelo Éter num sino; solta o ar num empurrão | F |
| 32 | **Mão de Oghma** — saqueador fundido a um Cristal-de-Oghma; o soco passa o custo a quem apanha | F |
| 33 | **Alambique de Carne** — cultista que destila o próprio sangue por tubos de vidro e o pinga nos aliados | F |
| 34 | **Aspirante de Coral** — mergulhador que pagou por coral no pescoço para ter o fôlego do Povo-Recife; engrossa a cada golpe | F |
| 35 | **Comedor de Alga** — come Alga-Luminosa para ver no escuro sobre Oghma; caça quem conjura | F |
| 36 | Guardião Cego da Entrada — costurou os olhos para não seguir a Luz-Afogada | C-A: os Guardiões-da-Entrada-Seca já estão no Codex; preço por escolha, não por magia |
| 37 | Remendado de Éter — racha a pele e sela com Éter, como Aelwin | C-A: vidro nas rachas = Quebrado de Vitrine (NA); e Aelwin é NPC único |
| 38 | Laçador de Doadores — cultista que caça voluntários com rede | C-A: humano com rede, sem preço no corpo |
| 39 | Recifeiro Desterrado — Povo-Recife exilado no Lago | C-A: o Povo-Recife é raça, não monstro; a âncora foi para o Aspirante |
| 40 | Bebedor de Corrente — atravessou uma Corrente-de-Éter e ganhou força | C-A: virou o Fervido (o que se queimou por dentro) |

### Crias de apetite (demônios encarnados)

| # | Conceito | Decisão |
|---|---|---|
| 41 | **Lambedor de Abóbada** (Morvath) — corpo de sebo pendurado nas abóbadas, lambe a argamassa até o teto ceder | F |
| 42 | **Pernalta do Conselho** (Urath) — golas altas sobre pernas de osso como andas; empurra para baixo o mais inteiro | F |
| 43 | **Véu Faminto** (Lyss) — sino de carne transparente que puxa para dentro tudo de bom que o outro juntou | F |
| 44 | Boia Traidora (Skarath) — boia de couro e bexiga com alças que são dedos; puxa ao fundo quem se apoia | C-R: mesmo molde do Cordão de Medida (Pântano, também de Skarath); trocada pelo Novelo de Anzóis (#51) |
| 45 | **Subida de Cracas** (Dorrhen) — coluna viva de cracas e mexilhões que sobe as paredes por onde todos tentaram sair; cresce em quem respira | F (era Escada de Braços: membros humanos indo para a saída repetiam a Cavadeira de Unhas de NA, C-R) |
| 46 | Divã de Musgo (Morvath) — massa macia que convida a descansar | C-A: "embala e rouba a ação" = Regaço da Margem (Pântano) |
| 47 | Gêmeo de Lodo (Veth) — copia o equipamento de quem está ao lado | C-A: par de corpos rivais já cortado duas vezes (Abraço Duplo, Abraço de Rivais) |
| 48 | Língua do Selo (Thessrak) — língua que saiu pelas rachas do selo | C-A: Thessrak não é um dos 13; parte do corpo dele = variante das Bocas-Filhas |
| 49 | Coroa de Afogados (Urath) — afogados empilhados uns sobre os outros | C-A: massa de afogados = Amálgama-Submerso |
| 50 | Lanterna de Fehk — luz que faz recuar | C-A: Fehk é de Nova Arcádia; luz que engana já é a Luz-Afogada |
| 51 | **Novelo de Anzóis** (Maalrek) — bolo de rede, linha e anzóis amarrado com a pele de quem morreu preso; morde mais fundo quem já está ferido | F (substituto sugerido pelo revisor; segunda cria de Maalrek, de anatomia diferente da Roda de Mandíbulas de NA) |

## 2. Lista final (21 novas + 4 slots, após a rodada 1 do revisor)

Reescritos (4 + 3 slots): Doador Inacabado · Dentado de Eras · Avesso de Oghma · Fervido da Corrente ·
*(slots)* Iniciado Refratado · Nadador Transparente · Encomenda Costurada.
Bestas Tortas (7 + 1 slot): Cação de Lastro (chefe) · Biguá de Vidro · Aranha de Bolha · Lesma de
Penacho · Ouriço de Lajedo · Cupinzeiro de Vidro · Camarão Faxineiro · *(slot)* Ariranha de Arcada.
Cobrados (5): Peito de Sino · Mão de Oghma · Alambique de Carne · Aspirante de Coral · Comedor de Alga.
Crias de Apetite (5): Lambedor de Abóbada (Morvath) · Pernalta do Conselho (Urath) · Véu Faminto
(Lyss) · Novelo de Anzóis (Maalrek) · Subida de Cracas (Dorrhen).

Cotas (U12, `COTAS_PADRAO`; a região ainda não tem entrada em `COTAS_ONDA`): famílias 7/8/5/5
(com slots); lacaio 8, padrão 9, elite 7 (3 novas + 4 slots), chefe 1; 12 papéis e 9 arquétipos;
5 demônios (Morvath, de lugar fixo aqui, mais Urath e Lyss, que nenhuma onda usou, Maalrek e
Dorrhen); habitat Lago 12, Ruínas Submersas 16, Câmara Seca 8.

## 3. Cortes e mudanças do revisor

Parecer completo: `docs/spec349/revisao-aethelgard.md` (revisor de unicidade Opus, independente).

- **Rodada 1 — CHANGES_REQUIRED (13 aprovadas, 11 mudanças, 1 corte).**
  - Corte: **Boia Traidora** (mesmo molde do Cordão de Medida do Pântano, também de Skarath) →
    **Novelo de Anzóis** (Maalrek): dano cresce com os Ferimentos do alvo.
  - **Escada de Braços** → **Subida de Cracas**: membros humanos indo para a saída repetiam a
    Cavadeira de Unhas (NA); fica Dorrhen e o peso que encarece o Fôlego, em cracas e mexilhões.
  - **Peito de Sino**: o sopro repetia o Fole de Costela (NA) → agarra e afunda junto; submerso, o
    alvo perde Fôlego e ele não.
  - **Encomenda Costurada**: sem cera (era o Estaqueiro do Pântano) e sem "Vane paga por afogados"
    (perto de segredo) → fraude de saqueadores que dobraram três Afogados num caixote para vender
    como bicho; o Lago os pôs de pé; a leitura é o corpo dobrado em ângulo de caixa.
  - **Avesso de Oghma**: estouro ao morrer repetia Lençol de Chaminé/Mula de Lágrimas → a gaiola de
    costelas fecha sobre o membro de quem está na frente e tira a Reação; sem pulmões à vista.
  - **Lesma de Penacho**: roubar Carta repetia a Gralha de Crematório → o primeiro efeito de Éter
    que a atinge não fere e volta em quem a toca.
  - **Ouriço de Lajedo**: espinho cravado repetia o Casaco de Sanguessugas → os espinhos que erram
    crescem na laje, que vira espinheiro.
  - **Aspirante de Coral**: "endurece até travar" repetia o Caído do Cadinho → o coral engrossa no
    lugar do último golpe; revezar quem bate quebra o padrão; arquétipo `bruto`.
  - **Fervido da Corrente**: retaliação corpo a corpo repetia o Pajem de Obsidiana → aura que cresce
    a cada Ferimento que ele leva.
  - **Pernalta × Véu** (par interno): a Pernalta rebaixa o mais inteiro (age por último); o Véu fica
    só com os reforços. A Pernalta ganhou a inspiração "pernaltas".
  - **Aranha de Bolha**: prender no lugar repetia o Romeiro de Âmbar → puxa para dentro do sino e
    isola o alvo dos aliados.
  - Notas aplicadas: Nadador explicitamente fora das patrulhas dos Afogados; Ariranha também nas
    Ruínas Submersas.
- **Rodada 2 — um item (R2-1), resto APPROVED.** O Novelo de Anzóis repetia a assinatura da Roda de
  Mandíbulas (NA, também Maalrek): a mecânica virou **refém nas linhas** (toma a forma do preso, e
  metade do dano que o grupo causa no Novelo vai para ele; contra-jogo: cortar a linha ou queimá-la
  antes de bater). O corpo ficou.
- **Revisão cruzada do coordenador (colisão com Brekmar).** O Sino de Enlace de Brekmar, escrito em
  paralelo, também é sino de carne translúcida de Lyss: o **Véu Faminto** trocou de anatomia e virou
  uma trança comprida de cabelo, pele e seda (`serpentiforme`/`couro_tecido`) que guarda nos nós o
  que tomou; a mecânica (puxar os reforços do alvo) ficou. `revisor_unicidade:
  coordenador-revisao-cruzada`.
- Parecer final copiado para `handoffs/SPEC-349-independent-review.md`.
