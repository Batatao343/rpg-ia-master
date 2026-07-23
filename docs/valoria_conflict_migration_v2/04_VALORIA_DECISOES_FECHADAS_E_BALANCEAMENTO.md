# Valoria — Decisões Fechadas e Parâmetros de Balanceamento

Este documento serve como referência rápida durante a decomposição em specs.

---

## 1. Decisões fechadas

As decisões abaixo não devem ser reabertas sem solicitação explícita do responsável pelo produto.

### Fronteira entre LLM e conflito

- roleplay, exploração e investigação continuam com LLM;
- a LLM prepara o encontro antes;
- não existe LLM durante combate, perseguição e loot;
- a LLM recebe um resumo depois;
- o resultado mecânico não pode ser reescrito pela narrativa.

### Projeto atual

- a migração deve considerar o código existente;
- não se presume reconstrução total;
- o harness decide como reaproveitar e migrar;
- o loot atual deve ser integrado;
- mundo, bestiário, NPCs, party, progressão, memória e persistência devem ser preservados quando compatíveis.

### Conteúdo

- bestiário é gerado previamente por LLM robusta;
- criaturas são vinculadas a regiões;
- encontros selecionam criaturas existentes do bestiário;
- todo NPC criado já nasce pronto para combate;
- perfil tático é gerado uma vez e persistido;
- a LLM gera zonas, objetos, interações, obstáculos e eventos com base na cena;
- efeitos mecânicos utilizam catálogo fechado;
- valores gerados pela LLM usam categorias de potência, não números livres;
- falhas utilizam fallback entre providers.

### Mundo e dificuldade

- perigo é absoluto;
- não existe escalonamento automático pela party;
- nível exato não é mostrado;
- o jogador pode entrar em região mortal e morrer.

### Representação do combate

- não há grid;
- existem zonas internas;
- distância usa Próximo, Distante e Separado;
- postura usa Protegido, Neutro e Exposto;
- ocultação usa Visível e Escondido;
- Engajamento é separado.

### Objetos

- objetos são gerados pela LLM a partir do contexto;
- o jogador vê interações e custos;
- efeitos não são mostrados automaticamente;
- objetos secretos exigem descoberta.

### Turnos e iniciativa

- turno possui Pré-Ação, Ação e Pós-Ação;
- iniciativa é por lados;
- quem iniciou claramente age primeiro automaticamente;
- caso contrário, 2d10 + maior Agilidade do lado;
- jogador escolhe a ordem da party a cada rodada.

### Testes e ataques

- ataque usa 2d10 + Virtude contra Esquiva;
- Vantagem usa 3d10 mantendo os dois maiores;
- Desvantagem usa 3d10 mantendo os dois menores;
- duplas de 1 a 9 são Crítico automático;
- dupla de 10 é Supercrítico automático;
- Crítico multiplica efeito principal por 2;
- Supercrítico multiplica por 3;
- testes gerais usam Ímpeto e Presságio.

### Cartas

- classes e subclasses continuam;
- preparação e Acervo continuam;
- 4/5/6/7 espaços preparados por faixa de nível;
- nível 1 começa com seis cartas conhecidas e quatro preparadas;
- evolução em Caminho A ou B a partir do nível 4;
- frequência é individual;
- Cartas de Virtude são duas, permanentes e fora da preparação.

### Ruptura e Abismo

- Ruptura é declarada antes da rolagem;
- gera uma Carga mesmo na falha;
- a Carga não afeta a própria Ruptura;
- não há limite geral de Ruptura por cena;
- Cargas persistem e ficam visíveis;
- Abismo é impessoal;
- não cria algo do nada;
- eventos possíveis são preparados antes do combate;
- eventos podem ser carregados durante o conflito sem LLM.

### Reações

- cartas podem ser Reações;
- jogador, companheiros e inimigos podem reagir;
- inimigo pode reagir se possuir gatilho e Entropia;
- reações podem responder a reações;
- cada personagem usa no máximo uma reação comum por cadeia;
- ataques de oportunidade não obedecem esse limite;
- todos os Engajados aptos podem realizar ataque de oportunidade.

### Movimento e ocultação

- corpo a corpo exige Próximo e Engajado;
- Engajar custa Pré ou Pós;
- Desengajar custa Ação;
- Fugir pode ser feito Engajado, sofrendo oportunidades;
- Guardar é universal e custa Ação;
- Esconder-se custa Ação;
- ocultação é relativa por observador;
- posição aproximada permite ataque com Desvantagem;
- acertar alvo oculto não o revela;
- Procurar revela apenas para quem encontrou;
- alertar toda a party custa Pré ou Pós;
- mudar distância ou ser reposicionado remove Escondido;
- atacar oculto concede Vantagem e revela depois.

### Vitalidade, Ferimentos e morte

- Vitalidade e Ferimentos são separados;
- Corpo define Vitalidade e espaços;
- Ferimentos são localizados;
- mesma região agrava;
- categoria cheia escala para a seguinte;
- último Crítico aciona Última Ação;
- depois ocorre Estado Terminal;
- sem aliado capaz, morte imediata;
- até duas tentativas de estabilização;
- Médico com kit e poção reanimam automaticamente;
- não existe limite artificial de reanimações;
- sobreviver ao fluxo de morte gera Cicatriz obrigatória.

### Armadura e dano

- armadura atua depois do acerto;
- Proteção reduz Gravidade;
- Integridade pode reduzir categorias adicionais;
- em 0, fica Comprometida;
- armadura e escudo não somam;
- dano físico: Cortante, Perfurante, Impactante;
- dano sobrenatural: Ígneo, Gélido, Elétrico, Arcano, Corrosivo, Abissal;
- armadura comum não protege sobrenatural sem propriedade compatível.

### Inimigos e informação

- Lacaio, Padrão, Elite/Chefe e Nomeado possuem graus diferentes de complexidade;
- NPC nomeado e inimigo nomeado usam sistema completo;
- jogador vê Vitalidade, Esquiva, Proteção, Integridade, recursos visíveis, estados, posição e Engajamentos;
- cartas ficam ocultas até o uso;
- carta usada permanece revelada;
- conhecimento persiste no bestiário;
- resistências são reveladas quando afetam a resolução;
- cálculos resolvidos são totalmente transparentes.

### Perfis e companheiros

- inimigos usam perfil tático persistido;
- prioridades são ordenadas;
- o primeiro comportamento válido prevalece;
- existem comportamentos Obrigatórios, Ofertas, Restrições e Autônomos;
- resistências a ordens podem ser Flexíveis, Resistentes, Absolutas ou Autônomas;
- jogador controla a party;
- ordem recusada retorna a escolha ao jogador;
- jogador mantém controle enquanto houver alguém consciente.

### Derrota e encerramento

- quem desfere o golpe final pode escolher não matar quando for coerente;
- inimigos podem se render pelo perfil;
- combate termina por derrota, fuga, rendição, objetivo ou gatilho previsto.

### Fuga e perseguição

- Fugir custa Ação;
- perseguição depende da personalidade do perseguidor;
- trilha: Pressionado, Afastado, Quase Livre, Escapou;
- protagonista sempre conduz a fuga;
- companheiros fazem 1d10 de Sorte;
- 1–2 Complicação, 3–8 Neutro, 9–10 Ajuda;
- saldo concede Vantagem ou Desvantagem;
- companheiro pode ser abandonado para remover sua Complicação;
- isso altera relações;
- destino é resolvido por simulação automática;
- sacrifício voluntário exige traço na ficha;
- ataque à distância continua sendo Ação;
- corpo a corpo exige reengajamento.

---

## 2. Parâmetros de balanceamento

Os itens abaixo podem ser ajustados por configuração e playtest sem reabrir a arquitetura.

- valores exatos de dano de algumas cartas;
- custos de Entropia;
- frequência de cartas;
- duração de estados específicos;
- valores das categorias Fraco, Moderado, Forte e Devastador por nível;
- composição de encontros por região;
- quantidade e força de reforços;
- chance e prioridade de eventos do Abismo;
- dificuldade exata da segunda estabilização;
- penalidade exata de ataques direcionados;
- propriedades individuais de armas e armaduras;
- cartas específicas de classes, subclasses e inimigos;
- limites e gatilhos particulares de perfis táticos;
- requisitos de algumas interações de cenário;
- efeitos específicos de Cicatrizes;
- limites de dano de armas lendárias, caso playtests indiquem ajuste.

---

## 3. Pontos que devem virar specs, não novas decisões de design

O coding agent deve resolver tecnicamente, a partir do projeto atual:

- como representar e persistir as novas regras;
- como migrar personagens, NPCs e bestiário existentes;
- como adaptar o combate atual;
- como integrar o loot existente;
- como preservar campanhas salvas;
- como validar preparações da LLM;
- como alternar providers;
- como registrar e reproduzir conflitos;
- como manter informações ocultas;
- como expor a nova experiência na interface;
- como testar e liberar a migração por etapas.

Esses itens não são dúvidas de gameplay. São decisões de implementação do harness.
