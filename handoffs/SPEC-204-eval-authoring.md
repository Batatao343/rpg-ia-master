# SPEC-204 — handoff de autoria de eval (F07 + F17–F19)

> **Origem:** executor da SPEC-204 (shell chat + contexto). **EVAL_AUTHORING_REQUIRED: true.**
> O executor **não** editou `web/e2e/critical-journeys.spec.ts`, `web/e2e/critical-journeys.yaml`,
> `evals/metrics-registry.yaml` nem `evals/manifest.lock.json`. Este documento lista o que a tarefa
> de eval (autor ≠ implementador) precisa ajustar/criar.

## 1. Estado das jornadas F01–F16 com a nova shell

Rodada local (`CI=1 npx playwright test e2e/critical-journeys.spec.ts`, Chromium local):
**15/16 verdes**. Seletores e textos antigos foram preservados de propósito (botão `☰ Ficha`
no topo, abas `Mapa`, `Missões` via "Jornada · Missões", placeholder do composer, `Agir`,
`Encerrar sessão`, `Fechar ficha`, `Sua mão`, `Aparar`, `Jogar Carta`).

| Jornada | Status | Motivo |
|---|---|---|
| F07 npc_interaction | **vermelha — mudança legítima de seletor** | D1/P1: "Pessoas" virou **seção do Codex** (aba `Codex` › seção `Pessoas`). O botão `Ficha` abre a aba Personagem; a aba `Pessoas` não existe mais no nível superior. |
| demais (F01–F06, F08–F16) | verdes | — |

Observação de ambiente (não é regressão): falhas intermitentes `requestfailed fonts.googleapis.com`
e `ERR_NO_BUFFER_SPACE` do WebSocket do Vite aparecem também no HEAD sem alterações.

### Ajuste proposto para F07 (sem afrouxar asserts)

```ts
test("F07 npc_interaction", async ({ page }) => {
  await openGame(page);
  await page.getByRole("tab", { name: "Codex" }).click();
  await page.getByRole("tab", { name: "Pessoas" }).click();
  await expect(page.getByText("Borin", { exact: true })).toBeVisible();
  await submitAction(page, "Converso com Borin");
  await expect(page.getByText("Borin, o barqueiro, responde sem desviar o olhar.")).toBeVisible();
  await page.reload(); await page.getByRole("button", { name: /^Ayla/ }).click();
  // O layout (aba Codex) é restaurado do localStorage; a seção volta ao default → reabrir Pessoas.
  await page.getByRole("tab", { name: "Codex" }).click();
  await page.getByRole("tab", { name: "Pessoas" }).click();
  await expect(page.getByText("Prometeu mostrar a rota.")).toBeVisible();
  await assertA11y(page);
});
```

### Ajustes opcionais (as jornadas já passam, mas o texto da spec pede)

- **F08**: hoje passa sem mudança. Recomenda-se escopar os cliques ao painel
  (`page.locator("#ws-panel-combate")`) e assertar `getByRole("tab", { name: "Combate" })`
  `aria-selected=true` + nenhuma `.tactical-dock`.
- **F16**: passa porque o executor manteve `☰ Ficha` em todas as larguras como atalho para a aba
  Personagem (desvio de R16, ver spec §8). Se a eval quiser remover o botão ≥ 1100px, trocar por
  `getByRole("tab", { name: "Mapa" })` visível direto em 1440 e manter `Fechar ficha` ≤ 480.
- **F04/F15**: passam inalteradas.

### Achado de infraestrutura

`playwright.config.ts` define `use.reducedMotion: "reduce"`, mas neste Chromium local
`matchMedia("(prefers-reduced-motion: reduce)")` retorna **false** nas jornadas (verificado).
Os testes do executor usam `page.emulateMedia({ reducedMotion: "reduce" })` explicitamente.
Sugere-se que a eval avalie mover `reducedMotion` para o `use` do projeto ou emular por página.

## 2. Jornadas novas a autorar (F17–F19)

Os testes do executor em `web/e2e/workspace-shell.spec.ts` (fora do gate F01–F16, 10 testes)
podem servir de referência de seletores; a eval deve reescrevê-los com seus próprios oráculos.

Seletores estáveis da shell:

| Elemento | Seletor |
|---|---|
| superfície do chat | `getByRole("region", { name: "Chat da aventura" })` |
| painel de contexto | `getByRole("region", { name: "Painel de contexto" })` |
| abas | `getByRole("tablist", { name: "Abas do painel" })` → tabs `Codex`, `Personagem`, `Combate`, `Bestiário`, `Mapa` |
| painéis | `#ws-panel-<codex|personagem|combate|bestiario|mapa>` (`role=tabpanel`) |
| seções do Codex | `getByRole("tablist", { name: "Seções do Codex" })` → `Locais (n)`, `Pessoas`, `Personagens (n)`, `Fações`, `Segredos (n)`, `Crônica` |
| seções do Personagem | `getByRole("tablist", { name: "Seções do personagem" })` → `Ficha`, `Jornada · Missões` |
| divisor | `getByRole("separator", { name: "Redimensionar chat e painel" })` (`aria-valuenow/min/max` em % do chat) |
| modos | `getByRole("group", { name: "Modo de exibição" })` → botões `Chat`, `Dividido` (só ≥ 1100px), `Painel` (`aria-pressed`) |
| histórico | botões `Voltar para a aba anterior` / `Avançar para a próxima aba` |
| composer | `getByRole("textbox", { name: "Sua ação" })` (visível em todos os modos) |
| fechar painel | `getByRole("button", { name: "Fechar ficha" })` |
| layout salvo | `localStorage["valoria:workspace:v1:<owner>:<game_id>"]` (`{version, mode, ratio, tab, lastSolo}`) |

- **F17 workspace_modes**: split 50/50 no primeiro uso (≥1100); `Chat`/`Painel`/`Dividido`;
  divisor por teclado (←/→ 5%, Shift 10%, Home/End limites, Enter 50%) e ponteiro; chat ≥ 380px e
  painel ≥ 360px; nunca 3 regiões; reload restaura modo/ratio/aba; overlays (level-up, morte,
  laboratório, lightbox) cobrem o viewport e devolvem foco; laboratório abre em Combate sem fetch
  de `/game/codex`.
- **F18 tabs_history**: 5 abas, setas/Home/End na tablist, `Alt+←/→`, `Ctrl+1` (chat),
  `Ctrl+2..6` (aba N), `Ctrl+\` (split ↔ último solo), `Esc` no painel foca o composer.
- **F19 preservation**: rascunho/scroll/foco/pending após 10 trocas; troca de jogo com SSE
  pendente não vaza rascunho/aba/scroll; voltar ao jogo anterior na mesma página restaura o
  rascunho; rascunho nunca em `localStorage`.

Após autorar: atualizar `web/e2e/critical-journeys.yaml`, `scripts/frontend_eval_report.py`
(`JOURNEY_RE` hoje só aceita F01–F16), `evals/metrics-registry.yaml` e relock de
`evals/manifest.lock.json` pelo fluxo protegido.
