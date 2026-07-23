# Valoria — Escopo da Migração e Fronteiras do Novo Sistema

**Objetivo deste documento:** explicar ao coding agent qual transformação está sendo realizada, sem prescrever arquitetura interna.

---

## 1. Ponto de partida

Valoria já é um jogo em funcionamento e não um projeto vazio.

O repositório atual contém sistemas ligados a:

- narrativa e Storyteller;
- roteamento de ações;
- criação e gestão de campanha;
- bestiário;
- NPCs;
- combate;
- loot;
- mundo e regiões;
- classes e personagens;
- itens;
- memória e persistência;
- eventos;
- APIs e interface;
- validação e testes.

Esse contexto deve orientar a migração. A implementação deve partir do que existe, não de um desenho hipotético isolado.

---

## 2. Transformação principal

O sistema atual utiliza LLM em partes do fluxo de combate. A migração cria uma fronteira mais rígida.

### Antes do conflito

A LLM continua ativa e pode:

- conduzir a história;
- interpretar a ação do jogador;
- decidir que a cena virou conflito;
- gerar a apresentação do encontro;
- selecionar inimigos do bestiário regional;
- incluir NPCs já existentes;
- criar as zonas e os objetos interativos;
- preparar possíveis eventos;
- fornecer o contexto necessário.

### Durante o conflito

A LLM deixa de participar.

O jogo resolve:

- iniciativa;
- turnos;
- cartas;
- ataques;
- reações;
- Ferimentos;
- armaduras;
- estados;
- comportamento inimigo;
- fuga;
- perseguição;
- eventos do Abismo;
- morte, rendição e captura;
- loot.

### Depois do conflito

A LLM recebe o resultado e retoma o mundo.

---

## 3. O que deve permanecer

A migração não deve, por princípio, substituir sistemas que já atendem ao jogo.

Devem ser avaliados para reaproveitamento:

- criação do mundo;
- conteúdo regional;
- bestiário persistente;
- criação de NPCs;
- party;
- inventário;
- classes;
- progressão;
- memória;
- loot;
- estado da campanha;
- interface atual;
- testes e ferramentas de playtest.

“Reaproveitar” não significa manter tudo sem mudança. Significa que o coding agent deve analisar impacto e compatibilidade antes de decidir reconstruir.

---

## 4. O que muda funcionalmente

### 4.1 Combate deixa de ser uma cena narrada turno a turno pela LLM

O combate passa a ser uma experiência própria, com interface de cartas, informações mecânicas, escolhas táticas e resolução direta.

A narração detalhada do mundo acontece antes e depois, não como fonte de decisão mecânica a cada turno.

### 4.2 Inimigos deixam de decidir por interpretação em tempo real

Cada arquétipo e NPC possui um perfil tático persistente, gerado previamente.

A descrição continua importante, porque ela origina o perfil. Entretanto, depois de salvo, o comportamento é executado pelas regras.

### 4.3 A cena narrativa vira uma cena jogável

A LLM passa a preparar zonas, objetos, rotas, posições e possíveis eventos a partir do que já estava acontecendo.

Isso preserva a criatividade da LLM sem permitir que ela invente vantagens ou obstáculos depois que o conflito começou.

### 4.4 NPCs deixam de ser apenas narrativos

Todo NPC gerado precisa possuir uma ficha utilizável em combate. A mesma identidade persiste caso seja encontrado novamente.

### 4.5 O bestiário torna-se também memória de conhecimento do jogador

Cartas, resistências e vulnerabilidades descobertas ficam conhecidas em encontros futuros com o mesmo arquétipo.

### 4.6 Fuga e perseguição tornam-se parte do mesmo sistema de conflito

Fugir não encerra a lógica do jogo e não devolve imediatamente o controle à LLM. Se houver perseguição, ela é resolvida primeiro.

### 4.7 Loot continua fora da LLM

O fluxo de loot existente deve receber o estado final do conflito e concluir sua resolução antes da retomada narrativa.

---

## 5. Papel da LLM na criação de conteúdo

A LLM continua sendo uma ferramenta central, mas seu papel muda conforme o momento.

### 5.1 Geração robusta e persistente

Uma LLM mais robusta pode criar previamente:

- arquétipos do bestiário;
- cartas de inimigos;
- perfis táticos;
- regras de fuga e perseguição;
- NPCs completos;
- variantes regionais;
- possíveis eventos do Abismo;
- conteúdo contextual de regiões.

Depois de criados e validados, esses elementos passam a ser conteúdo persistente.

### 5.2 Preparação contextual

A LLM da campanha monta cada encontro com base no contexto atual, utilizando o conteúdo persistido e as operações permitidas.

### 5.3 Narração posterior

A LLM recebe fatos concluídos e os transforma em prosa, diálogo, reação dos NPCs e continuidade da campanha.

---

## 6. Fronteiras obrigatórias

### 6.1 A LLM não pode durante o conflito

- escolher a ação de um inimigo;
- alterar uma rolagem;
- conceder bônus improvisados;
- adicionar um objeto;
- criar uma carta;
- criar um reforço não preparado;
- mudar o dano;
- evitar uma morte;
- reinterpretar uma falha;
- decidir loot;
- concluir uma perseguição por narrativa.

### 6.2 O sistema determinístico não deve durante o mundo narrativo

- substituir a capacidade da LLM de interpretar conversas;
- limitar o roleplay a opções fechadas;
- transformar toda exploração em combate;
- gerar automaticamente consequências narrativas complexas sem devolver o resultado à LLM;
- apagar Memórias ou relações existentes.

---

## 7. Relação entre narrativa e objetos interativos

A LLM só deve criar como interativo algo coerente com a cena.

Se a narração apresentou:

- uma alavanca;
- uma ponte instável;
- barris de óleo;
- um sino;
- uma estátua rachada;
- uma passagem estreita;

esses elementos podem ser convertidos em interações.

Ela não deve inserir, no instante da preparação, uma arma de cerco ou uma saída secreta sem qualquer base no local ou no evento.

O jogador vê as possibilidades de interação, mas não necessariamente o resultado.

---

## 8. Relação com o bestiário regional

A preparação do encontro deve respeitar a região.

A LLM seleciona criaturas:

- associadas à região;
- justificadas pelo evento;
- presentes em uma variante autorizada;
- ou explicitamente introduzidas por um acontecimento canônico.

Uma criatura fora de sua região exige uma razão do mundo, não apenas conveniência de balanceamento.

---

## 9. Relação com o nível do encontro

O Nível do Encontro nasce do local e da cena.

A party não determina o nível automaticamente.

A preparação pode escolher um encontro incidental, padrão, perigoso ou de clímax dentro do que aquela região comporta.

O jogador não recebe esse número.

---

## 10. Relação com o Abismo

O Abismo permanece uma fonte narrativa e mecânica importante.

Como não há LLM durante o conflito, as possibilidades de intervenção são preparadas antes.

A seed e o estado da cena podem carregar um evento válido quando seus gatilhos forem atendidos.

A LLM só narra depois o resultado consolidado. Durante o conflito, a assinatura visual e os efeitos já são conhecidos pelo jogo.

---

## 11. Relação com companheiros

O jogador controla a party durante o conflito, mas os companheiros mantêm personalidade.

Traços e restrições podem recusar ordens incompatíveis.

Exemplo:

- um paladino não assassina um inocente;
- um guardião não abandona seu posto;
- um covarde pode recusar um sacrifício;
- um personagem com o traço apropriado pode se oferecer para ficar para trás.

A LLM não decide isso no momento. Ela criou ou ajudou a criar o personagem anteriormente; o comportamento já está representado em sua ficha.

Depois, a LLM interpreta o impacto relacional do que ocorreu.

---

## 12. Compatibilidade com o jogo atual

O coding agent deve determinar:

- quais fluxos atuais continuam válidos;
- quais dados precisam ser convertidos;
- quais conteúdos precisam ser enriquecidos;
- quais partes podem coexistir durante a transição;
- quais comportamentos antigos precisam ser descontinuados;
- como manter campanhas e personagens já salvos;
- como preservar o loot e a persistência existentes;
- como aproveitar testes atuais.

Este documento não determina a resposta. A resposta deve vir da análise do repositório.

---

## 13. Estratégia funcional de migração

A decomposição em specs deve, no mínimo, cobrir estes blocos funcionais:

1. preparação de encontro;
2. cena congelada;
3. participantes e informações visíveis;
4. turnos e iniciativa;
5. cartas e recursos;
6. ataques, testes e críticos;
7. reações e ataques de oportunidade;
8. posições, zonas e objetos;
9. armadura, dano e Ferimentos;
10. comportamento tático;
11. controle e restrições de companheiros;
12. Abismo durante conflitos;
13. fuga e perseguição;
14. morte, rendição e captura;
15. conhecimento do bestiário;
16. integração com loot;
17. resumo final e retomada narrativa;
18. compatibilidade e migração do estado atual.

A ordem e a forma de implementação devem ser propostas pelo harness.

---

## 14. Fora de escopo deste handoff

Este pacote não define:

- nomes de arquivos;
- classes ou módulos;
- frameworks;
- padrões internos;
- banco de dados;
- mensagens de fila;
- endpoints;
- linguagem de programação;
- estrutura de diretórios;
- estratégia exata de persistência;
- bibliotecas;
- como dividir serviços;
- quais componentes atuais serão removidos.

Também não exige que o projeto seja reescrito do zero.

---

## 15. Resultado esperado da análise do coding agent

Antes de implementar, o coding agent deve produzir:

- mapa funcional do que já existe;
- diferenças entre o sistema atual e o sistema desejado;
- sistemas que serão preservados;
- sistemas que precisarão ser adaptados;
- riscos de compatibilidade;
- estratégia para campanhas e conteúdos existentes;
- sequência de specs pequenas;
- critérios de aceite associados às regras deste pacote.

A análise deve respeitar a direção funcional sem assumir que os documentos conhecem melhor a arquitetura do que o próprio repositório.
