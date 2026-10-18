# SPEC-216 — Mobile single-pane (uma superfície por vez)

> **Status:** `done`
> **Criada:** 2026-10-15 · **Atualizada:** 2026-10-15
> **Depende de:** SPEC-204 `done` (workspace), SPEC-205 `done` (mira direta), SPEC-212 `done` (gate desktop) (ordem final 2026-10-15)
> **Desbloqueia:** evidência mobile para SPEC-198 (ordem final 2026-10-15)
> **Origem:** pacote `proximas-specs/…`, prompt 14
> **EXECUTOR_MODEL:** `Terra` (≡ Sonnet, ver docs/planos/equivalencia-modelos-claude.md)
> **REVIEW_MODEL:** `Sol` (≡ Opus em contexto separado) · **REVIEW_REQUIRED:** `false`
> **EVAL_AUTHORING_REQUIRED:** `true` — eval de viewport mobile (320x568, 390x844, WebView) em Playwright; autoria em tarefa separada, antes da otimização de produto.

---

## 1. Contexto & Objetivo

[D] Mobile nunca divide chat + painel horizontalmente: uma superfície por vez (chat OU uma aba), troca rápida, retorno ao chat sem perder estado. Fase posterior ao desktop; não bloqueia o beta desktop (SPEC-212) nem a SPEC-198.

[F] Hoje o mobile é "desktop espremido": `web/src/styles.css` tem `@media (max-width: 900px)` que transforma `.hud` em gaveta fixa (`transform: translateX(100%)`, `.hud.is-open`), `@media (max-width: 480px)` (topbar quebra linha, `.actionbar` sticky com `env(safe-area-inset-bottom)`, input 16px) e `@media (max-width: 600px)` só para conta. `PlayScreen.tsx` controla a gaveta por `hudOpen/setHudOpen` e `.play.is-combat`. Combate (`CardHand`, `SceneZones`, `ReactionPrompt`) vive na coluna do chat. [F] Existem `web/android/` (Capacitor, SPEC-193), `web/src/native/{backPolicy,lifecycle,platform}.ts` e `web/src/voice/{controller,recorder,useVoiceInput}.ts` (SPEC-187). Não existe diretório `native/` na raiz.

[F→contrato] A SPEC-204 (R12) já define `effectiveMode(state, viewportPx)` em `web/src/workspace/workspaceModel.ts`: abaixo de 1100px não há `split` efetivo (alterna `chat`/`context`), e abaixo de 900px a gaveta atual pode permanecer **até esta spec**. Logo, 900–1100px já é single-pane pela 204; esta spec substitui a gaveta <900px e adiciona barra inferior, composer móvel e combate em tela própria.

[R] Objetivo: modo mobile single-pane que **reusa** o estado de workspace e o motor de combate da SPEC-204/205 (apenas outra apresentação), com combate em tela própria sem hover/drag.

## 2. Requisitos

- **R1** — Abaixo do breakpoint mobile (default **900px**, alinhado ao limite de gaveta da SPEC-204 R12; ver §8) o shell renderiza exatamente UMA superfície: chat ou uma das abas `ContextTab` da SPEC-204 (`codex|personagem|combate|bestiario|mapa`), decidida por `effectiveMode` (estendido, não duplicado). A gaveta `.hud` deixa de existir nesse intervalo. Teste: nenhuma viewport mobile tem duas superfícies visíveis simultaneamente.
- **R2** — Troca de superfície por barra inferior (alvos >=44px); voltar do Android (`web/src/native/backPolicy.ts`) retorna ao chat antes de sair/abrir confirmação. Swipe é opcional e nunca única via.
- **R3** — Estado de workspace (aba ativa/histórico em `workspaceReducer`, draft/scroll em `web/src/workspace/chatSessionStore.ts`, ação pendente em `pendingOperation.ts`) vem dos mesmos módulos da SPEC-204; proibido segundo estado ou lógica duplicada. Trocar superfície e voltar preserva draft, scroll e ação pendente (`web/src/pendingOperation.ts`).
- **R4** — Composer: com teclado virtual aberto o campo e o botão Agir permanecem visíveis (`visualViewport`/`dvh`, safe-area), sem sobreposição à barra inferior; input >=16px.
- **R5** — Voz (SPEC-187) utilizável no composer; fluxo Voz → Parar → transcript editável → Agir explícito preservado; microfone liberado ao trocar de superfície/background (comportamento já do controller).
- **R6** — Combate em tela própria: o início do encontro é narrado no chat ([D] "encontro começa e termina pelo chat"); ao receber a resposta com `combat.active` falso→verdadeiro (ação `combat_started` do reducer da SPEC-204), o chat exibe a narração e um selo/botão "Ir para o combate"; a troca automática para a superfície Combate ocorre após a narração ter sido renderizada (default §8 P4), com retorno rápido ao chat; ao encerrar, o desfecho aparece no chat e a superfície Combate mostra o resultado (R10 da 204). Sem dependência de hover ou drag.
- **R7** — Mira por toque: alternativa a todo hover/drag da SPEC-205 usando a **mesma** máquina `web/src/combat/useTargeting.ts` (`idle → aiming → submitting`): toque na carta seleciona, toque no alvo confirma, botão Cancelar explícito substitui Esc; tooltip de carta (R13 da 205) abre por toque longo ou botão "detalhes", nunca só por hover. Payload idêntico ao desktop (`card_id`, `target_id`, `ruptura`, `reaction_card_id`, `action_id`).
- **R8** — Reduced motion respeitado; foco vai ao título da superfície ao trocar; `aria-current` na aba ativa.
- **R9** — Sem overflow horizontal em 320x568 e 390x844; sem texto cortado; topbar não sobrepõe a barra inferior.
- **R10** — Mesmo comportamento na WebView Capacitor (AVD, cookies/CSRF inalterados, SPEC-193).
- **R11** — Zero mudança de API, de schema de save e de regras de combate.

### Fora de escopo
Segundo motor/regra de combate; app iOS; publicação Play (SPEC-198); novo conteúdo de abas (SPEC-209/210/211); streaming; tablet como alvo próprio (usa split desktop); billing.

## 3. Design técnico

- **Arquivos novos (propostos [H])**: `web/src/workspace/useMobileSurface.ts` (derivação sobre `WorkspaceState`/`effectiveMode` da SPEC-204, sem estado próprio além de transições de apresentação; função pura `mobileSurface(state, viewportPx) -> "chat" | ContextTab` exportada para teste Node); `web/src/components/MobileTabBar.tsx`; `web/src/components/MobileCombatScreen.tsx` (compõe os mesmos `CardHand`/`SceneZones`/`ReactionPrompt`); jornadas Playwright em tarefa de eval separada.
- **Alterados**: `web/src/components/PlayScreen.tsx` (apresentação por breakpoint; a gaveta `.hud` <900px é substituída pela superfície Personagem); `web/src/styles.css` (consolidar breakpoints 900/480/600 num conjunto mobile único com tokens); `web/src/native/backPolicy.ts` (voltar → chat).
- **State ownership**: workspace/aba/draft = SPEC-204; combate/mira = SPEC-205; ação pendente = `pendingOperation.ts`; voz = `voice/controller.ts`. Esta spec só adiciona apresentação.
- **Contrato de UI**: barra inferior com Chat + 5 abas; combate ativo mostra selo e abre Combate; modais de morte/level-up sobrepõem qualquer superfície.
- **Degradação**: sem `visualViewport` cai para `100dvh` + `env(safe-area-inset-bottom)`; sem swipe, só toque; sem microfone, botão de voz oculto (SPEC-187).
- **[H]** breakpoint por `matchMedia` com histerese para não remontar o chat ao girar a tela.

## 4. Plano passo a passo

### Etapa 0 — Eval (tarefa separada, EVAL_AUTHORING_REQUIRED)
Handoff para jornadas Playwright mobile (320x568, 390x844, emulação de teclado, touch, axe) congeladas ANTES da otimização; quem implementa não edita expected/dataset.

### Etapa 1 — Estado e roteamento de superfície
Testes (Node, `web/tests/mobileSurface.test.mjs`, `node --test`): `mobile_surface_single_below_breakpoint` (nunca dois valores visíveis); `mobile_surface_matches_effectiveMode_900_1100`; `switch_and_back_preserves_draft_and_pending` (chatSessionStore + pendingOperation); `combat_started_offers_combat_after_narration`; `back_policy_returns_to_chat_first`. Implementar.

### Etapa 2 — Shell e barra inferior
Testes Playwright (`web/e2e/mobile-single-pane.spec.ts`, viewports 320x568 e 390x844, `hasTouch`): `one_surface_visible`, `tabbar_targets_44px`, `no_horizontal_overflow`, `focus_moves_to_surface_title`, `aria_current_on_active`, `reduced_motion_no_layout_animation`, axe sem serious/critical (R1, R2, R8, R9). Implementar `MobileTabBar`, CSS, back policy.

### Etapa 3 — Composer, teclado e voz
Testes: `composer_visible_with_virtual_keyboard` (viewport reduzido simulando teclado via `visualViewport`), `voice_flow_transcript_editable_then_act` e `mic_released_on_surface_switch` com áudio sintético (padrão `web/e2e/voice-input.spec.ts`, SPEC-187) (R4, R5).

### Etapa 4 — Combate em tela própria e mira por toque
Testes: `tap_card_tap_target_submits_same_payload_as_desktop` (intercepta o POST/SSE e compara com a jornada desktop da SPEC-205), `cancel_button_clears_aiming`, `card_details_without_hover`, `combat_end_shows_outcome_in_chat` (R6, R7); nenhum `hover()`/`dragTo()` no caminho.

### Etapa 5 — WebView Capacitor
Smoke no AVD com build debug; sync de `web/android` sem alterar `applicationId` (SPEC-198).

Cada etapa: `cd web && npm run build && npm test && npx playwright test e2e/mobile-single-pane.spec.ts` e `uv run pytest` verdes.

## 5. Critérios de aceite

- [x] Jornadas mobile (eval congelado) passam em 320x568 e 390x844 sem overflow, com teclado/áudio/toque.
- [x] Nenhuma viewport mobile exibe chat e painel lado a lado.
- [x] Draft, scroll e ação pendente sobrevivem a troca de superfície e a voltar.
- [x] Combate/mira por toque completos sem hover/drag; payload idêntico ao desktop.
- [x] Reduced motion, foco e `aria-current` verificados; axe sem serious/critical.
- [x] Smoke WebView no AVD documentado.
- [x] Nenhuma mudança de API/save/regra; testes desktop (SPEC-204/205/212) verdes.
- [x] `uv run pytest` e `npm run build` verdes; testes Node do cliente verdes.

## 6. Smoke

Offline/MockLLM e API determinística: criar jogo, trocar superfícies, iniciar combate, escolher carta e alvo por toque, voltar ao chat. Sem provider real nem custo. Smoke Android só em AVD local.

## 7. Riscos & compatibilidade

- Saves: nenhuma migração; só apresentação.
- Risco: lógica de workspace divergir entre desktop e mobile — mitigado por R3 e teste de paridade.
- Risco: teclado virtual da WebView difere do Chromium emulado — por isso R10 e smoke no AVD.
- Risco: antecipar para a Play — SPEC-198 não depende desta spec (D6).

## 8. Pontos de decisão do dono

1. Breakpoint mobile: default 900px (mesmo limite de gaveta da SPEC-204 R12; 900–1100px já é single-pane pela 204, sem barra inferior). Alternativa: 700px exigiria reabrir R12 da 204.
2. Barra inferior vs gesto: default barra inferior obrigatória, swipe opcional posterior.
3. Mobile no beta fechado ou pós-beta desktop: default pós-gate desktop (D6).
4. Troca automática para Combate ao iniciar encontro: default trocar após a narração renderizar (com selo "Ir para o combate" sempre disponível); alternativa: nunca trocar sozinho.

## 9. Evidência requerida

Relatório Playwright mobile (JSON + screenshots), saída de Node/pytest/build, screenshots/vídeo do AVD, diff provando ausência de mudança de API/save, ESTADO_ATUAL/ROADMAP atualizados.

## 10. Execução (2026-10-17)

Implementado conforme §3 (defaults §8 usados: breakpoint 900px, barra obrigatória, troca automática após a narração). Fechado em 2026-10-17: testes < 900px adaptados (commit `test(e2e): adapt sub-900px journeys...`) e smoke AVD executado (`docs/spec216/evidence/avd_smoke.json`; limite de voz documentado). Evidência: `docs/spec216/README.md`.
