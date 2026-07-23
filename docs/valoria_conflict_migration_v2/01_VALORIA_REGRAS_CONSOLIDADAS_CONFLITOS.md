# Valoria — Regras Consolidadas do Sistema de Conflitos

**Versão:** 2.0 — Handoff funcional após análise do projeto atual  
**Escopo:** combate, fuga, perseguição, preparação de encontros, comportamento tático, cartas, Ferimentos, Abismo, bestiário, loot e retorno à narrativa

---

## 1. Visão do sistema

Valoria será dividido em dois modos complementares.

### 1.1 Mundo narrativo

Roleplay, exploração, investigação, conversas, deslocamentos pelo mundo, descoberta de locais, relações, Memórias e consequências narrativas continuam sendo conduzidos pela LLM e pelos sistemas atuais do jogo.

A LLM é responsável por criar, interpretar e narrar a ficção. Ela pode gerar pessoas, locais, situações e eventos, desde que produza as informações necessárias para que esses elementos sejam persistentes e utilizáveis pelo restante do jogo.

### 1.2 Conflito determinístico

Combate, fuga, perseguição e loot funcionam como um jogo tático de cartas. Durante esses fluxos, não existe chamada de LLM.

A resolução utiliza apenas:

- regras conhecidas;
- cartas;
- recursos;
- estados;
- dados;
- elementos de cenário preparados antes do conflito;
- perfis táticos previamente gerados;
- eventos previamente disponíveis.

Quando o conflito termina, o resultado é entregue à LLM para que a história continue. A LLM não pode alterar o que foi resolvido.

### 1.3 Regra central

> A LLM cria o contexto antes do conflito e narra suas consequências depois. O conflito em si é resolvido integralmente pelo jogo.

---

## 2. Relação com o projeto atual

O projeto já possui uma base ampla de mundo, agentes narrativos, bestiário, NPCs, party, progressão, itens, loot, memória, persistência, eventos e testes.

A migração não pretende reconstruir todos esses sistemas. Ela substitui principalmente o modo como os conflitos são preparados e resolvidos.

Devem ser preservados, sempre que compatíveis:

- o mundo e sua lore;
- as regiões e seus conteúdos;
- o bestiário regional;
- a criação e persistência de NPCs;
- a party e seus vínculos;
- a progressão do personagem;
- os itens e o inventário;
- o fluxo de loot já existente;
- a continuidade narrativa;
- as Memórias e fatos persistentes;
- os testes e ferramentas de validação existentes.

A forma concreta de reaproveitar ou migrar cada parte será definida pelo coding agent depois de analisar o código atual.

---

## 3. Preparação do conflito pela LLM

Antes de um combate ou perseguição, a LLM transforma a cena narrativa em uma cena jogável.

Ela deve considerar o contexto real do momento:

- local onde a cena acontece;
- descrição já apresentada ao jogador;
- objetos já mencionados;
- participantes presentes;
- estado físico dos participantes;
- relações e intenções;
- região;
- perigo do lugar;
- evento que iniciou o conflito;
- clima, iluminação e condições ambientais;
- objetivos dos envolvidos;
- possíveis acontecimentos externos já coerentes com a cena.

A LLM prepara:

- as zonas da cena;
- as ligações entre as zonas;
- as posições iniciais;
- os Engajamentos iniciais;
- os inimigos selecionados do bestiário regional;
- os NPCs presentes;
- os objetos interativos;
- as interações possíveis de cada objeto;
- coberturas, obstáculos e rotas;
- condições ambientais;
- reforços e gatilhos possíveis;
- objetivos especiais do conflito;
- condições especiais de encerramento;
- possíveis eventos do Abismo.

Depois que a cena é aceita e o conflito começa, ela não pode ser ampliada ou reinterpretada pela LLM.

### 3.1 Catálogo fechado

A LLM pode criar combinações narrativas livres, mas os resultados mecânicos devem utilizar apenas operações reconhecidas pelo jogo.

Ela pode descrever uma alavanca que derruba o salão, mas a interação precisa corresponder a consequências que o jogo conhece, como:

- alterar terreno;
- bloquear uma rota;
- liberar uma rota;
- causar dano;
- solicitar uma reação;
- aplicar um estado;
- reposicionar participantes;
- gerar reforços;
- destruir um objeto;
- mudar uma condição ambiental.

A descrição pode ser criativa. O efeito mecânico não pode ser inventado fora do catálogo.

### 3.2 Potência em vez de números livres

A LLM não escolhe livremente dano, dificuldade, resistência, duração ou quantidade de reforços.

Ela seleciona uma categoria:

- Fraco;
- Moderado;
- Forte;
- Devastador.

O valor correspondente depende do Nível do Encontro.

### 3.3 Falha na preparação

Se a proposta de cena for inválida, o sistema deve tentar corrigi-la utilizando os providers disponíveis.

O projeto pode percorrer diferentes providers de LLM até obter uma preparação válida. Caso todos falhem, deve existir uma cena simplificada de segurança, sem inventar resultados fora das regras.

---

## 4. Bestiário regional e NPCs prontos para combate

### 4.1 Bestiário

As criaturas disponíveis são criadas previamente por uma LLM mais robusta e salvas no bestiário.

Cada criatura é associada às regiões onde pode aparecer. Durante a campanha, a LLM que prepara a cena seleciona criaturas válidas para a região e para o contexto do encontro.

Uma criatura do bestiário já possui tudo o que precisa para participar do jogo:

- identidade e descrição;
- papel no encontro;
- atributos;
- Vitalidade;
- defesa;
- armadura ou proteção natural;
- recursos;
- cartas;
- reações;
- resistências e vulnerabilidades;
- regras de Ferimentos;
- perfil tático;
- regras de fuga e perseguição;
- comportamento moral ou instintivo relevante.

### 4.2 NPCs gerados durante o roleplay

Sempre que a LLM criar um NPC, ela também deve criar sua representação completa para combate.

Isso vale para comerciantes, sacerdotes, guardas, nobres, criminosos, viajantes e qualquer outro personagem. O jogador pode iniciar um conflito com alguém que parecia apenas narrativo; portanto, esse NPC já deve estar pronto.

A ficha fica persistida junto ao NPC para manter consistência em encontros futuros.

### 4.3 Perfil tático pré-gerado

A LLM robusta gera o perfil tático do arquétipo ou NPC uma única vez. Esse perfil é salvo e utilizado nos conflitos futuros.

A LLM não decide turnos em tempo real.

---

## 5. Perigo absoluto do mundo

O mundo não escala automaticamente para acompanhar o protagonista.

Uma região extremamente perigosa continua perigosa para um personagem iniciante. Uma região segura continua relativamente fácil para um personagem veterano.

O jogador pode viajar para um lugar acima de sua capacidade, enfrentar uma ameaça muito superior e morrer.

O jogo não mostra:

- nível recomendado;
- classificação mecânica do local;
- aviso de que o encontro está acima do personagem;
- garantia de que a ameaça é vencível.

A narrativa pode apresentar sinais:

- cadáveres;
- destruição;
- silêncio incomum;
- relatos de sobreviventes;
- marcas de criaturas;
- reação dos companheiros;
- histórias sobre a região.

Cabe ao jogador interpretar o risco.

### 5.1 Nível do encontro

O Nível do Encontro depende principalmente:

- do local;
- da periculosidade real da região;
- do tipo de evento;
- da importância daquele conflito;
- de ameaças únicas presentes.

Ele não depende do nível atual da party para ficar “justo”.

---

## 6. Zonas e distância abstrata

Não haverá grid tático.

A cena possui zonas criadas a partir do local narrado, como:

- salão principal;
- sacada;
- corredor norte;
- fosso;
- ponte;
- rua lateral;
- telhado.

Essas zonas permitem que objetos, rotas, áreas e reforços tenham um lugar coerente dentro da cena.

Para o jogador, a distância continua abstrata:

- **Próximo**;
- **Distante**;
- **Separado**.

A postura é registrada separadamente:

- **Protegido**;
- **Neutro**;
- **Exposto**.

A ocultação também é separada:

- **Visível**;
- **Escondido**.

Engajamento é uma relação independente. Dois personagens podem estar Próximos sem estarem Engajados.

### 6.1 Mudança de distância

Uma manobra de Pré-Ação ou Pós-Ação muda um estágio:

- Próximo para Distante;
- Distante para Separado;
- Separado para Distante;
- Distante para Próximo.

Usando Pré-Ação e Pós-Ação para mover, um personagem pode atravessar dois estágios no mesmo turno.

### 6.2 Protegido e Exposto

Esses estados podem ser momentâneos ou sustentados.

Momentâneo afeta o próximo ataque aplicável e depois termina.

Sustentado permanece enquanto sua causa concreta continuar existindo, como uma pilastra, correntes, cobertura, iluminação ou Guardar.

---

## 7. Objetos interativos

A LLM gera os objetos a partir da cena.

Exemplo:

- Objeto: Alavanca Enferrujada;
- Distância: Próximo;
- Interação disponível: Ativar;
- Custo: Pré-Ação ou Pós-Ação.

O jogador vê apenas:

- o objeto percebido;
- as interações disponíveis;
- o custo da interação;
- requisitos evidentes.

O jogador não recebe automaticamente a descrição completa do efeito. Uma alavanca pode abrir uma porta, derrubar o chão, disparar uma armadilha ou interromper um ritual. O resultado é descoberto quando a interação acontece ou quando já foi identificado por investigação anterior.

Objetos secretos não aparecem até serem descobertos.

Objetos podem:

- ser usados uma única vez;
- ter usos limitados;
- mudar de estado;
- ser destruídos;
- bloquear ou liberar rotas;
- alterar as zonas;
- iniciar eventos;
- afetar todos em uma área.

---

## 8. Virtudes e progressão

As cinco Virtudes são:

- Mente;
- Agilidade;
- Força;
- Carisma;
- Corpo.

Elas variam de 0 a 5.

Na criação, o personagem distribui:

- 4;
- 3;
- 2;
- 1;
- 1.

As classes apenas recomendam Virtudes. Elas não alteram essa distribuição.

O nível máximo é 10. O personagem recebe +1 em uma Virtude nos níveis:

- 2;
- 4;
- 6;
- 8;
- 10.

O limite continua sendo 5.

### 8.1 Corpo

Corpo define Vitalidade, capacidade de suportar Ferimentos e limites de Gravidade.

| Corpo | Vitalidade | Leves | Graves | Críticos |
|---:|---:|---:|---:|---:|
| 0 | 6 | 2 | 1 | 1 |
| 1 | 8 | 3 | 1 | 1 |
| 2 | 10 | 3 | 2 | 1 |
| 3 | 12 | 4 | 2 | 2 |
| 4 | 14 | 4 | 3 | 2 |
| 5 | 16 | 5 | 3 | 3 |

Limites de Gravidade:

| Corpo | Leve | Grave | Crítico |
|---:|---:|---:|---:|
| 0 | 1–3 | 4–6 | 7+ |
| 1 | 1–4 | 5–8 | 9+ |
| 2 | 1–5 | 6–10 | 11+ |
| 3 | 1–6 | 7–12 | 13+ |
| 4 | 1–7 | 8–14 | 15+ |
| 5 | 1–8 | 9–16 | 17+ |

Aumentar Corpo recalcula imediatamente esses valores.

---

## 9. Cartas e preparação

As cinco classes permanecem como núcleo do personagem:

- Devoto do Abismo;
- Sangromante;
- Corruptor;
- Arcanista Cinzento;
- Médico de Campo.

Classe e subclasse continuam existindo. A subclasse abre uma linha própria de cartas exclusivas.

### 9.1 Acervo e Preparação

O personagem possui um Acervo de cartas conhecidas e uma quantidade menor de cartas preparadas.

Espaços preparados:

| Nível | Cartas preparadas |
|---|---:|
| 1–3 | 4 |
| 4–6 | 5 |
| 7–9 | 6 |
| 10 | 7 |

No nível 1, escolhe seis cartas entre classe e subclasse e prepara quatro. Não existe divisão mínima obrigatória.

Fora de combate, quando estiver seguro e sem ameaça imediata, pode reorganizar livremente as cartas preparadas.

A cada nível, escolhe:

- uma nova carta de classe ou subclasse; ou
- a evolução de uma carta já conhecida.

### 9.2 Patamares

- Inicial: níveis 1–3;
- Avançado: níveis 4–6;
- Superior: níveis 7–10.

Ao abrir um patamar, o personagem ainda pode escolher cartas anteriores.

### 9.3 Evolução em caminhos

A partir do nível 4, uma carta pode ser evoluída uma única vez.

O jogador escolhe permanentemente entre Caminho A ou Caminho B. O caminho substitui o efeito normal e a Ruptura base pela versão evoluída correspondente.

Não existe mistura entre caminhos nem uma segunda evolução.

### 9.4 Frequências

Cada carta define sua própria frequência:

- Livre;
- uma vez por turno;
- uma vez por cena;
- uma vez por descanso curto;
- uma vez por descanso longo.

---

## 10. Cartas de Virtude

As perícias tradicionais são substituídas por Cartas de Virtude.

O personagem escolhe exatamente duas na criação. Elas podem pertencer à mesma Virtude ou a Virtudes diferentes.

Essas cartas:

- são permanentes;
- não ocupam espaços preparados;
- não são conquistadas novamente depois;
- evoluem conforme a Virtude relacionada.

Estágios:

- Virtude 1–2: Estágio I;
- Virtude 3–4: Estágio II;
- Virtude 5: Estágio III.

---

## 11. Estrutura do turno

Cada turno possui:

1. Pré-Ação;
2. Ação;
3. Pós-Ação.

Pré-Ação e Pós-Ação permitem uma manobra simples, como:

- mudar um estágio de distância;
- Engajar;
- reposicionar um aliado;
- alertar a party sobre a posição aproximada de um alvo oculto;
- usar um objeto simples;
- realizar outra manobra explicitamente permitida.

A Ação permite:

- atacar;
- usar uma carta;
- Guardar;
- Desengajar;
- Fugir;
- Esconder-se;
- Procurar;
- usar um objeto complexo;
- realizar uma ação relevante prevista pela cena.

---

## 12. Iniciativa por lados

Se um lado iniciou claramente o confronto, ele age primeiro automaticamente na primeira rodada.

Exemplos:

- emboscada;
- ataque deliberado antes da reação do outro lado;
- preparação bem-sucedida;
- invasão iniciada de modo claro.

Quando nenhum lado possui iniciativa narrativa, cada lado rola:

**2d10 + maior Agilidade entre seus participantes conscientes.**

O lado vencedor age primeiro.

No turno da party, o jogador escolhe livremente a ordem do protagonista e dos companheiros. A ordem pode mudar a cada rodada.

O lado inimigo utiliza os perfis táticos para definir a ordem e as ações.

---

## 13. Ataques e testes

### 13.1 Ataques

Ataques usam:

**2d10 + Virtude adequada contra Esquiva.**

A Virtude é determinada pela arma ou pela carta.

Exemplos:

- armas pesadas: Força;
- arco, adaga e rapieira: Agilidade;
- magia precisa ou arcana: Mente;
- comando, fé, medo ou presença: Carisma;
- sangue, carne e transformação: Corpo.

Quando uma carta permite mais de uma Virtude, a escolha é feita ao preparar a carta e permanece até a próxima reorganização.

### 13.2 Críticos

Nos dois dados mantidos:

- qualquer dupla de 1 a 9 é acerto automático e Crítico;
- dupla de 10 é acerto automático e Supercrítico.

Crítico multiplica o efeito principal por 2.

Supercrítico multiplica o efeito principal por 3.

Isso vale para jogador, companheiros, NPCs e inimigos.

Em cartas com vários efeitos, apenas o efeito identificado como principal é multiplicado.

### 13.3 Vantagem e Desvantagem

- Vantagem: rola 3d10 e mantém os dois maiores;
- Desvantagem: rola 3d10 e mantém os dois menores;
- uma cancela a outra;
- não há acúmulo de dados adicionais.

Crítico é verificado nos dados mantidos.

### 13.4 Testes gerais

Testes fora dos ataques usam dois dados distintos:

- Ímpeto;
- Presságio.

Resultado:

**Ímpeto + Presságio + Virtude contra a dificuldade.**

Consequência:

- Ímpeto maior: consequência favorável;
- Presságio maior: consequência desfavorável;
- empate: resultado puro, sem consequência secundária.

Dificuldades-base:

| Grau | Dificuldade |
|---|---:|
| Fácil | 9 |
| Comum | 12 |
| Difícil | 15 |
| Extremo | 18 |
| Quase impossível | 21 |

Ataques de combate não utilizam essa matriz de consequência.

---

## 14. Ruptura

Ruptura é a versão extrema de uma carta preparada.

Ela é declarada antes da rolagem.

Ao usar Ruptura:

- paga-se o custo normal da carta;
- aplica-se a versão de Ruptura disponível;
- gera-se 1 Carga do Abismo, mesmo em falha;
- a Carga recém-gerada não pode afetar a própria Ruptura.

Ruptura não possui limite geral por cena. O limite vem da frequência, dos custos e dos recursos.

Em ataques, Ruptura concede Vantagem.

Em testes gerais, rola-se dois dados de Ímpeto e um de Presságio, mantendo o maior Ímpeto.

Ruptura e Crítico podem acontecer ao mesmo tempo e seus efeitos se acumulam.

---

## 15. Cargas do Abismo

As Cargas formam um único reservatório visível do protagonista.

Elas:

- persistem até serem gastas;
- não possuem máximo automático;
- não desaparecem ao fim de uma cena;
- podem ser combinadas para consequências maiores;
- não possuem origem mecânica individual.

O Abismo é uma força impessoal. Não possui moral, objetivo ou plano.

Ele atua no ponto mais frágil da situação atual e transforma algo que já existe. Não cria elementos do nada.

Pode:

- revelar;
- soltar;
- deformar;
- acelerar;
- romper;
- reposicionar por uma causa existente;
- transformar permanentemente algo que já existia.

Não pode:

- desfazer um sucesso já resolvido;
- controlar mentalmente um NPC;
- obrigar alguém a agir contra sua personalidade;
- criar diretamente um Ferimento;
- agravar mecanicamente um Ferimento fora do combate normal;
- adicionar um elemento sem base na cena.

### 15.1 Abismo em conflito determinístico

Antes do conflito, a LLM prepara possíveis eventos do Abismo coerentes com a cena.

Esses eventos ficam disponíveis como acontecimentos fechados. Durante o conflito, podem ser carregados de forma determinística ou aleatória pela seed, conforme:

- Cargas disponíveis;
- gatilhos;
- prioridade;
- estado atual da cena;
- usos permitidos.

Eles podem acontecer sem chamada de LLM.

A manifestação possui uma assinatura recorrente:

- o som ambiente é abafado;
- as cores perdem intensidade;
- uma fissura negra e fina aparece;
- um pulso pálido atravessa a fissura;
- a realidade muda;
- a fissura desaparece, mas a mudança permanece.

O gasto é mostrado imediatamente ao jogador.

---

## 16. Reações

Cartas podem possuir o tipo Reação e um gatilho claro.

Sequência básica:

1. uma ação é declarada;
2. seus alvos, escolhas e custos são definidos;
3. abre-se a possibilidade de reação;
4. as reações válidas são escolhidas e pagas;
5. a ação é resolvida.

A declaração original não pode ser alterada depois da abertura da reação.

### 16.1 Reações da party e dos inimigos

Jogador, companheiros e inimigos podem reagir.

Inimigos utilizam reações de acordo com seu perfil tático, seus recursos e seus gatilhos. Uma reação pode exigir Entropia.

Reações podem responder a outras reações quando o gatilho permitir.

Na mesma cadeia, cada personagem pode utilizar no máximo uma reação comum. A cadeia termina quando ninguém possuir ou desejar utilizar outra reação válida.

A mesma carta não pode ser repetida dentro da mesma cadeia, salvo texto explícito.

### 16.2 Ordem das reações

A ordem-base é:

1. alvo direto;
2. aliados do alvo;
3. aliados do ator;
4. maior Agilidade em conflitos de ordem;
5. critério estável de desempate.

Quando a party possui mais de uma reação válida sem conflito, o jogador escolhe sua ordem.

### 16.3 Ataques de oportunidade

Ataques de oportunidade são reações universais provocadas por abandonar um Engajamento sem Desengajar.

Eles não são limitados pela regra de uma reação comum por cadeia.

Cada inimigo Engajado, consciente e capaz de atacar pode realizar seu próprio ataque de oportunidade.

Isso também vale para personagens da party contra inimigos que abandonem o Engajamento.

---

## 17. Engajamento, Guardar e movimento

### 17.1 Engajamento

Para um ataque corpo a corpo comum, o atacante precisa estar:

- Próximo;
- Engajado com o alvo.

Engajar custa Pré-Ação ou Pós-Ação.

Um personagem pode estar Engajado com vários inimigos.

### 17.2 Desengajar

Desengajar custa a Ação.

Ele encerra com segurança os Engajamentos escolhidos, evitando ataques de oportunidade.

### 17.3 Guardar

Guardar custa a Ação.

Enquanto Guardando:

- ataques Defensáveis contra o personagem sofrem Desvantagem;
- os ataques do personagem também sofrem Desvantagem.

O personagem pode abandonar Guardar livremente antes de agir, perdendo a proteção.

Guardar não depende de escudo. É uma postura universal.

### 17.4 Defensável

Ataques e efeitos podem ser marcados como Defensáveis.

Um ataque Defensável pode ser dificultado por Guardar e pode permitir o uso de escudo compatível.

Um ataque não Defensável ignora esses benefícios, embora a armadura ainda possa funcionar se for compatível.

---

## 18. Esconder-se e procurar

Esconder-se custa a Ação e exige uma fonte plausível:

- escuridão;
- fumaça;
- vegetação;
- multidão;
- cobertura;
- obstáculo;
- outro elemento coerente.

Ocultação é relativa a cada observador.

Um personagem pode estar Escondido de um inimigo e Visível para outro.

### 18.1 Alvo sem posição conhecida

Quem não sabe onde o alvo está não pode atacá-lo diretamente.

Pode:

- Procurar;
- atacar uma área coerente;
- utilizar uma habilidade apropriada.

### 18.2 Posição aproximada

Se souber a posição aproximada, pode atacar com Desvantagem.

Acertar o alvo não remove Escondido. O personagem apenas sofreu o golpe.

### 18.3 Procurar e alertar

Procurar custa a Ação.

Quando encontra o alvo, ele fica Visível apenas para quem o encontrou.

Para avisar a party, o personagem gasta Pré-Ação ou Pós-Ação. Toda a party capaz de receber o aviso passa a conhecer a posição aproximada e pode atacar com Desvantagem.

A posição aproximada permanece até o alvo:

- mudar de distância;
- trocar de esconderijo;
- ser reposicionado;
- realizar um deslocamento que invalide a posição anterior.

### 18.4 Movimento oculto

Qualquer mudança de distância encerra Escondido.

Trocar de esconderijo ou ser reposicionado também encerra Escondido.

Pequenos ajustes dentro do mesmo local não contam como mudança de distância.

### 18.5 Ataque oculto

Atacar enquanto Escondido concede Vantagem.

O personagem permanece Escondido durante toda a resolução do ataque e se torna Visível depois, mesmo que erre.

Cartas específicas podem alterar essa regra.

---

## 19. Armas

Dano-base por categoria:

| Categoria | Dano |
|---|---:|
| Leve, uma mão | 3 |
| Marcial, uma mão | 4 |
| Versátil, duas mãos | 6 |
| Pesada, duas mãos | 8 |

Cada tipo de arma possui uma propriedade-base fixa.

Armas normais possuem no máximo duas propriedades:

- uma propriedade-base;
- uma propriedade adicional.

A propriedade adicional pode ser substituída por um profissional ou processo adequado. Não é alterada por descanso comum.

### 19.1 Armas lendárias

Uma arma normal só se torna lendária por um acontecimento excepcional da campanha.

Ela mantém:

- seu tipo central;
- sua propriedade-base;
- sua identidade.

Depois, ganha nome, história e poderes próprios.

Limites sugeridos de dano lendário:

- leve: até 6;
- média: até 9;
- pesada: até 12.

Armas lendárias não usam o limite comum de propriedades. Cada uma possui regras próprias.

### 19.2 Armas versáteis e pesadas

A escolha de empunhar uma arma versátil com uma ou duas mãos é feita no início do turno e permanece até o próximo turno.

Escudo equipado impede normalmente o uso de arma de duas mãos.

Arma pesada usada abaixo do requisito de Força sofre Desvantagem nos ataques.

---

## 20. Armaduras, escudos e Integridade

### 20.1 Armaduras

| Armadura | Proteção | Integridade | Penalidade de Esquiva | Reduções máximas por ataque |
|---|---:|---:|---:|---:|
| Leve | 1 | 4 | 0 | 1 |
| Média | 2 | 6 | -1 | 2 |
| Pesada | 3 | 8 | -2 | 3 |

A armadura protege o corpo de forma abstrata. Ataques direcionados a uma região não ignoram automaticamente a armadura.

Depois que um golpe atinge e sua Gravidade é determinada, a Proteção reduz a gravidade automaticamente. O jogador pode gastar Integridade para reduzir categorias adicionais, respeitando o limite da armadura.

Quando chega a 0 Integridade, a armadura fica Comprometida:

- mantém sua Proteção básica;
- mantém peso e penalidades;
- não pode gastar Integridade;
- perde propriedades especiais e resistências.

### 20.2 Escudos

Escudos possuem Proteção, Integridade e propriedades próprias.

Quando um ataque Defensável atinge, o jogador escolhe usar armadura ou escudo. Os valores não são somados.

Categorias:

| Escudo | Proteção | Integridade | Requisito | Efeito adicional |
|---|---:|---:|---:|---|
| Broquel | 1 | 3 | nenhum | impacto mínimo na mobilidade |
| Comum | 2 | 5 | Força 2 | defesa intermediária |
| Pesado | 3 | 7 | Força 3 | -2 Esquiva e Desvantagem em testes de Agilidade |

Abaixo do requisito de Força, o usuário sofre Desvantagem em seus próprios ataques.

Escudos podem ter propriedades contra tipos sobrenaturais específicos ou amplos.

### 20.3 Recuperação de Integridade

Descanso curto recupera metade da Integridade máxima, arredondando para cima.

Descanso longo recupera toda a Integridade.

Reparos completos e reposição de propriedades especiais podem exigir o contexto apropriado quando a regra do item determinar.

---

## 21. Tipos de dano

### 21.1 Físicos

**Cortante:** ao causar Ferimento, aplica Sangramento. O alvo perde 1 Vitalidade ao fim do próximo turno. Não acumula.

**Perfurante:** reduz a Proteção da armadura em 1 para aquele ataque.

**Impactante:** quando a armadura protege, ela perde 1 Integridade adicional.

### 21.2 Sobrenaturais

**Ígneo:** se ao menos 1 dano atravessar as defesas, causa +2 de dano imediato.

**Gélido:** se ao menos 1 dano atravessar, o próximo ataque contra o alvo recebe Vantagem.

**Elétrico:** se ao menos 1 dano atravessar, o alvo sofre Desvantagem no próximo ataque.

**Arcano:** remove um benefício temporário mágico, sobrenatural ou originado de carta.

**Corrosivo:** quando armadura compatível é utilizada, cada redução adicional de Gravidade custa o dobro de Integridade.

**Abissal:** se ao menos 1 dano atravessar, o alvo fica Exposto. O próximo ataque ignora Resistência ou Resistência Maior, mas não Imunidade. A armadura compatível continua funcionando.

### 21.3 Resistência e vulnerabilidade

- Resistência: reduz 2;
- Resistência Maior: reduz 4;
- Vulnerabilidade: aumenta 2;
- Vulnerabilidade Maior: aumenta 4;
- Imunidade: dano zero.

Fontes iguais não acumulam. Resistência e vulnerabilidade se compensam pela intensidade.

### 21.4 Ordem da defesa

1. dano e multiplicador de Crítico;
2. Imunidade, Resistência ou Vulnerabilidade;
3. Proteção;
4. Integridade;
5. Vitalidade e Gravidade;
6. Ferimentos e efeitos secundários.

Armadura comum protege apenas dano físico. Dano sobrenatural só permite Proteção e Integridade quando o equipamento possui propriedade compatível.

---

## 22. Vitalidade e Ferimentos

Vitalidade representa a capacidade imediata de suportar o conflito.

Quando o dano ultrapassa a Vitalidade atual, o excedente é comparado aos limites de Gravidade do personagem e cria um Ferimento:

- Leve;
- Grave;
- Crítico.

### 22.1 Localização

Todo Ferimento possui uma região e uma consequência específica.

A região depende de:

- tipo de ataque;
- trajetória;
- anatomia e tamanho do atacante;
- posição relativa;
- região acessível;
- ataque direcionado.

Ataques direcionados são permitidos e sofrem penalidade de acerto. Se o ataque apenas reduz Vitalidade e não cria Ferimento, não aplica a consequência localizada.

### 22.2 Escalonamento

Se uma categoria estiver cheia, o novo Ferimento sobe para a categoria seguinte.

Ferimentos na mesma região agravam o existente:

- Leve + Leve = Grave;
- Leve + Grave = Crítico;
- Grave + Leve = Crítico;
- outras combinações seguem a mesma lógica de agravamento.

Todos os locais do corpo podem causar Ferimentos Críticos. Não existe morte automática apenas porque o Ferimento atingiu cabeça ou tronco.

---

## 23. Sangromante e custos de Vitalidade

O Sangromante pode pagar habilidades com Vitalidade e reduzir sua Vitalidade a 0.

Se estiver em 0 e ainda precisar pagar, o déficit é convertido em Ferimentos usando seus limites de Gravidade.

Armadura não protege contra esse sacrifício voluntário.

---

## 24. Última Ação, Estado Terminal e morte

Quando o último espaço de Ferimento Crítico é preenchido, o personagem realiza imediatamente sua Última Ação, mesmo fora da ordem normal.

Na Última Ação:

- recebe Vantagem extrema, representada por 3 dados mantendo o melhor resultado adequado;
- ignora as limitações físicas dos Ferimentos durante aquela ação;
- pode usar qualquer carta preparada, mesmo esgotada;
- ignora falta de Entropia ou Vitalidade;
- custos ausentes não criam novos Ferimentos;
- pode declarar Ruptura;
- a Ruptura gera Carga normalmente.

Depois da resolução, entra em Estado Terminal.

Uma habilidade comum de cura não cancela o Estado Terminal. Apenas uma habilidade específica de sobrevivência ou cura cuja Ruptura diga isso pode impedir o desfecho.

Essa Ruptura converte o último Crítico em Grave. Se os espaços Graves estiverem cheios, cria um Grave temporariamente acima do limite. Enquanto esse excesso existir, a Vitalidade não é recuperada por descansos.

### 24.1 Terminal sem ajuda

Se não existir aliado próximo e capaz de intervir, ocorre morte imediata.

Se existir alguém capaz, há até duas tentativas de estabilização. A segunda é mais difícil ou ocorre sob prazo menor. Duas falhas causam morte.

### 24.2 Estabilização

- aliado sem item: teste normal;
- kit: Vantagem;
- Médico de Campo sem kit: Vantagem;
- Médico de Campo com kit: reanimação automática e metade da Vitalidade máxima;
- poção adequada: reanimação automática e metade da Vitalidade máxima.

Tratamento improvisado retorna o personagem com 1 Vitalidade.

Tratamento adequado retorna com metade da Vitalidade máxima.

No turno seguinte, o personagem pode agir normalmente, limitado apenas pelas consequências dos Ferimentos ativos.

Não existe limite artificial de reanimações por combate. Recursos, aliados e estado da cena determinam o que é possível.

### 24.3 Consciência após o conflito

- apenas Leves: pode acordar em segurança;
- algum Grave: necessita tratamento e pode acordar durante descanso curto;
- algum Crítico: permanece inconsciente até intervenção adequada.

---

## 25. Tratamento, descanso e kits

### 25.1 Vitalidade

- descanso curto: recupera metade da Vitalidade máxima, arredondando para cima;
- descanso longo: recupera toda a Vitalidade, salvo impedimento de Ferimento ativo.

### 25.2 Ferimentos

**Leve:** removido gratuitamente em descanso curto ou após descanso longo.

**Grave:** durante descanso curto, tratamento com kit ou habilidade adequada suprime a consequência e prepara sua remoção no próximo descanso longo. Custa 1 carga.

**Crítico:** Médico de Campo com kit conta como intervenção adequada. Custa 2 cargas, suprime a consequência e permite a remoção no descanso longo. Um personagem comum com kit apenas estabiliza.

### 25.3 Kits

| Kit | Cargas máximas |
|---|---:|
| Improvisado | 1 |
| Comum | 3 |
| Reforçado | 5 |

Reanimação automática de Médico de Campo com kit consome 1 carga.

Recuperação em descanso longo:

- improvisado: +1;
- comum: +1;
- reforçado: +2.

Nunca ultrapassa o máximo. Reposição completa depende de suprimentos, compra, criação ou instalação adequada.

Cartas podem possuir custos próprios de kit.

---

## 26. Cicatrizes

Cicatriz não surge de todo Ferimento Crítico.

Ela surge obrigatoriamente quando o personagem sobrevive ao fluxo de morte: preenchimento do último Crítico, Última Ação e Estado Terminal.

A LLM cria a Cicatriz depois do conflito, com base em:

- local do Ferimento;
- arma ou criatura;
- tratamento recebido;
- contexto;
- classe;
- Memórias;
- relação com o Abismo.

Toda Cicatriz possui:

- uma consequência negativa real;
- uma habilidade positiva causalmente ligada ao trauma.

O jogador não pode recusá-la.

---

## 27. Categorias de inimigos

### 27.1 Lacaio

- usa Vitalidade simplificada;
- qualquer Ferimento o remove do combate;
- não possui Última Ação.

### 27.2 Inimigo padrão

- usa Vitalidade e Ferimentos;
- ao preencher o último Crítico, é derrotado;
- não entra em Estado Terminal, salvo regra explícita.

### 27.3 Elite e chefe

- usam o sistema completo;
- podem possuir fases, Última Ação ou sobrevivência específica.

### 27.4 NPC nomeado, inimigo nomeado e companheiro

Usam o sistema completo, independentemente de serem aliados ou adversários.

---

## 28. Informação exibida dos inimigos

O jogador vê inicialmente:

- Vitalidade atual e máxima;
- Esquiva;
- Proteção;
- Integridade atual e máxima;
- recursos visíveis;
- estados e condições;
- posição;
- Engajamentos.

Ficam ocultos até serem descobertos:

- cartas ainda não utilizadas;
- reações ainda não utilizadas;
- Virtudes;
- perfil tático;
- prioridades;
- espaços internos de Ferimentos;
- recursos não perceptíveis;
- resistências, vulnerabilidades e imunidades ainda não ativadas.

### 28.1 Cartas reveladas

Quando o inimigo utiliza uma carta, ela é mostrada integralmente e permanece revelada pelo restante do combate.

O jogador passa a conhecer:

- efeito;
- custo;
- alcance;
- frequência;
- gatilhos;
- estado de disponibilidade ou recarga.

Cartas descobertas entram no bestiário e começam reveladas em encontros futuros com o mesmo arquétipo.

Variantes podem possuir cartas exclusivas ainda ocultas.

### 28.2 Resistências e vulnerabilidades

Quando uma resistência, vulnerabilidade ou imunidade afeta uma resolução, ela é revelada, permanece visível e entra no bestiário.

### 28.3 Transparência da resolução

Toda ação já resolvida mostra sua matemática completa:

- dados;
- modificadores;
- total;
- Esquiva;
- acerto ou falha;
- Crítico ou Supercrítico;
- dano inicial;
- resistências;
- Proteção;
- Integridade;
- dano final;
- Ferimentos;
- estados aplicados.

---

## 29. Perfil tático determinístico

Cada inimigo ou NPC possui um perfil tático gerado previamente por uma LLM robusta e salvo em sua ficha.

Esse perfil traduz sua descrição e personalidade em comportamentos objetivos.

Exemplos:

- protege o mais fraco;
- não abandona o posto;
- foge quando gravemente ferido;
- persegue inimigos em fuga;
- preserva a própria vida;
- prioriza alvos feridos;
- utiliza uma reação defensiva antes de gastar recursos ofensivos;
- não ataca inocentes;
- sacrifica-se pelo grupo.

As prioridades aparecem em ordem na ficha. A primeira prioridade válida prevalece.

O perfil precisa contemplar:

- escolha de ações;
- escolha de alvos;
- uso de recursos;
- uso de reações;
- fuga;
- perseguição;
- rendição;
- restrições morais ou instintivas;
- desempates.

### 29.1 Tipos de comportamento

- **Obrigatório:** o personagem executa quando o gatilho ocorre;
- **Oferta:** apresenta uma escolha ao jogador, como aceitar um sacrifício;
- **Restrição:** impede uma ordem incompatível;
- **Autônomo:** assume o controle quando um estado específico retira o comando do jogador.

### 29.2 Resistência a ordens

- **Flexível:** pode ser contrariada normalmente;
- **Resistente:** exige lealdade ou efeito apropriado;
- **Absoluta:** nunca pode ser contrariada;
- **Autônoma:** quando ativada, executa o comportamento sem ordem.

Exemplo: um paladino com proteção de inocentes absoluta recusa assassinar um inocente.

---

## 30. Controle da party

Durante o combate, o jogador controla:

- protagonista;
- companheiros;
- ordem dos turnos da party;
- cartas;
- alvos;
- movimento;
- equipamentos;
- recursos.

O jogo valida as ordens contra os traços do companheiro.

Se uma ordem for recusada, o jogador escolhe outra ação válida.

O perfil tático só assume o turno quando o personagem não está sob controle do jogador por uma condição explícita, como medo, confusão, controle mental, inconsciência ou separação não acompanhada.

Enquanto houver alguém consciente da party no conflito, o jogador continua controlando a party, mesmo que o protagonista tenha fugido ou caído.

---

## 31. Derrota não letal e rendição

### 31.1 Golpe não letal

Quem desfere o golpe final pode escolher que ele seja não letal, desde que a forma do ataque permita.

A escolha ocorre quando o golpe derrota o alvo.

Ataques incompatíveis, como destruição completa, queda fatal ou efeitos explicitamente letais, não podem ser convertidos sem uma regra específica.

O alvo fica inconsciente ou incapacitado em vez de morrer.

### 31.2 Rendição

Inimigos podem se render deterministicamente conforme seu perfil.

Gatilhos possíveis:

- líder derrotado;
- Vitalidade muito baixa;
- aliados em número insuficiente;
- rota de fuga bloqueada;
- objetivo impossível;
- medo ou lealdade quebrada.

A rendição encerra a hostilidade daquele participante, salvo se for recusada, violada ou houver regra específica.

---

## 32. Encerramento do combate

O combate termina quando:

- um lado não possui participantes hostis ativos;
- todos os hostis fugiram;
- todos os hostis se renderam;
- o objetivo mecânico do encontro foi concluído;
- um gatilho preparado encerrou o conflito.

O combate não termina por uma interpretação livre de que os inimigos “perderam interesse”. Isso precisa estar representado pelo perfil, objetivo ou evento.

---

## 33. Fuga

Fugir custa a Ação.

Pode ser declarado mesmo estando Engajado. Nesse caso, cada inimigo Engajado e capaz realiza um ataque de oportunidade.

Se o personagem continuar capaz de agir, inicia a fuga.

Desengajar antes evita os ataques, mas normalmente exige outra oportunidade para iniciar a fuga, salvo carta específica.

A perseguição só acontece se o perseguidor decidir seguir conforme seu perfil.

Exemplos:

- predador faminto tende a perseguir;
- animal territorial pode parar na fronteira;
- guardião não abandona o posto;
- guarda pode perseguir para prender;
- mercenário ferido pode desistir;
- inimigo vingativo pode seguir mesmo em risco.

---

## 34. Perseguição

A trilha possui:

- Pressionado;
- Afastado;
- Quase Livre;
- Escapou.

Se o fugitivo recuar abaixo de Pressionado, é alcançado e o combate retorna.

Posição inicial:

| Distância ao iniciar | Estado da perseguição |
|---|---|
| Próximo | Pressionado |
| Distante | Afastado |
| Separado | Quase Livre |

### 34.1 Condutor

O protagonista sempre conduz a fuga da party.

Escolhe a abordagem e a Virtude coerente:

- Agilidade para correr e desviar;
- Mente para rotas e atalhos;
- Força para romper obstáculos;
- Corpo para resistência prolongada;
- Carisma para coordenar ou mobilizar ajuda.

A dificuldade depende do perseguidor principal.

### 34.2 Companheiros

Cada companheiro realiza um Teste de Sorte:

| 1d10 | Resultado |
|---:|---|
| 1–2 | Complicação |
| 3–8 | Neutro |
| 9–10 | Ajuda |

Ajuda e Complicação se anulam.

- saldo positivo: Vantagem;
- saldo negativo: Desvantagem;
- empate: teste normal.

Não acumulam além de uma Vantagem ou Desvantagem.

### 34.3 Abandonar companheiro

Antes do teste principal, o jogador pode deixar para trás um companheiro que tenha causado Complicação.

Isso remove a Complicação, separa o NPC da party e altera a forma como ele e outros NPCs percebem o protagonista.

O destino é resolvido por uma simulação automática completa, considerando estado, perfil, terreno, perseguidores e seed.

O resultado pode ser:

- fuga;
- captura;
- rendição;
- esconderijo;
- combate;
- morte;
- reencontro futuro.

### 34.4 Sacrifício voluntário

Um companheiro só se oferece para ficar para trás quando possui um traço que permita isso, como `se_sacrifica_pelo_grupo`, e seus gatilhos estão ativos.

A prioridade desse traço é definida na ficha.

O jogador pode aceitar ou recusar.

A percepção dos NPCs depende dos valores, da relação e do contexto; não existe penalidade automática universal.

### 34.5 Ataques na perseguição

Ataque à distância continua sendo uma Ação normal.

Ataque corpo a corpo exige reengajamento.

Quando o fugitivo está Pressionado, o perseguidor pode usar Pré-Ação para Engajar, encerrar a perseguição e atacar com sua Ação.

Em Afastado ou Quase Livre, precisa primeiro reduzir a distância ou usar uma carta específica.

---

## 35. Loot e retorno à narrativa

O fluxo de loot já existente faz parte da migração e deve ser integrado ao novo resultado de conflito, não recriado sem necessidade.

Combate, perseguição e loot são concluídos sem LLM.

Depois, a LLM recebe um resumo canônico contendo:

- participantes;
- sobreviventes;
- mortos;
- inconscientes;
- rendidos;
- fugitivos;
- capturados;
- Ferimentos;
- Cicatrizes a gerar;
- recursos gastos;
- cartas descobertas;
- resistências descobertas;
- objetos utilizados;
- mudanças permanentes no cenário;
- companheiros separados;
- decisões morais;
- fatos de relação;
- loot obtido;
- estado final da party.

A LLM continua a narrativa usando esses fatos. Ela não pode reverter ou alterar nenhum deles.

---

## 36. Critérios funcionais de pronto

O sistema está funcionalmente pronto quando:

- roleplay e exploração continuam com LLM;
- todo conflito é preparado antes de começar;
- a LLM não é chamada durante combate, perseguição ou loot;
- inimigos são selecionados do bestiário regional;
- todo NPC gerado já está pronto para combate;
- objetos interativos são criados a partir da cena;
- o jogador vê apenas as interações dos objetos, não seus efeitos ocultos;
- toda ação utiliza regras e operações reconhecidas;
- o mesmo estado, seed e decisões produzem o mesmo resultado;
- os inimigos utilizam perfis táticos salvos;
- as ordens dos companheiros respeitam seus traços;
- reações podem criar cadeias limitadas pelos participantes e recursos;
- ataques de oportunidade não usam o limite comum de reação;
- cartas inimigas são ocultas até o primeiro uso;
- conhecimento descoberto persiste no bestiário;
- fuga e perseguição são resolvidas sem LLM;
- companheiros abandonados são simulados automaticamente;
- o loot atual recebe o resultado do conflito;
- a LLM recebe apenas o resumo final;
- a narrativa não altera fatos resolvidos.
