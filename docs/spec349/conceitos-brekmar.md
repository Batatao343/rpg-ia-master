# SPEC-349 · onda de Brekmar — conceitos (gerar 2× e cortar, R9)

Processo (Etapa 3, padrão das ondas 1 e 2): tabuleiro de 21 vagas com eixos fechados **antes** da
prosa (`data/bestiario/fichas/brekmar.yaml` → `vagas:`, verde em U2/U3/U12 e contra os eixos das 6
fichas retro), depois 45 conceitos de 1 linha, corte pelo autor (Opus) até 21, prosa, e corte
independente do revisor de unicidade (Opus).
Resultado do autor: **21 novas + 0 slot**; depois da revisão: **20 novas**. A curadoria (`curadoria_legado.yaml`) não tem nenhum
`generico` com `regiao_onda: brekmar`: as 6 entradas da região (Pirata de Brekmar, Capanga do Poço,
Arpoador Osshari, Rato de Cais de Brekmar, Cobrador do Gancho, Capitã da Corda Molhada) são `valoria`
e entram só como retro (R6).

Comparado contra: as 6 retro; os docs `monsters/` de Brekmar e da Costa Negra no Codex (Tubarão-de-Casco,
Polvo-dos-Destroços, Caranguejo-Maré, Gaivota-Ladra, Enguia-do-Cais, O Que Come nas Praias,
Maré-Vermelha-Viva, Sussurro-do-Leviatã, Afogados-do-Porto, Capitão-Sem-Porto, Guarda-Sangrinomante de
Kahen, Tripulação-Amaldiçoada, Capangas-do-Poço, Contrabandistas-da-Névoa, Mercado-de-Ophidia,
Coral-de-Osso, Verme-de-Osso, Polvo-de-Crânio, Serpente-de-Maré, Caranguejeiro, Gaivota-Carniceira-Gigante,
Os Que Voltaram); as 27 de Nova Arcádia e as 22 do Pântano.

Âncoras usadas: o Estaleiro das Almas e o osso de leviatã nas quilhas (`locations.txt:455`,
`items.txt:1333`); as lanternas de óleo (`locations.txt:429`); as Docas Velhas (`locations.txt:475`); a
Maré Vermelha (`creatures.txt:1466`); o Ossário e o crânio que responde (`factions.txt:305`,
`creatures.txt:1470`); a Boca do Fundo e as rinhas (`factions.txt:283`); os Cinzéus que não sentem dor
(`races.txt:235`); a sangrinomancia e o preço em dor (`npcs.txt:137`); o Poço das Dívidas
(`factions.txt:270`, `items.txt:1456`); Lyss e a Casa das Marés (`npcs.txt:291`, `factions.txt:324`,
`daily_life.txt:261`).

**Segredos fora do texto público:** nada nas fichas diz que o Estaleiro cobra uma alma por casco, que o
Povo-Recife cobra, que há dívidas fabricadas, que Kahen quer adiar Lyss, nem de onde vem O Que Come nas
Praias. O Povo-Recife ficou de fora desta onda por isso (conceito 30).

Demônios da onda (6): **Lyss** (lugar fixo, obrigatória), Urath (primeira cria do Orgulho em qualquer
onda), Vhrak, Dorrhen, Veth, Skarath. Nenhum repete `(plano_corporal, material)` de cria do mesmo demônio
em Nova Arcádia ou no Pântano (R29).

Inspirações externas (R12, só ideia, fonte registrada na ficha e no fim do doc de arte): marés vermelhas,
osteopetrose, cracas, isópodes gigantes, peixes-pescadores e peixes-sapo, pepinos-do-mar (túbulos de
Cuvier), consolidação viciosa de fraturas, medusas, carrancas do São Francisco e figuras de proa,
teredo (caruncho-de-navio).

## 1. Os 45 conceitos

Legenda: **F** = ficou · **C-A** = cortado pelo autor (motivo) · **C-R** = cortado pelo revisor.

### Corpos reescritos (Reescritos)

| # | Conceito | Decisão |
|---|---|---|
| 1 | **Casco de Costelas** — navio do Estaleiro afundado nas Docas Velhas cuja quilha de osso de leviatã regenerou a carne do bicho de onde foi cortada, usando as cavernas do casco como esqueleto | F (chefe) |
| 2 | **Quilhado do Estaleiro** — aprendiz das rampas que respirou anos de pó de osso de leviatã; a espinha rompeu as costas numa crista de quilha | F |
| 3 | **Odre de Óleo** — acendedor das lanternas do porto cuja gordura virou óleo de leviatã em bolsas sob a pele; estoura em fogo | F |
| 4 | **Lavado da Maré Vermelha** — pescador em quem a Maré Vermelha entrou por um corte; pele em fitas de alga, rastro que puxa para o mar | F |
| 5 | Clandestino Enferrujado — fugitivo da Lista com a Ferrugem do Sangue florescendo no sal | C-A: Praga de Ferro é âncora de Nova Arcádia; repetiria Caído do Cadinho e Arame Vivo |
| 6 | Calafate de Piche — calafate com a pele virada piche | C-A: material sem anatomia nem gancho de lore |
| 7 | Salgado de Barril — carga humana salgada pelos contrabandistas que volta | C-A: lê-se como múmia (genérico) e cola nos Afogados-do-Porto |
| 8 | Farpado do Cais — mordido por Lycan com farpas de osso crescendo | C-A: variante de Lycan; a direção proíbe variante da mesma ideia |
| 9 | Olhos de Ophidia — marinheiro que olhou as cores erradas e ganhou pele de lula | C-A: cola nos Que Voltaram; o horror de Ophidia é não ter certeza (`creatures.txt:1624`) |
| 10 | Sobra da Praia — corpo a que faltam partes, deixado pelo Que Come nas Praias | C-A: toca o segredo do Que Come nas Praias |
| 11 | Afogado de Dívida — devedor jogado ao mar que volta com a placa do Poço no peito | C-A: Afogados-do-Porto com adereço |

### Bestas da entropia (Bestas Tortas)

| # | Conceito | Decisão |
|---|---|---|
| 12 | **Cardume Coagulado** — cardume que a Maré Vermelha colou num corpo só, dezenas de cabeças de peixe ao longo do flanco | F |
| 13 | **Gato de Lastro** — gato de porão de navio com osso de leviatã, ossos pesados como chumbo; senta na carga e não sai | F |
| 14 | **Craca de Amarra** — colônia de cracas nas amarras velhas que cimenta larvas sobre as outras criaturas como armadura | F |
| 15 | **Piolho de Leviatã** — isópode do tamanho de um cão vindo do Cemitério com o osso das quilhas; enrola e rola | C-R: colide com o Caranguejeiro do Codex (crustáceo de carcaça de leviatã), com o Patinador (PM) no "foge sem ser alcançado" e com a Roda de Mandíbulas (NA) no rolar; e era a 5ª criatura causada por leviatã/Estaleiro |
| 16 | **Pescador de Lanterna** — peixe do fundo que anda nas nadadeiras e imita, com a isca, a lanterna que falta no píer | F |
| 17 | **Tripeiro de Fundo** — pepino-do-mar do tamanho de um homem que despeja tripas grudentas em quem o fere | F |
| 18 | Biguá de Argola — biguá de contrabandista que engole anéis | C-A: ave ladra = Gaivota-Ladra (Codex) e Gralha de Crematório (NA) |
| 19 | Jangada de Lontras — lontras que dormem de mãos dadas e cresceram unidas | C-A: corpo composto de animais colados repete o Cardume; fica o Cardume, que tem âncora (Maré Vermelha) |
| 20 | Lula de Lampião — lula que imita lanternas | C-A: duplica o Pescador e cola no Polvo-dos-Destroços |
| 21 | Caramujo de Âncora — caracol gigante das correntes de âncora | C-A: concha + preso repete a Craca |
| 22 | Pulga de Areia — anfípode do tamanho de um cão que limpa corpos na praia | C-A: = Caranguejo-Maré |
| 23 | Cavalo de Maré — cavalo-marinho gigante preso às estacas | C-A: sem papel tático que não esteja coberto; lê-se como bicho de enfeite |

### Humanoides que pagaram o preço (Cobrados)

| # | Conceito | Decisão |
|---|---|---|
| 24 | **Sangria de Aluguel** — sangrinomante sem permissão de Kahen; o sangue coagula em crostas que ele empresta a quem protege | F |
| 25 | **Torcido da Rinha** — Cinzéu de rinha da Boca do Fundo com fraturas que soldaram tortas porque nunca doeram | F |
| 26 | **Anzolado da Casa** — cliente gasto da Casa das Marés que se crava de anzóis para sentir e prende quem escolhe | F |
| 27 | **Tambor do Ossário** — Osshari de vigília no crânio do leviatã cujo peito abriu em caixa de tambor | F |
| 28 | **Penhorado do Poço** — devedor que penhorou dentes, olho e dedos e os trocou por peças de navio | F |
| 29 | Mascador de Fúria — soldado de sindicato que masca Néctar da Fúria e luta com membros pendurados | C-A: "luta sem sentir" é do Torcido; dois ignora-dor na região |
| 30 | Mergulhador do Recife — Povo-Recife calcificado nas docas do norte | C-A: o que o Povo-Recife faz no Estaleiro é segredo; o corpo não se explica em público sem entregar |
| 31 | Mula de Veneno — contrabandista que leva veneno de Ophidia no corpo | C-A: = Mula de Lágrimas (Pântano) |
| 32 | Laçador de Zhelu — caçador de gente da Madame Zhelu | C-A: humano comum sem preço no corpo; cabe nos Capangas |
| 33 | Cartógrafo Tatuado — obcecado por Ophidia com mapas na pele | C-A: conceitual (o perigo é a obsessão, não o corpo) |
| 34 | Guarda de Correntes — Cinzéu de Kahen com correntes-gancho nas costas | C-A: = Guarda-Sangrinomante de Kahen (Codex) |

### Crias de apetite (demônios encarnados)

| # | Conceito | Decisão |
|---|---|---|
| 35 | **Sino de Enlace** (Lyss) — sino de carne translúcida que anda nas pernas de quem está dentro; troca de hospedeiro e solta o anterior vazio | F |
| 36 | **Carranca de Proa** (Urath) — carranca de capitão orgulhoso com braços de homem e dentes; só aceita lutar com quem tem mais renome | F |
| 37 | **Estivador das Facas** (Vhrak) — dois mortos de sindicatos rivais colados peito com peito em volta das facas | F |
| 38 | **Boia de Braços** (Dorrhen) — saco inchado de gás com um anel de braços de afogado; agarra e afunda junto | F |
| 39 | **Broca de Costado** (Veth) — teredo do tamanho de um bote que fura o navio que vai melhor e a armadura mais grossa | F |
| 40 | **Mão Estendida** (Skarath) — figura alta de mão oferecida e outro braço escondido sob a axila | F |
| 41 | Língua da Casa (Lyss) — boca de muitas línguas na Casa das Marés | C-A: segunda cria de Lyss mais fraca que o Sino, e o tom sexual explícito foge da voz |
| 42 | Torcida da Boca do Fundo (Maalrek) — massa de rostos que se alimenta das rinhas | C-A: massa de rostos é quase conceitual, e Maalrek já tem a Roda de Mandíbulas (NA) |
| 43 | Placa Raspada (Daruun) — placa do Poço que ganha dentes | C-A: Daruun já tem Escritura (NA) e Fardo (Pântano); objeto que morde = Portão que Morde |
| 44 | Covarde de Convés (Fehk) — marinheiro escondido no porão | C-A: Fehk é de Nova Arcádia e o Vira-Costas basta |
| 45 | Âncora Arrastada (Dorrhen) — corpo amarrado a uma âncora | C-A: mesma ideia da Boia (afundar junto); fica a Boia, que é corpo e não adereço |

## 2. Lista do autor (20 novas, depois do corte do revisor)

| Família | Lacaio | Padrão | Elite | Chefe |
|---|---|---|---|---|
| Reescritos (4) | Odre de Óleo | Lavado da Maré Vermelha | Quilhado do Estaleiro | Casco de Costelas |
| Bestas Tortas (5) | Gato de Lastro, Craca de Amarra, Tripeiro de Fundo | Cardume Coagulado, Pescador de Lanterna | — | — |
| Cobrados (5) | Penhorado do Poço | Sangria de Aluguel, Torcido da Rinha, Anzolado da Casa | Tambor do Ossário | — |
| Crias de Apetite (6) | Boia de Braços | Estivador das Facas, Broca de Costado, Mão Estendida | Sino de Enlace, Carranca de Proa | — |

Cotas: lacaio 6 · padrão 9 · elite 4 · chefe 1; 11 papéis táticos; 11 arquétipos; 6 demônios;
habitat Porto de Brekmar 14, Docas Velhas 12.

## 3. Cortes do revisor

Revisor de unicidade: Opus (`spec-reviewer`), 2 rodadas; parecer completo em `docs/spec349/revisao-brekmar.md`.

- **Rodada 1 (CHANGES_REQUIRED, 13/21 aprovadas):** corte do **Piolho de Leviatã** (colide com o Caranguejeiro do Codex, o Patinador do Pântano e a Roda de Mandíbulas). Assinaturas refeitas: Penhorado (penhor com resgate que sobe, não foge; era a Gralha), Broca (o furo vaza até nivelar por baixo; era o Enxerto/Convidado de Cera), Quilhado (atravessa a fila em vez de rachar peça), Sangria (remenda Ferimento aberto em vez de casca que segura golpe; era a Craca), Tambor (ressonância na crista do crânio e no chão de tábuas; era o Fole de Costela), Sino (o hospedeiro vira as pernas e a Carta dele é usada contra os aliados; era o "rasgar de fora" do Casco/Regaço), Mão Estendida (falsa trégua; saiu o "sorriso antes da hora", que ecoava a dica de mesa do segredo do Estaleiro).
- **Rodada 2: APPROVED** para as 20. Ajuste de eixo: o Sino passou de `drenador` a `controlador`.

**Padrões a evitar nas próximas ondas (P2-3/P2-4):** não acrescentar outro efeito de "alvo preso sem agir" (já há Casco, Boia e Tripeiro); estourar em quem está junto ao cair (Odre é a 3ª no bestiário); tirar alguém da luta pela água (Lavado, Boia); dreno por contato (Cardume); e criaturas causadas por osso de leviatã/Estaleiro (4 nesta onda: Casco, Quilhado, Odre, Gato).
