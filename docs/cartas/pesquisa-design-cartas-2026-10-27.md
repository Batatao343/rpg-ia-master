# Pesquisa: design de combate em cartas / deckbuilders táticos

Data: 2026-10-27. Escopo: orientar o redesenho do combate do RPG de texto (LLM monta a cena; resolução determinística com 2d10, Vitalidade/Ferimentos, Entropia, Reações).

Como ler as marcações:
- **[L]** = página aberta e lida (WebFetch).
- **[S]** = só o resumo/trecho do buscador.
- **[T]** = só título ou descrição (vídeo ou página bloqueada).

Nenhum vídeo foi assistido e não achei transcrição de nenhum deles. Várias fontes primárias bloquearam a leitura: GDC Vault, gamedeveloper.com, mtg.wiki, glasp (resumo do GDC de StS), GameSkinny e o Amara (legendas do GMTK). Nesses casos, o que está aqui vem de resumos de terceiros. Leia com essa ressalva.

---

## 1. Princípios de bom combate de cartas

**Decisão significativa a cada turno.** O Griftlands trocou "gastar recurso para mexer num dado" por cartas. Kevin Forbes conta que a versão com dado era "bem menos divertida que lutar". A mão limitada e aleatória obriga o jogador a se proteger contra mais de um cenário (*hedge*), em vez de só otimizar um número [L Uppercut].

Lição direta para nós: o 2d10 não pode ser a decisão. A decisão é qual carta jogar e quando. O dado só modula o resultado.

**Telegrafia da intenção do inimigo.** No Slay the Spire, cada inimigo mostra o próximo golpe. A análise da Stanford (Mechanics of Magic) diz que isso transforma o combate "num quebra-cabeça com solução" [L]. As melhores jogadas são "matar com o dano exato antes do golpe grande". A tensão vem de escolher entre atacar e defender.

O Into the Breach leva isso ao extremo: todo ataque inimigo é telegrafado e os ataques do jogador não têm aleatoriedade, e o resultado "parece um quebra-cabeça" [S]. O Griftlands usa intenções tanto na luta quanto na negociação [L Wikipedia]. O StS2 mostra várias intenções lado a lado, com números [S].

Regra que sai disso: quanto mais aleatório o resolvedor (2d10), mais informação o jogador precisa ter **antes** de decidir. Isso inclui a intenção do inimigo e a faixa de resultado da própria carta.

**Economia de recurso.** O padrão é energia por turno, mão comprada e descarte do que sobrou no fim do turno. É o modelo do Griftlands: pontos de ação, e a mão não usada é descartada [L Wikipedia].

O Inscryption troca energia por sacrifício (sangue). Isso dá valor até às cartas mais fracas, porque viram combustível. Depois os ossos entram como uma segunda moeda de longo prazo [S feedme.design]. O Dominion põe tudo no baralho, inclusive recurso e pontos [S]. O próprio Donald X notou que vários recursos dentro do deck geram "mãos terríveis ocasionais".

**Sinergia vs. consistência.** O vídeo do GMTK "Why Synergies are the Secret to Slay the Spire's Fun" defende que a graça do StS está nas sinergias [T]. O Balatro tem coringas propositalmente "espetados" (*spiky*): a variância permite runs muito diferentes e, de vez em quando, quebradas [L Super Jump].

O contrapeso é que cada carta comprada dilui o deck. As cartas de entulho (*deck cloggers*) existem justamente para punir. Funcionam bem como preço de um efeito forte [S TV Tropes / devs].

**Curva e equilíbrio.** No StS, a meta declarada era "toda carta tem seu lugar", e a secundária era "nada que distorça demais" [L Mechanics of Magic; S GDC 2019]. O equilíbrio é "frutado" (*fruity*): papéis distintos que se sobrepõem entre estratégias, em vez de um custo/poder transitivo rígido.

Também está na fonte: uma lendária rara e quebrada é aceitável, porque achá-la é a recompensa. Uma comum um pouco barata demais, que todo mundo pega por hábito, leva nerf. Ajuste por métrica: taxa de escolha e taxa de vitória por carta. O Monster Train fazia o mesmo, com taxa de escolha e de vitória por combinação de clãs [S].

**Risco-recompensa.** Atacar de forma imprudente expõe o jogador a dano grande. Ficar passivo deixa o inimigo desgastá-lo [L]. Rosewater lista **surpresa** (informação oculta gera tensão) e **inércia** (o jogo caminha para o fim) entre as dez coisas que todo jogo precisa [L Ten Things 1 e 2].

Combate longo demais é falha de design: precisa de relógio. O Inscryption usa uma balança de cabo de guerra como relógio e condição de vitória [L Game Developer].

**Contadores e jogo de resposta.** Garfield, em "Design Lessons from Poker": informação oculta abre espaço de jogo e reduz a paralisia por análise [S Riptide Lab]. No Netrunner, a corporação baixa cartas viradas e paga "rez" na hora que quiser, o que permite blefe [S].

Para nós, as Reações cumprem esse papel. O inimigo também pode ter Reações ocultas, mas com uma pista de que existe alguma.

**Keywords.** Uma palavra substitui uma frase, e assim a complexidade percebida cai sem perder profundidade [S Game Developer, "What's in a keyword"]. O Marvel Snap tem um tipo de carta só e complexidade baixa com profundidade alta. Brode diz que o lugar onde o jogador desiste é a complexidade [S Guardian].

---

## 2. Como fazer MUITAS cartas com identidade própria

1. **Templates componíveis: gatilho + condição + efeito (+ custo/contrapartida).** Exemplo: "Ao jogar · se o alvo está Sangrando · causa +3". Num motor determinístico isso vira um dado em JSON, e não código por carta. Os keywords são templates com nome.

   A arquitetura é dedução minha. O apoio vem das fontes sobre keywords e espaço de design [S itch.io/Game Developer]. O alerta delas: um keyword parece ótimo até você tentar escrever mais de duas cartas com ele. Espaço aberto demais gera cartas desconexas.

2. **"Color pie" por facção/postura.** O Magic mantém um documento do "color pie mecânico" (2017 e revisão de 2021). Ele diz quais efeitos cada cor tem como primário, secundário ou terciário [S MTG Nexus/mtgrocks].

   Para nós, as 5 Posturas diante do Abismo seriam as "cores". Cada uma tem 2–3 efeitos primários (ex.: Ferimento, Entropia, Reação, compra, mitigação), 2 secundários e proibições explícitas. Proibir é o que cria identidade.

3. **Raridade = complexidade (New World Order).** A complexidade das comuns é limitada e a complexidade sobe para as raridades maiores [S mtg.wiki/StarCityGames]. Rosewater separa três camadas: complexidade de **compreensão** (ler a carta), de **mesa** (o que rastrear) e **estratégica**. As duas primeiras ficam baixas e a profundidade fica embaixo [L Lenticular].

   Regra prática do NWO: uma comum não afeta mais de uma outra carta enquanto está em jogo.

4. **Design lenticular.** A carta parece simples para o iniciante e esconde profundidade para o veterano. Exemplos: um gatilho de morte, ou o valor de segurar a carta até o momento certo [L].

   O contraexemplo também está na fonte: uma carta que faz o iniciante segurá-la esperando um alvo que nunca chega (Aven Cloudchaser). Todo efeito precisa de um **valor de superfície** óbvio.

5. **"Toda carta tem seu lugar."** Cada carta precisa de pelo menos uma situação em que é a melhor jogada [L Mechanics of Magic, citando a meta do StS]. O teste é escrever essa situação junto com a carta. Se não existe, ela é uma carta em branco.

6. **Gerar muito e cortar.** A Mega Crit fez brainstorm de milhares de cartas e "cortou o refugo" [S Game Developer]. O StS2 descartou centenas de ideias num "processo incrivelmente destrutivo" [S PC Gamer/Softonic].

7. **Armadilhas.**
   - **Power creep:** medir por taxa de escolha/vitória e não por intuição.
   - **Redundância:** duas cartas com o mesmo momento ideal → fundir.
   - **Carta em branco:** sem situação em que seja a melhor.
   - **"Interessante ≠ divertido":** jogadores queriam jogar as cartas e não descartá-las por habilidades [L Rosewater, 20 lições].
   - **"Torne a jogada divertida a estratégia correta"** [L]. Se defender sempre vence, o jogo vira turtle.
   - **Rosewater: restrição gera criatividade** [L]. O vocabulário de keywords deve ser pequeno e fechado.

---

## 3. Clareza e UX (texto + web)

- **Intenção visível e numérica.** Ícone mais número, várias intenções lado a lado [S StS2 guide]. No texto, uma linha fixa: "Intenção: Golpe pesado 8–12 · Reação oculta (1)".
- **Preview do resultado.** No Into the Breach a UX "faz você se sentir esperto" [T Prototypr, bloqueado]. A ideia comprovada no jogo é não esconder consequência [S]. Para o 2d10: mostrar a faixa e a probabilidade antes de confirmar ("acerto em 11+ · 55% · 4–7 de dano"). A matemática é Python, então dá para calcular exato.
- **Legibilidade acima de tudo.** O Inscryption tirou o texto das cartas, deixando só nome e ícones, por causa da baixa resolução [L]. O Balatro é "um número e um naipe, só isso", e os coringas são fáceis de ler porque a base é simples [L].
- **Tooltips para keywords.** A crítica principal ao StS: sinergias que só se descobrem na comunidade afastaram iniciantes. A sugestão é tooltip [L Mechanics of Magic].
- **Log legível.** Proposta minha a partir das fontes. O log mecânico fica separado da narração da LLM (que é sabor): `Você: Corte Baixo → 2d10=13 (+2 Postura) = 15 vs 12 · 5 dano · Ferimento: Sangrando`. A LLM narra **depois**, com os números já fixos.
- **História "carregada de lado".** O Griftlands deixa a lore fora do caminho crítico e disponível sob demanda, para não cansar na repetição [L Uppercut]. A narração da LLM no combate deve ser curta por golpe e rica só no início e no fim.
- **Seja direto.** Rosewater: "não tenha medo de ser óbvio" [L].

---

## 4. Lições por jogo

**Griftlands** (a mais relevante: combate + negociação com cartas, em contexto de RPG).
- Dois decks (luta e negociação), ambos com intenção do oponente [L].
- Na negociação, os **argumentos** são efeitos persistentes que se atacam diretamente. Existem um argumento central (o "núcleo") e argumentos menores, e a **compostura** funciona como escudo [L Wikipedia; S PC Gamer/GameSkinny].
- **Dominar em vez de matar:** dano suficiente faz o oponente fugir, e isso muda missões e recompensas futuras [L]. Consequência narrativa sai de estado mecânico.
- Perder a negociação não acaba o jogo, pode virar combate [L].
- Efeitos cruzam sistemas: aceitar uma bebida forçada põe cartas de status "Tipsy" no deck de combate [L Uppercut].
- O que eles cortaram: dados de perícia, equipamento craftável e level-up, porque o deckbuilding tornou tudo isso supérfluo [L]. Para nós: cuidado com sistemas paralelos ao deck que competem com ele.
- Crítica dos reviews: a negociação vira sucesso/fracasso binário e se desconecta do diálogo [S Linux Format]. O resultado deve ter graus.

**Slay the Spire**
- Intenção telegrafada, combate como quebra-cabeça [L].
- Entulho temporário (status) vs. permanente (maldição) [S Fandom]. É um modelo direto para Ferimento (status do combate) vs. cicatriz/corrupção (maldição que persiste).
- Equilíbrio por métricas e Discord, raro quebrado aceitável [L/S].

**Inscryption**
- O custo é sacrifício: todo recurso tem um preço narrativo [L/S]. A escalada é temática (sacrificar o olho, o dente), o custo mecânico **é** a história.
- Relógio de cabo de guerra [L].
- O gancho está na moldura narrativa: antagonista, cartas que falam [L].

**Monster Train**
- Pick/win rate por combinação de clãs [S].
- Novos tipos de carta (Sala, Equipamento) no 2 [S].
- A palestra "good → great" de Andrew (Shiny Shoe) só tem título [T].

**Corrupção / custo de vida (fora dos 4)**
- **Darkest Dungeon:** stress chega a 100 → teste de resolução → Aflição (debuff que espalha stress) ou Virtude (buff). Inspirado em "heróis são humanos" [S PC Gamer/GDC 2016]. Encaixa bem com Entropia e Virtudes, que o jogo já tem.
- **Comentário de jogadores/devs sobre deckbuilders de corrupção:** autodano aleatório parece "sorte". O recomendado é custo **previsível**, rampa lenta e builds que recompensam a corrupção [S itch.io].

**Hand of Fate**
- O "Dealer" tem um deck próprio que cresce junto com o do jogador e narra cada carta [S Wikipedia/Semel].
- Os eventos de chance são 4 cartas embaralhadas de sucesso/fracasso [S].
- É o análogo mais próximo de "LLM narra, deck decide". Crítica dos reviews: o deck pouco entra na narrativa [S RPGamer].

**Cultist Simulator**
- Cartas como substantivos que entram em "verbos" com timer [S].
- Cartas que expiram ou se transformam em algo nocivo se não forem usadas [S RPGFan]. Serve de modelo para cartas de Entropia que apodrecem na mão.

**Arkham Horror LCG**
- Saco do caos: o token sorteado modifica a perícia contra a dificuldade [S].
- A dificuldade se ajusta trocando tokens, e o estado do jogo adiciona tokens [S].
- Para nós: no lugar de um 2d10 puro, um **modificador de Entropia** que "suja" o resultado conforme a corrupção sobe.
- Trauma persiste entre cenários [S].

**Night of the Full Moon:** não pesquisado, sem fonte útil.

---

## 5. Mecânicas recomendadas (com fonte)

1. **Intenção do inimigo sempre visível**, com número ou faixa e várias lado a lado. Uma "Reação oculta" aparece só como contagem. *Fontes:* StS / StS2 / Into the Breach / Griftlands; Garfield sobre informação oculta.
2. **Preview determinístico antes de confirmar:** chance do 2d10 e faixa de dano/Ferimento. *Fonte:* Into the Breach (telegrafia total). O preview é proposta minha.
3. **Energia por turno + mão de 5 + descarte da sobra.** Mantém a decisão dentro do turno. *Fontes:* StS, Griftlands.
4. **Dominar vs. matar (golpe não-letal → fuga/rendição)** com consequência no mundo. *Fonte:* Griftlands (*overpower*). Já existe parcialmente no SPEC-325.
5. **Ferimento = carta de status no deck do ferido**, temporária no combate, e **cicatriz = maldição** permanente até ser tratada. *Fontes:* StS (status vs. maldição); Griftlands ("Tipsy" cruzando sistemas).
6. **Entropia como saco do caos:** cada faixa de Entropia acrescenta um modificador negativo possível ao 2d10, e também um positivo ("o Abismo empresta"). *Fontes:* Arkham LCG; Darkest Dungeon (Aflição/Virtude).
7. **Cartas "Abissais" com custo previsível em Vitalidade/Entropia** no lugar da energia. O sacrifício como recurso, com o preço sempre explícito. *Fontes:* Inscryption; comentário sobre autodano previsível vs. aleatório.
8. **Ponto de ruptura** (Entropia no máximo): teste → Aflição ou Virtude. *Fonte:* Darkest Dungeon.
9. **Argumentos persistentes também no conflito social** (núcleo + argumentos menores atacáveis, compostura). Isso unifica luta e conversa num só motor de cartas. *Fonte:* Griftlands.
10. **Cartas que apodrecem:** cartas de Entropia na mão que se transformam se não forem jogadas em N turnos. *Fonte:* Cultist Simulator.
11. **Relógio do combate** (balança ou escalada por rodada) para garantir que o combate termine. *Fontes:* Inscryption (balança); Rosewater (inércia).
12. **Vocabulário fechado de ~12–16 keywords**, cada um com tooltip, todo efeito sendo gatilho+condição+efeito em dados. *Fontes:* artigos sobre keywords; Mechanics of Magic (tooltips); Marvel Snap (baixa complexidade).
13. **Color pie das 5 Posturas:** primário/secundário/proibido por efeito. *Fonte:* Mechanical Color Pie (MTG).
14. **Raridade = complexidade (NWO)**: comuns com 1 linha e no máximo 1 interação; raras podem ser *spiky*. *Fontes:* New World Order; Lenticular; Balatro.
15. **Telemetria de escolha/vitória por carta no playtest harness** (o projeto já tem `playtest/`) e meta "toda carta tem um momento". *Fontes:* StS (GDC 2019); Monster Train.

Bônus para a arquitetura com LLM: o deck do "Dealer" monta o encontro e a LLM só narra o que as cartas decidiram. *Fonte:* Hand of Fate.

---

## 6. Fontes

Lidas **[L]**:
- Rosewater, "Lenticular Design" (2014): https://magic.wizards.com/en/news/making-magic/lenticular-design-2014-03-31
- Rosewater, "Ten Things Every Game Needs" pt. 1: https://magic.wizards.com/en/news/making-magic/ten-things-every-game-needs-part-1-2011-10-24
- Rosewater, "Ten Things Every Game Needs" pt. 2: https://magic.wizards.com/en/news/making-magic/ten-things-every-game-needs-part-1-part-2-2011-12-19
- Notas da GDC 2016 "20 Years, 20 Lessons" (Rosewater): https://notes.hamatti.org/Sources/Talks/'Magic-the-Gathering'-20-Years,-20-Lessons-Learned-by-Mark-Rosewater
- Uppercut, Griftlands / Kevin Forbes: https://uppercutcrit.com/?p=2431
- Wikipedia, Griftlands: https://en.wikipedia.org/wiki/Griftlands
- Mechanics of Magic (Stanford), crítica sobre StS: https://mechanicsofmagic.com/2022/05/22/critical-play-is-this-game-balanced-10/
- Game Developer, origem do Inscryption: https://www.gamedeveloper.com/design/how-game-jam-sacrifices-became-inscryption
- Super Jump, Balatro: https://www.superjumpmagazine.com/getting-to-the-heart-of-the-cards-of-balatro

Só trecho do buscador **[S]**:
- GDC 2019, StS "Metrics Driven Design": https://www.gamedeveloper.com/design/learn-i-slay-the-spire-i-s-metrics-driven-approach-to-game-balancing-at-gdc-2019
- Road to the IGF, StS: https://www.gamedeveloper.com/disciplines/road-to-the-igf-mega-crit-games-i-slay-the-spire-i-
- Guia de intenções do StS2: https://sts2.untapped.gg/guides/how-to-read-enemy-intent
- Cartas do StS (Fandom): https://slay-the-spire.fandom.com/wiki/Cards
- Cortes de cartas do StS2: https://en.softonic.com/articles/slay-the-spire-2-was-about-to-have-fewer-cards-because-of-dark-souls
- NWO (mtg.wiki): https://mtg.wiki/page/New_World_Order
- NWO (StarCityGames): https://articles.starcitygames.com/articles/new-world-order-and-complexity-creep/
- Mechanical Color Pie 2021 (mtgrocks): https://mtgrocks.com/lead-designer-shares-mechanical-future-of-magic-the-gathering/
- Keywords em jogos de carta: https://www.gamedeveloper.com/game-platforms/card-games-what-s-in-a-keyword
- Post sobre espaço de design de keywords: https://itch.io/post/6084750
- Monster Train, Q&A do dev: https://www.digitallydownloaded.net/2020/02/developer-q-a-monster-train-a-deckbuilding-roguelike-with-a-hellish-theme.html
- Review do Inscryption (feedme.design): https://www.feedme.design/while-everyones-off-playing-balatro-im-still-obsessed-with-inscryption
- Marvel Snap, entrevista com Brode (Guardian): https://www.inkl.com/news/i-craved-a-bite-size-experience-ben-brode-on-the-making-of-marvel-snap
- Netrunner (Riptide Lab): https://riptidelab.com/android-netrunner-full-review/
- Dominion (Wikipedia): https://en.wikipedia.org/wiki/Dominion_(card_game)
- Arkham Horror LCG (Wikipedia): https://en.wikipedia.org/wiki/Arkham_Horror:_The_Card_Game
- Arkham Horror LCG (review Zatu): https://zatu.com/blogs/reviews/arkham-horror-the-card-game-review
- Darkest Dungeon (PC Gamer): https://www.pcgamer.com/uk/how-darkest-dungeon-got-inspiration-from-band-of-brothers-and-aliens
- Hand of Fate (Wikipedia): https://en.wikipedia.org/wiki/Hand_of_Fate_(video_game)
- Hand of Fate, entrevista com Jaffit: https://paulsemel.com/exclusive-interview-hand-of-fate-creative-director-morgan-jaffit/
- Cultist Simulator (Wikipedia): https://en.wikipedia.org/wiki/Cultist_Simulator
- Cultist Simulator (review RPGFan): https://www.rpgfan.com/review/cultist-simulator/
- Into the Breach, GDC 2019 (80.lv): https://80.lv/articles/gdc-2019-an-inside-look-at-into-the-breach
- Linux Format, review do Griftlands: https://www.pressreader.com/australia/linux-format/20210921/281603833593821
- Deck cloggers (TV Tropes): https://www.tvtropes.org/pmwiki/pmwiki.php/Main/DeckClogger

Só título **[T]** (vídeos e páginas bloqueadas; nenhuma transcrição obtida):
- GMTK, "Why Synergies are the Secret to Slay the Spire's Fun" (vídeo): https://amara.org/v/C3BET
- GDC 2019, Giovannetti: vídeo no Vault e resumo do glasp bloqueados: https://glasp.co/youtube/7rqfbvnO_H0
- GDC 2019, Davis, "Into the Breach Design Postmortem" (vídeo)
- GDC 2016, Sigman, "Darkest Dungeon: A Design Postmortem" (vídeo)
- Shiny Shoe/Unity, "Deckbuilder game design w/ Shiny Shoe (Monster Train 2)" (livestream): https://activation.unity3d.com/kr/campaign/indie-survival-guide
- Game Maker's Notebook, LocalThunk (podcast): https://gamemakersnotebook.libsyn.com/balatro-creator-localthunk-talks-inspirations-and-jokers
- Prototypr, "Into the Breach's UX makes you feel smart" (403): https://blog.prototypr.io/into-the-breachs-ux-makes-you-feel-smart-a9cb03210757
- Donald X, "Secret History of the Dominion Cards" (BGG): não aberto
- Ludonarrative, Adam Millard, Design Doc: nada específico achado
- r/gamedesign, r/slaythespire, r/tabletopgamedesign: as buscas não retornaram threads do Reddit
