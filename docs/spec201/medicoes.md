# SPEC-201 — Medições e auditoria de reduced-motion/a11y (R9/R10)

Commit auditado `afe9894` (working tree limpo em `web/src`). Tudo que **não** foi medido está marcado `não medido`.

## Ambiente

| Item | Valor |
|---|---|
| Máquina | Windows 11 Home, Intel Core i5-12450HX, 15,7 GB RAM (máquina de desenvolvimento do dono; Q3 default) |
| Navegador | Chromium (`chrome-151.0.7922.71`, `~/.agent-browser/browsers`), via `@playwright/test` 1.55.1 |
| Node | v24.19.0 · `motion` 12.42.0 |
| Display | viewport 1440×900; taxa de quadros do Chromium headless ≈ 144 Hz (mediana de quadro ≈ 7 ms) |
| Throttling | nenhum (Q3: 4× CPU não aplicado → `não medido` para máquina fraca/mobile) |
| Fonte dos dados | `web/e2e/diagnostics/spec201-capture.spec.ts`, teste "axe + reduced-motion + medicoes" → `dados/medicoes.json` (bruto) |

Reprodução: `cd web && RPG_SPEC201=1 npx playwright test e2e/diagnostics --grep @spec201 --workers=1 -g medicoes`.

## 1. `filter: blur` animado no StoryLog (histórico longo)

Método: fixture com 60 mensagens (≈240 caracteres cada); `reducedMotion: no-preference`; sonda `requestAnimationFrame` registra o tempo entre quadros; janela = 1,5 s após abrir o save (montagem), depois rolagem programática do `.story` do fim ao topo. 3 repetições por condição; "sem blur" injeta `.msg{filter:none!important}`.

| Condição | Janela | Quadros (n) | p95 (ms) | máx (ms) | Quadros >33 ms |
|---|---|---|---|---|---|
| com blur | montagem | 428 / 414 / 421 | 13,9 / 13,9 / 13,9 | 27,8 / 48,6 / 27,6 | 0 / 1 / 0 |
| sem blur | montagem | 441 / 415 / 426 | 13,9 / 13,9 / 13,9 | 21,0 / 27,8 / 20,9 | 0 / 0 / 0 |
| com blur | rolagem | 60 / 62 / 61 | 7,1 / 7,1 / 7,0 | 7,2 / 7,1 / 7,1 | 0 / 0 / 0 |
| sem blur | rolagem | 60 / 61 / 60 | 7,1 / 7,1 / 7,1 | 7,1 / 7,3 / 7,1 | 0 / 0 / 0 |

**Leitura [F]:** nesta máquina o `blur` do `StoryLog` não degrada a rolagem e o p95 é idêntico; o único quadro longo (48,6 ms; antes 34,7 ms em outra execução — a posição varia) ocorreu **só com blur** na montagem, mas 1 evento em 3 repetições é **inconclusivo** (variância dentro do ruído). **[H]** em hardware mais fraco o custo cresce (60 `filter` simultâneos na montagem): `não medido` (sem throttling). Mesmo assim o histórico recarregado não deveria animar (matriz M09), o que elimina a hipótese.

## 2. `EmberField` ocioso (canvas contínuo)

Método: CDP `Performance.getMetrics` (`TaskDuration`, `ScriptDuration`) em 3 s de ociosidade na tela de saves, 3 repetições por condição.

| `prefers-reduced-motion` | `TaskDuration`/3 s (min · mediana · máx) | `ScriptDuration`/3 s | `.ember-canvas` |
|---|---|---|---|
| `no-preference` | 208,5 · **210,1** · 246,2 ms | 47,6 · 49,0 · 54,4 ms | `display:block` |
| `reduce` | 73,0 · **76,4** · 98,6 ms | 8,2 · 8,6 · 9,7 ms | `display:none` |

**Diferença [F]:** ≈ +134 ms de thread principal a cada 3 s (≈ +4 % de uma thread; a execução anterior deu ≈ +123 ms) e ≈ +40 ms de script, só pelo canvas. A sonda de `rAF` da própria página rodou a ~145 quadros/s em ambas as condições (ela mesma é um `rAF`), portanto **não** distingue o canvas; a métrica válida é a de `TaskDuration`. Medição de FPS do canvas isolado e de GPU: `não medido`.

**`EmberField` em `reduce` [F]:** `EmberField.tsx:8-9` retorna antes de agendar o `rAF` (confirmado pela queda de script 49→8,6 ms e pelo `display:none` do CSS). **[H] refutada**: o JS não segue rodando. Lacunas: a checagem é só na montagem (não escuta mudança da preferência) e **não** pausa com a aba oculta (`visibilitychange`; Chromium já limita `rAF` em aba oculta, mas o laço continua agendado) — `não medido` o custo em aba oculta.

## 3. Peso do pacote `motion` (R9)

`npm run build` (Vite 5.4.21): `index-C9FagaNt.js` **411,24 kB / 130,63 gzip** (chunk principal), `index-DjT_xkor.js` 8,67 kB (3,59 gzip), `web-DXKVgxIg.js` 0,87 kB, CSS 61,74 kB (13,00 gzip), 481 módulos.
Proxy do custo de `motion`: bundle isolado com `esbuild --bundle --minify` apenas de `motion`, `AnimatePresence`, `MotionConfig` (`motion/react`, React externo) = **125,5 kB min / 42,7 kB gzip**, ≈ 30 % do chunk principal. O build **sem** o pacote (remover os 7 imports) **não foi executado** — exigiria alterar `web/src` (proibido nesta spec) — `não medido` o delta real do Vite; o número acima é um limite superior do import completo, sem tree-shaking por feature (`LazyMotion`).

## 4. Reduced motion (R10)

Método: `reducedMotion: "reduce"` (padrão do projeto), varredura de `getComputedStyle(...).animationName` e comparação com o bloco `styles.css:825-828`.

| Achado | Classe | Evidência |
|---|---|---|
| Nenhum elemento mantém `animation` CSS sob `reduce` (`movingInReduce: []`) | [F] | `dados/medicoes.json` |
| `MotionConfig reducedMotion="user"` (`App.tsx:714`) remove transformações do `motion`, mas **não `opacity`** → o fade de 0,55 s do `StoryLog` e o fade entre telas permanecem | [F] (documentação do Motion) / [H] visualmente | `StoryLog.tsx:69-73`; `App.tsx:766-860` |
| Bloco CSS reduz `transition-duration` a 0,01 ms, **não** `transition: none`; mudanças de estado seguem instantâneas | [F] | `styles.css:825-828` |
| `EmberField` desligado por JS e CSS | [F] | seção 2 |
| Foco visível **sem hover**: `:focus-visible` global 2 px `--accent` (`styles.css:140`); capturas `*-focus.webp` mostram o anel | [F] | `capturas/*/saves-focus.webp`, `combat-card-focus.webp`, `create-card-focus.webp` |
| `aria-live`: só a região de voz (`PlayScreen.tsx:231`) e `.thinking` (`StoryLog.tsx:42`, só enquanto pensa); **narração nova não é anunciada** (`section.story` sem `aria-live`/`role=log`) | [F] | `dados/medicoes.json → liveRegions, storyAttrs` |
| `tablist` do Hud sem teclado de abas (setas não mudam a seleção) | [F] (era [H] na spec) | `dados/tablist-arrow-keys-*.json` |
| Contraste `--faint`/`--muted` sobre `--bg` | `não medido` com ferramenta; axe `wcag2a,wcag2aa` → **0 violações** na tela de jogo (fixture) | `dados/medicoes.json → axeViolations: []` |
| Modais sem gerência de foco | [F] | `atrito-sem-animacao.md` A09 |
| `behavior: smooth` | só em `Hud.tsx:407` (`scrollIntoView` da busca da crônica), sem checar `reduce` | [F] |

## 5. Tamanhos de alvo (px, mínimos medidos em 1440×900)

`.iconbtn` 58×35 · `.tab` 82×34 · `.btn` 59×48 · `.codex-cat` 89×30 · `.worldmap__node` 68×22 (`cursor:default`) · `.combat-card__play` 201×30 · `.actionchip` 60×36. `.msg__cost-button`: `não medido` (fixture sem custo). Todos ≥24 px nos dois eixos, exceto a altura do nó de mapa (22 px, WCAG 2.2 AA 2.5.8).

## 6. Layout do combate (fixture de combate)

A 1440×900: `tactical-dock` altura 414 px, `section.story` altura **99 px**; a 1280×800: dock 368 px, story 99 px (`dados/combat-card-states-*.json`). A narração fica ilegível com o dock aberto (`capturas/1440x900/combat-active.webp`).

## 7. Segurança de informação (sentinela, §3.5 da spec)

Fixture com nó de mapa **não visitado** `Cripta SEGREDO_SENTINELA_XYZ` (nome e `lore_seed`). Resultado (`dados/sentinel.json`): **DOM = limpo**, **atributos (`title/alt/aria-label/data-*`) = limpos**, **rede = a resposta de `/data/map` contém o sentinela** (o cliente só mascara na renderização: "???"). O teste de captura assere DOM/atributos limpos (passa) e **registra** o vazamento de rede como achado (M23). O Codex só lista o que o servidor devolve; fixture sem item secreto no payload → nada a mascarar.

## Não medido (resumo)

CPU 4×/dispositivo móvel (Q3) · FPS/GPU do canvas isolado · custo em aba oculta · bundle real sem `motion` · contraste por ferramenta dedicada · leitor de tela real (Q4: NVDA/VoiceOver não usados) · `.msg__cost-button` · Account com dados reais (fixture sem `/account/*`).
