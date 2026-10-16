# SPEC-204 — Shell chat + contexto: split view e cinco abas navegáveis

> **Status:** `in-progress` (implementação entregue; faltam autoria de eval F07/F17–F19, revisão Sol independente e smoke §6 — ver §10)
> **Criada:** 2026-10-15 · **Atualizada:** 2026-10-16
> **Depende de:** SPEC-201 `done` (matriz de efeitos — informa, não bloqueia layout), SPEC-235 `done` (ciclo de ação pendente confiável) · SPEC-172 `done` (F01–F16), SPEC-077 `done` (contrato tático evoluído sem mudar API) (ordem final 2026-10-15)
> **Desbloqueia:** SPEC-205, SPEC-208, SPEC-209, SPEC-210, SPEC-211, SPEC-212, SPEC-216 (ordem final 2026-10-15)
> **Origem:** pacote `proximas-specs/pacote-prompts-rpg-beta-2026-10-15/`, prompt 02
> **EXECUTOR_MODEL:** `Sol` (≡ Opus, ver `docs/planos/equivalencia-modelos-claude.md`)
> **REVIEW_MODEL:** `Sol` (≡ Opus em contexto separado) · **REVIEW_REQUIRED:** `true`
> **EVAL_AUTHORING_REQUIRED:** `true` — adaptar seletores de F04/F08/F15/F16 em `web/e2e/critical-journeys.spec.ts` à nova shell e adicionar jornadas F17 (workspace modes), F18 (abas/histórico), F19 (preservação draft/scroll/foco/pending em troca de aba e de jogo); autoria em tarefa separada, antes da implementação, por quem não implementa.

Legenda: **[F]** fato observado no HEAD `6b94f66` · **[D]** decisão de produto fechada · **[H]** hipótese técnica · **[R]** recomendação.

---

## 1. Contexto & Objetivo

**[D]** Todo enredo acontece no chat. No desktop coexistem no máximo **duas superfícies**: o chat e UM menu contextual, começando em ~50/50 e redimensionável; qualquer uma pode ocupar 100% da área útil. Nunca chat + combate + terceiro HUD. Abas navegáveis como num navegador: Codex, Personagem, Combate, Bestiário, Mapa. Trocar de aba não pode perder draft, scroll, foco nem ação pendente. Mobile (uma superfície por vez) é fase posterior (SPEC-216).

**[F]** Hoje a tela de jogo é um grid fixo de duas colunas: `.stage { grid-template-columns: minmax(0, 1fr) 360px }` (`web/src/styles.css:352`), com `narrative-stage` (arte de cena + `StoryLog`) à esquerda e `<Hud>` fixo à direita (`web/src/components/PlayScreen.tsx:147-155`). Abaixo de 900px o HUD vira gaveta fixa (`styles.css:812-823`). O bloco `prefers-reduced-motion` fica em `styles.css:825-828`, e `App.tsx:697` envolve o app em `<MotionConfig reducedMotion="user">`.

**[F]** `web/src/components/Hud.tsx` (628 linhas) tem `type Tab = "ficha" | "combate" | "personagens" | "mapa" | "faccoes" | "missoes" | "cronica" | "codex"` (l.13), estado local `useState<Tab>("ficha")` (l.26) e auto-troca: entrou em luta → `combate`, saiu → `ficha` (l.28-34). O Bestiário é uma categoria de `CodexTab.tsx` (`CATEGORIES`, l.7-13: locations, factions, characters, creatures, secrets). `WorldMap` é renderizado dentro da aba `mapa` do Hud (l.95-110).

**[F]** Os controles táticos (`CardHand`, `ReactionPrompt`, `WoundTrack`, `SceneZones`) ficam num `.tactical-dock` de largura total **entre** `.stage` e a `actionbar` (`PlayScreen.tsx:159-178`), ou seja, competem com o chat como uma terceira faixa. O draft do composer é `const [input, setInput] = useState("")` em `PlayScreen` (l.39); `PlayScreen` é montado sob `motion.div key="play"` (`App.tsx:815-834`), **não** keyed por `game_id`. `StoryLog` força `scrollTop = scrollHeight` a cada mudança de `entries`/`thinking` (`StoryLog.tsx:16-19`). A ação pendente é persistida em `localStorage` por `valoria:pending:v1:<owner>:<game>` (`pendingOperation.ts`), e `clearOwner` limpa no logout.

**[F]** Não existe split, resize, modo solo, histórico de abas, nem persistência de layout.

Objetivo: substituir o grid fixo por um **workspace** de duas superfícies (`ChatSurface` + `ContextSurface`) com três modos, cinco abas com histórico tipo navegador, preservação de estado do chat por jogo e persistência local do layout, sem mudar API nem duplicar a fonte de verdade do combate.

## 2. Requisitos

- **R1 — Modos.** O workspace tem exatamente três modos: `chat` (chat 100%), `split` (chat + uma aba) e `context` (aba 100%). Nenhum estado da UI renderiza simultaneamente chat, aba de contexto e uma terceira região de conteúdo de jogo.
- **R2 — Split padrão.** Primeiro uso de um save abre em `split` com proporção 0,5 (±0,01) em viewport ≥ 1100px.
- **R3 — Resize.** O divisor é `role="separator"` com `aria-orientation="vertical"`, `aria-valuenow/min/max` (percentual do chat), focável; ponteiro (pointer events com captura) e teclado (←/→ = 5%, Shift+←/→ = 10%, Home/End = limites, Enter = volta a 50%). Limites mínimos: chat ≥ 380px e contexto ≥ 360px; se o viewport não comporta ambos, o modo efetivo cai para uma superfície (ver R12). Duplo clique no divisor restaura 50%.
- **R4 — Cinco abas.** `ContextSurface` expõe exatamente `codex`, `personagem`, `combate`, `bestiario`, `mapa`, num `role="tablist"` com `role="tab"`/`aria-selected`/`aria-controls`, foco roving (←/→/Home/End) e `role="tabpanel"` rotulado.
- **R5 — Migração sem perda (D1).** Todo conteúdo das oito abas atuais continua acessível: Ficha → Personagem; Missões → Personagem › "Jornada"; Pessoas, Fações, Crônica → seções do Codex; Combate → Combate; Mapa → Mapa; Bestiário sai do `CodexTab` para aba própria reutilizando os mesmos dados (`getCodex`, categoria `creatures`). Teste de inventário falha se algum componente-filho atual (`FichaTab`, `CombatTab`, `PeopleTab`, `FactionsTab`, `QuestsTab`, `ChronicleTab`, `CodexTab`, `WorldMap`, `GeneratedPortrait`) deixar de ser montável a partir da nova shell.
- **R6 — Navegação tipo navegador.** Cada visita de aba (e de seção interna que opte por isso) empilha uma entrada num histórico do workspace (máx. 50). Botões Voltar/Avançar (`aria-label` explícito, `disabled` quando vazio) e atalhos: `Alt+←`/`Alt+→` voltar/avançar; `Ctrl/⌘+1` chat solo; `Ctrl/⌘+2..6` abrir aba N; `Ctrl/⌘+\` alterna `split`↔último modo solo; `Esc` no `ContextSurface` devolve foco ao composer sem mudar de modo. Atalhos não disparam com foco em `input`/`textarea` exceto `Esc` e `Ctrl/⌘+1`.
- **R7 — Preservação ao trocar aba/modo.** Trocar aba, modo ou proporção não altera: o texto do composer, a seleção de reação (`reactionCardId`), o estado de gravação de voz, a posição de scroll do `StoryLog` (se o usuário não estava no fim, não é forçado ao fim) e a `PendingOperation` em curso. Abas visitadas preservam scroll interno enquanto o jogo estiver aberto.
- **R8 — Isolamento por `game_id`.** Draft, scroll e histórico de abas são chaveados por `game_id`; trocar de jogo (inclusive com SSE pendente, F15) nunca exibe draft, aba ou scroll do jogo anterior. Voltar ao jogo anterior na mesma sessão de página restaura o draft dele.
- **R9 — Persistência de layout.** Modo, proporção e aba ativa persistem por save em `localStorage` (`valoria:workspace:v1:<owner>:<game>`), com `try/catch` em leitura e escrita; JSON inválido, versão diferente ou storage indisponível caem no default sem erro de console. `clearOwner` equivalente remove as chaves do dono no logout. O draft **não** é gravado em disco (ver §8 P3).
- **R10 — Combate (D2).** Ao `combat.active` passar de falso → verdadeiro, o workspace abre `combate` em `split` 0,5 se estava em `chat`, ou troca a aba se já em `split`/`context`; nunca abre terceira coluna. Ao encerrar, a aba Combate permanece aberta (sem auto-troca para Ficha) e mostra o resultado/estado pós-combate até o jogador navegar. `CardHand`, `ReactionPrompt`, `WoundTrack` e `SceneZones` saem do `.tactical-dock` e passam a renderizar **só** dentro da aba Combate; manobras (`actionchips`) idem. O envio continua pelo mesmo `onAction(text, ActionOptions)` — zero mudança de API.
- **R11 — Barra global mínima (D2).** Em todos os modos há uma barra global com Vitalidade, Entropia, relógio/local e selo "em combate"; em `chat` solo é o único indicador de estado. Ela não contém controles táticos.
- **R12 — Viewports estreitos.** Abaixo de 1100px, `split` não é oferecido como modo efetivo: o workspace alterna entre `chat` e `context` (uma superfície por vez) preservando a preferência gravada; abaixo de 900px o comportamento visual atual de gaveta pode ser mantido até SPEC-216, desde que R1/R7/R8 valham. Zero controle fora da tela e zero overflow horizontal em 320/390/768/1440.
- **R13 — Movimento reduzido.** Transições de modo/aba usam `motion` respeitando `MotionConfig reducedMotion="user"`; com `prefers-reduced-motion: reduce`, nenhuma animação de largura/translação, resize sem inércia.
- **R14 — CSS isolado.** Todo CSS novo vive em `web/src/workspace.css` (importado uma vez); `styles.css` só recebe remoções das regras mortas (`.stage` grid, `.tactical-dock`, gaveta do `.hud`) em commit separado, para reduzir conflito com a SPEC-197.
- **R16 — Overlays e modais.** `LevelUpModal`, `DeathModal` (`App.tsx:736`), o diálogo de resultado do laboratório (`PlayScreen.tsx:254`, `role="dialog" aria-modal="true"`) e o `ArtworkDialog` (ampliar arte, `web/src/components/ArtworkDialog.tsx`) continuam cobrindo o viewport inteiro (não só uma superfície), prendem foco enquanto abertos e, ao fechar, devolvem foco ao elemento de origem (composer ou controle da aba). Nenhum overlay muda modo/aba/ratio do workspace. O botão de gaveta do HUD (`hudOpen`, `PlayScreen.tsx:42`) é removido ≥ 1100px e substituído pelo seletor de aba.
- **R17 — Laboratório de combate (SPEC-090).** Com `data.combat_simulation.enabled`, o workspace abre em `split` com a aba Combate, as abas que dependem de campanha (Mapa, Codex) ficam visíveis porém com estado vazio explicativo (sem fetch que dê 4xx), e as regras R1/R7/R10 continuam valendo.
- **R15 — Sem regressão de jornadas.** F01–F16 continuam verdes após a tarefa de eval adaptar seletores (sem afrouxar asserts), e F17–F19 novas passam.

### Fora de escopo

- Conteúdo novo/redesenho interno das abas (dossiês, deck fora de combate, viagem) — SPEC-209/210/211.
- Gesto de alvo direto em cartas — SPEC-205. Efeitos/motion finais — SPEC-208 (aqui só transições mínimas).
- Layout mobile single-pane definitivo — SPEC-216.
- Seletor "Falar com" do protótipo v01 — **não entra** (interlocutor automático é SPEC-202).
- URL/rota por aba (`history.pushState`) — o app não usa roteador; histórico fica em memória (§8 P2).
- Qualquer mudança em backend, schema de save ou contrato `GameResponse`.

## 3. Design técnico

### Arquivos novos

- `web/src/workspace/workspaceModel.ts` — tipos e reducer puro (sem React):
  ```ts
  export type WorkspaceMode = "chat" | "split" | "context";
  export type ContextTab = "codex" | "personagem" | "combate" | "bestiario" | "mapa";
  export interface WorkspaceState {
    version: 1; mode: WorkspaceMode; ratio: number;      // fração do chat, 0..1
    tab: ContextTab; history: ContextTab[]; cursor: number; lastSolo: "chat" | "context";
  }
  export type WorkspaceAction =
    | { type: "open_tab"; tab: ContextTab }   // empilha; se mode==="chat" → split
    | { type: "set_mode"; mode: WorkspaceMode }
    | { type: "set_ratio"; ratio: number }    // clamp feito pelo componente via px
    | { type: "back" } | { type: "forward" }
    | { type: "combat_started" } | { type: "combat_ended" };
  export const DEFAULT_WORKSPACE: WorkspaceState;
  export function workspaceReducer(s: WorkspaceState, a: WorkspaceAction): WorkspaceState;
  export function clampRatio(ratio: number, totalPx: number, minChatPx = 380, minCtxPx = 360): number;
  export function effectiveMode(s: WorkspaceState, viewportPx: number): WorkspaceMode; // R12
  ```
- `web/src/workspace/workspaceStorage.ts` — `loadWorkspace(owner, game)`, `saveWorkspace(owner, game, s)`, `clearWorkspaceOwner(owner)`; validação estrita de forma/versão; tudo em `try/catch` (padrão de `pendingOperation.ts`).
- `web/src/workspace/chatSessionStore.ts` — `Map<game_id, { draft: string; scrollTop: number; atBottom: boolean; reactionCardId?: string }>` em memória de módulo; `get/set/forget(game_id)`; `forgetAll()` no logout.
- `web/src/workspace/Workspace.tsx` — layout (`chat`/`split`/`context`), divisor `Splitter`, atalhos de teclado, barra Voltar/Avançar, `GlobalStatusBar`.
- `web/src/workspace/ChatSurface.tsx` — `SceneArtwork` + `StoryLog` + `actionbar`/composer/voz extraídos de `PlayScreen`; lê/grava draft e scroll no `chatSessionStore`.
- `web/src/workspace/ContextSurface.tsx` — tablist das 5 abas + painéis; monta abas visitadas e esconde (não desmonta) as inativas com `hidden` para preservar scroll/estado interno (R7) — **[H]** custo de memória aceitável para 5 painéis; se o Mapa pesar, desmontar com snapshot de scroll.
- `web/src/workspace/tabs/{PersonagemTab,CombateTab,BestiarioTab}.tsx` — composições finas dos componentes existentes (sem lógica nova de jogo).
- `web/src/workspace.css` — todas as regras novas (R14).
- `web/tests/workspaceModel.test.mjs` — testes Node do reducer/clamp/storage (padrão `web/tests/*.test.mjs` já usado na SPEC-172).

### Arquivos alterados

- `PlayScreen.tsx` — vira orquestrador: topbar + `Workspace`; remove `.stage`, `<Hud>` e `.tactical-dock`; `input` sai de `useState` local para `chatSessionStore` keyed por `data.game_id`.
- `Hud.tsx` — deixa de ser `<aside>` com tablist própria; exporta os subcomponentes (`FichaTab`, `CombatTab`, `PeopleTab`, `FactionsTab`, `ChronicleTab`) para as novas abas. Remove a auto-troca (l.28-34); a regra passa ao reducer (`combat_started`/`combat_ended`).
- `CodexTab.tsx` — recebe seções extras (Pessoas, Fações-reputação, Crônica) e `excludeCategories?: ["creatures"]`; categoria `creatures` passa a ser servida pela aba Bestiário com o mesmo fetch.
- `App.tsx` — em logout chama `clearWorkspaceOwner` e `chatSessionStore.forgetAll()` junto de `clearOwner`; nenhuma mudança no fluxo SSE/pending.
- `StoryLog.tsx` — auto-scroll só quando o usuário está "no fim" (limiar 48px) ou quando a entrada nova é do próprio jogador; expõe `onScroll` para o store.
- `styles.css` — remoções (commit separado, R14).

### State ownership

| Estado | Dono | Persistência |
|---|---|---|
| `GameResponse` (combate, ficha, mapa) | `App.tsx` (servidor é a verdade) | nenhuma nova |
| `PendingOperation` | `pendingOperation.ts` | localStorage existente, inalterado |
| Modo/ratio/aba/histórico | `Workspace` via `workspaceReducer` | `valoria:workspace:v1:<owner>:<game>` (sem histórico) |
| Draft/scroll/reação por jogo | `chatSessionStore` | memória da página (não disco) |
| Estado interno de abas (categoria do Codex, busca da crônica) | cada aba | memória, enquanto montada |

**[R]** O combate não ganha store paralelo: `CombateTab` lê `data.combat` como hoje (`CombatTab c={data?.combat}`), atendendo "não duplicar a fonte de verdade".

### Degradação/fallback

- `localStorage` indisponível/cheio → default `split 0.5`, sem erro; layout funciona só em memória.
- Payload de workspace corrompido → descartado e regravado no próximo save.
- `ResizeObserver` ausente → modo efetivo calculado por `window.innerWidth` no `resize`.
- Erro de render numa aba → `ErrorBoundary` por painel mostra mensagem e mantém chat intacto.

## 4. Plano passo a passo (TDD)

Pré-condição: tarefa de eval separada (EVAL_AUTHORING_REQUIRED) entregou F17–F19 e seletores adaptados de F04/F08/F15/F16 em `web/e2e/critical-journeys.spec.ts` + `web/e2e/critical-journeys.yaml`, inicialmente vermelhos onde dependem da nova shell; `evals/metrics-registry.yaml` e `evals/manifest.lock.json` (protegidos em `evals/protected-paths.txt`) atualizados e relockados por ela, não pelo executor. O executor não edita nenhum desses arquivos.

### Etapa 1 — Modelo puro
1. **Testes** (`web/tests/workspaceModel.test.mjs`): `default_is_split_half`; `open_tab_from_chat_goes_split`; `history_back_forward_and_cap_50`; `open_after_back_truncates_forward`; `combat_started_from_chat_opens_combate_split`; `combat_started_in_context_switches_tab_only`; `combat_ended_keeps_combate_tab`; `clamp_respects_min_px`; `effective_mode_below_1100_is_single`.
2. **Implementação:** `workspaceModel.ts`.
3. **Verificação:** `cd web && node --test tests/`.

### Etapa 2 — Storage
1. **Testes:** `load_invalid_json_returns_default`; `load_wrong_version_returns_default`; `storage_throwing_is_silent`; `keys_are_owner_and_game_scoped`; `clear_owner_removes_only_owner_keys`.
2. **Implementação:** `workspaceStorage.ts`, `chatSessionStore.ts`.

### Etapa 3 — Extração do ChatSurface
1. **Testes:** F04/F05/F14 adaptados verdes (submit, replay idempotente, recuperação de rede inalterados).
2. **Implementação:** mover composer/voz/StoryLog; draft no store por `game_id`; auto-scroll condicional.

### Etapa 4 — ContextSurface + migração das abas
1. **Testes:** teste de inventário (R5) + F06 (mapa/viagem), F09 (quest em Personagem › Jornada), F11, F12 verdes; axe sem serious/critical.
2. **Implementação:** abas, `CodexTab` com seções, `BestiarioTab`.

### Etapa 5 — Workspace, divisor, atalhos, combate
1. **Testes:** F17 (três modos, resize teclado/ponteiro, limites, overlays de R16 cobrindo o viewport e devolvendo foco, laboratório R17), F18 (cinco abas, voltar/avançar, atalhos), F08 (combate abre split com Combate; Cartas só na aba), F19 (draft/scroll/foco/pending entre abas e entre jogos com SSE pendente).
2. **Implementação:** `Workspace.tsx`, `GlobalStatusBar`, remoção do `.tactical-dock`.

### Etapa 6 — Responsivo, reduced-motion, limpeza CSS
1. **Testes:** F16 em 320/390/768/1440 sem overflow; projeto Playwright com `reducedMotion: "reduce"` asserta ausência de transição de largura.
2. **Implementação:** `workspace.css` finalizado; commit separado removendo regras mortas de `styles.css`.
3. **Verificação final:** `npm run build`, `node --test`, `npx playwright test`, `uv run python scripts/frontend_eval_report.py`, `uv run pytest`.

## 5. Critérios de aceite

- [x] Desktop 1440×900: chat solo, split 50/50, contexto solo, alternância das 5 abas, iniciar/encerrar combate — capturas por estado (`docs/spec204/capturas/`).
- [x] Nenhum DOM com três regiões de conteúdo simultâneas (assert em `workspace-shell.spec.ts`; F17/F08 dependem da eval).
- [x] Divisor operável só por teclado e só por ponteiro; limites mínimos respeitados; clique dentro das superfícies não é capturado pelo divisor.
- [x] Draft, scroll, foco no composer e `PendingOperation` sobrevivem a 10 trocas de aba/modo (teste do executor; F19 pendente da eval).
- [x] Troca de jogo com SSE pendente não vaza draft/aba/scroll (F15 verde + teste do executor; F19 pendente).
- [x] Reload restaura modo/ratio/aba do save; storage bloqueado não gera `console.error`.
- [x] Todo conteúdo das 8 abas antigas acessível (teste de inventário R5 em `web/tests/workspaceModel.test.mjs`).
- [x] `CardHand`/`ReactionPrompt`/`SceneZones`/`WoundTrack` renderizam só na aba Combate.
- [ ] F01–F19 100% — **F07 vermelha por mudança legítima de seletor** (Pessoas → Codex) e F17–F19 não autoradas: `handoffs/SPEC-204-eval-authoring.md`. pageerror/console.error/5xx = 0, axe serious/critical = 0 e overflow = 0 em 320/390/768/1440 nas jornadas verdes e nos testes do executor.
- [x] `prefers-reduced-motion: reduce` sem animação de layout.
- [x] Level-up, morte, resultado do laboratório e lightbox cobrem o viewport, prendem e devolvem foco, sem alterar o workspace (R16); laboratório de combate abre em split/Combate (R17).
- [x] CSS novo só em `web/src/workspace.css`; diff em `styles.css` só remoção.
- [x] `npm run build`, `node --test`, `uv run pytest` verdes; nenhum arquivo em `evals/protected-paths.txt` alterado pelo executor.
- [x] Nenhuma mudança de API/save (diff em `api.py`, `state.py`, `persistence.py` vazio).

## 6. Smoke

Offline/MockLLM (sem provider real; a spec é frontend puro):
1. `uv run uvicorn api:app --port 8000` com `RPG_FORCE_MOCK=1`; `cd web && npm run build`.
2. Criar personagem, jogar 3 turnos alternando Codex/Mapa/Personagem com texto no composer não enviado — draft intacto.
3. Provocar combate (mock) em `chat` solo → abre split com Combate; jogar uma Carta; encerrar → aba permanece.
4. Arrastar divisor para 70/30, recarregar → ratio restaurado; trocar para outro save → layout próprio/default.
5. Repetir passo 2 com DevTools emulando reduced-motion e viewport 1024px (modo single).

Provider real: não aplicável. Não há structured output novo.

## 7. Riscos & compatibilidade

- **Saves:** nenhum campo novo no save; layout é preferência local. Saves antigos carregam sem mudança (default de workspace).
- **Conflito com SPEC-197** (`in-progress`, tocou `styles.css` em `45c3681`): mitigado por R14; rebase esperado só no commit de remoção.
- **Evals:** mudar seletores de F04/F08/F15/F16 é mudança de evaluator → feita na tarefa de eval, com revisão; o executor não edita `web/e2e/` de jornada. **[H]** `web/e2e/contracts` (protegido) não existe hoje; se existir na execução, respeitar.
- **Performance:** manter 5 painéis montados pode custar memória; **[H]** aceitável, medir com o Mapa aberto; fallback documentado em §3.
- **Android (SPEC-193):** WebView em telefone fica abaixo de 1100px → modo single (R12); F16 cobre 390. Botão voltar nativo continua com `decideBack` de `App.tsx`; **[R]** não ligar o back nativo ao histórico de abas nesta spec (fica para SPEC-216).
- **[F]/[H]** `PlayScreen` não é keyed por `game_id` hoje; o draft atual provavelmente sobrevive a troca de jogo — R8 corrige; F19 deve provar o comportamento antes/depois.
- **Atalhos:** `Alt+←` conflita com voltar do navegador em alguns SOs — interceptar só com foco dentro do app (`preventDefault` condicionado).

## 8. Pontos de decisão do dono

- **P1 — Agrupamento das abas (D1, default recomendado):** Facções e Crônica viram seções do Codex; Missões vira "Jornada" dentro de Personagem; 5 abas: Codex, Personagem, Combate, Bestiário, Mapa. **[R]** Pessoas (lista de NPCs do `PeopleTab`) também vira seção do Codex, ao lado de "Personagens" do codex do jogador, até a SPEC-211 unificar em dossiês. Confirmar.
- **P2 — Combate e barra global (D2, default recomendado):** chat solo mantém barra mínima (Vitalidade, Entropia, relógio, selo em combate); controles táticos saem do chat para a aba Combate; início de combate abre split 50/50 com Combate automaticamente, nunca terceira coluna. Evolui a UI da SPEC-077 sem mudar API. Confirmar também: **ao encerrar combate, manter a aba Combate** (default) em vez de voltar à aba anterior.
- **P3 — Draft em disco:** default **não** persistir draft em `localStorage` (texto do jogador fica só em memória da página; reload perde rascunho, como hoje). Alternativa: persistir por owner+game com limpeza no logout.
- **P4 — Histórico em URL:** default memória apenas (sem `pushState`), porque o app não tem roteador e o back nativo Android já tem semântica própria.

## 9. Evidência requerida

- Relatório em `docs/spec204/README.md`: capturas 1440×900 dos três modos + combate, saída do `frontend_eval_report.py` (F01–F19), contagem axe/console/overflow.
- Saída de `node --test` (reducer/storage) e `npm run build`.
- `uv run pytest` final (contagem completa) e `git diff --stat` mostrando `styles.css` só com remoções e backend intocado.
- Handoff da tarefa de eval (F17–F19 + seletores) referenciado, com hash do commit que a fixou antes da implementação.
- Parecer de revisão Sol independente em `handoffs/SPEC-204-SOL-independent-review.md`.

## 10. Execução (2026-10-16)

Evidência: [`docs/spec204/README.md`](../docs/spec204/README.md). Handoff de eval:
[`handoffs/SPEC-204-eval-authoring.md`](../handoffs/SPEC-204-eval-authoring.md).

**Defaults de decisão aplicados (§8):** P1 = 5 abas (Codex, Personagem, Combate, Bestiário, Mapa);
Pessoas, Fações (reputação + registros do Codex) e Crônica viram seções do Codex; Missões vira
"Jornada · Missões" em Personagem. P2 = barra global mínima (Vitalidade, Entropia, selo "em combate";
local/relógio seguem no topo); controles táticos só na aba Combate; início de combate abre split
50/50 com Combate; ao encerrar, a aba Combate permanece com aviso "Combate encerrado". P3 = rascunho
só em memória (`chatSessionStore`), nunca em disco. P4 = histórico só em memória (sem `pushState`).

**Desvios registrados:**
- **Ordem de execução:** a tarefa de eval (EVAL_AUTHORING_REQUIRED) não precedeu a implementação;
  o executor manteve seletores antigos para preservar F01–F16 e escreveu o handoff. Resultado:
  15/16 verdes; F07 aguarda a eval.
- **R16 (botão de gaveta ≥ 1100px):** o botão `☰ Ficha` foi mantido em todas as larguras como
  atalho que abre a aba Personagem (não é mais gaveta nem alterna o chat), para não quebrar F02,
  F06, F09, F12, F13 e F16. A eval pode removê-lo ≥ 1100px depois de adaptar F16.
- **Composer:** fica visível em todos os modos (sob o chat no split; largura total em chat/contexto),
  o que viabiliza `Esc` no painel "devolver foco ao composer sem mudar de modo" (R6).
- **R12 abaixo de 900px:** a gaveta antiga foi aposentada; abaixo de 1100px o painel ocupa a
  área do chat (uma superfície por vez), com o composer visível. Preferência `split` fica gravada
  (`lastSolo` decide a superfície única).
- **R14:** remoção das regras mortas de `styles.css` (`.stage`, `.hud`/gaveta, `.hud__head`,
  `.hud__close`, `.tactical-dock*`) feita no mesmo diff de trabalho; o coordenador pode separá-la
  em commit próprio (só deleções).
- **Contraste:** `.combat-empty` (`--faint`) falhava axe 4,08:1 no painel; `workspace.css` usa
  `--muted` dentro dos painéis.
- **Teste existente ajustado:** `web/e2e/image-quote.spec.ts` (SPEC-188, 390px) abre a Ficha antes
  de procurar o retrato (antes o HUD oculto contava como "visível"); `tests/test_visual_assets.py`
  procura `SceneArtwork` em `workspace/ChatSurface.tsx`.

**SPEC-201 aplicada no escopo da shell:** A06/M19 (tablists com foco roving e setas/Home/End —
painel, Codex e Personagem); A07/M20 (sem auto-troca para Ficha ao fim do combate; aviso
explícito); A08/M09 (`role="log"` + `aria-live="polite"` + `aria-busy` durante streaming);
A09/M26 (LevelUp/Morte/laboratório/memorial com foco inicial, Tab preso, retorno de foco,
`aria-labelledby`; Esc = "mais tarde" no level-up); A13 (botão "Enviando…" + `aria-busy`).
Fora do escopo da shell e **não** corrigido: A01 (hitbox do Create), A04, A14, A18, A19.

**Pendências para `done`:** (1) eval: F07 adaptada + F17–F19 + relock; (2) revisão Sol
independente (`handoffs/SPEC-204-SOL-independent-review.md`); (3) ~~smoke §6~~ executado na revisão Sol
(uvicorn + MockLLM, verde — `docs/spec204/README.md` § Smoke §6).
