# Decisões de produto — acordadas na conversa

## Visão
Chat-first RPG. A narrativa inteira — abertura, diálogos, ameaças, início/fim de combate, consequências — é vivida no chat. Outras telas são superfícies de jogo e consulta, não substitutas do chat. O produto deve parecer vivo e responsivo, não um conjunto de painéis espremidos ou um chat maquiado.

## Hierarquia de telas
Desktop: só CHAT ou só UMA aba contextual, ou CHAT + UMA aba contextual (default ~50/50 e resize; ambas full-screen). Abas: Codex, Personagem, Combate (deck/preparação também fora de encontro), Bestiário, Mapa. Navegação simples tipo navegador. Nunca abrir HUD/combat/third panel como terceira coluna concorrente. O chat mantém draft e histórico entre trocas. Mobile: uma tela por vez, fase posterior.

## Combate
Encontro começa e termina pelo chat. Interface tática inspirada em card battlers, sem copiar estética ou regras. Ações diretas; carta alvo dirigida -> seleciona e clica o alvo, executa; ação sem alvo -> um clique. Feedback claro de custo real, alvo/alcance/zona, turnos, inimigos, passivas, reações, recursos, estado/resultados. Sem confirmações repetitivas. Inimigos e NPCs não mudam identidade ou desaparecem por confusão com fauna/cena. O chat recebe desfecho; UI recebe XP e números.

## Narrador/NPC
Roteamento automático por linguagem natural e contexto. Não exigir botão seletor de 'Narrador/NPC'. Pergunta AO narrador sobre um NPC não vira fala daquele NPC. Voz/Whisper transcreve para composer editável, usuário confirma envio normalmente; SPEC-186/187 já implementadas no repo consultado.

## Codex, bestiário e imagens
Dossiês vivos, não chatlogs acumulados. Distinguir fato, suspeita, rumor, percepção e visibilidade do jogador. Relação com NPC e o que NPC parece saber sem abrir secrets privados. Arte do personagem, NPCs, mapas, criaturas e cartas por ID canônico, se efetivamente gerada e permitida ao jogador.

## Visual
Agente escolhe identidade/motion com liberdade e responsabilidade técnica. Duas tarefas diferentes: **1 diagnosticar/mapear pontos de efeito; 2 implementar padrões aprovados na spec**. Hover, pressionar, seleção, transição, carta, impacto, revelação, feedback; sem efeito decorativo em todos controles. Protótipos anexos são inspiração, não pixel-perfect.

## Ordem
P1 beta desktop jogável/front/cartas → P2 latência e custo (medir antes de otimizar) → P3 consistência profunda de memórias/segredos. Instrumentação e exportação de beta atravessam P1, sem auditor automático.

## Memória e latência
Visão de cache/RAM/HD é hipótese arquitetural a testar: pequeno estado ativo da cena; contexto relevante de interlocutor/local; história longa no archivist/RAG. Fatos canônicos persistem imediatamente; Codex/Bestiário/sumários podem projetar em segundo plano com consistência eventual. Não adicionar 'classificador Jev' automaticamente: SPEC-180 terminou NO_GO; avaliar só depois de medir TTFT/TTLT e custo.

## Auditoria beta
Capturar fluxos e causas; exportar sessões sob demanda, incluindo transcritos e estado com controles de privacidade, entregando pasta ao Codex/Claude para auditoria com créditos do usuário. Nada de auditor automático pago, nada de replay humano como produto principal. Auditor aponta segredos vazados, incoerências, balanceamento, falhas de UX, evidência por turno e novos evals candidatos.

## Não decidido / delegação
Easing, paleta final, bibliotecas de animação, detalhes de cartas, prototipação e arquitetura específica serão decididos pelo coding agent com evidências e dentro das decisões fechadas. Questões de mudança substantiva de gameplay, custo permanente ou vazamento de informação voltam ao dono do produto.
