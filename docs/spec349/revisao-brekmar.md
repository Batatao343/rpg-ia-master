# SPEC-349 — revisão de unicidade, onda de Brekmar (rodada 1)

> **Veredito:** `CHANGES_REQUIRED`
> **Revisor:** Opus (spec-reviewer, não é o autor) · **Data:** 2026-11-01 · **Commit revisado:** `2724d35f` (branch `bst-brekmar`)

## Escopo

`data/bestiario/fichas/brekmar.yaml` (21 `nova` + 6 `retro`) contra o checklist §3.9 e R5–R12/R23.
Comparado com: a própria onda, as 6 retro, o Codex de Brekmar e da Costa Negra
(`lore_nova/creatures.txt:1408-1560`), `nova_arcadia.yaml` (NA), `pantano_melancolia.yaml` (PM), os
3 segredos indicados e `rumors.txt:270`. Fora do escopo: números, lint e motor (isso fica com o Sol).
Nenhuma ficha foi editada. Não rodei testes, porque a revisão é só de leitura.

Nota de nome: `scripts/check_handoff_names.py` **rejeita** este nome de arquivo. O parecer final
(R10) deve ir para `handoffs/SPEC-349-independent-review.md`; o coordenador move ou funde.

## Por criatura (checklist §3.9: 1 reskin · 2 frase única · 3 Valoria · 4 física/luta · 5 sem segredo)

| # | id | 1 | 2 | 3 | 4 | 5 | Parecer |
|---|---|---|---|---|---|---|---|
| 1 | mon_casco_de_costelas | ok | ok | ok | ok | ok | **APPROVED**. "Voltam com menos gente" é público (`locations.txt:455`). O eco do Coração-Que-Bate-Ainda (osso que refaz corpo) funciona como âncora, não como reskin. |
| 2 | mon_quilhado_do_estaleiro | ✗ | ✗ | ok | ok | ok | **CHANGES**. "Ignora o escudo e racha a peça de proteção" repete o Enxerto da Fornalha (NA, "racha a peça") e o Portão que Morde (NA, quebra a defesa de metal/couro), e choca com a Broca (#20) dentro da onda: são dois `quebra_defesa` que estragam a peça. |
| 3 | mon_odre_de_oleo | ok* | ok | ok | ok | ok | **APPROVED** com nota. É a 3ª criatura "ao cair, estoura em quem está em contato" (Lençol de Chaminé NA, Mula de Lágrimas PM). Passa porque o efeito é outro (marca de óleo que dobra o fogo), mas não deve haver uma 4ª. |
| 4 | mon_lavado_da_mare_vermelha | ok | ok | ok | ok | ok | **APPROVED**. Deriva da Maré-Vermelha-Viva (que puxa para o mar) e anda no sentido contrário dos Afogados-do-Porto. Nota P2 junto da Boia (#19), abaixo. |
| 5 | mon_cardume_coagulado | ok* | ok | ok | ok | ok | **APPROVED** com nota. O dreno por contato lembra o Arame Vivo (NA); o que o distingue é morder todos os que encostam e o relógio de secar. O par com o Lavado na Maré Vermelha não é problema: um é homem controlador, o outro massa de peixe drenadora. |
| 6 | mon_gato_de_lastro | ok | ok | ok | ok | ok | **APPROVED** com nota (saturação de leviatã, abaixo). A causa é a mesma da Tripulação-Amaldiçoada ("navio com osso na quilha muda quem vive nele"), só que num gato. Corpo e mecânica são únicos. |
| 7 | mon_craca_de_amarra | ok | ✗* | ok | ok | ok | **APPROVED**. Fica com a ideia de "casca que protege o aliado", e por isso quem muda é a Sangria (#11). |
| 8 | mon_piolho_de_leviata | ✗ | ✗ | ok | ok | ok | **CHANGES**. Colide no Codex com o Caranguejeiro (crustáceo do tamanho de um cão que come tecido nas carcaças de leviatã; o isópode também é crustáceo). "Foge e ninguém o alcança" repete o Patinador de Óleo (PM, mesmo `batedor_rapido`), e o rolar já é da Roda de Mandíbulas (NA). |
| 9 | mon_pescador_de_lanterna | ok | ok | ok | ok | ok | **APPROVED**. A isca que imita a lanterna de óleo é de Brekmar. Toca o Polvo-dos-Destroços (pega bêbados), mas o corpo e a emboscada são outros. |
| 10 | mon_tripeiro_de_fundo | ok | ok | ok | ok | ok | **APPROVED**. É uma armadilha reativa para as outras criaturas, sem par na região. |
| 11 | mon_sangria_de_aluguel | ok | ✗ | ok | ok | ok | **CHANGES**. Dentro da onda, é a mesma coisa que a Craca: "gruda crosta num aliado e ela segura o próximo golpe" × "cobre o aliado de casca que tira a força dos golpes". Também encosta na "coagulação forçada" do Guarda-Sangrinomante (Codex). |
| 12 | mon_torcido_da_rinha | ok | ok | ok | ok | ok | **APPROVED**. É o único "não sente dor" da onda (o Arpoador retro "sente pouco" é artilharia). Endurecer por ferida difere do Caído do Cadinho (NA), que endurece por rodada. |
| 13 | mon_anzolado_da_casa | ok | ok | ok | ok | ok | **APPROVED**. Com o Sino (#16), a Casa das Marés tem dois: o Anzolado é humano com coleira-punição; o Sino, cria que engole. São distintos. |
| 14 | mon_tambor_do_ossario | ✗ | ok | ok | ok | ok | **CHANGES**. A anatomia e o contra-jogo repetem o Fole de Costela (NA): "barril de costelas abertas" × "costelas abertas como aduelas de barril", e "chegar pelo lado e furar o fole" × "chegar pelos lados e cortar o couro do peito". |
| 15 | mon_penhorado_do_poco | ✗ | ✗ | ok | ok | ok* | **CHANGES**. A mecânica é a da Gralha de Crematório (NA): "rouba a Carta preparada e foge; se cai antes, a Carta volta" × "arranca item/moeda/carta preparada, foge na rodada seguinte; derrubado, devolve". O autor cortou o Biguá (#18 dos conceitos) por esse mesmo motivo. Rato de Cais (retro) e Gaivota-Ladra (Codex) também são ladrões. |
| 16 | mon_sino_de_enlace | ✗ | ✗ | ok | ok | ok | **CHANGES**. É a 3ª da onda em que o alvo fica preso e não age, e a estrutura é a do Casco (#1, chefe): "puxa para dentro; para soltar, rasga-se o corpo de fora". Também repete o Regaço da Margem (PM: preso no colo, não age). "Lyss consome a cidade devagar" é público (`casa_mares_dominio_lyss.md`, `visibility: public`), então não vaza o segredo de Kahen. |
| 17 | mon_carranca_de_proa | ok | ok | ok | ok | ok | **APPROVED**. É a primeira cria de Urath. O duelo com quem mais a feriu, ignorando o resto, não tem par. |
| 18 | mon_rixa_costurada | ok | ok | ok | ok | ok | **APPROVED**. O troco vai para o lado de cada corpo, não para quem bateu, e isso é único. A cria de Vhrak em NA é séssil de ferro, sem choque. |
| 19 | mon_boia_de_bracos | ok | ok | ok | ok | ok | **APPROVED** com nota. O anel de braços abertos encosta no Regaço (PM), mas a contagem de afundar na borda é própria. Nota P2: Lavado e Boia têm o mesmo desfecho ("cai/é puxado para fora da luta pela água"). É aceitável como combo, desde que o motor trate isso como um único efeito de "fora da luta" e não como dois. |
| 20 | mon_broca_de_costado | ✗ | ✗ | ok | ok | ok | **CHANGES**. "Escolhe o alvo com mais proteção e tira defesa até o fim" é o Enxerto da Fornalha (NA, "puxa para o mais blindado, defesa vale metade"). É também a lógica da outra cria de Veth, o Convidado de Cera (NA, "escolhe a Carta mais cara e tranca"): o mesmo demônio repete "atacar o melhor". E duplica o Quilhado (#2) dentro da onda. |
| 21 | mon_mao_estendida | ok* | ok | ok | ok | ✗ | **CHANGES** (P2, texto e mecânica). "A boca sorri um pouco antes da hora" e o telégrafo "o sorriso chega um pouco antes da hora" copiam a dica de mesa do segredo do Estaleiro ("O armador sorri um pouco antes da hora", `secret_estaleiro_almas_cobra_alma_por_casco.md`). Isso planta a pista do segredo de Durrak numa cria de Skarath. Além disso, "pune quem a ataca de frente" fica perto da outra cria de Skarath, o Cordão de Medida (PM: devolve o ataque a quem o fez). |

Retro (6): eixos conferidos. Nenhuma nova repete a velha: o Cobrador do Gancho é quadrúpede, o Anzolado e a Carranca são outros corpos, e a Capitã da Corda Molhada não tem par entre as novas.

## Achados (correções)

| ID | Sev. | Arquivo:linha | Problema | Correção sugerida |
|---|---|---|---|---|
| P1-1 | P1 | brekmar.yaml:1192-1197 (Penhorado) | Clone da mecânica da Gralha de Crematório (NA) | Usar o Poço: a coisa arrancada vira **penhor** e ele **não foge**. A cada rodada o resgate custa mais (a dívida corre). Matá-lo não devolve; só "pagar" (gastar Fôlego ou ação ao lado dele) devolve. Sem fuga e sem "devolve se cair". |
| P1-2 | P1 | brekmar.yaml:1589-1594 (Broca) | Enxerto (NA) + Convidado de Cera (mesmo demônio) + Quilhado | Inveja como **nivelar por baixo**: fura e faz **vazar** o alvo que está melhor. No fim da rodada, o de mais Fôlego ou Vitalidade perde a diferença para o pior do grupo até alguém tapar o furo (gastar ação). Nada de "o mais blindado" nem de defesa. Se o papel deixar de ser `quebra_defesa`, reabrir a vaga no tabuleiro. |
| P1-3 | P1 | brekmar.yaml:167-172 (Quilhado) | "Racha a peça" = Enxerto/Portão (NA); duplica a Broca | Como uma quilha corta a água: o golpe ignora a guarda do alvo e **atravessa**, acertando também o seguinte da fila, e ele termina **atrás** do alvo. É posicional, sem dano à peça. |
| P1-4 | P1 | brekmar.yaml:883-887 (Sangria) | Mesma função da Craca (casca que absorve golpe no aliado) | **Cura paga com o próprio corpo**: fecha um Ferimento já aberto no contratante com uma crosta. A crosta não segura golpe; ele fica com a pele fina à mostra (mais fácil de ferir). Assim a Craca protege antes e a Sangria remenda depois. |
| P1-5 | P1 | brekmar.yaml:1100-1121 (Tambor) | Anatomia e contra-jogo do Fole de Costela (NA) | Tirar o "peito-barril de costelas abertas". Pôr a ressonância no **crânio**: crista óssea alongada e oca como o crânio do leviatã, mais o saco da garganta. O som sai quando ele bate a cabeça no chão ou na parede. Contra-jogo sem "furar pelos lados": por exemplo, tirá-lo de chão de pedra ou osso, que é o que ressoa, ou rachar a crista. |
| P1-6 | P1 | brekmar.yaml:1270-1275 (Sino) | Mesmo verbo do Casco ("dentro; rasgar de fora") e do Regaço (PM) | Manter a troca de hospedeiro como assinatura: quem é puxado vira **as pernas do Sino**, e o Sino usa a Carta preparada (ou o ataque) dele **contra os aliados dele**. Quando entra outro, o anterior cai "vazio" (sem Fôlego). Tirar o "alvo não age + o sino se cura". |
| P1-7 | P1 | brekmar.yaml:610-687 (Piolho) | Caranguejeiro (Codex) + Patinador (PM) + Roda (NA) | **Cortar** e repor a vaga com um conceito que não seja de carcaça de leviatã (cf. nota de saturação). Se ficar, mudar origem e corpo: nada de crustáceo de carcaça do tamanho de um cão. A assinatura passa a ser **derrubar** (quem está de pé perde a próxima defesa) e, ferido, ele se fecha e ganha casca em vez de fugir sem alcance. |
| P2-1 | P2 | brekmar.yaml:1659, 1682 (Mão Estendida) | Repete a dica de mesa do segredo do Estaleiro; reação a ataque frontal perto do Cordão de Medida (Skarath, PM) | Reescrever o "sorriso antes da hora". Mudar a traição de "pune quem bate" para "**trai quem confiou**": na 1ª rodada protege ou não ataca o alvo (falsa trégua); na seguinte, o braço escondido golpeia esse mesmo alvo sem que a guarda conte. |
| P2-2 | P2 | onda (Casco, Quilhado, Odre, Gato, Piolho) | **5 de 21** têm osso ou óleo de leviatã/Estaleiro como causa. Somado à Tripulação-Amaldiçoada, a frase "o leviatã mudou X" deixa de identificar | Resolvida em parte com o P1-7. Opcional: dar ao Gato outra causa de "lastro" que não seja a quilha (ex.: lastro de pedra/chumbo de porão), mantendo corpo e mecânica. |
| P2-3 | P2 | onda (Casco, Sino, Boia, Tripeiro) | Quatro efeitos de "alvo preso/sem agir" numa onda de 21 | Com o P1-6 caem para três (Casco, Boia, Tripeiro), cada um com gatilho próprio: engolir, agarrar na borda, reagir ao golpe. Não acrescentar outro. |
| P2-4 | P2 | Odre / Lavado+Boia / Cardume | Notas de padrão (estouro ao cair, "fora da luta pela água", dreno por contato) | Sem ação agora. Registrar no doc de conceitos como padrões a evitar nas próximas ondas. |

## Cortes (para a §3 de `docs/spec349/conceitos-brekmar.md`)

- **Piolho de Leviatã**: cortar ou reconceber (Caranguejeiro do Codex + Patinador do PM + saturação de leviatã).
- Nenhum outro corte. Os demais CHANGES se resolvem trocando a mecânica ou a anatomia, sem perder o conceito.

## Correções aplicadas

(nenhuma; rodada 1)

## Pendências

Rodada 2 depois das correções P1-1 a P1-7 e P2-1.

## Comandos rodados

```text
nenhum teste (revisão só de leitura); grep/awk/read nas fichas, no Codex e nos segredos
```

---

## Rodada 2 — 2026-11-01 · commit revisado `b7826c2c`

> **Veredito final:** `APPROVED`
> **Revisor:** Opus (spec-reviewer, não é o autor). Revisão só de leitura, sem testes.

Revisei só as 7 fichas alteradas e o corte. Para cada assinatura nova, procurei colisão com a
própria onda, com as retro, com o Codex de Brekmar e da Costa Negra, com NA e com PM.

| id | Parecer | Nota |
|---|---|---|
| mon_piolho_de_leviata | **cortado** | A vaga 8 saiu do tabuleiro, e não sobrou nenhuma referência na ficha nem nos conceitos. A saturação de leviatã (P2-2) caiu de 5 para 4; aceitável. |
| mon_quilhado_do_estaleiro | **APPROVED** | Agora a investida atravessa: ignora a guarda, acerta o de trás e reposiciona às costas. Não estraga mais a peça, então saiu do choque com Enxerto e Portão. O Velório de Sal (NA) também atravessa a fila, mas à distância e sem reposicionar. |
| mon_sangria_de_aluguel | **APPROVED** | Remendo de Ferimento já aberto, pago com o próprio corpo, sem absorver golpe. Separou da Craca. Curar Ferimento existe no Fardo (PM) e na Coisa do Esgoto (NA), mas lá é em si mesmo ou por pedágio; aqui é no aliado, à custa do próprio corpo. |
| mon_tambor_do_ossario | **APPROVED** | Crista craniana oca, saco de garganta, tom que corre pelas tábuas e contra-jogo de mudar de chão (pedra/areia) ou rachar a crista. Saiu do Fole de Costela. Essa condição de terreno não tem par. |
| mon_penhorado_do_poco | **APPROVED** | Penhor com resgate que sobe, só pagar devolve, matar perde. Saiu da Gralha. Nota: o Fardo de Espólio (PM, Daruun) também cobra em Fôlego, mas é pedágio por rodada para impedir cura; aqui é resgate de uma coisa tomada. São distintos. |
| mon_sino_de_enlace | **APPROVED** | O hospedeiro vira as pernas, o Sino usa a Carta preparada dele contra os aliados e o anterior cai vazio. Nenhuma ficha anterior vira a carta do jogador contra o próprio grupo. Saiu do Casco e do Regaço. Pendência de eixo (não de unicidade): a vaga 16 segue como `drenador`, e o Sino já não drena; o coordenador pode reavaliar para `controlador`, se o lint deixar. |
| mon_broca_de_costado | **APPROVED** | Fura o mais inteiro, o furo vaza até igualar ao mais ferido, e tapar custa uma ação. Ela nunca fura o mais ferido. A inveja como nivelamento é única e já não repete o Convidado de Cera nem o Enxerto. O papel virou `drenador`, como o Cardume; o mecanismo é diferente. |
| mon_mao_estendida | **APPROVED** | O "sorriso antes da hora" saiu (0 ocorrências na ficha), então a pista do segredo do Estaleiro não aparece mais. A falsa trégua trai quem não atacou, o inverso do Cordão de Medida. Nota menor: "bater logo" lembra o contra-jogo do Vira-Costas (NA), mas lá o primeiro golpe é devolvido; o incentivo é oposto. |

Nada novo colidiu. Segredos continuam fora do texto público. Pendências que ficam: P2-3 e P2-4
(padrões a evitar nas próximas ondas) e o papel da vaga 16, acima.
