# SPEC-349 (esteira) · Deserto de Zhur — conceitos (gerar 2× e cortar, R9)

Processo (Etapa 3, padrão das ondas 1 e 2): tabuleiro de 26 vagas com eixos fechados **antes** da
prosa (`data/bestiario/fichas/deserto_zhur.yaml` → `vagas:`, verde com `lint.py --vagas` e conferido
à mão contra as 6 fichas retro), depois 52 conceitos de 1 linha, corte pelo autor (Opus) até 26,
prosa, e corte independente do revisor de unicidade (Opus).
Resultado do autor: **21 novas + 5 slots** (4 reinventados, 1 adotado: o Verme-de-Vidro do Codex
no slot `enemy_verme_areia_jovem`, como a curadoria já decidira).

Comparado contra: as 6 retro de Zhur (Devorador de Sol, Escorpião de Cristal, Escaravelho de Vidro,
Hiena do Sol Partido, Colosso de Duna Oca, Eclipse Caminhante); os 31 docs `monsters/` com a tag
`deserto_zhur` (Abutre-de-Sal, Bebedores-de-Memória, Besouro-de-Espelho, Cacto-de-Cristal,
Camelo-de-Cristal, Caravana-Fantasma, Cobra-Chocalho-de-Cristal, Coisa-da-Borda-Sul,
Cristal-de-Urath, Devoradores de Sol guerreiros, Eco-da-Lua, Escorpião-de-Cristal,
Falcão-de-Obsidiana, Flor-da-Meia-Noite, Homem-de-Vidro, Lagarto-Espelho, Lince-de-Areia-de-Vidro,
Líquen-de-Vidro, Miragem-de-Vaelith, Miragem-Primordial, O Que Caiu com a Lua, Os Reis-Enterrados,
Prole-de-Urath, Raiz-Bebedora-Profunda, Saqueadores-de-Cristal, Serpente-do-Crepúsculo, Tempo-Morto,
Vento-com-Vozes, Verme-de-Vidro, Verme-de-Vidro-Ancião, Vidro-Cantante); as 27 de Nova Arcádia e as
22 do Pântano.

Regra própria desta onda: o deserto inteiro já é "vidro e cristal" no Codex. Para não fazer dez
reskins de Homem-de-Vidro, **vidro é contexto, não identidade**: cada criatura nova tem de se
distinguir por uma coisa que o corpo FAZ (bebe hálito, flutua de lastro, prova o gesto, guarda
comida viva nas costas), e no máximo um terço das novas tem `material: vidro_cristal`.

Inspirações externas (R12, só ideia, fonte registrada na ficha e no fim do doc de arte): escamas
placoides de tubarão, geodo de ametista, varanos ao sol, tatu-bola, besouro do nevoeiro do Namibe,
caravela-portuguesa, formiga-leão, jerboa, diabo-espinhoso e picanço, rato-de-ninho.

## 1. Os 52 conceitos

Legenda: **F** = ficou · **C-A** = cortado pelo autor (motivo) · **C-R** = cortado pelo revisor.

### Corpos reescritos (Reescritos)

| # | Conceito | Decisão |
|---|---|---|
| 1 | **Andarilho de Duas Idades** — acordou de um bolsão de Tempo-Morto com metade velha e metade criança; toma os anos de quem segura | F |
| 2 | **Esfolado da Tempestade** — esfolado pela Tempestade de Navalha, músculo exposto com lascas de vidro crescidas como escamas que lixam | F |
| 3 | **Provador da Borda** — ficou onde o som tem gosto; o peito abriu em leque de costelas e a língua prova o gesto antes dele | F |
| 4 | **Peito de Geodo** — dormiu encostado num Cristal-de-Urath; o tórax abriu como pedra rachada forrada de pontas violeta que ele dispara | F |
| 5 | **Fervente de Ferrugem** — doente da Ferrugem do Sangue levado para cavar no sol; o sangue ferve e ele rebenta as veias abraçado | F |
| 6 | **Carregador de Liteira** — servo enterrado com um rei; os varais da liteira cresceram pelos ombros; segue quem tirou algo da câmara | F (slot `enemy_mumia_de_po`) |
| 7 | Fundido da Estação — viajante em que a areia da Estação do Vidro fundiu sobre a pele suada | C-A: estátua de vidro que anda = Homem-de-Vidro |
| 8 | Lycan de Sol — Praga dos Ossos cujo exoesqueleto o sol calcinou | C-A: nenhuma criatura nova é Lycan (fora de escopo, como no Pântano) |
| 9 | Preso no Ciclo — alguém preso no Tempo-Morto no meio de uma ferida que abre e fecha | C-A: repete o Andarilho (Vaelith no corpo); ficou o mais legível |
| 10 | Mão Adiantada — braço que vive um instante no futuro e bate antes do corpo | C-A: perigo quase conceitual; o efeito não tem silhueta |
| 11 | Sedento Oco — cativo drenado de água ainda vivo, pele de tambor | C-A: múmia com outro nome (proibido_nome no espírito) |
| 12 | Ecoante Seco — viajante que repete a última frase de quem morreu | C-A: assombração; Vento-com-Vozes já é isso |
| 13 | Cego de Prisma — olhos viraram prismas que espalham a luz da lua | C-A: Homem-de-Vidro de rosto; sem física própria |

### Bestas da entropia (Bestas Tortas)

| # | Conceito | Decisão |
|---|---|---|
| 14 | **Varano Vidrado** — o lagarto cujo couro os Devoradores vestem; a areia fundiu nas costas na Estação; toma calor e queima | F |
| 15 | **Tatu de Navalha** — casco em cintas cheio de lâminas da Tempestade; rola através da linha | F |
| 16 | **Lambedor de Hálito** — besouro do nevoeiro que aprendeu que o ar mais úmido é o de quem dorme | F |
| 17 | **Lastreiro da Cratera** — comeu o Pó-de-Estrela-Caída e ficou leve; bexiga no céu presa a uma pedra; pesca de cima | F |
| 18 | **Cavador de Funil** — larva do tamanho de um boi no fundo de um funil de areia de vidro | F |
| 19 | **Saltador de Palafita** — roedor saltador de canelas que viraram varetas de vidro; o grito chama o bando | F |
| 20 | **Pipa de Costelas** — bicho chato de pele entre costelas longas que o vento da borda carrega; cospe vidro do papo | F (slot `enemy_djinn_menor`) |
| 21 | **Braceiro da Borda Sul** — peito pálido colado na parede da queda, oito braços que sobem pela beirada e a quebram | F (slot `enemy_aranha_de_cristal`, chefe) |
| 22 | **Verme de Vidro** — adoção do Verme-de-Vidro do Codex (`creatures.txt:1140`) | F (slot `enemy_verme_areia_jovem`, adotado) |
| 23 | Odreira — formiga-pote que guarda sangue de quem dorme no abdômen | C-A: segundo drenador de quem dorme; ficou o Lambedor |
| 24 | Feneco do Tempo — raposa de orelhas que ouve o coração um instante antes | C-A: efeito temporal sem corpo torto; repete o Andarilho |
| 25 | Nadador de Areia — lagarto que nada sob a areia como peixe | C-A: Verme pequeno (marcador de variante no espírito) |
| 26 | Órix de Coroa — antílope de chifres que cresceram em coroa de cristal | C-A: o orgulho ficou com as crias de Urath; chifre grande é pouco |
| 27 | Escaravelho Rolador — rola bolas de areia de vidro em volta de carcaças | C-A: segundo escaravelho da região (retro Escaravelho de Vidro) |
| 28 | Camelo de Odre Duplo — corcova que guarda sangue | C-A: Camelo-de-Cristal com outra corcova |
| 29 | Cobra de Calor — serpente que sente calor e morde de noite | C-A: Serpente-do-Crepúsculo |
| 30 | Morcego de Lente — morcego que vê pela obsidiana | C-A: sem ligação com Zhur além do material |
| 31 | Mosca de Miragem — enxame que faz figura de gente | C-A: perigo conceitual (enxame-ilusão) |

### Humanoides que pagaram o preço (Cobrados)

| # | Conceito | Decisão |
|---|---|---|
| 32 | **Costurado de Lentes** — vigia Devorador com discos de obsidiana costurados no corpo todo; aponta a palma e marca | F |
| 33 | **Couro Pegado** — guerreiro em que o couro de varano criou raiz; antebraço de escamas largo como porta | F |
| 34 | **Mãos de Cinzel** — Saqueador-de-Cristal cujas mãos viraram cunhas de Éter; escuta onde racha | F |
| 35 | **Aguadeiro de Bucho** — Devorador com um odre costurado sob a pele da barriga; dá de beber aos caídos | F |
| 36 | **Caçador Sem Calor** — Devorador coberto de barro e cinza que fica frio como miragem e ataca entre elas | F |
| 37 | Bebedor de Anciões — casta que bebe memória do sangue | C-A: Bebedores-de-Memória já existem no Codex |
| 38 | Remendado de Escamas — saqueador que costura escamas de escorpião na pele | C-A: repete o Couro Pegado com outro bicho |
| 39 | Corredor de Pés de Couro — batedor de pés trocados por almofadas de lince | C-A: enxerto sem preço legível; Lince-de-Areia já existe |
| 40 | Cristalizado Voluntário — Devorador que bebe veneno de escorpião para endurecer a pele | C-A: Homem-de-Vidro de propósito |
| 41 | Rei Desenterrado — saqueador que se sentou no trono de um Rei-Enterrado | C-A: o trono ficou com a cria de Urath; e é assombração no Codex |

### Crias de apetite (demônios encarnados)

| # | Conceito | Decisão |
|---|---|---|
| 42 | **Altivo do Vidro** (Urath) — esqueleto empurrado para cima pelo orgulho; não se defende e devolve cada golpe | F |
| 43 | **Trono de Ajoelhados** (Urath) — monte de viajantes ajoelhados fundidos, com um corpo ereto sentado no alto | F (slot `enemy_boss_general_escorpiao`, chefe) |
| 44 | **Despenseiro de Espinhos** (Maalrek) — lagarto espinhento que espeta a presa viva nas costas e bebe dela por dias | F |
| 45 | **Lacrador de Saídas** (Dorrhen) — serpente de papo aceso que cospe paredes de vidro mole nas passagens | F |
| 46 | Juntador de Cacos (Daruun) — rato pelado de costas coladas de moedas e cacos; tira coisas dos alforjes | C-R: 3ª cria de Daruun nas ondas e repete o Fardo de Espólio do Pântano (saqueador covarde que não solta o que pegou); vira o 46b |
| 46b | **Furador de Odres** (Veth) — bicho pelado de um dente só, oco como sovela; fura o cantil de quem tem mais e não bebe | F (revisor: Veth estraga em vez de guardar) |
| 47 | Nó de Rixa (Vhrak) — dois guerreiros de clãs rivais fundidos peito contra peito; quatro braços batendo | C-coordenador: quase igual à Estivador das Facas de Brekmar (escrita em paralelo); "dois corpos fundidos" já é de Costa Negra e Pradaria, e a área que cresce com Ferimentos é da Roda de Mandíbulas |
| 47b | **Guia Avesso** (Skarath) — guia que vendeu a caravana e voltou do avesso, cabeça para as costas e pele de sal; põe a mão no ombro de quem confia e o golpe seguinte atravessa a defesa | F (revisão cruzada do coordenador) |
| 48 | Abraço da Queda (Dorrhen) — braços compridos que agarram e se jogam da borda com a vítima | C-A: puxar para a queda repetia o Braceiro; Dorrhen ficou com o Lacrador |
| 49 | Bebe-Areia (Dorrhen) — sedento que bebeu areia achando que era água | C-A: Dorrhen já tem cria; e o corpo era só barriga cortada |
| 50 | Gêmeo de Inveja (Veth) — dois Devoradores ligados por um tubo de sangue | C-A: plano acoplado já é do Nó de Rixa (o demônio Veth voltou no 46b, por indicação do revisor) |
| 51 | Coroa que Fura (Urath) — coroa de cristal que cresce para dentro do crânio | C-A: Urath já tem duas crias de anatomias diferentes |
| 52 | Bezerro da Cratera (O Que Caiu com a Lua) — cria do primordial adormecido | C-A: tocaria segredo (`secrets.txt:281`) e o primordial não é demônio; ficou só o Lastreiro, que come o pó da cratera |

## 2. Lista do autor (21 novas + 5 slots)

| Família | Novas | Slots |
|---|---|---|
| Reescritos | Andarilho de Duas Idades, Esfolado da Tempestade, Provador da Borda, Peito de Geodo, Fervente de Ferrugem | Carregador de Liteira |
| Bestas Tortas | Varano Vidrado, Tatu de Navalha, Lambedor de Hálito, Lastreiro da Cratera, Cavador de Funil, Saltador de Palafita | Verme de Vidro (adotado), Pipa de Costelas, Braceiro da Borda Sul |
| Cobrados | Costurado de Lentes, Couro Pegado, Mãos de Cinzel, Aguadeiro de Bucho, Caçador Sem Calor | — |
| Crias de Apetite | Altivo do Vidro (Urath), Despenseiro de Espinhos (Maalrek), Lacrador de Saídas (Dorrhen), Furador de Odres (Veth), Guia Avesso (Skarath) | Trono de Ajoelhados (Urath) |

Cotas (conferidas à mão; o gate usa as cotas padrão): 21 novas; famílias 6/9/5/6; lacaio 6,
padrão 10, elite 8, chefe 2 (os dois slots de chefe); 13 papéis; 11 arquétipos; 5 demônios (Urath,
Maalrek, Dorrhen, Veth, Skarath; Urath obrigatório, com duas crias de anatomias diferentes: esqueleto ereto e monte composto);
habitat Mar de Vidro 23, Borda do Vazio 6. Âncoras usadas: Devoradores do Sol e Khatarn (Costurado,
Couro Pegado, Aguadeiro, Caçador, Guia Avesso), miragens que aprendem (Caçador Sem Calor), O Que Caiu
com a Lua (Lastreiro, sem tocar o segredo), Estação do Vidro e areia que vitrifica (Varano, Saltador,
Tatu, Lacrador), Urath (Altivo, Trono, Peito de Geodo), Vaelith (Andarilho), Borda do Vazio
(Provador, Braceiro, Pipa, Lacrador).

## 3. Cortes do revisor

Revisor de unicidade: `opus-spec-reviewer` (Opus), rodada 1 = CHANGES_REQUIRED com 6 correções
obrigatórias, todas aplicadas; parecer por criatura em `handoffs/SPEC-349-independent-review.md`
(rodada 2: APPROVED).

| # | Criatura | Motivo do revisor | O que mudou |
|---|---|---|---|
| 1 | Juntador de Cacos | 3ª cria de Daruun; repete o Fardo de Espólio do Pântano | Cortado. No lugar, **Furador de Odres** (Veth): estraga em vez de guardar; outro corpo |
| 2 | Aguadeiro de Bucho | Silhueta de barriga enorme = Mula de Lágrimas do Pântano | Os odres saíram da barriga e foram para os antebraços, pendurados até os joelhos |
| 3 | Provador da Borda e Altivo do Vidro | Costelas abertas em leque repetidas (Peito de Geodo, Fole de Costela de Nova Arcádia) | O leque fica só no Peito de Geodo. Provador: queixo partido em duas pinças de osso. Altivo: canelas de osso e crânio esticado para cima |
| 4 | Trono de Ajoelhados | "Puxa quem dobra para a base e cresce" = Fila de Grilhões de Nova Arcádia | Ninguém é puxado; o de cima castiga quem já está de joelhos |
| 5 | Despenseiro de Espinhos | 2º lagarto de dorso vidrado da onda (com o Varano) | Virou ave corredora sem voo (picanço ao pé da letra); a vaga 18 passou a `bipede_ereto` e o tabuleiro foi relintado |
| 6 | Braceiro da Borda Sul | Oito braços pálidos = Fardo de Espólio e lembra a aranha do slot | Só dois braços, compridos como mastros, de três cotovelos |

Sugestões opcionais aplicadas: S2 (`evitar` do Peito de Geodo afasta o Sorvedouro do Código), S3
(cena do Fervente saiu da escavação do Mãos de Cinzel) e S5 (`evitar` do Costurado afasta a retro
Devorador de Sol). As demais (S1, S4, S6, S7) ficam como nota para a Etapa 5 (Cartas).

Rodada 2 do revisor: APPROVED, com os opcionais R2-a (`evitar` do Altivo) e R2-b (cena do Furador) aplicados.
Troca do coordenador depois da rodada 2: o Nó de Rixa saiu e entrou o Guia Avesso (Skarath, vaga 21 → `bipede_curvado / sal_mineral / quebra_defesa / tatico`), com revisão cruzada do coordenador.
