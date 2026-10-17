# SPEC-208 — Design system de efeitos: implementação por iterações verticais

> **Status:** `done`
> **Criada:** 2026-10-15 · **Atualizada:** 2026-10-16
> **Depende de:** SPEC-201 `done` (matriz de efeitos), SPEC-204 `done` (shell), SPEC-205 `done` (gesto) (ordem final 2026-10-15)
> **Desbloqueia:** SPEC-209, SPEC-210, SPEC-211 (ordem final 2026-10-15)
> **Origem:** pacote `proximas-specs/pacote-prompts-rpg-beta-2026-10-15/`, prompt 05
> **EXECUTOR_MODEL:** `Terra` (≡ Sonnet, ver docs/planos/equivalencia-modelos-claude.md)
> **REVIEW_MODEL:** `Sol` (≡ Opus em contexto separado) · **REVIEW_REQUIRED:** `false`
> **EVAL_AUTHORING_REQUIRED:** `false` — verificação por Playwright/axe determinísticos já existentes em `web/e2e/`; nenhum eval protegido novo. Se SPEC-201 exigir métrica de cliques falhos/cancelamentos como eval, é handoff separado.

Legenda: **[F]** fato observado no source · **[D]** decisão de produto fechada · **[H]** hipótese técnica · **[R]** recomendação.

---

## 1. Contexto & Objetivo

**[D]** Duas tarefas distintas: (1) diagnosticar/mapear (SPEC-201) e (2) implementar padrões aprovados (esta). Hover, pressionar, seleção, transição, carta, impacto, revelação e feedback existem **onde servem à jogada**; sem efeito decorativo em todos os controles. O agente tem liberdade de easing/paleta/biblioteca, com responsabilidade técnica e evidência.

**[F] Estado atual do front (`web/`)**
- `motion` `^12.42.0` (instalado 12.42.0) é a única lib de animação; usos: `App.tsx`, `StoryLog.tsx`, `SceneArtwork.tsx`, `DeathModal.tsx`, `LevelUpModal.tsx`. Nenhum `layoutId`/`layout` em uso. Sem GSAP/WebGL.
- `App.tsx:697` `<MotionConfig reducedMotion="user">`; `styles.css` ~l.825 bloco global `@media (prefers-reduced-motion: reduce)` (`animation: none`, `transition-duration: 0.01ms`, `.ember-canvas {display:none}`). `EmberField.tsx` é canvas 2D decorativo, desligado em reduced-motion.
- Tokens em `:root` de `web/src/styles.css`: cores OKLCH (`--bg`, `--surface`, `--line`, `--ink`, `--accent`, `--accent-glow`, `--danger`, `--danger-bright`, `--mana`, `--stamina`), raios (`--r-sm/md/pill`), `--shadow-deep`, um único easing `--ease: cubic-bezier(0.16,1,0.3,1)`, z-index (`--z-hud/banner/overlay`). **Não há tokens de duração, elevação em degraus nem estados de interação.** Durações são literais espalhadas (0.12s, 0.3s, 0.45s, 0.55s…; ~44 ocorrências de `transition/animation/ease`).
- Interação mínima: `.btn:active` (`translateY(1px) scale(0.99)`), `.btn--primary:hover`, `:focus-visible` global (outline 2px accent). Hover de cartas/abas/escolhas de raça-classe é praticamente inexistente.
- **[F] Bundle atual medido (web/dist, HEAD 6b94f66, 2026-10-15):** `index-CUkFp7vO.js` 408 505 B (≈129 KB gzip), `index-By4ttJGn.css` 61 669 B (≈13 KB gzip), chunks menores `index-B4ESVPSx.js` 8 674 B, `web-BdihnjUL.js` 870 B. Total JS+CSS bruto ≈ 480 KB. A Etapa 0 **remede** (a SPEC-204/205 alteram o número).
- **[F] `web/playwright.config.ts` define `reducedMotion: "reduce"` por padrão** e `projects: [{name:"chromium"}]` somente. Logo, testes de movimento exigem um projeto/contexto com `reducedMotion: "no-preference"`; os demais continuam em `reduce`.
- E2E existentes: `web/e2e/{critical-journeys,visual-surfaces,voice-input,image-quote,...}.spec.ts` + `fixtures.ts`; `@axe-core/playwright` já é devDependency.

**Objetivo:** transformar a matriz aprovada da SPEC-201 em (a) **tokens** de motion/cor/elevação no design system (CSS custom properties) + (b) **um wrapper fino sobre `motion`** e (c) efeitos entregues em **iterações verticais** pelo caminho do beta, cada um com contrato completo (§3.3), orçamento de bundle/frame e testes. O foco é corrigir uso (affordance, alvo, seleção), depois transição, depois revelação; atmosfera por último e só se sobrar orçamento.

**[H]** `motion` + CSS (transform/opacity) cobre todo o catálogo P0/P1 do arsenal-base; GSAP, shaders, WebGL e partículas novas não são necessários. **[D7 do brief]** O arsenal do pacote (`referencias/ARSENAL_VISUAL.md`) é **referência provisória**, não a seleção original do dono (`PENDENCIA_ARSENAL_ORIGINAL.md`); quando a seleção original for recuperada, a matriz da SPEC-201 é atualizada primeiro e esta spec apenas consome os itens aprovados (sem duplicar efeitos).

## 2. Requisitos

- **R1 — Pré-condição bloqueante.** A implementação só inicia com SPEC-201 `approved`, SPEC-204 e SPEC-205 `done`. Cada efeito implementado referencia o ID da linha na matriz da SPEC-201 (`matrix_ref`); efeito sem `matrix_ref` é rejeitado na revisão. Teste de lint: `web/src/design/effects.registry.ts` falha se alguma entrada não tiver todos os campos de §3.3.
- **R2 — Tokens.** Acrescentar a `:root` (sem renomear tokens existentes): durações `--dur-instant/fast/base/slow`, easings `--ease-out` (alias do `--ease` atual), `--ease-in-out`, `--ease-spring-soft`, elevação `--elev-0..3`, estados `--state-hover/pressed/selected/armed/disabled` (derivados de `--accent`/`--line` por `color-mix`/oklch), foco `--focus-ring`. Valores numéricos finais são decididos na Etapa 1 **com medição** e registrados em `docs/spec208/README.md`; a spec fixa apenas a faixa de partida **[H]**: instant ≤ 80 ms, fast 120–160 ms, base 200–280 ms, slow ≤ 450 ms (nenhum efeito de feedback de input > 160 ms).
- **R3 — Espelho em JS.** `web/src/design/motion.ts` exporta os mesmos tokens como constantes tipadas lidas de uma fonte única (CSS vars via `getComputedStyle` na inicialização, com fallback literal), para que CSS e `motion` nunca divirjam; teste unitário compara os dois.
- **R4 — Wrapper sobre `motion`.** `web/src/design/` expõe primitivos mínimos: `Pressable` (hover/press/focus de controle primário), `Selectable` (indicador persistente com `layoutId`), `Reveal` (presença/abertura), `useEffectsEnabled()` (reduced-motion + aba em background + flag de kill). Proibido importar `motion` direto em componentes novos de efeito (exceto os 5 usos legados, migrados só quando a iteração os tocar).
- **R5 — Reduced-motion e a11y preservados.** `MotionConfig reducedMotion="user"` e o bloco global CSS permanecem intactos. Todo efeito tem fallback estático **equivalente em informação** (texto/ícone/borda), nunca sumindo a informação. Foco e hitbox **não dependem de hover**; nenhum estado mecânico espera a animação terminar. Com `prefers-reduced-motion: reduce`, nenhum `transform` animado >0.01 ms; opacidade/cor estática permitidas.
- **R6 — Não bloquear nada.** Animações são interrompíveis (nova ação cancela a anterior sem salto), não atrasam input, SSE nem commit de ação (idempotência por `action_id` da SPEC-205 intocada). Pending/falha/retry têm estado visual próprio e **sem atualização otimista irreversível** [D, briefing §4.3].
- **R7 — Sem vazamento por animação.** Efeitos de revelação (Codex/Bestiário/Mapa) operam sobre dado já autorizado ao jogador; arte/nome/silhueta de entidade não descoberta **não** está no DOM, nem em `<img>` oculta, nem em prefetch/`link rel=preload`, nem em atributo `data-*`/`aria-*`/tooltip (alinhado ao contrato da SPEC-206). Teste inspeciona DOM e requests de rede.
- **R8 — Orçamento de bundle e frame.** Delta de bundle desta spec ≤ **+15 KB gzip JS** e ≤ **+3 KB gzip CSS** sobre o baseline remedido na Etapa 0 **[R; dono pode alterar, §8]**; nenhuma dependência nova sem justificativa de §3.6. Frame: nenhum efeito pode produzir long task >50 ms nem frame >16,7 ms p95 em perfil de CPU 4× throttle (Chromium via CDP) durante os fluxos medidos; animações só de `transform`/`opacity` (nada de `blur()` animado em listas longas nem `layout` em `StoryLog`).
- **R9 — Atmosfera contida.** `EmberField` e qualquer efeito contínuo: pausa com aba oculta (`visibilitychange`), cap de partículas, não roda atrás do chat durante combate. Nenhum movimento contínuo novo sobre texto de leitura.
- **R10 — Kill switch.** `useEffectsEnabled()` respeita `localStorage["rpg.effects"]="off"` e `?effects=off` (diagnóstico/suporte): todos os efeitos viram estáticos sem recarregar lógica.
- **R11 — Instrumentação barata.** Sem telemetria nova de rede. Os efeitos expõem `data-effect="<id>"` e `data-effect-state` para os testes; eventos de custo (long tasks) só em teste/dev.
- **R12 — Iterações verticais entregáveis isoladas.** Cada iteração (§4) é mergeável sozinha com gate próprio verde; a seguinte só começa com a anterior verde. SPEC-209/210/211 só são desbloqueadas ao fechar as iterações 1–2 (primitivos + shell); as iterações 3–4 podem fechar em paralelo a elas.

### Fora de escopo
- Mudar mecânica, regras, números de cartas, layout/IA do shell (SPEC-204) ou contrato de API de combate (SPEC-205).
- Redesenhar menus (SPEC-209/210/211), mobile/single-pane (SPEC-216), tema/paleta global do produto além dos tokens de estado/elevação.
- Som (opcional futuro, não obrigatório), GSAP, WebGL/shaders, partículas novas, screen shake global (P3 do arsenal: **off**), efeitos de glare/parallax (P2) — só entram por decisão do dono (§8).
- Copiar arte, estilos exatos ou assets de jogos de terceiros; baixar assets externos.
- Criar/alterar evaluator, expected ou dataset protegido.

## 3. Design técnico

### 3.1 Arquivos novos
- `web/src/design/tokens.css` — importado por `styles.css`; define os tokens de R2 (ou bloco `@layer tokens` no próprio `styles.css` se o build preferir; decisão da Etapa 1).
- `web/src/design/motion.ts` — constantes espelho (R3), `prefersReduced()`, `useEffectsEnabled()`.
- `web/src/design/primitives.tsx` — `Pressable`, `Selectable`, `Reveal` (R4).
- `web/src/design/effects.registry.ts` — array tipado `EffectContract[]` (§3.3), fonte da verdade lida pelos testes.
- `web/src/design/*.test.ts` (vitest/node:test conforme o runner existente do `web/`; confirmar na Etapa 0) — tokens CSS↔JS, registry completo.
- `web/e2e/effects.spec.ts` — Playwright (projetos `chromium` e `chromium-motion`, §3.5).
- `docs/spec208/README.md` — medições (bundle antes/depois, frame, long tasks), registro de valores finais de tokens, matriz de efeitos entregues × SPEC-201.

### 3.2 Arquivos alterados (por iteração, mínimo necessário)
`web/src/styles.css` (migra literais de duração/easing dos blocos tocados para tokens; **não** reescreve o arquivo inteiro), `web/src/components/{CreateScreen,CardHand,SceneZones,ReactionPrompt,Hud,CodexTab,WorldMap,StoryLog,PlayScreen}.tsx` conforme a iteração, e os componentes do shell criados pela SPEC-204 — nomes previstos lá: `web/src/workspace/{Workspace,ChatSurface,ContextSurface}.tsx`, divisor `Splitter`, `ContextTab = codex|personagem|combate|bestiario|mapa`, CSS em `web/src/workspace.css` (R14 da 204: tokens desta spec são **consumidos** lá, sem mover regras de layout da 204 para `design/`); e da SPEC-205 — `web/src/combat/useTargeting.ts`, `components/combat/{Arena,TargetChip,CardTooltip}.tsx`. Confirmar na Etapa 0 (podem ter mudado na implementação). `web/playwright.config.ts`: acrescentar o projeto `chromium-motion` (sem alterar os existentes). **State ownership:** nenhum estado de jogo; estado visual efêmero fica no componente (`useState`/`motion` values). Layout/aba/split persistido continua dono da SPEC-204. Nenhuma mudança de save, API ou backend.

### 3.3 Contrato por efeito (`EffectContract`)
```ts
type EffectContract = {
  id: string;                 // ex.: "ctrl.press", "card.arm", "tab.indicator"
  matrix_ref: string;         // ID de linha da matriz SPEC-201 (formato `M\d{2}`, ex.: "M01"); teste valida regex e existência na tabela da 201
  reason: string;             // por que existe (informação que transmite)
  trigger: string;            // evento exato (pointerenter, focus-visible, armed, server-confirmed, ...)
  states: { start: string; end: string; pending?: string; error?: string };
  duration_token: "instant"|"fast"|"base"|"slow";
  easing_token: string;       // token de §R2
  interruptible: true;        // literal: sempre
  reduced_motion_fallback: string; // equivalente estático informativo
  cost: { cpu: "css"|"transform"|"layout"; bundle_kb_gzip: number; frame_budget_ms: number };
  test: string;               // caminho::nome do teste
  data_dependency: "none"|"player-authorized"; // R7
  sound: null;                // prompt 05: feedback sonoro opcional, NÃO obrigatório; fora desta spec (§8.4) → sempre null
};
```
Entradas obrigatórias do registry por iteração estão em §4. O registry é **catálogo de efeitos entregues**, não runtime.

### 3.4 Efeitos de partida por iteração (sujeitos à matriz aprovada da SPEC-201 — [R], substituíveis)
- **It.1 controles primários:** `ctrl.hover` (elevação `--elev-1`→`2`, ≤ 2 px, sem layout shift), `ctrl.press` (já existe `:active`; formaliza em token), `ctrl.focus` (anel `--focus-ring`, independente de hover), `choice.select` (raça/classe do `CreateScreen`: hover + seleção com indicador persistente), `ctrl.pending/error` (spinner CSS/linha de estado; texto "Enviando…/Falhou — tentar de novo").
- **It.1b chat (M03/M04 da SPEC-201):** `chat.pending` (estado `pending`/`aria-busy` no composer + rótulo de fase SSE), `chat.entry` (fade só no bloco novo; zero animação no histórico/reload; sem `blur` em lista), `chat.retry` (erro reativa o botão com texto; mesmo `action_id`). `npc.portrait.enter` (primeira aparição do retrato de NPC/cena via `VisualArtwork`/`SceneArtwork`: fade curto **depois** que a imagem carregou; placeholder estático com alt; sem pré-carregar retrato de NPC não apresentado — R7).
- **It.2 shell (SPEC-204):** `tab.indicator` (`layoutId` compartilhado no seletor das 5 abas), `split.toggle` (layout compartilhado chat↔split 50/50; conteúdo sem reflow animado, apenas contêiner), `tab.content` (cross-fade curto preservando foco e scroll — não monta/desmonta o chat), `split.resize` (o `Splitter` da SPEC-204) sem animação durante arraste (anima só ao soltar/"snap").
- **It.3 combate (SPEC-205):** `card.hover/focus` (custo/alcance legíveis sem hover), `card.arm` (sobe e fica armada; `Esc` desarma), `target.valid` (destaque de alvos válidos + linha de mira SVG opcional; rótulo textual do alvo), `card.resolve` (lançamento curto **após** confirmação do servidor), `hit.feedback` (chip de dano/status atualiza no ponto; sem número flutuante em reduced), `reaction.present` (presença não bloqueante), `passive.trigger` (chip curto no ator quando o servidor reporta passiva/gatilho de Entropia aplicado no turno — só a partir do payload, nunca previsto no cliente), `encounter.enter/exit` (overlay curto com título; corte direto em reduced). Excluído: screen shake.
- **It.4 revelação:** `codex.entry.reveal`, `bestiary.discover` (troca direta silhueta→arte **só** após dado autorizado chegar; sem pré-render de arte oculta), `map.marker` (marcador/caminho conhecido; fog intacto). `data_dependency: "player-authorized"`.

### 3.5 Estratégia de teste
- Projeto Playwright novo `chromium-motion` (`reducedMotion: "no-preference"`) usado **somente** por `effects.spec.ts`; todo o resto da suíte permanece `reduce` [F]. Cada efeito: (a) estado final correto em `no-preference`; (b) fallback estático em `reduce` (assert de `getComputedStyle().transitionDuration`/`animationName`, ausência de `transform` em movimento); (c) operável por teclado (foco → ativar → `Esc`); (d) `AxeBuilder` sem violações serious/critical nos estados armado/foco/erro; (e) viewports 1440 e 1280×720 (desktop; mobile fora de escopo).
- Teste de não-bloqueio: durante `card.resolve`, dispara-se nova ação e o servidor falso recebe-a em <100 ms; durante `ctrl.pending`, SSE falso continua entregando.
- Teste de vazamento (R7): intercepta requests e varre DOM por IDs/URLs de entidade não descoberta.
- Medição (Etapa 0 e fim de cada iteração): `npm run build` → tamanhos de `web/dist/assets/*` (raw+gzip) em script local; frame/long task via CDP com CPU throttle 4× em fixtures determinísticas (API mock), registrados em `docs/spec208/README.md`. Sem provider real.

### 3.6 Política de dependências
Adicionar biblioteca só com: justificativa medida de que `motion`+CSS não resolve, licença verificada, delta de bundle dentro de R8, fallback sem a lib e aprovação do dono (§8). GSAP/WebGL/shader/Lottie: **não** por padrão [D]. Nenhum asset de jogo de terceiros.

### 3.7 Degradação
`motion` falhar/ausente ⇒ CSS puro mantém hover/foco/seleção estáticos; JS desligado de efeitos ⇒ kill switch R10. Aba em background ⇒ efeitos contínuos pausam; ao voltar não reproduzem fila acumulada.

## 4. Plano passo a passo (TDD)

### Etapa 0 — Verificação de pré-condições e baseline
1. Confirmar SPEC-201 `approved`, SPEC-204/205 `done` em `specs/index.yaml`; senão **parar** (R1). Reler a matriz aprovada e mapear linhas → iterações; listar nomes reais dos componentes do shell da SPEC-204.
2. `npm run build` em `web/`; registrar raw/gzip de `web/dist/assets/*` (hoje ≈408 505 B JS / 61 669 B CSS) e fixar o teto numérico de R8. Medir frame/long task baseline dos fluxos (criação, chat, combate) com throttle 4×.
3. Confirmar runner de testes unitários do `web/` (`package.json` scripts; há `test:e2e`).
**Verificação:** `docs/spec208/README.md` com baseline; nenhum arquivo de produto alterado.

### Etapa 1 — Tokens + primitivos + registry (Iteração 1, parte a)
1. **Testes primeiro:** `test_tokens_css_js_parity` (R3); `test_registry_complete` (R1: campos obrigatórios, `matrix_ref` presente, `interruptible: true`); `test_no_direct_motion_import` (R4, glob em componentes novos).
2. Implementar `tokens.css`, `motion.ts`, `primitives.tsx`, `effects.registry.ts`; migrar literais dos blocos de `.btn`/`:focus-visible`.
3. Playwright: projeto `chromium-motion`; spec de `ctrl.hover/press/focus/pending/error` (+ reduced + axe + teclado).
**Verificação:** `cd web && npm run build && npm run test:e2e -- effects.spec.ts` verde; bundle dentro do teto.

### Etapa 2 — Controles e criação de personagem (Iteração 1, parte b)
1. **Testes:** `choice.select` — hover, foco por teclado e seleção persistente em raça/classe (assert `aria-pressed|aria-checked`, `data-effect-state=selected`); fallback reduced = borda/ícone.
   Chat (It.1b): `chat.pending` bloqueia reenvio e mostra fase SSE (`aria-busy`); `chat.entry` anima só o bloco novo e nada no reload (assert: histórico carregado sem `data-effect-state=entering`); `chat.retry` reusa o `action_id`; `npc.portrait.enter` não emite request de imagem de NPC antes da primeira aparição (interceptação de rede).
2. Aplicar `Selectable` em `CreateScreen` e os efeitos de chat/retrato; sem alterar o fluxo/payload de criação nem o contrato SSE.
**Verificação:** e2e de criação existente em `critical-journeys` continua verde.

### Etapa 3 — Shell (Iteração 2)
1. **Testes:** `tab.indicator` move para a aba ativa e permanece após reload do estado da SPEC-204; `split.toggle` não perde draft do composer nem scroll do `StoryLog`; foco preservado; reduced = troca instantânea.
2. `Selectable`/`layout` no seletor de abas e contêiner do split; **sem** `layout` no `StoryLog`.
**Verificação:** e2e shell da SPEC-204 + axe verdes; sem long task >50 ms ao alternar.

### Etapa 4 — Combate (Iteração 3)
1. **Testes (servidor falso):** carta com alvo: clique arma → alvos válidos destacados → clique executa → `card.resolve` só após resposta; `Esc` desarma; carta sem alvo executa em 1 clique; alvo morto/Entropia insuficiente mostram estado textual; nova ação durante animação é aceita; reduced = sem trajetória, estado/texto idênticos.
2. Implementar efeitos de §3.4 It.3 sobre o contrato de `valid_targets` da SPEC-205 (não inventar campo).
**Verificação:** e2e de combate (jornada F-série da SPEC-172 que cobre combate) verde; frame p95 ≤ 16,7 ms com 4× throttle.

### Etapa 5 — Revelação sem vazamento (Iteração 4)
1. **Testes:** R7 (DOM + rede) para Codex/Bestiário/Mapa com entidade não descoberta; revelação ocorre só após dado autorizado; reduced = troca direta.
2. Implementar `Reveal` nas telas já entregues por SPEC-209/210/211 **ou**, se estas ainda não existirem, apenas nos pontos atuais (`CodexTab`, `WorldMap`) e deixar `Reveal` pronto para consumo (registrar no README).
**Verificação:** varredura de vazamento verde.

### Etapa 6 — Fechamento
1. Reexecutar medição de bundle/frame; preencher `docs/spec208/README.md` (matriz entregue × SPEC-201, deltas, valores finais de tokens, efeitos rejeitados e por quê).
2. `/wrap-up`: `uv run pytest` offline verde (nenhum backend alterado, mas obrigatório pelo CLAUDE.md), atualizar `ESTADO_ATUAL.md` e `ROADMAP.md`, `specs/index.yaml` (coordenador).

## 5. Critérios de aceite
- [x] Pré-condições R1 verificadas e registradas antes do primeiro commit de produto.
- [x] Tokens de R2 presentes em `:root`; paridade CSS↔JS testada; tokens pré-existentes inalterados.
- [x] `effects.registry.ts` completo: todo efeito com os 12 campos obrigatórios de §3.3 (+ `sound: null`), `matrix_ref` válido, teste existente.
- [x] `MotionConfig reducedMotion="user"` e bloco global de reduced-motion intactos (diff mostra zero remoção).
- [x] Em `reduce`: nenhum transform animado; toda informação continua visível (assert por efeito).
- [x] Teclado: todo efeito armável/selecionável funciona sem hover; `Esc` cancela mira.
- [x] axe sem violações serious/critical nos estados armado/foco/erro/pending em 1440 e 1280×720.
- [x] Nenhuma ação enviada espera animação; ação duplicada não gera estado duplicado (reaproveita idempotência SPEC-205).
- [x] R7: varredura de DOM e rede sem entidade/arte não descoberta.
- [x] Bundle ≤ baseline + 15 KB gzip JS / +3 KB gzip CSS; zero dependência nova (ou aprovada em §8); sem GSAP/WebGL.
- [x] Frame p95 ≤ 16,7 ms e zero long task >50 ms nos fluxos medidos (4× throttle), números em `docs/spec208/README.md`. Fechado na revisão Sol: a causa real eram animações **contínuas** em combate (véu/bandeira/ponto da aba) e transições de cor/sombra/opacidade; corrigidas, os 3 fluxos (criação, chat, combate+abas) contra o build dão p95 ≤ 14,0 ms e 0 long task em 9 execuções finais (5 registradas em `docs/spec208/evidence/perf-runs.jsonl`); gate absoluto em `RPG_E2E_SERVER=preview`.
- [x] Kill switch `?effects=off` torna todos os efeitos estáticos (e2e).
- [x] Suíte e2e anterior (`critical-journeys`, `visual-surfaces`, `voice-input`) continua verde sem edição de seus assertivos.
- [x] `uv run pytest` verde (suíte completa offline); `npm run build` verde.

## 6. Smoke
Offline por padrão: API falsa/mock dos e2e, MockLLM, sem provider real e sem custo. Roteiro: criar personagem (hover/seleção/confirmar) → chat → abrir aba e split → iniciar combate pelo chat → armar carta, mirar, executar, reação → desfecho → alternar abas → abrir Codex/Bestiário/Mapa com item descoberto e não descoberto → repetir com `prefers-reduced-motion: reduce` e `?effects=off`. Captura de vídeo/trace Playwright anexada à evidência. Provider real só opt-in com teto explícito (não necessário aqui: nenhuma mudança de backend).

## 7. Riscos & compatibilidade
- **Dependência temporal:** SPEC-204/205 ainda não existem; nomes de componentes e contrato `valid_targets` podem diferir. Mitigação: Etapa 0 relê o estado real; nenhum nome desta spec além de `web/src/design/*` é vinculante.
- **Conflito de merge** com SPEC-197 (`App.tsx`/`styles.css` em andamento) e com 204/205. Mitigação: alterações localizadas, migração de literais só nos blocos tocados, rebase por iteração.
- **Playwright default `reduce`** pode mascarar bugs de movimento; mitigado pelo projeto `chromium-motion`. Flakiness de animação: asserts em estado final/atributos, nunca em frames intermediários; `retries: 0` mantido.
- **Custo de CPU em notebook fraco:** teto de frame + kill switch + só transform/opacity.
- **Vazamento por revelação:** R7 + dependência de SPEC-206 (taxonomia); se 206 não estiver `done` ao chegar na It.4, a It.4 só toca pontos já públicos e é registrada como parcial.
- Sem impacto em saves, backend, quota ou latência de turno. Layout/aba persistidos (SPEC-204) não são alterados.
- Licença/assets: nenhum asset externo; links do arsenal são estudo de comportamento.

## 8. Pontos de decisão do dono
1. **Teto de bundle (R8):** +15 KB gzip JS / +3 KB CSS. *Default recomendado:* manter; aumentar só com evidência de ganho de jogabilidade.
2. **Efeitos P2/P3 do arsenal** (glare em carta rara, parallax de arte, tinta/folha no Codex, screen shake, partículas/shader/CRT). *Default:* fora desta spec; reavaliar após beta com dados de uso.
3. **Dependência nova** (ex.: GSAP/Lottie) caso uma medição mostre que `motion` não basta. *Default:* não; exige decisão explícita.
4. **Som opcional** dos efeitos. *Default:* sem som nesta spec.
5. **Seleção original do arsenal** (D7): ao ser recuperada, atualizar matriz da SPEC-201 antes da It.3/4; *default:* seguir o arsenal-base já aprovado na 201 sem esperar.
6. **Piso do reduced-motion:** *Default:* equivalência informativa total, sem nenhum movimento (opacidade/cor estáticas permitidas).

## 9. Evidência requerida
- `docs/spec208/README.md` com: baseline e final de bundle (raw/gzip por arquivo), frame/long tasks por fluxo (4× throttle), tabela efeito × `matrix_ref` × teste × custo, valores finais dos tokens, efeitos rejeitados.
- Saída de `npm run build`, `npm run test:e2e -- effects.spec.ts` e da suíte e2e completa; relatório axe; traces/vídeos Playwright (normal, reduced, `effects=off`).
- Saída de `uv run pytest` offline.
- Registro da verificação de R1 (status das SPEC-201/204/205 no `specs/index.yaml` no momento do início).
- Review independente não exigido (`REVIEW_REQUIRED: false`); se alguma iteração tocar vazamento de conhecimento (It.4) e SPEC-206 divergir, escalar para Sol.

## 10. Registro de execução (2026-10-16)
- Evidência: [docs/spec208/README.md](../docs/spec208/README.md). 19 efeitos no registry (It.1, 1b, 2, 3 e 4 parciais), projeto Playwright `chromium-motion`, testes Node `web/tests/design.test.mjs`.
- Defaults da §8 usados: teto +15/+3 KB (uso +1,7/+1,0 KB), sem P2/P3, sem dependência, sem som, arsenal-base, piso de reduced-motion = equivalência informativa.
- Desvios: (a) `passive.trigger`, `encounter.enter/exit`, `reaction.present`, linha de mira SVG ficaram fora (precisam de payload novo/SPEC-209); (b) o `Reveal` de Bestiário/Mapa cobre só o que o servidor já entrega — o `/data/map` ainda envia nome/`lore_seed` de nós em fog (M23, servidor/SPEC-211); (c) o critério de long task absoluto não é atingível sem tocar o shell da 204; (d) correções de atmosfera achadas pela medição: `combat-veil` (box-shadow inset animado) e farol do mapa passaram a animar só `opacity/transform`; `.story { overflow-anchor: none }` (a remoção do `filter` das entradas antigas reativava o scroll anchoring e quebrava `workspace-shell` "rascunho, scroll").
- Falhas pré-existentes/ambientais (também no HEAD sem as mudanças): `voice-input` "native Chromium MediaRecorder" (`audio/wav` no Chromium local) e intermitência de `fonts.googleapis.com` (requestfailed) em specs protegidos; os testes novos ignoram o Google Fonts.
- Revisão independente Sol (2026-10-16, [handoff](../handoffs/SPEC-208-SOL-independent-review.md)): fechou o critério de frame/long task (correções de R8/R9 medidas, gate absoluto contra o build), produziu a evidência de vídeo (normal/reduced/`effects=off`) e rejeitou com medição a fade do bloco novo do chat (M09 fica "sem animação no histórico nem no bloco novo; sem blur"). Efeitos de §3.4 adiados (`passive.trigger` sem payload do servidor, `encounter.enter/exit` M36 P2 → §8.2, `reaction.present` M18 exige janela de gatilho do backend → SPEC-209, linha de mira SVG opcional) ficam como desvio explícito: §3.4 é [R] substituível e nenhum critério de §5 os exige.
