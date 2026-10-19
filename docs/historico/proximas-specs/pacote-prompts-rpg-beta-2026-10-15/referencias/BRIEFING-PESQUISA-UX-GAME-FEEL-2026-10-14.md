# Briefing de pesquisa para o coding agent — UX de RPG chat-first, combate de cartas e game feel

**Data:** 14/10/2026  
**Status:** Pesquisa e diretrizes de produto; **NÃO é uma SPEC aprovada**. O coding agent deve ler o repositório, inspecionar os contratos de backend e escrever a(s) spec(s) segundo as convenções existentes.  
**Referência navegável:** `rpg-combate-experiencia-v03.html` (protótipo isolado, valores de exemplo não canônicos).

## 1. Restrições fechadas pelo dono do produto

1. A narrativa acontece no **chat**, inclusive o disparo e a conclusão dos combates; um painel tático não substitui a história.
2. Desktop: **chat + exatamente um contexto**, inicialmente por volta de 50/50, com cada lado expansível para tela cheia. Nunca chat + combate + terceiro HUD simultâneo.
3. Contextos consultáveis por abas: **Codex, Personagem, Combate, Bestiário e Mapa**. O jogador pode consultar combate fora dele para organizar cartas e habilidades.
4. Mobile: **uma tela por vez**. Priorizar a versão desktop nesta onda.
5. Interlocutor do chat (narrador/NPC): **inferência contextual automática**, não um seletor obrigatório.
6. Ações precisam dar feedback visual vivo e intencional, não acumular efeitos decorativos. A identidade artística final fica a cargo da investigação de UX/implementação do coding agent, com o HTML como referência comportamental, não tema rígido.
7. Reduzir **etapas e confirmações artificiais no produto**, e também **checkpoints desnecessários de aprovação** com o dono do jogo. Só pedir decisões que alteram o produto substancialmente.
8. Primeira prioridade: **beta desktop jogável, frontend legível e combate por cartas**. Segunda: latência. Terceira: consistência histórica aprofundada, mantendo invariantes essenciais desde já.

## 2. Pesquisa externa: achados com nível de evidência

### A. Slay the Spire — UX de interação (fonte de análise de estúdio, 2018)

https://www.cloudfallstudios.com/blog/2018/2/20/flash-thoughts-slay-the-spires-ui

- Cartas precisam se comportar como objetos físicos fáceis de lançar: pequenos rastros de compra/descarte, alvo com **área de clique generosa**, e animação não bloqueante.
- **Aplicação ao RPG:** ao escolher carta direcionada, destacar alvos permitidos; clique no inimigo executa sem segundo botão de confirmar. Carta sem alvo pode executar diretamente. Permitir cancelar mira com Esc. Mostrar custo, dano, alcance e restrições antes de agir.

### B. Mega Crit — intenções inimigas como informação estratégica (fala de desenvolvedores)

https://arstechnica.com/video/watch/war-stories-slay-the-spire-war-stories/?c=series  
https://podscripts.co/podcasts/think-like-a-game-designer/anthony-giovannetti-crafting-slay-the-spire-nurturing-team-dynamics-balancing-life-and-launches-and-embracing-the-magic-of-mods-59

- Os criadores relatam que decisões pareciam arbitrárias antes de sinalizar intenções dos inimigos.
- **Aplicação:** exibir *intenção perceptível*, não informação onisciente. Ex.: 'prepara investida', 'mira o arqueiro' quando observado; 'intenção desconhecida' caso contrário. Respeitar segredos, percepção e regras canônicas. Não revelar planos privados automaticamente.

### C. Mega Crit — animação e nitidez, sob controle do tempo de jogo (fonte primária)

https://megacrit.com/news/2024-10-02-neowsletter-issue-2/

- O estúdio enfatiza UX rápida, maior vivacidade das transições e visual mais nítido.
- **Aplicação:** animações de resposta devem iniciar imediatamente, ser curtas e não atrasar a próxima ação nem bloquear o fluxo de chat.

### D. Balatro — estética é resultado da coesão de interações (entrevista com o criador)

https://www.gameinformer.com/interview/2024/03/21/balatro-was-almost-called-joker-poker-and-other-details-from-its-creator

- O criador descreve a construção iterativa e coesa de CRT, cartões, fundos e shader, em vez de uma lista arbitrária de efeitos.
- **Aplicação:** construir vocabulário de movimento próprio: **hover/seleção**, **compromisso**, **impacto**, **consequência**, **mudança de contexto**; não implantar toda biblioteca de efeitos em toda tela.

### E. Pesquisa acadêmica: game feel — física percebida, amplificação, simplificação

https://arxiv.org/abs/2011.09201

- Survey de mais de 200 fontes distingue ajustar sensação física (*tuning*), amplificar o significado do evento (*juicing*) e remover atrito na execução da intenção (*streamlining*).
- **Aplicação:** primeiro corrigir hitboxes e escolhas, depois adicionar resposta tátil visual, depois atmosfera. O polimento que não aumenta clareza/expressão tem prioridade baixa.

### F. Reddit — observações qualitativas, não regra universal

https://www.reddit.com/r/IndieDev/comments/1sa2nfr/how_do_you_improvethink_about_game_feel/  
https://www.reddit.com/r/IndieDev/comments/1i5akvt/  
https://www.reddit.com/r/slaythespire/comments/1rpuzot/mouse_card_controls_horrible/  
https://www.reddit.com/r/slaythespire/comments/1x45uhb/what_is_happening_here_targeting_issue_after/

- Jogadores e devs propõem **preview visual do destino**, setas/linhas de alvo e feedback que comunique causalidade.
- Comentários mostram que **screenshake excessivo** gera desconforto; reclamações de alvo difícil e cartões que 'não pegam' reforçam a importância de hitboxes amplas em resoluções variadas.
- **Aplicação:** efeito proporcional à magnitude do evento; shake pontual opcional somente em grandes impactos; alvo fácil de acertar; suporte a click-to-target, com drag-and-drop apenas se for confiável e não obrigatório.

### G. Palestras em vídeo no YouTube / GDC

- **Juice It or Lose It**, Martin Jonasson & Petri Purho: https://www.youtube.com/watch?v=Fy0aCDmgnxg ; registro institucional: https://gdcvault.com/play/1016789/Juice-It-or-Lose
- **Secrets of Game Feel and Juice**, Game Maker's Toolkit: https://www.youtube.com/watch?v=216_5nu4aVQ
- **The Art of Screenshake**, Jan Willem Nijman: https://www.youtube.com/watch?v=AJdEqssNZ-U
- **Slay the Spire: Metrics Driven Design and Balance**, GDC: https://www.gdcvault.com/play/1025731/-Slay-the-Spire-Metrics

**Limite de verificação:** são referências verificadas por registros, descrições e menções acadêmicas; isto **não** equivale a ter assistido a cada vídeo integralmente.

### H. Acessibilidade de movimento

https://developer.mozilla.org/en-US/docs/Web/CSS/Reference/At-rules/%40media/prefers-reduced-motion

- Respeitar a preferência do sistema `prefers-reduced-motion`; efeitos informativos devem ter equivalente textual/visual estático. Não tornar animação pré-requisito mecânico.

### I. X / TikTok / 'Escola'

- X: existe material público de exploração de microanimações, mas não se verificou postagem especializada diretamente relevante com evidência tão forte quanto as fontes acima; não basear decisão mecânica em post isolado. Exemplo de exploração de movimento com propósito: https://x.com/MarceloDesignX/status/2010827847435157833
- TikTok: resultados diretos de criadores ficaram bloqueados à ferramenta de pesquisa; **não inventar clipes nem alegar análise de vídeos que não foram abertos**.
- 'Escola': a referência nominal mencionada na conversa não foi identificada de modo inequívoco; se o dono encaminhar URL específico, adicioná-lo à bibliografia, sem atrasar o trabalho atual.

## 3. Diretrizes propostas para o combate (codificação pelo agente)

- Combate nasce da narrativa, e seu encerramento produz desfecho narrativo; nunca permanecer no estado tático após acabar o encontro.
- Se a ação requer alvo: clicar ação/carta **arma**; o inimigo válido fica destacado; clicar alvo **executa** imediatamente. `Esc` cancela. Se uma ação não precisa de alvo, um clique executa. Confirmação excepcional somente para ação especialmente irreversível, justificada na spec.
- HUD tático sempre indica: turno/rodada, vitalidade, efeitos relevantes, posições, alvos válidos, intenção *observável* do inimigo, Entropia, cartas, ataques básicos, custo e consequências de curto prazo.
- Passivas são **visíveis como estados e gatilhos**, não falsas cartas ativas; reações só surgem quando podem ser usadas.
- Animações devem priorizar *feedback de comando* (hover, focus, press) → *estado preparado* (card lift, alvo destacado) → *execução* (trajeto e impacto) → *resultado* (dano, condição, morte, texto no chat). Não bloquear input pela duração estética.
- Não inventar números ou regras. A demonstração HTML inclui dano de ações básicas e cartas conceituais que **não são dados canônicos**.
- Cada ação enviada ao backend deve ser idempotente, evitando dano duplicado e turnos duplicados após demora, retry ou timeout.

## 4. Critérios mínimos que a spec deve formalizar

1. Rodar vertical slice: exploração no chat → ameaça → combate → múltiplas cartas/ações → reação/ferimento → vitória/retirada → história retomada, sem um terceiro painel.
2. Testar cartas diretas e miradas, cancelamento de mira, mouse/teclado, carta sem alvo, alvo morto, Entropia insuficiente e resize da janela.
3. Tempo de feedback de **interface** deve ser imediato e independente da chamada ao modelo; marcar visualmente ação pendente, resolvida ou falha sem aplicar estado otimista irreversível incorretamente.
4. Entradas de batalha e finalização têm transições visuais compreensíveis, não causam perda do contexto do chat e não imprimem XP como fala do narrador.
5. Respeitar movimento reduzido, contraste e foco do teclado; nenhuma animação impede informação essencial.
6. Playtests objetivos e coleta de taxas de cliques falhos/cancelamentos, duração de ação, latência percebida, erros de seleção e travas de fim de combate. A instrumentação deve ser barata e apropriada à beta.
7. Evals determinísticos devem ser concebidos e congelados **antes da implementação**, seguindo as normas do repositório. Não alterar avaliador congelado para fazê-lo passar.

## 5. Organização de futuras specs (não redigir diretamente sem auditoria do código)

**Primeira spec:** diagnóstico UX e matriz de oportunidades de animação e redução de atrito em telas atuais, amarradas a eventos e critérios testáveis; inventariar quais elementos ficam em chat, Codex, Personagem, Combate, Bestiário e Mapa.  
**Segunda spec:** design system HTML de referência com estados interativos, tokens, transições e acessibilidade; refletir layout desktop chat+um painel.  
**Terceira spec:** interface tática integrada de combate e vertical slice jogável com contrato real, evitando novas regras.  
**Quarta spec:** regressão/evals, métricas e polish para beta desktop.  
**Ordem interna recomendada:** criar tarefas de avaliação congelada antes da implementação de cada entrega; interface e combate têm prioridade sobre exploração de otimização com JEV ou reconstrução completa de memória.

**Handoff solicitado ao coding agent:** confirme o que já existe no repositório; evite duplicar specs ou mudar contrato sem necessidade; identifique diferenças entre protótipo e mecânicas canônicas; escreva specs curtas, independentes, com decisões explícitas, riscos e critérios de aceite reproduzíveis. Não implementar conteúdo fora de escopo no mesmo PR.
