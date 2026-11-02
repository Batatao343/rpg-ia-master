# SPEC-349 · esteira · Floresta dos Sussurros — conceitos (gerar 2× e cortar, R9)

Processo (Etapa 3, padrão das ondas 1 e 2): tabuleiro de 25 vagas com eixos fechados **antes** da
prosa (`data/bestiario/fichas/floresta_sussurros.yaml` → `vagas:`, verde com `lint.py --vagas` e
contra as 4 fichas retro), depois 52 conceitos de 1 linha, corte pelo autor (Opus) até 25, prosa, e
corte independente do revisor de unicidade (Opus, `spec-reviewer`).
Resultado do autor: **21 novas + 4 slots** (`enemy_aranha_lobo`, `enemy_urso_coruja_mutante`,
`mon_ent_dormindo`, `enemy_sombra_espreitadora`, todos reinventados no mesmo id).

Comparado contra: as 4 retro da região (Urso-de-Espinha, Serpente-Raiz, Mariposa do Sussurro,
Caçador de Casca); os 32 docs `monsters/` do Codex que citam a floresta (Lobo-de-Olhar-Errado,
Cervo-Sem-Fuga, Ave-Imóvel, Coruja-de-Duas-Vozes, Javali-de-Casca, Aranha-da-Névoa-Negra,
Coletor-de-Galhos, O Coletor-Primordial, Mãe-da-Folhagem, Veado-Branco-de-Muitos-Chifres,
Tronco-Faminto, Árvore-Sussurrante, Galhos-Que-Apontam, Trepadeira-Mentirosa, Semente-do-Oculto,
Cogumelo-Espelho, Flor-Olho, Pó-de-Sonho, Luz-Mentirosa, Memória-Errante, Voz-de-Morto-Conhecido,
Eco-de-Passos, Caçador-de-Costas, Os Que Não Saíram, Perdidos-Permanentes, Colhedores-de-Pó,
Filho-de-Thessavar, Coisa-Sussurrante, As Que Estavam Antes das Árvores, A Raiz-Que-Lembra,
Mariposa-Memória, Serpente-Raiz); as 27 de Nova Arcádia e as 22 do Pântano.

**Linha da região.** A floresta já tem muitos perigos de isca, voz e memória (cervos que guiam, luzes
e trilhas que mentem, vozes de mortos). Nada disso entra de novo. As criaturas novas são físicas e
puxam de cinco âncoras: o escuro feito de propósito (luz, silêncio, céu fechado), o Pó de Sonho e
quem o colhe, a pradaria da Era 0 engolida, a Fronteira com Xylos (onde nada cruza; Solveth e a
magia de sangue de Zhur nas raízes) e a expedição de Quell e os Mercadores de Curiosidades.

Demônios da onda: **Thessavar** (lugar fixo; 2 crias de anatomias diferentes da Arraia do Pântano),
**Urath** (primeira cria; ref. timeline_completa.txt:196), **Veleth** e **Maalrek** (anatomias
diferentes das crias de outras regiões, R29).

Inspirações externas (R12, só ideia, fonte registrada na ficha e no fim do doc de arte): grilos de
caverna, casuar, preguiça-gigante, morcego-vampiro e orelhudo, besouro-bombardeiro, onicóforos,
colugo, vespa-caçadora-de-tarântula, planária cabeça-de-martelo, caranguejo-ermitão, tatuzinho e
picanço.

## 1. Os 52 conceitos

Legenda: **F** = ficou · **C-A** = cortado pelo autor (motivo) · **C-R** = cortado pelo revisor.

### Corpos reescritos (Reescritos)

| # | Conceito | Decisão |
|---|---|---|
| 1 | **Lixado da Fronteira** — passou pela névoa de Solveth e saiu gasto como pedra de rio; tocos de pó desfazem o que agarram | F |
| 2 | **Abafador de Candeias** — perdido de olhos cobertos de pele e feltro preto que bebe a luz; desce dos troncos e apaga a lanterna no abraço | F |
| 3 | **Fechado de Escápulas** — omoplatas crescidas em duas portas de osso que se fecham diante de quem ele protege | F |
| 4 | **Virado do Avesso** — viciado que comeu Pó no fundo; o Oculto mostrou o lado de dentro: músculo por fora, devolve cada golpe | F |
| 5 | **Calado das Guelras** — boca selada pela pele, respira por fendas no pescoço; corre em silêncio atrás de quem arfa | F |
| 6 | Pálido de Olhos de Társio — perdido de olhos enormes que vê no escuro | C-A: segundo "perdido adaptado ao escuro" ao lado do Abafador; fica o que tem mecânica (apagar a luz) |
| 7 | Enraizado no Coração — viajante que sentou e virou árvore | C-A: homem-árvore genérico; Tronco-Faminto e Árvore-Sussurrante já cobrem a mata que come |
| 8 | Andarilho de Perna Longa — uma perna cresceu e ele anda em círculos | C-A: repete Os Que Não Saíram (andar em círculos) e é perigo fraco |
| 9 | Corpo de Galhada — ossos crescidos como galhos que apontam | C-A: reskin físico dos Galhos-Que-Apontam |
| 10 | Encasulado de Calos — pele que cresceu em camadas até virar casulo | C-A: silhueta ilegível em contraluz; sem papel tático próprio |
| 11 | Lycan do escuro — Praga dos Ossos que transformou e ficou na floresta | C-A: nenhuma criatura nova é Lycan (fora de escopo); a placa óssea já está no Fechado |
| 12 | Escondido da Praga — doente da Praga do Ferro que se escondeu num oco | C-A: Praga do Ferro é de Nova Arcádia (Arame Vivo); aqui seria transplante |
| 13 | Colheita que Anda — colhedor morto de cujo corpo frutifica o Pó | C-A: lê como Hospedeiro de Xylos com fungo vermelho; o Pó não coloniza gente |

### Bestas da entropia (Bestas Tortas)

| # | Conceito | Decisão |
|---|---|---|
| 14 | **Saltão Desbotado** — grilo das tocas, cego e sem cor, do tamanho de um cão; salta nas costas | F (slot `enemy_aranha_lobo`) |
| 15 | **Casuar de Elmo Fundo** — ave sem voo da selva cujo casco cresceu sobre os olhos; chuta quem se move | F (slot `enemy_urso_coruja_mutante`) |
| 16 | **Preguiça da Pradaria** — bicho de pasto da Era 0 que dorme de pé no caminho antigo; garras de gancho | F (slot `mon_ent_dormindo`) |
| 17 | **Morcego Rasteiro** — orelhas maiores que as asas; anda nos punhos e marca o barulhento | F |
| 18 | **Besouro do Estalo** — jato fervente com estouro seco; parte dos ruídos súbitos da floresta | F |
| 19 | **Onça Vazada** — cruzou a fronteira e voltou com as rosetas virando furos; some na luz manchada | F |
| 20 | **Lagarta de Visgo** — verme de veludo da Era 0 que prende num leque de cola | F |
| 21 | **Toldo das Clareiras** — membrana do tamanho de vela de navio que fecha o céu das clareiras e cai | F (chefe) |
| 22 | **Vespa Coveira** — ferroa quem sangra, paralisa vivo e arrasta para o buraco do ovo | F |
| 23 | **Bugio Invertido** — macaco para quem o chão é o céu; solta para cima quem agarra | F |
| 24 | Toupeira de Estrela — focinho de tentáculos, sobe sob a trilha | C-A: "sai do chão e some" repete a Cavadeira de Unhas (Nova Arcádia) |
| 25 | Opilião de Breu — corpo de punho sobre pernas de dois metros | C-A: silhueta de compasso aberto repete o Patinador de Óleo (Pântano) |
| 26 | Anta de Placa Seca — anta de Xylos que secou no lado seco | C-A: a ideia "secou na travessia" ficou com o Ressecado, que é gente e carrega a Colmeia |
| 27 | Bisão da Pradaria Engolida — manada pálida que pasta no escuro | C-A: mesmo gancho da Preguiça (pradaria engolida); a Preguiça guarda o slot e o sonho |
| 28 | Alce de Galhada para Dentro — chifres que cresceram para o crânio | C-A: a floresta já tem três cervídeos (Cervo-Sem-Fuga, Veado-Branco, Mãe-da-Folhagem) |
| 29 | Correição em Ponte — formigas que fazem pontes vivas | C-A: tapete de bichos repete o Lençol de Chaminé (Nova Arcádia) |
| 30 | Louva-a-deus que Congela — só se mexe quando não é olhado | C-A: mecânica de "estátua quando olhada" é clichê de terror e beira o conceitual |
| 31 | Cecília Cega — anfíbio sem pernas que cava no lodo da fronteira | C-A: serpentiforme de chão ao lado da Serpente-Raiz e da Sombra Deitada |
| 32 | Ouriço de Breu — espinhos ocos que sugam luz | C-A: espinho é do Urso-de-Espinha; "sugar luz" ficou com o Abafador |
| 33 | Tamanduá de Garra — língua e garras longas | C-A: garras gigantes já são da Preguiça |
| 34 | Javali Sem Pele — javali esfolado pela corrupção | C-A: Javali-de-Casca já existe; esfolado repete o Virado |

### Humanoides que pagaram o preço (Cobrados)

| # | Conceito | Decisão |
|---|---|---|
| 35 | **Dedos de Colheita** — colhedor de mãos nuas cujos dedos viraram talos de Pó; quebra-os no rosto do inimigo | F |
| 36 | **Olho de Pétala** — caçador dos Mercadores de Curiosidades com uma Flor-Olho enraizada na órbita; atira no escuro | F |
| 37 | **Mapa de Cicatrizes** — ajudante da expedição de Quell que corta as trilhas na pele; as cicatrizes andam | F |
| 38 | **Ressecado da Travessia** — Hospedeiro mandado pela Colmeia ao lado seco; fungo morto em placas, bebe feridas | F |
| 39 | **Mascador de Raiz** — mago de revelação de mandíbula presa à Raiz-Que-Lembra; vê a próxima Carta | F |
| 40 | Mula de Pó — contrabandista que leva o fungo costurado na pele | C-A: repete a Mula de Lágrimas (Pântano) |
| 41 | Costurado de Pálpebras — iniciado que costurou os olhos para ver o oculto | C-A: perigo quase conceitual e sem corpo legível além do fio |
| 42 | Vigia de Vestra — guarda viciado no limite seguro de colheita | C-A: é um Colhedor-de-Pó do Codex com outro nome |
| 43 | Gancheiro dos Corvos — coletor de corpos da Guilda que entra no escuro | C-A: sem preço pago no corpo; é só um humano armado |
| 44 | Ouvinte da Raiz — pregou a orelha à raiz para ouvir o antes | C-A: mesma fonte (Raiz-Que-Lembra) do Mascador, com mecânica mais fraca |

### Crias de apetite (demônios encarnados)

| # | Conceito | Decisão |
|---|---|---|
| 45 | **Sombra Deitada** (Thessavar) — planária preta que se deita no lugar da sombra e bebe pela barriga | F (slot `enemy_sombra_espreitadora`) |
| 46 | **Ermitão de Carcaça** (Thessavar) — larva que veste bichos mortos e troca de corpo no meio da luta | F |
| 47 | **Desafiante Rubro** (Urath) — macaco de peito de vidro vermelho que só luta com o mais forte | F |
| 48 | **Enrolado da Clareira** (Veleth) — tatuzinho do tamanho de uma roda que se fecha à luz e rola | F |
| 49 | **Picanço de Espinheiro** (Maalrek) — pássaro de bico curvo que espeta gente viva e volta | F |
| 50 | Assento Acolhedor (Dorrhen) — toco onde os perdidos sentam e que se fecha | C-A: árvore que come repete o Tronco-Faminto |
| 51 | Colecionador de Dentes (Daruun) — bicho que guarda o que rouba no ventre | C-A: repete o Coletor-de-Galhos e o Fardo de Espólio (Pântano) |
| 52 | Abraço de Ódio (Vhrak) — dois lobos fundidos se mordendo | C-A: é o Abraço Duplo cortado na onda 1 |

## 2. Lista do autor (21 novas + 4 slots)

Reescritos (5): Lixado da Fronteira · Abafador de Candeias · Fechado de Escápulas · Virado do Avesso ·
Calado das Guelras.
Bestas Tortas (7 + 3 slots): Morcego Rasteiro · Besouro do Estalo · Onça Vazada · Lagarta de Visgo ·
Toldo das Clareiras (chefe) · Vespa Coveira · Bugio Invertido · *(slots)* Saltão Desbotado · Casuar de
Elmo Fundo · Preguiça da Pradaria.
Cobrados (5): Dedos de Colheita · Olho de Pétala · Mapa de Cicatrizes · Ressecado da Travessia ·
Mascador de Raiz.
Crias de Apetite (4 + 1 slot): Ermitão de Carcaça (Thessavar) · Desafiante Rubro (Urath) · Enrolado da
Clareira (Veleth) · Picanço de Espinheiro (Maalrek) · *(slot)* Sombra Deitada (Thessavar).

Cotas (U12, `COTAS_PADRAO`, a região não tem entrada própria em `COTAS_ONDA`): famílias 5/10/5/5;
lacaio 7, padrão 10, elite 7, chefe 1; 13 papéis e 9 arquétipos; 4 demônios (Thessavar, Urath,
Veleth, Maalrek); habitat Floresta 20, Fronteira 9.

## 3. Cortes do revisor

Ver o parecer do revisor de unicidade (registrado no hand-back da onda) e o que foi aplicado.
