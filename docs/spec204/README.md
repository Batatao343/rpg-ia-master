# SPEC-204 — evidência de execução (shell chat + contexto)

Status: `done` — implementação, revisão Sol, smoke §6 e eval (F07 adaptada + F17–F19, registry
1.8.0) entregues. Detalhe e desvios: §10/§11 da spec.

## O que mudou

- **Workspace** (`web/src/workspace/`): `workspaceModel.ts` (reducer puro: modos `chat|split|context`,
  5 abas, histórico ≤ 50, `combat_started/ended`, `clampRatio`, `effectiveMode` < 1100px),
  `workspaceStorage.ts` (`valoria:workspace:v1:<owner>:<game>` via `safeStorage`, validação
  estrita, sem histórico nem rascunho), `chatSessionStore.ts` (rascunho/scroll/reação por
  `game_id`, só memória), `Workspace.tsx` (barra global, divisor `role=separator`, atalhos,
  combate → split 50/50), `ChatSurface.tsx` (arte, lugares, onboarding, StoryLog + `Composer`),
  `ContextSurface.tsx` (tablist roving + painéis mantidos montados/ocultos + ErrorBoundary),
  `tabs/{Personagem,Combate,Bestiario}Tab.tsx`, `RovingTablist.tsx`, `useModalFocus.ts`.
- **PlayScreen** virou orquestrador (topbar + `<Workspace key={game_id}>` + overlays); saíram
  `.stage`, `<Hud>`, `.tactical-dock` e `hudOpen`. **Hud.tsx** só exporta painéis (sem auto-troca).
- **CodexTab**: seções extras (Pessoas, Fações = reputação + registros, Crônica), `excludeCategories`,
  hook `usePlayerCodex` e `CreatureList` reaproveitados pelo Bestiário.
- **StoryLog**: auto-scroll só no fim (48px) ou em ação própria; restaura scroll ao reaparecer;
  `role=log` + `aria-live` + `aria-busy` durante streaming.
- **Modais** (LevelUp, Morte, laboratório, memorial): foco inicial, Tab preso, retorno de foco,
  `aria-labelledby`; Esc = "mais tarde" no level-up.
- **App**: logout/troca de dono limpa layout do dono e rascunhos em memória; passa `owner`.
- **CSS**: novo só em `web/src/workspace.css`; `styles.css` só com 23 linhas removidas.
- Backend/API/save: **intocados** (`api.py`, `state.py`, `persistence.py` sem diff).

## Testes

| Suíte | Resultado |
|---|---|
| `npm test` (Node) | **72/72** (22 novos em `tests/workspaceModel.test.mjs`: reducer, clamp, storage, store, inventário R5) |
| `npm run build` | verde |
| `e2e/workspace-shell.spec.ts` (novo, 1440/390, axe) | **11/11** |
| `e2e/critical-journeys.spec.ts` | executor: 15/16 (F07 por seletor legítimo). **Após a eval: 19/19** (ver § Eval) |
| demais e2e (suíte completa: 65 passed, 19 skipped) | `image-quote` 7/7 (390px ajustado); `voice-input` "native Chromium MediaRecorder" falha **também no HEAD** (Chromium local grava `audio/wav`); `pending-discard @1440` e `account-lifecycle` (timing) falharam só sob carga concorrente e passam isolados |
| `uv run pytest -q --ignore=tests/test_project_index.py` | **2761 passed, 168 skipped**, exit 0 |

axe serious/critical = 0, `console.error`/`pageerror`/5xx = 0 e overflow = 0 nos testes verdes.

## Capturas

`capturas/1440-split.webp`, `1440-split-codex.webp`, `1440-chat.webp`, `1440-contexto.webp`,
`1440-combate.webp`, `1440-pos-combate.webp`, `390-chat.webp`, `390-contexto.webp` (o
`workspace-shell.spec.ts` grava PNGs novos em `web/test-results/spec204-capturas/`, gitignored).

## Smoke §6 (revisão Sol, 2026-10-16)

`uvicorn api:app` (perfil legacy, `RPG_FORCE_MOCK=1`, build do WT) + Chromium via Playwright;
saves criados por `POST /game/new` (MockLLM). Log em `smoke/smoke-log.txt`, capturas em `smoke/*.webp`.

1. Split inicial 50%; 3 turnos com rascunho não enviado alternando Codex/Mapa/Personagem —
   rascunho intacto, 2 regiões visíveis.
2. Chat solo → ataque → combate abre split 50% com aba Combate (sem mover foco para o painel);
   Carta jogada; ao encerrar, aba Combate permanece com aviso "Combate encerrado".
3. Divisor por teclado 50→70%; reload → 70%; outro save → split 50%, rascunho vazio, aba default.
4. 1024px + reduced-motion: modo único (chat/painel), rascunho intacto, sem transição, overflow 0;
   390px painel único, overflow 0. `pageerror`/`console.error` = 0.

## Eval (tarefa separada, 2026-10-16)

F07 adaptada (Codex › Pessoas) e F17 `workspace_modes`, F18 `tabs_history`, F19
`workspace_preservation` autoradas em `web/e2e/critical-journeys.spec.ts` (detalhe em §11 da spec).
`EVALUATOR_VERSION` e registry **1.8.0**; `evals/manifest.lock.json` regerado por
`python -m evals.core.governance lock` e `check` verde. Rodada completa (Chromium local, porta
temporária): **19/19**; `frontend_eval_report.py --check` exit 0:

```
journeys: registered 19, executed 19, passed 19
frontend_critical_journey_pass_rate=1.0; page_errors=0; console_errors=0; failed_requests=0;
5xx=0; horizontal_overflow=0; a11y_serious_critical=0; hard_gates_passed=true
```

`uv run pytest` completo (sem pipe, após rebuild do Project Index): **2896 passed, 168 skipped**, exit 0.

Publicar exige aprovação do environment `eval-governance` (régua protegida alterada).

## Limites

- `reducedMotion: "reduce"` do `playwright.config.ts` não chega ao Chromium local (verificado via
  `matchMedia`); os testes do executor emulam por página.
- Mobile definitivo é SPEC-216; < 1100px aqui é "uma superfície por vez" com composer fixo.
- Pré-existente (não alterado): a faixa `image-offers` ("Cotar retrato", nível do `App`) fica acima de
  `.play` (`height: 100dvh`) e empurra a base da tela ~64px para baixo; o composer continua
  acessível por rolagem do documento. Sugestão para SPEC-208/216: mover as ofertas para dentro da
  barra global do workspace.
