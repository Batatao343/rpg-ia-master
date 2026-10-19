# SPEC-201 — Diagnóstico UX e matriz de efeitos/interações

> **Status:** `done`
> **Criada:** 2026-10-15 · **Atualizada:** 2026-10-16
> **Depende de:** nenhuma · somente leitura do source (ordem final 2026-10-15)
> **Desbloqueia:** SPEC-204, SPEC-208 (ordem final 2026-10-15)
> **Origem:** pacote `docs/historico/proximas-specs/pacote-prompts-rpg-beta-2026-10-15/`, prompt 01
> **EXECUTOR_MODEL:** `Terra` (≡ Sonnet, ver docs/planos/equivalencia-modelos-claude.md)
> **REVIEW_MODEL:** `Sol` (≡ Opus em contexto separado) · **REVIEW_REQUIRED:** `false`
> **EVAL_AUTHORING_REQUIRED:** `false` — spec de diagnóstico, sem mudança de produto e sem eval novo. Os critérios de aceite das linhas da matriz viram eval apenas na SPEC-208+ (handoff separado).

Rótulos: **[F]** fato observado no source · **[D]** decisão de produto fechada · **[H]** hipótese técnica · **[R]** recomendação.

---

## 1. Contexto & Objetivo

**[D]** O produto é chat-first: a narrativa inteira vive no chat; as demais superfícies são de jogo e consulta
(`DECISOES_PRODUTO.md`). A UI atual é percebida como estática e densa, e o dono não quer "dez animações por
controle": quer **resposta, clareza, vivacidade e atmosfera**, sem efeito decorativo em todo controle.

**[F]** Hoje não existe nenhum inventário de efeitos. O que há de motion está espalhado: `motion ^12.42.0`
(`web/package.json:19`), `<MotionConfig reducedMotion="user">` (`web/src/App.tsx:697`), `AnimatePresence`
nas trocas de tela (`App.tsx:743`), `motion.article` com fade+`y`+`blur` em cada mensagem
(`web/src/components/StoryLog.tsx:69`), `motion.div` em `DeathModal`/`LevelUpModal`, `AnimatePresence` na
arte de cena (`SceneArtwork.tsx:14`), `@keyframes` CSS (`pulse`, `throb`, `beacon`, `shake`, `barhit`,
`veilpulse`, `lvl-pulse`, `prologue-pulse`, `blink`) e um bloco global
`@media (prefers-reduced-motion: reduce)` (`web/src/styles.css:825`) que zera `animation` e reduz
`transition-duration`. Nenhum `layoutId`/`layout` é usado. Specs relacionadas já `done`: SPEC-054
(polish CSS de imersão), SPEC-077 (UI tática de Cartas), SPEC-157 (auditoria de frontend/sessão), SPEC-172
(frontend evals F01–F16), SPEC-090 (simulador de combate). Nenhuma entrega uma matriz de efeitos.

**Objetivo.** Produzir, **sem mudar o produto**, um documento auditado (`docs/spec201/matriz-efeitos.md`)
com capturas reproduzíveis que mapeie onde um efeito/interação **resolve um problema real de uso**, o que
pode ser corrigido **sem animação**, e que lacunas de design system/tokens precisam existir antes da SPEC-208.
Cobre as telas atuais e, como "pontos de efeito previstos", as telas planejadas (SPEC-204 shell, 205 combate,
209–211 menus), sem especificá-las.

**Correção de premissa [F]:** o prompt original cita uma "tela de mapa". Ela **não existe**: o mapa é a aba
`mapa` do `Hud` (`web/src/components/Hud.tsx:96`, componente `WorldMap.tsx`, com `onTravel`). O diagnóstico
trata-o como aba. Idem Bestiário: hoje é parte de `CodexTab.tsx` (tiers `codex-beast`), não uma aba própria.

## 2. Requisitos

- **R1 — Inventário de superfícies.** O documento lista toda superfície renderizada por `web/src/App.tsx`
  (`screen`: bootstrap, auth, account, saves, create, simulator, play) e por `PlayScreen` (StoryLog, SceneArtwork,
  chips de ação, composer/voz, `tactical-dock` com `CardHand`/`ReactionPrompt`/`WoundTrack`/`SceneZones`, `Hud`
  com suas 8 abas `ficha|combate|personagens|mapa|faccoes|missoes|cronica|codex`, `LevelUpModal`,
  `DeathModal`, `OnboardingHint`, `Banner`, `ArtworkDialog`/`ImageQuoteDialog`, `GeneratedPortrait`/`GeneratedArtCard`,
  `VisualArtwork`, `QuestsTab`, `CodexTab`, `WorldMap`, `SaveScreen`, `AuthScreen`/`TurnstileChallenge`,
  `AccountScreen`, `CombatSimulatorScreen`, `EmberField`). Estados de loading/erro/vazio de cada tela
  (bootstrap, auth, saves, account, create/prólogo) entram como superfícies próprias.
  Cada superfície aponta o arquivo e linhas reais.
- **R2 — Matriz de efeitos.** Tabela única com as colunas exatas:
  `ID | tela | interação | problema atual [F/H] | efeito/interação proposto | propósito | prioridade | a11y | perf | risco de confusão | critério de aceite`.
  Prioridade usa P0–P3 (mesma faixa do arsenal-base). Toda linha tem **problema atual evidenciado** (captura,
  trecho de CSS/TSX ou medição); linha sem problema evidenciado é rejeitada (anti-decoração).
- **R3 — Regra anti-decoração.** Nenhum efeito é proposto "para todo controle". Cada linha deve declarar uma
  das 6 funções do arsenal (affordance, preparação, compromisso, consequência, revelação, transição); linha
  puramente cosmética é P2/P3 e marcada `opcional`. A matriz termina com uma lista explícita "o que NÃO
  animar" (ex.: parágrafos de narração longa, listas de Codex, tooltips de custo).
- **R4 — Atrito removível sem animação.** Lista separada, com correção proposta que não use motion: p.ex.
  hitbox/estado `:hover`/`:focus-visible`/`:disabled` ausente, rótulo, ordem de foco, texto de erro, estado
  vazio, `transition: all` genérico, alvos de clique pequenos, `title=` como único tooltip. Cada item com
  evidência e arquivo.
- **R5 — Gaps de design system.** Seção que audita tokens e estados e diz o que falta: cores
  (OKLCH em `styles.css:11-35`), tipografia (`--display`/`--body`), raios, sombras, `--ease` único, z-index
  (`--z-hud/--z-banner/--z-overlay`), **ausência** de tokens de duração, de escala de elevação, de estado
  (hover/pressed/selected/disabled/loading/error/revealed/secret), de foco por contexto e de espaçamento.
  Verificar contagem de `transition: all` e de valores hard-coded (`#cbc6ba`, `#b3852f`, `0.15s`, `0.12s`)
  que escapam dos tokens.
- **R6 — Estados mínimos por componente interativo.** Para cada componente de R1, tabela
  `default | hover | focus-visible | pressed | selected | disabled | loading | error | revealed/secret`
  marcando `ok/parcial/ausente` com evidência. `revealed/secret` documenta que nenhum efeito, tooltip,
  imagem, prefetch ou atributo de DOM pode expor conteúdo `hidden/secret` (ver §3.5).
- **R7 — Capturas reproduzíveis.** Um script Playwright **somente de captura**
  (`web/e2e/diagnostics/spec201-capture.spec.ts` ou `web/scripts/spec201-capture.mjs`, ver §3.3) gera PNGs em
  **1440×900** e **1280×800** a partir de fixtures determinísticas, com `reducedMotion: "no-preference"`
  para os estados com motion e `"reduce"` para o baseline de a11y. Saída em
  `docs/spec201/capturas/<viewport>/<superficie>-<estado>.png` + `docs/spec201/capturas/INDEX.md` (nome,
  viewport, fixture, comando). Sem rede, sem provider, sem custo.
- **R8 — Pontos de efeito previstos.** Seção separada, **sem proposta de implementação**, para as telas
  futuras: shell SPEC-204 (troca de aba, split↔full, resize, foco/scroll/draft preservados), combate SPEC-205
  (arma→mira→executa, entrada/saída de encontro, resultado), menus SPEC-209/210/211 (deck, mapa/viagem,
  codex/bestiário/dossiês). Cada ponto lista: gatilho real do backend/estado, função do arsenal, risco de
  spoiler, prioridade provisória. Marcado explicitamente como `previsto`.
- **R9 — Prova de motion atual.** Levantar o que de fato anima hoje e quanto custa: lista de `motion.*`
  (com `initial/animate/transition`), `@keyframes`, `transition` por seletor; `EmberField` (canvas
  `components/EmberField.tsx`) com FPS/CPU medidos em modo ocioso; efeito do `filter: blur` animado em
  `StoryLog` ao rolar histórico longo; peso de `motion` no bundle (`npm run build`, tamanho do chunk com e
  sem import do pacote, via saída do Vite). Medições registradas com método, máquina e variância; sem
  "otimismo artificial": se não mediu, marca `não medido`.
- **R10 — Reduced motion e a11y.** Verificar com `reducedMotion: "reduce"`: `MotionConfig`
  (`reducedMotion="user"` só desliga `transform`/layout do `motion`, **não** opacity) vs bloco CSS global;
  identificar o que ainda se move (**[H]** `motion.article` mantém fade; `behavior: smooth` de scroll, se houver;
  `EmberField` é ocultado por CSS mas pode seguir rodando JS). Verificar foco visível sem hover, ordem de Tab,
  `aria-live` (existe em `.thinking`, `StoryLog.tsx:42`, e no status de voz, `PlayScreen.tsx:231`; narração
  nova **não** é anunciada — [F] a validar),
  papel `tablist` no `Hud` sem setas de teclado (**[H]**), contraste de `--faint`/`--muted` sobre `--bg`.
- **R11 — Critério de aceite por linha.** Cada linha da matriz tem critério observável e testável pela
  SPEC-208 (ex.: "carta armada tem `aria-pressed=true` e borda `--accent` sem depender de transform; Esc
  desarma; reduce-motion mostra o mesmo estado"). Critérios não podem depender de tempo de animação.
- **R13 — Arte contextual real vs informação mecânica.** Seção que lista (a) onde arte real já
  catalogada/gerada (`services/visual_catalog.py`, `SceneArtwork`, `GeneratedPortrait`, cartas, criaturas,
  NPCs, mapa) agrega atmosfera e pode ganhar efeito de revelação/transição, e (b) onde imagem **não** pode
  carregar informação mecânica (custo, dano, alvo válido, estado de Ferimento, fog): essa informação tem
  sempre texto/token equivalente. Cada item cita o ID canônico da fonte da arte e a regra de visibilidade.
- **R14 — Prioridade de interação antes de transição.** A ordenação da matriz segue: hover/focus/press →
  indicação de seleção → confirmação implícita (estado visível que dispensa diálogo "tem certeza?") →
  saída visível (resultado/erro) → só então transições cosméticas. Linha que é transição cosmética não pode
  ser P0. Também lista onde hoje há confirmação repetitiva removível.
- **R15 — Referências do pacote.** `referencias/ARSENAL_VISUAL.md`, `referencias/REFERENCIAS_LINKS.md` e os
  HTMLs de `design-html/` são citados por linha quando inspiram uma proposta, sempre como **referência de
  comportamento** (números/cartas/falas dos HTMLs são mock **[D]**). Nenhuma proposta introduz framework de UI
  duplicado ou UI kit genérico; `motion` + CSS existentes são o teto de dependências.
- **R12 — Não alterar produto.** O PR da execução toca apenas `docs/spec201/**`, o script/spec de captura
  e, no máximo, `web/package.json` scripts (ver §3.3). Zero mudança em `web/src/**`, `api.py`, `state.py`.

### Fora de escopo

- Implementar qualquer efeito, token, componente ou tela (SPEC-208 em diante).
- Redesenhar shell, abas, combate ou menus (SPEC-204/205/209–211).
- Prévia HTML/CSS/JS interativa de todas as interações (pode ser objeto da SPEC-208).
- Definir easing/durações finais, paleta final ou nova biblioteca de animação (**[D]** decisão delegada ao
  agente da SPEC-208, com evidência desta matriz; `motion` permanece a única biblioteca — nada de GSAP).
- Mobile single-pane (SPEC-216); apenas notas de a11y/perf em 390px **não** entram.
- Mecânica, números e regras de combate dos HTMLs de `design-html/` (**[D]** são mock; regras vêm do repo).
- Evals novos; qualquer alteração em `evals/`.
- Importar a seleção original do arsenal (pendente, ver §8-Q2).

## 3. Design técnico

### 3.1 Arquivos novos (entregáveis da execução)

| Arquivo | Responsabilidade |
|---|---|
| `docs/spec201/matriz-efeitos.md` | Documento principal: R1–R11 (inventário, matriz, atrito, gaps, estados, previstos, medições, a11y). |
| `docs/spec201/atrito-sem-animacao.md` | Lista R4 isolada (pode ser seção do principal se <60 linhas). |
| `docs/spec201/gaps-design-system.md` | R5/R6 (tokens, estados, tabela componente×estado). |
| `docs/spec201/medicoes.md` | R9/R10: método, comandos, resultados brutos, `não medido`. |
| `docs/spec201/capturas/INDEX.md` + PNGs | R7. |
| `web/e2e/diagnostics/spec201-capture.spec.ts` | Captura Playwright (§3.3). Fora do required gate. |

Arquivos alterados: nenhum de produto. (**[R]** `web/playwright.config.ts` não muda; o diretório
`e2e/diagnostics/` é selecionado por `--grep @spec201` ou por projeto opt-in no próprio arquivo via
`test.use`, sem editar a config compartilhada.)

### 3.2 Pré-auditoria (fatos já verificados no HEAD; a execução confirma e expande)

- **[F]** `web/src/components/StoryLog.tsx`: cada `Entry` é `motion.article` com `initial {opacity 0, y 14,
  filter blur(3px)}`, 0.55s `[0.16,1,0.3,1]`; texto via `useTypewriter(entry.text, entry.streaming)` (pseudo-
  streaming: SSE fatia mensagem pronta, ver SPEC-200); cursor `msg__cursor`; botão de custo `✧` com
  `aria-expanded`. Animar `filter: blur` em N mensagens é candidato a custo (**[H]**, medir em R9).
- **[F]** `Hud.tsx`: `tab` é `useState` local com auto-troca para `combate` ao entrar em luta e de volta a
  `ficha` ao sair (`Hud.tsx:26-34`) — o jogador perde a aba em que estava. `nav.tabs role="tablist"` com
  `role="tab"`/`aria-selected`; sem `layoutId` nem indicador deslizante; <900px o `Hud` vira gaveta
  (`styles.css:~817`, `translateX(100%)`).
- **[F]** `PlayScreen.tsx:147-176`: `CardHand`/`ReactionPrompt`/`WoundTrack`/`SceneZones` ficam num
  `tactical-dock` na **coluna do chat** (contradiz o alvo de SPEC-204/205, que os leva à aba Combate);
  draft `input` é `useState` do `PlayScreen` (`:39`) — perde-se ao trocar de `screen`.
- **[F]** `CardHand.tsx` (≈100 linhas): alvo por `<select>`, botão "Jogar Carta" (`combat-card__play`),
  Ruptura em toggle; sem mira por clique no inimigo, sem Esc, sem tooltip de custo/limites; `title="Custo de
  Entropia"` é o único hint. `SceneZones.tsx` é lista textual, inimigos não clicáveis.
- **[F]** `CreateScreen.tsx`: wizard `STEPS = ["O Mundo","Origem","Vocação","Região","Identidade"]`
  (`:23`); cartas `role="radiogroup"` com `aria-pressed` num `<button class="card__name card__select">`
  **dentro** de `.card` — a área clicável efetiva é o botão, não o cartão inteiro, enquanto `.card:hover`
  (`styles.css:295`) sugere clique no todo. **Hipótese direta** para o relato de "click/seleção imprecisa";
  confirmar em captura e por `elementFromPoint`.
- **[F]** `styles.css`: 22 ocorrências de `:hover`; `:focus-visible` global (`:140`) mais exceções
  pontuais; 5 usos de `transition: all`; durações hard-coded (0.12s/0.15s/0.16s/0.18s/0.2s/0.3s/0.4s/0.55s);
  um único token de easing `--ease`; zero tokens de duração/elevação/estado; `.worldmap__node` com
  `cursor: default` e `:disabled` (`:1123`) — nós de mapa sem affordance de clique consistente.
- **[F]** `App.tsx:743-837`: `AnimatePresence mode="wait"` com fade 0 → 1 entre telas; sem preservação de
  scroll/foco entre `play` ↔ `account`.
- **[F]** Fixture de captura: `web/e2e/fixtures.ts` (`DeterministicBackend`, `gameState()`) intercepta a API
  e serve estado com `combat.active=false`, `enemies=[]`, `cards=[]`. **Não** tem handler de
  `/game/combat-simulator`. Para estados de combate, a captura deve (a) injetar um `GameResponse` de combate
  via `page.route` dentro do próprio spec de diagnóstico (copiando a forma de `gameState()` sem editar
  `fixtures.ts`), ou (b) usar a API real em modo `RPG_FORCE_MOCK=1` com `CombatSimulatorScreen`/`POST
  /game/combat-simulator` (SPEC-090: modo `combat_simulation` não chama LLM). **[R]** (b) como fonte de
  verdade visual, (a) para casos determinísticos de borda (alvo morto, Entropia insuficiente).
- **[F]** `web/playwright.config.ts`: `testDir ./e2e`, `retries: 0`, `reducedMotion: "reduce"` por padrão,
  Chromium local ou `RPG_BROWSER_EXECUTABLE`, `webServer` Vite em `127.0.0.1:4173`, locale `pt-BR`. O
  diagnóstico precisa sobrescrever `reducedMotion` por teste (`test.use({ reducedMotion: ... })`).

### 3.3 Script de captura (assinatura e contrato)

```ts
// web/e2e/diagnostics/spec201-capture.spec.ts  (@spec201)
type Shot = { surface: string; state: string; viewport: "1440x900" | "1280x800"; fixture: string };
// saída: docs/spec201/capturas/{viewport}/{surface}-{state}.png  (caminho relativo à raiz do repo)
// estados mínimos: default, hover (page.hover), focus (keyboard.press Tab), pressed (mouse.down sem up),
// selected, disabled, loading, error, combat-active, combat-card-armed*, level-up, death, map-fog, codex-secret-locked
// (*armed só se existir na UI atual; senão registrar "ausente" na matriz)
```

- Rodar com `cd web && npx playwright test e2e/diagnostics --grep @spec201` (+ `RPG_BROWSER_EXECUTABLE`
  se necessário). **Não** entra em `npm run e2e`/CI obrigatório; evita atualizar baselines por diferença de
  fonte/GPU (**[F]** `visual-surfaces.spec.ts` já limita snapshots a Linux pinado).
- Determinismo: relógio fixo, `EmberField` pausado por `matchMedia`/`reducedMotion` quando o estado não
  depende dele; um shot extra "ember-on" documenta o fundo.
- Dados de fixture sem segredo real: nomes e fatos fictícios; qualquer estado `secret` é construído com
  texto sentinela (`SEGREDO_SENTINELA_XYZ`) para o teste de DOM (§3.5).

### 3.4 Esqueleto da matriz (linhas semente; a execução confirma, corrige e completa)

Todas as linhas abaixo são **[H]/[R] a validar com captura**, nenhuma é decisão.

| ID | Tela | Interação | Problema atual | Efeito proposto | Propósito | Pri | A11y | Perf | Risco | Critério |
|---|---|---|---|---|---|---|---|---|---|---|
| M01 | Create | selecionar raça/classe/região | clique só no botão interno; hover sugere o cartão todo [F] | hitbox no cartão inteiro + halo de foco + indicador de selecionado persistente | affordance | P0 | `aria-pressed` + foco visível sem hover | CSS puro | baixo | clique em qualquer ponto do cartão seleciona; selecionado visível em `reduce` |
| M02 | Create | avançar passo do wizard | corte seco entre passos; stepper `.wizard__step` sem indicador deslizante | transição curta de painel + indicador de passo | transição | P1 | `aria-current=step` mantido | opacity/transform | baixo | foco vai ao título do passo; sem perda de seleção |
| M03 | Play/StoryLog | nova narração | todo bloco repete fade+blur; typewriter sobre texto já pronto | manter fade só para o bloco novo; remover blur em histórico; sem animação em reload | consequência | P1 | `aria-live=polite` só na mensagem nova | evitar blur em lista longa | médio (leitura) | histórico carregado sem animação; 1 anúncio por turno |
| M04 | Play/composer | enviar ação | feedback de pendente restrito a `.thinking`; botão sem estado `pending` | estado `pending`/`disabled` no composer + rótulo de fase SSE | compromisso | P0 | `aria-busy`, texto de fase | CSS | baixo | enviar bloqueia reenvio e mostra fase; erro reativa o botão com texto |
| M05 | Hud | trocar aba | sem indicador de seleção animado; auto-troca de aba ao entrar/sair de luta | indicador persistente (`layoutId`) ; **[R]** não forçar troca sem aviso | transição | P0 | setas ←/→ no `tablist` | layout leve | médio | aba ativa inequívoca em `reduce`; troca automática anunciada |
| M06 | Hud/Combate | armar carta e escolher alvo | `<select>` + botão; sem estado armado, sem Esc | previsto SPEC-205 (ver §3.6) | preparação | P0 | Esc, Enter, foco | transform | médio | só registrar problema aqui |
| M07 | Hud/Combate | custo/limite de carta | só `title=`, ilegível em toque/teclado | tooltip/painel focável com custo real, frequência, razão de indisponível | affordance | P0 | focável, não só hover | CSS | baixo | motivo de `disabled` visível por texto |
| M08 | Play | dano em Vitalidade | `barhit` existe (`styles.css:648`); `shake` global | manter feedback de barra; chip de delta textual | consequência | P0 | texto equivalente | CSS | baixo | delta mostrado sem depender de animação |
| M09 | Hud/Mapa | selecionar/viajar | `cursor: default` em nós; fog só por opacidade | cursor/halo em nó viajável; fog também por texto/ícone | affordance/revelação | P1 | foco no nó, rótulo de fog | CSS/SVG | baixo | nó não-viajável explica por quê; sem tooltip com spoiler |
| M10 | Hud/Codex | abrir categoria/ficha | sem estado revelado vs bloqueado visual consistente | revelação sutil só ao descobrir; bloqueado sem DOM do conteúdo | revelação | P1 | `aria-label` genérico no bloqueado | troca direta | **alto** (spoiler) | busca de `SEGREDO_SENTINELA_XYZ` no DOM = 0 |
| M11 | Overlay | LevelUp/Death | `motion.div` ok; `lvl-pulse` infinito no cartão | pulso só no item sugerido; parar em `reduce` | consequência | P2 | foco preso no modal | CSS | baixo | `Esc`/foco retornam à origem |
| M12 | Shell | fundo `EmberField` | canvas contínuo; CSS oculta mas JS pode seguir [H] | pausar em aba oculta/`reduce`; custo medido | atmosfera | P3 | decorativo `aria-hidden` | medir CPU | baixo | 0 frames em `reduce`/background |
| M13 | Auth/Save/Account | submit e erro | `role=alert/status` só em Account; Auth/Save a verificar | padronizar loading/erro/vazio | compromisso | P1 | `role=status/alert` | — | baixo | todo submit tem estado `loading` e `error` anunciados |
| M14 | Retrato/Arte | geração/quote | estados de espera de arte dependem de CSS próprio | skeleton neutro, sem informação mecânica na imagem | revelação | P2 | `alt` obrigatório | lazy | médio | imagem nunca carrega número/regra |

### 3.5 Segurança de informação (invariante da matriz)

Toda proposta de efeito precisa declarar: o que a animação/tooltip/hover revela, e provar que não antecipa
conteúdo `hidden/secret` (DOM, atributos `title/alt/aria-label/data-*`, `src` de imagem, `prefetch`,
`<link rel=preload>`). **[R]** o teste de aceite é: com fixture que contém um item `secret`/não descoberto
com texto sentinela, `page.content()` e todas as requisições de rede capturadas não contêm o sentinela nem
o `src` da arte do item.

### 3.6 Pontos de efeito previstos (R8; sem proposta de implementação)

| Superfície futura | Gatilho real | Função | Risco/observação |
|---|---|---|---|
| Shell SPEC-204: abas, split↔full, resize | seleção de aba; `combat.active` | transição | draft do chat e scroll preservados; sem terceira coluna **[D]** |
| Combate SPEC-205: arma→mira→executa | clique em carta; `valid_targets` | preparação/compromisso | feedback de UI independe do LLM; sem confirmação repetida **[D]** |
| Combate: entrada/saída de encontro | `combat.active` true/false; `ConflictSummary` | transição/consequência | XP/números só na UI, não na prosa **[D]** |
| Combate: dano/status/reação | `ActionResponse`/`reactions` do backend | consequência | texto equivalente; sem shake sob `reduce` |
| Menu Deck/Personagem SPEC-209 | preparar cartas fora de luta | preparação | só dados canônicos |
| Menu Mapa/viagem SPEC-210 | `onTravel`, fog | revelação/transição | tooltip sem spoiler |
| Menu Codex/Bestiário/dossiês SPEC-211 | descoberta, fato vs rumor | revelação | arte secreta fora do DOM até descoberta |

## 4. Plano passo a passo

### Etapa 1 — Congelar baseline e ambiente (sem produto)
1. **Verificação (não é TDD de produto):** `git rev-parse HEAD` registra o commit auditado; `git status`
   não pode mostrar mudança em `web/src/**` ao final. Registrar versões (`node -v`, `npx playwright
   --version`, Chromium usado, SO).
2. `cd web && npm run build` registra tamanho de chunks (R9).

### Etapa 2 — Script de captura (teste primeiro)
1. **Teste** do próprio script: asserta que cada `Shot` listado produz PNG não vazio, em ambos os
   viewports, e que o sentinela secreto não aparece no DOM capturado (§3.5).
2. **Implementação:** `spec201-capture.spec.ts` com fixtures (a)/(b) de §3.2; `test.use({ viewport,
   reducedMotion })` por bloco.
3. **Verificação:** `cd web && npx playwright test e2e/diagnostics --grep @spec201` verde; PNGs em
   `docs/spec201/capturas/**`.

### Etapa 3 — Inventário e estados (R1, R6)
Percorrer `App.tsx`, `PlayScreen.tsx`, `Hud.tsx` e cada componente de R1; preencher tabela componente×estado
com evidência (captura ou trecho). **Verificação:** nenhuma célula sem `ok/parcial/ausente`.

### Etapa 4 — Medições (R9, R10)
Medir com Playwright/Chromium DevTools (`performance.measure`, `page.evaluate`, trace opcional): custo de
renderização de histórico longo (ex. 60 mensagens) com e sem `filter: blur`; CPU ocioso com `EmberField`;
tamanho do bundle. Rodar com 3 repetições e reportar min/mediana/max. Auditoria a11y: `@axe-core/playwright`
(**[F]** já é devDependency, `web/package.json:24`; não adicionar
dependência). **Verificação:** `medicoes.md` com comandos copiáveis.

### Etapa 5 — Matriz, atrito, gaps, previstos
Escrever `matriz-efeitos.md` seguindo R2–R5, R8, R11, §3.4 (linhas semente confirmadas ou removidas, novas
adicionadas). **Verificação:** checklist de §5; revisão por pares do documento (Sol, não obrigatória).

### Etapa 6 — Fechamento
`git diff --stat` mostra só `docs/spec201/**` e `web/e2e/diagnostics/**`. Handoff curto para SPEC-208 com a
lista P0 e as decisões em aberto.

## 5. Critérios de aceite

- [x] `docs/spec201/matriz-efeitos.md` existe com as colunas exatas de R2 e ≥ 25 linhas, cada uma com
      problema atual evidenciado (captura/arquivo:linha/medição) e critério de aceite observável (R11).
- [x] Toda linha declara função do arsenal (R3); linhas puramente cosméticas marcadas `opcional` (P2/P3).
- [x] Seção "o que NÃO animar" presente e justificada.
- [x] Lista de atrito sem animação com ≥ 10 itens e evidência (R4), incluindo o diagnóstico da hitbox dos
      cartões do `CreateScreen` confirmado ou refutado por `elementFromPoint`.
- [x] Gaps de design system (R5) citam tokens existentes e os que faltam, com contagem real de
      `transition: all`, durações e cores hard-coded obtida por `grep`.
- [x] Tabela componente×estado completa (R6) para todos os componentes de R1.
- [x] Capturas em 1440×900 e 1280×800 geradas pelo script versionado, `INDEX.md` com comando de
      reprodução; baseline `reduce` e `no-preference` para estados com motion.
- [x] Medições (R9) com método e variância; tudo não medido marcado `não medido`.
- [x] Auditoria de reduced-motion/a11y (R10) com achados classificados [F] vs [H].
- [x] Seção de arte contextual vs informação mecânica (R13) com IDs canônicos e regra de visibilidade.
- [x] Ordenação da matriz respeita R14 (nenhuma transição cosmética em P0) e lista confirmações repetitivas removíveis.
- [x] Referências do pacote citadas como comportamento, sem dependência nova (R15).
- [x] Seção de pontos de efeito previstos (R8) cobrindo SPEC-204, 205, 209, 210, 211.
- [x] Teste do sentinela secreto (§3.5) passa: DOM e rede sem o texto/`src` sentinela.
- [x] `git diff` não toca `web/src/**`, `api.py`, `state.py`, `evals/`. (`specs/index.yaml`: só o campo `status` desta spec foi atualizado por instrução da execução.)
- [x] `cd web && npm run build` verde; `uv run pytest` verde (suíte offline inalterada).
- [x] Documento declara a correção "não existe tela de mapa; é aba do Hud" e "Bestiário está no Codex".

## 6. Smoke

Offline, sem provider real e sem custo:

1. `cd web && npm run build`.
2. `cd web && npx playwright test e2e/diagnostics --grep @spec201` com fixtures determinísticas; abrir 3
   PNGs aleatórios do `INDEX.md` e conferir viewport/estado.
3. Opcional (b): `RPG_FORCE_MOCK=1 uv run uvicorn api:app --port 8000` + `npm run dev`, abrir o simulador de
   combate (`CombatSimulatorScreen`) para os shots de combate; nenhuma chamada LLM.
4. Provider real: **não** usar. Qualquer captura com LLM real exigiria autorização e teto próprios (fora desta spec).

## 7. Riscos & compatibilidade

- **Saves/API:** nenhuma mudança. Sem migração.
- **Merge com SPEC-197 (em progresso):** há mudanças locais não commitadas em `App.tsx`/`styles.css` de
  outra frente; esta spec **não** os altera. Auditar o HEAD commitado e anotar `dirty` se o working tree
  divergir (capturas devem indicar o commit/estado usado).
- **Matriz virar lista de desejos:** mitigada por R2 (problema evidenciado) e R3 (função declarada).
- **Fixtures de combate incompletas** podem esconder estados reais: por isso a opção (b) via simulador.
- **Capturas dependem de fonte/GPU:** por isso ficam fora do gate obrigatório e não viram baseline.
- **Arsenal-base provisório [D7]:** `referencias/ARSENAL_VISUAL.md` não é a seleção original do dono; o
  catálogo é usado só como vocabulário, e itens de origem desconhecida ficam marcados.
- **MockLLM:** irrelevante para a matriz; texto de narração nos shots é fixture.

## 8. Pontos de decisão do dono

- **Q1 — Local das capturas.** Default recomendado: versionar PNGs em `docs/spec201/capturas/` (≈ 40–60
  arquivos). Alternativa: gerar sob demanda e versionar só o `INDEX.md` (menor repo). Impacta tamanho do histórico.
- **Q2 — Arsenal original.** Default: prosseguir com o arsenal-base e anexar um adendo
  `ARSENAL_ORIGINAL_IMPORTADO.md` quando o dono enviar a seleção; a matriz não bloqueia por isso
  (**[D7]**/`PENDENCIA_ARSENAL_ORIGINAL.md`).
- **Q3 — Nível mínimo de medição de perf.** Default: 3 repetições, máquina de desenvolvimento do dono,
  sem dispositivo móvel. Alternativa: incluir throttling de CPU 4× como proxy de máquina fraca.
- **Q4 — Escopo de a11y.** Default: auditoria funcional (teclado, foco, `aria-live`, contraste) sem leitor
  de tela real; teste com NVDA/VoiceOver só se o dono quiser.

## 9. Evidência requerida

- Hash do commit auditado e `git status` ao fim (limpo em `web/src`).
- Saída de `npm run build` (tamanhos de chunk) e de `npx playwright test e2e/diagnostics --grep @spec201`.
- `docs/spec201/capturas/INDEX.md` com comando de reprodução e lista de PNGs.
- `docs/spec201/medicoes.md` com dados brutos, repetições e máquina.
- `grep` reproduzível das contagens citadas em R5 (hover, `transition: all`, durações, cores literais).
- Handoff para SPEC-208: top P0, decisões em aberto, restrições de a11y e de spoiler.

## 10. Execução (2026-10-16)

- **Entregáveis:** `docs/spec201/{matriz-efeitos,atrito-sem-animacao,gaps-design-system,medicoes,README}.md`, `capturas/INDEX.md` + 90 PNGs (45 por viewport), `dados/*.json`, `web/e2e/diagnostics/spec201-capture.spec.ts`. Evidência e achados: `docs/spec201/README.md`.
- **Defaults de decisão usados:** Q1 PNGs versionados (90 arquivos, ~14 MB, acima da estimativa de 40–60 por incluir `--motion` e 2 viewports) · Q2/D7 arsenal-base como referência provisória (sem adendo `ARSENAL_ORIGINAL_IMPORTADO.md`) · Q3 3 repetições, máquina de desenvolvimento, sem throttling · Q4 auditoria funcional sem leitor de tela real.
- **Desvios:** (1) o spec de captura se auto-pula sem `RPG_SPEC201=1` (para não entrar no gate F01–F16/`test:e2e`); o comando da spec passa a exigir essa variável. (2) Estados de combate/morte/level-up via injeção de `GameResponse` no próprio spec (opção (a)); a opção (b), simulador real com `RPG_FORCE_MOCK=1`, não foi usada. (3) "Matriz ≥25 linhas": 36 entregues. (4) `web/package.json` não foi alterado. (5) O bundle sem `motion` não foi medido (exigiria mexer em `web/src`).
- **Verificação:** `npm run build` verde (481 módulos); captura 16 passed/2 skipped; jornadas F01–F16 16/16; `uv run pytest` (offline) sem falhas.
