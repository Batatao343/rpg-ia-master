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
- Falham só por contrato antigo < 900px: F16, F17, combat-gesture@390 (2), combat-outcome@390, workspace-shell "telefone 390" (2)
  -> `handoffs/SPEC-216-eval-followup.md` (precisam de adaptação de eval por tarefa separada).

## Limites
- Smoke WebView/AVD (Etapa 5) não executado nesta sessão; critério segue aberto. Screenshots: `evidence/` (320 e 390).
- Hysteresis do breakpoint não necessária: o chat não remonta ao girar (mesma árvore).
