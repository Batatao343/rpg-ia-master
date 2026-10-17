# SPEC-208 — Design system de efeitos: evidência

Implementação por iterações verticais sobre `motion` + CSS (sem dependência nova, sem som, sem GSAP/WebGL).
Matriz de origem: `docs/spec201/matriz-efeitos.md` (linhas `M01`–`M36`). Arsenal: base provisório (D7), como a SPEC-201.

## R1 — pré-condições (registradas no início)
`specs/index.yaml` no HEAD `ceadfe1`: SPEC-201 `done`, SPEC-204 `done`, SPEC-205 `done`. Nomes reais usados:
`web/src/workspace/{Workspace,ChatSurface,ContextSurface,RovingTablist}.tsx`, `web/src/combat/{Arena,TargetChip}.tsx`,
`web/src/components/{CardHand,CodexTab,WorldMap,StoryLog,CreateScreen,LevelUpModal,EmberField}.tsx`.

## O que mudou
- `web/src/design/` (novo): `tokens.css` (R2), `tokens.ts` (espelho, R3), `killswitch.ts` + `motion.ts` (`useEffectsEnabled`,
  `transitionFor`, R10), `primitives.tsx` (`Pressable`, `Selectable`, `Reveal`, `ArrivalLi`; único arquivo novo que importa `motion`, R4),
  `effects.registry.ts` (18 efeitos com os 12 campos + `sound: null`, R1/§3.3; `chat.entry` saiu na revisão — ver "rejeitados").
- Tokens (aditivos, nenhum legado alterado): `--dur-instant/fast/base/slow` = 80/140/240/420 ms; `--ease-out` (alias de `--ease`),
  `--ease-in-out` `(0.65,0,0.35,1)`, `--ease-spring-soft` `(0.34,1.3,0.64,1)`; `--elev-0..3`; `--state-hover/pressed/selected/armed/disabled`
  (`color-mix` sobre `--accent`/`--line-soft`); `--focus-ring`; e os gaps da SPEC-201: `--danger-dim` (antes inexistente, o CTA do combate perdia o fundo) e `--ink-soft`.
- `styles.css`: `@import` dos tokens; bloco `.btn` migrado para tokens; base `.btn` legível (fim do botão "Depois" ilegível do LevelUp: `btn--ghost` + fundo/cor base);
  bloco final "SPEC-208" com os efeitos de CSS. `workspace.css`: a transição do split usa `--dur-base`.
- Componentes tocados: `RovingTablist` (indicador `Selectable` com `layoutId` por tablist), `StoryLog` (nenhuma entrada anima, sem `blur`),
  `ChatSurface` (`Pressable` com `aria-busy`/"Enviando…"), `CreateScreen` (cartão inteiro clicável), `CardHand`/`TargetChip`/`WorldMap` (atributos `data-effect*`),
  `CodexTab`/`BestiarioTab` (chegadas do servidor), `EmberField` (R9/M25), `LevelUpModal` (M27).
- Kill switch: `?effects=off` ou `localStorage["rpg.effects"]="off"` marca `<html data-effects="off">` e zera animações/transições (R10).
- `MotionConfig reducedMotion="user"` e o bloco global `@media (prefers-reduced-motion: reduce)` ficaram intactos (teste `R5` em `web/tests/design.test.mjs`).

## Efeitos entregues × matriz × teste (registry)
| id | matriz | teste (`e2e/effects.spec.ts`) | custo |
|---|---|---|---|
| ctrl.hover / ctrl.press | M27 | `ctrl.hover`, `ctrl.press` | CSS |
| ctrl.focus | M01 | `ctrl.focus` (+axe) | CSS |
| ctrl.pending / chat.pending | M08 | `ctrl.pending` (2 testes: pendente + erro), `chat.pending` | CSS |
| choice.select | M01 | `choice.select` (hitbox por `elementFromPoint`, persistência, teclado, axe) | CSS |
| tab.indicator / tab.content | M19 | `tab.indicator` (clique+setas+axe), `tab.content` | layout leve / opacity |
| split.toggle | M13 | `split.toggle` | colunas do contêiner |
| card.hover / card.blocked / card.arm | M15 / M16 / M14 | idem (armado: aria-pressed, Esc, teclado, axe) | transform/shadow |
| target.valid | M14 | `target.valid` (+axe) | CSS |
| card.resolve / hit.feedback | M14 / M30 | só após resposta do servidor; barra por `scaleX` (não `width`) | CSS/transform |
| codex.entry.reveal | M24 | `codex.entry.reveal` (R7: DOM, `<link>` e rede sem a sentinela) | opacity |
| map.marker | M22 | `map.marker` (R7: fog sem nome/lore no DOM) | CSS |
| ember.pause | M25 | `ember.pause` (reduce, aba oculta; pausa em combate) | canvas 30 fps, teto de 40 partículas |

Playwright: projeto novo `chromium-motion` (`reducedMotion: "no-preference"`, só `effects.spec.ts`); o projeto `chromium` roda o mesmo arquivo em `reduce`
(estado final equivalente). Viewports 1440×900 e 1280×720; axe sem serious/critical nos estados foco/pendente/erro/armado/mira/codex/mapa/abas/criação.

## Medições
Bundle (`npm run build`, gzip nível 6, soma dos assets; baseline = HEAD `ceadfe1` antes das mudanças; final = após a revisão Sol):
| arquivo | baseline | final | delta |
|---|---|---|---|
| JS (3 chunks) | 147 916 B (≈144,5 KB) | 149 617 B (≈146,1 KB) | **+1 701 B** (teto +15 KB) |
| CSS | 14 361 B (≈14,0 KB) | 15 453 B (≈15,1 KB) | **+1 092 B** (teto +3 KB) |
Sem dependência nova (`package.json` inalterado).

Frame/long task — critério R8 em absoluto, contra o **build** (`vite preview`), CDP CPU 4×, viewport 1440×900, fluxos
`perf: 4x CPU — criação` (hover e seleção de raça/classe/região) e `perf: 4x CPU — chat … e combate` (3 ações com
streaming; armar carta, Esc, 4 abas). Cada fluxo mede efeitos **desligados** (kill switch real: `localStorage` + evento
`storage`, desliga CSS e primitivos JS) e **ligados**, depois de um aquecimento descartado. Reproduzir:
`cd web && npm run build && RPG_E2E_SERVER=preview npx playwright test e2e/effects.spec.ts -g perf --project=chromium-motion`.
Monitor da máquina de medição = 144 Hz (quantum de frame 6,9 ms: 7 / 13,9 / 20,8 ms = 1 / 2 / 3 vsyncs).

5 execuções finais (bruto em [`evidence/perf-runs.jsonl`](evidence/perf-runs.jsonl)), efeitos **ligados**:
| fluxo | frame p90 (ms) | frame p95 (ms) | long tasks > 50 ms |
|---|---|---|---|
| criação | 7,1 ×5 | 7,1 ×4 · 13,7 | 0 em 5 |
| chat | 13,8 ×4 · 7,1 | 13,9–14,0 | 0 em 5 |
| combate + abas | 7,1–13,7 | 13,9–14,0 | 0 em 5 |
Com os efeitos desligados o p95 fica em 7,1–13,9 ms e também 0 long task. Mais 4 execuções do fluxo chat+combate durante a
revisão: 0 long task e p95 ≤ 14,0 em todas. Antes da última rodada de correções, 2 de ~8 execuções tiveram **uma** long
task de 51–59 ms no combate com efeitos ligados; não reapareceu nas 9 execuções finais (registrado por honestidade: o
fluxo está perto do limite de 50 ms sob 4×).

O que a revisão Sol encontrou e corrigiu (medido por variantes A/B no mesmo fluxo):
- **Animações contínuas na tela de combate** (pulso do `combat-veil`, `throb` da bandeira "Em combate" e do ponto da aba):
  com QUALQUER uma delas ativa, o p90 dobrava (7 → 14 ms) e surgiam long tasks de 50–90 ms ao armar carta/trocar aba;
  sem elas, 0 long task. As "long tasks com efeitos desligados ao montar aba" do relatório anterior vinham daí, não do shell
  da SPEC-204. Agora: véu estático com uma entrada curta (`opacity`), bandeira/ponto estáticos (a informação é texto/cor),
  farol do mapa parado em combate, alertas de HP baixo/Carga severa com 3 pulsos (R9: nada contínuo atrás do chat em combate;
  teste `R9: em combate nenhuma animação contínua…` via `document.getAnimations()`).
- **Transições fora de transform/opacity** no bloco SPEC-208 (`box-shadow`, `border-color`, `background`, `filter`, `width`
  da barra de Vitalidade): R8 pede só transform/opacity. Cor/sombra/borda agora trocam no ato; a barra usa `scaleX`; território
  disputado no mapa deixou de animar `box-shadow` em loop. Lint em `tests/design.test.mjs` (`R8: no bloco SPEC-208 só transform/opacity…`).
- **Fluxo de chat**: a fade do bloco novo (M09) + o fade de opacidade do botão ao desabilitar/reabilitar somavam ~1 vsync ao p95
  (20,8–27,7 ms vs 13,9 sem eles); a fade foi rejeitada e o botão só transita `transform` (pressionar).
- `Reveal` (Codex/Bestiário) virou animação CSS de compositor (sem `motion` JS `y`), decidida na montagem.
- Kill switch: `rpg.effects` mudado em outra aba agora vale sem recarregar (listener global de `storage`).

## Efeitos rejeitados / adiados (e por quê)
- `chat.entry` (fade do bloco novo, M09): medido — somava ~1 vsync ao p95 do chat sob 4×; o typewriter + cursor já mostram o que chega.
  M09 segue cumprido em "histórico/reload sem animação; sem `blur` em lista" (teste `M09: entradas do chat não animam…`).
- `passive.trigger`, `encounter.enter/exit`, `reaction.present` (presença animada): exigem payload/contrato novo do servidor ou mexem em layout de combate; ficam para a SPEC-209 (sem previsão no cliente — regra da própria spec).
- Linha de mira SVG (`target.valid` opcional): o destaque de alvo + rótulo textual já cobre a função (preparação) sem SVG por frame.
- `Reveal` no Bestiário/Mapa de entidades **não descobertas**: o cliente só recebe descobertas; o `/data/map` ainda entrega nome/`lore_seed` de nós em fog na REDE (M23) — correção é do servidor (SPEC-211), fora desta spec; o DOM segue limpo (testado).
- Screen shake, glare, parallax, shader/partículas novas, som, GSAP/Lottie: fora (§8 defaults).

## Decisões da §8 (defaults usados)
1. Teto +15 KB JS / +3 KB CSS: mantido (uso: +1,7 KB / +1,0 KB). 2. P2/P3 do arsenal: fora. 3. Dependência nova: não. 4. Som: não.
5. Arsenal-base como referência (matriz da 201). 6. Piso do reduced-motion: equivalência informativa total (opacidade/cor estáticas), sem movimento.

## Evidência de aceite (§6, vídeos)
Smoke §6 em três modos — criar (hover/seleção) → chat → split + abas → combate (armar, mira inválida/válida, Esc, executar) →
abas — gravado em [`evidence/smoke-normal.webm`](evidence/smoke-normal.webm), [`smoke-reduced.webm`](evidence/smoke-reduced.webm)
e [`smoke-effects-off.webm`](evidence/smoke-effects-off.webm) (0,9–1,3 MB cada) + capturas finais `.png`. Os `trace.zip`
(6–12 MB cada) não foram versionados; reproduzir com `RPG_EFFECTS_EVIDENCE=1 npx playwright test e2e/effects.spec.ts -g smoke --project=chromium-motion`
(os traces ficam em `web/test-results/`).

## Limites / pendências
- Medição de frame em máquina de 144 Hz; num monitor de 60 Hz o quantum é 16,7 ms e o critério p95 ≤ 16,7 equivale a "≥ 95 % dos
  frames no vsync". O gate absoluto só roda contra o build (`RPG_E2E_SERVER=preview`); contra o dev server (React dev) o teste é
  um alarme de regressão grosseira.
- Adiados por precisarem de servidor/contrato novo: `passive.trigger` (sem campo de gatilho no payload), `reaction.present`
  (M18 pede painel só com gatilho real do backend — hoje a reação é declarada junto da ação; SPEC-209), `encounter.enter/exit`
  (M36, P2 → §8.2). Linha de mira SVG: opcional, não feita.
- `/data/map` ainda envia nome/`lore_seed` de nós em fog na rede (M23, servidor/SPEC-211); o DOM segue limpo.

## Execução (2026-10-16, revisão Sol)
Ver [handoff da revisão](../../handoffs/SPEC-208-SOL-independent-review.md) para comandos e exit codes.
