# SPEC-181 — Shell de RPG, navegação por áreas e direção audiovisual

> **Status:** `draft` · **Criada:** 2026-10-12 · **Prioridade:** P1 (principal frontend)  
> **Depende de:** SPEC-180 `done` · **Não altera:** mecânica de mundo, balanceamento ou contratos canônicos.

## 1. Contexto & objetivo

O app hoje é uma `PlayScreen` de diário com HUD de oito abas em uma coluna de 360px. A linguagem visual apresenta texturas, ornamentos e partículas, mas não delimita os diferentes *lugares do jogo*: exploração, conversas, mapa, inventário, preparação de personagem e combate. O alvo é um **game shell** com navegação persistente, cenas próprias e efeitos significativos, e não mais um chat decorado.

## 2. Requisitos

- **R1:** criar shell com navegação reconhecível: **Jornada**, **Pessoas**, **Inventário/Ficha**, **Mapa**, **Missões**, **Crônica/Códice**. Área de combate é um modo contextual, não uma aba permanente competindo com exploração. Indicadores de localização, relógio, condições e objetivo ativo permanecem estáveis.
- **R2:** jornada apresenta cena/arte, trecho narrativo organizado por capítulos/turnos, ação contextual, interlocutor em cena e pistas de continuidade. Texto livre continua ferramenta de agência, não principal elemento visual.
- **R3:** Pessoas abre dossiê completo da SPEC-178; Mapa abre interface cartográfica central; Inventário/Ficha mostra cartas, passivas, equipamento e progressão; Missões mostra objetivo claro. Não colocar os oito modos como pequenas tabs de um painel lateral de 360px.
- **R4:** definir design tokens semânticos para superfície, camadas, estados interativos, risco, recurso, foco e texto. Reduzir ornamento repetido/glow decorativo; aumentar hierarquia por escala, contraste, composição e espaço vazio. Manter identidade de dark fantasy/Valoria.
- **R5:** sistema de motion baseado em eventos: transição de modo (250–450ms), entrada de NPC, entrada de combate, hit, reação, ferimento, derrota, vitória. Animações não bloqueiam input nem sincronização do estado; há fallback completo para reduced motion.
- **R6:** implementar navegação responsiva: rail ou menu persistente em desktop, bottom/tab navigation e painéis focados no mobile. Scroll por área independente, sem roubo de foco por modais, sem overflow horizontal.
- **R7:** áudio ambiental/feedback é opcional, por padrão respeita configuração do usuário e nunca toca automaticamente antes de interação explícita quando restrito pelo navegador. Nada depende de áudio para ser compreendido.

## 3. Design técnico

Arquivos novos: `web/src/layouts/GameShell.tsx`, `GameNavigation.tsx`, `ScenePanel.tsx`, `AreaView.tsx`, `uiTokens.ts` ou CSS tokens, `useGameMode.ts`; componentes em `web/src/components/` reaproveitados. `web/src/App.tsx` mantém bootstrap/auth/saves/operações; GameShell controla visualização mas **não** altera save. `styles.css` segmentado em módulos por área, sem regressões globais. `motion/react` já instalado e `prefers-reduced-motion` já existe, evoluir em vez de instalar framework novo.

## 4. Etapas (testes primeiro)

1. Fixture de navegação Jornada→Pessoas→Mapa→Ficha→Jornada preserva ação em curso, scroll/foco e não cria turno.
2. Implementar shell e tokens + migrar cada aba; comparar screenshots sob ambiente pinado.
3. Configurar motion no inventário de eventos e fallback reduced-motion.
4. Executar F01–F24 e snapshots opt-in nos viewports estabelecidos.

## 5. Aceite

- [ ] Áreas distintas legíveis sem depender de input de chat; no desktop, navegação principal sempre reconhecível.
- [ ] Mobile 320/390 utilizável com teclado/toque; nenhum overlay tapa ação principal.
- [ ] Elementos decorativos reduzidos e hierarquia validada por revisão humana com checklist, não por pontuação subjetiva automatizada como hard gate.
- [ ] `prefers-reduced-motion` remove transições fortes, sem perda de estado.
- [ ] Browser/a11y/performance e build verdes.

## 6. Riscos

UI refactor grande pode alterar foco, scroll e histórico. Migrar uma área de cada vez; registrar visual snapshots dos estados, mas não snapshotar texto variável de LLM.
