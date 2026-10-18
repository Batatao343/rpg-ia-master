# SPEC-216 — Mobile single-pane (evidência)

## O que mudou (somente apresentação; zero API/schema/regra)
- `web/src/workspace/mobileSurface.ts` (puro): breakpoint 900px, `mobileSurface(state, px)` sobre `effectiveMode`,
  `shouldAutoOpenCombat`, ponte `registerBackBridge/offChatSurface/returnToChat` p/ o voltar do Android.
- `components/MobileTabBar.tsx`: `nav "Superfícies"` (Chat + 5 abas, >=44px, `aria-current="page"` só no ativo).
- `Workspace.tsx`: < 900px renderiza título focável (`surface-title`, foco a cada troca), barra inferior, sem
  `ws-bar`/abas/× do painel; combate abre automaticamente SÓ depois da narração (rAF x2 + teto 2,5 s); composer
  fica no chat e some nas outras superfícies (voz cancelada -> microfone liberado).
- `useVisualViewport.ts`: `--app-vh` segue `visualViewport` (teclado virtual); a barra se esconde com o teclado.
- `ChatSurface.tsx`: botão "Ir para o combate"; `CombateTab/CardHand/CardTooltip`: "Cancelar mira" e
  "Detalhes de <Carta>" por toque (mesma máquina `useTargeting`, mesmo payload). `SceneArtwork`: sem fade com reduced motion.
- `native/backPolicy.ts` + `lifecycle.ts` + `App.tsx`: voltar numa superfície != chat leva ao chat primeiro.
- `workspace.css`: bloco mobile (barra, título, composer 44px/16px, offers/pendente dentro da viewport, sem transições
  com reduced motion no mobile).

## Testes
- Playwright (Chromium empacotado, `mobile-320`/`mobile-390`, `--workers=1`): M01–M07 = 14/14, 3 execuções consecutivas verdes.
- `npm test`: 124/124 (inclui `tests/mobileSurface.test.mjs`, 5 testes); `npm run build` verde.
- Desktop (projeto `chromium`): F01–F15 e F18–F40 verdes; pytest completo ver spec.
- Testes < 900px adaptados ao contrato mobile (F16, F17, combat-gesture@390, combat-outcome@390, workspace-shell "telefone 390",
  deck-character 320/390/768, portrait-overlay@390): traduzidos, não removidos (barra "Superfícies", foco no título, "Detalhes de <Carta>").
  Governança: `evals.core.governance check` verde sem relock (specs de jornada não entram no manifesto).
- Suíte Playwright completa como no CI (Chromium empacotado, 2 workers, todos os projetos): 0 falhas exceto 2 de `account-lifecycle`
  (SPEC-190), que falham igual em `main` (verificado em worktree de main). `npm test` 124/124, build verde, pytest só com os 2 de staleness do project_index.

## Limites
- Screenshots Chromium: `evidence/` (320 e 390).

## Smoke WebView/AVD (Etapa 5) — `evidence/avd_smoke.json`, `avd-01-chat-bar.png`, `avd-02-keyboard.png`
AVD `rpg34` (android-34), APK debug (`CAP_BUILD=debug CAP_SERVER_URL=http://10.0.2.2:8765 npx cap sync android`, JDK 21), API LOCAL (MockLLM, perfil legacy),
WebView dirigido por CDP cru (o `connectOverCDP` do Playwright não conecta ao WebView 113). Resultados:
- Barra "Superfícies" com 6 botões, `platform=android`, exatamente uma superfície visível (chat): PASS.
- Teclado (toque real via adb, IME real): o WebView encolhe (viewport 842 -> 530) e campo + Agir ficam inteiros acima do teclado: PASS.
- Voltar do Android: Mapa -> voltar -> Chat (título "Chat"), app vivo: PASS.
- Liberação do microfone na troca de superfície: NÃO verificável neste alvo. `http://10.0.2.2` não é contexto seguro
  (`navigator.mediaDevices` indefinido) e o sync debug só libera cleartext para 10.0.2.2 (`http://localhost` cai em chrome-error).
  Coberto no Chromium (M04, mobile-320/390) e o `getUserMedia` real em https foi provado no smoke SPEC-193 v2. Para fechar no WebView
  seria preciso apontar o sync para o staging https (fora do escopo "API local").
- Hysteresis do breakpoint não necessária: o chat não remonta ao girar (mesma árvore).
