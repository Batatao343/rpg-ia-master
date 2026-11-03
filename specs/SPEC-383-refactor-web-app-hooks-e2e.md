# SPEC-383 — Front: hooks do `App.tsx`, `GameActionsContext`, `Hud.tsx` por aba e poda de e2e de prints

> **Status:** `draft`
> **Criada:** 2026-11-03 · **Atualizada:** 2026-11-03
> **Origem:** auditoria de qualidade de 03/11 — `docs/auditorias/auditoria-qualidade-codigo-2026-11-03.md` §4.5 (itens 1–7) e §5 letra G; regras da onda em §6 (W1–W8)
> **Depende de:** SPEC-379 R6 pousada (testes que leem o fonte de `App.tsx`); SPEC-367, SPEC-368 e SPEC-371 pousadas (tocam `App.tsx`, `types.ts`, `combat/deck.ts`, `CodexTab.tsx`, `tabs/DossierDetail.tsx`, `components/combat/*`; W1)
> **Desbloqueia:** SPEC-385 (contrato front↔back)
> **EXECUTOR_MODEL obrigatório:** `Terra`
> **REVIEW_MODEL obrigatório:** `Sol`
> **REVIEW_REQUIRED:** `true`
> **EVAL_AUTHORING_REQUIRED:** `false` — `web/e2e/contracts` é caminho protegido de eval (`evals/protected-paths.txt:13`): **não criar nem tocar** (W5)

Rótulos: **[F]** fato conferido no fonte em 03/11 · **[H]** hipótese a confirmar na execução · **[D]** decisão do dono (§8).

---

## 1. Contexto & Objetivo

[F] `web/src/App.tsx` tem 1.136 linhas, 19 `useState`, 18 `useRef` e nenhum Context. Num só
componente moram autenticação/sessão (`:98-330`), cotação e confirmação de imagem (`:82-90`,
`:378-443`), o turno com stream SSE, fallback POST e "Tentar de novo" (`:332-376`, `:491-767`),
saves/histórico (`:445-489`, `:769-844`) e as ações de ficha/cartas (`:846-945`). Os quatro
handlers `onEquip`/`onPrepareCards`/`onCardReward`/`onGeneratePortrait` descem por props
`App` → `PlayScreen` (`PlayScreen.tsx:27-31,130-131`) → `Workspace` (`Workspace.tsx:42-46,365-366`)
→ `ContextSurface` (`ContextSurface.tsx:46-50,123,127`) → `CombateTab` (`CombateTab.tsx:62-79`) ou
`PersonagemTab` → `CharacterTab` (`CharacterTab.tsx:48-49,85`) → `FichaTab` (`Hud.tsx:39-40`).
`onEquip` atravessa 6 níveis; os 3 de cartas, 5.

[F] `components/Hud.tsx` (577 linhas) não é um HUD: exporta 7 blocos de aba (`FichaTab:39`,
`PeopleTab:131`, `FactionsTab:170`, `HeardNews:239`, `ChronicleTab:274`, `PartyBars:390`,
`CombatTab:419`) e os auxiliares `itemIcon:11`, `EquipFn:19`, `useVitalityHit:26`. As abas vivem em
duas pastas: `components/tabs/` (implementações) e `workspace/tabs/` (onde `BestiarioTab.tsx` e
`PersonagemTab.tsx` só reexportam o componente de `components/tabs/`, 2–4 linhas cada).

[F] Em `web/e2e/` há 4 arquivos de captura de prints/diagnóstico, opt-in por variável de ambiente
(`deck-342-prints.spec.ts:6`, `spec347-prints.spec.ts:5`, `spec354-prints.spec.ts:30,42,80`,
`diagnostics/spec201-capture.spec.ts:12`). **Exceção:** `spec354-prints.spec.ts:16-27` define
`retrato_marcador_sem_flag_1440`/`_390`, que **rodam sempre** (sem `test.skip`) e são gate: apagar
o arquivo sem movê-los perde cobertura. Há 2 classes CSS sem uso (`styles.css:607`,
`styles.css:1185-1186`).

Objetivo: refatoração **pura** (W2/W3) que deixa o `App.tsx` em ~300 linhas de composição e
JSX, troca o prop-drilling por um Context estável e quebra o `Hud.tsx` por aba, **sem mudar um
comportamento observável**. O trecho mais arriscado (turno/stream/retry) vai por último, com
testes de caracterização antes.

## 2. Requisitos

- **R1 — Hooks em `web/src/hooks/`.** O `App.tsx` passa a chamar hooks, um por commit (W4), do
  menos ao mais arriscado:
  1. `useImageQuote` — estado `imageQuote`/`imageBusy`/`imageError` + `resetImageQuote`,
     `openImageQuote`, `handleGeneratePortrait`, `confirmImageQuote` (`App.tsx:82-90`, `:378-443`).
  2. `useSaves` — `loadHistory`, `handleCreate`, `handleCreateSimulation`, `handleContinue`,
     `handleContinueSave`, `handleDeleteSave`, `handleNew` (`:445-489`, `:769-844`).
  3. `useAuthSession` — os 3 `useEffect` do app (listener `rpg:auth-expired` `:98-109`, ciclo
     nativo `:111-126`, bootstrap `:155-210`) **na mesma ordem relativa**, `resumeSession`,
     `completeAuthenticatedSession`, login/logout/exclusão (`:130-303`) e o saldo
     (`refreshBalance`/`syncAccountBalance`, `:309-330`; pode ser um `useAccountBalance` no mesmo
     arquivo).
  4. `useTurn` — `turn`/`resetTurn`, `turnToken`, `retryBypass`, `retrying`, `openingMemo`,
     `streamEntryId`, `pendingVisual`, `simNoticed`, `volatileWarned`, `markOpening`, `onTurn`,
     o stream (`ensureStreamId`…`finishStreamEntry`), `refreshTurnCost`, `handleAction`,
     `retryTurn`/`retryTurnInner`, `discardPending` (`:67-72`, `:332-376`, `:491-767`).
  5. `useGameActions` — `handleEquip`, `handleCardReward`, `handlePrepareCards`, `handleLevelUp`,
     `handleDeathChoice`, `handleUiError` (`:846-945`); alimenta o R2.
  Ao fim, `App.tsx` ≤ 350 linhas (meta ~300) e contém só: estado compartilhado (§3.1), chamadas
  de hook, `artPanel`, JSX e `LegalLinks`.
- **R1.1 — Guarda de corrida intacta.** O corpo de `handleAction` preserva **exatamente** a
  sequência atual: leitura-e-zeragem de `retryBypass` antes do teste de `busy` (`:581-582`);
  captura de `gid`/`generation`/`user` e `token = ++turnToken.current` (`:583-584`); `active()`
  comparando `session`, `gameId` e `turnToken` (`:585`); `clearOwnPending` com
  `clearPendingIfOwn` (`:620`); os ramos `narrativeShown`/4xx/fallback POST (`:654-691`); e o
  `finally` que só destrava se `active()` (`:703-709`). `retryTurnInner` preserva o incremento de
  `turnToken` antes de descartar o fluxo SSE (`:730`, `:742`) e o `retryBypass.current = true`
  imediatamente antes do reenvio (`:752-753`). O diff desses corpos é só de indentação/nome de
  variável de contexto (ex.: `core.session.current`); nenhuma linha reordenada.
- **R1.2 — Semântica de closure intacta.** Todo handler devolvido por hook continua sendo
  função recriada a cada render, lendo o estado daquele render (`busy`, `data`, `imageQuote`,
  `imageBusy`, `authRequired`), como hoje. **Proibido** embrulhar em `useCallback`/`useMemo` o
  que hoje não é; os 3 que já são (`resetTurn :72`, `clearBanner :74`, `handleUiError :846`)
  mantêm as mesmas deps. Motivo: `retryBypass` existe justamente porque o `busy` do closure é
  velho (`:581`); "consertar" isso muda o comportamento do retry.
- **R1.3 — Sem `useEffect` novo e sem mudar deps** nos hooks do R1; o `eslint-disable` de
  `:125` muda de arquivo junto com o efeito, com o mesmo texto. Nenhum `eslint-disable` novo.
- **R2 — `GameActionsContext`.** Novo `web/src/context/GameActionsContext.tsx` com
  `{ onEquip?, onPrepareCards?, onCardReward?, onGeneratePortrait? }` (mesmas assinaturas de
  `PlayScreen.tsx:27-31`). O `App` provê os 4 sempre; o valor default (sem provider) é `{}`, para
  que componentes renderizados fora do app (SSR dos testes Node) continuem sem esses botões, como
  hoje quando a prop falta (`CombateTab.tsx:313,328,418,421`; `Hud.tsx:106,112`). Consumo só em
  `CombateTab.tsx` e `CharacterTab.tsx`, que repassam por prop aos filhos atuais (`FichaTab`,
  `EspolioPanel`, `ForjaPanel`, `LojaCartasPanel`, `CombatDeckTab`, `Arena`) — **nenhum arquivo
  de `components/combat/*` muda** (W1 com a 368). As 4 props somem de `PlayScreen`, `Workspace`,
  `ContextSurface`, `CombateTab` e `CharacterTab`. `busy`, `onAction` e `onOpenLevelUp` **não**
  entram no Context (`deck.test.mjs:52` exige `busy={busy}` no `<CombatDeckTab`).
- **R2.1 — Valor estável.** O valor do provider é criado uma vez (`useMemo(…, [])`) e delega a
  um ref atualizado por `useEffect` sem deps — o padrão já usado em `ChatSurface.tsx:59-61`.
  Assim o Context não causa re-render em consumidor nenhum. Exceção ao R1.3 limitada a esse
  único efeito, declarado **depois** dos 3 efeitos do `useAuthSession`.
- **R3 — `Hud.tsx` por aba (move puro).** Cada bloco vai para `web/src/components/tabs/`:
  `FichaTab.tsx`, `PeopleTab.tsx`, `FactionsTab.tsx`, `HeardNews.tsx`, `ChronicleTab.tsx`
  (com `ProjectionSeal`), `PartyBars.tsx`, `CombatTab.tsx` (com `Combat`); auxiliares
  compartilhados (`Bar`, `AbyssChip`, `CondChips`, `itemIcon`, `EquipFn`, `useVitalityHit`) em
  `components/tabs/hudParts.tsx`. Corpo das funções byte-igual (só imports mudam). `Hud.tsx` é
  apagado e os 4 importadores atualizados (`Workspace.tsx:6`, `CombateTab.tsx:3`,
  `ContextSurface.tsx:4`, `CharacterTab.tsx:4`). `workspace/tabs/BestiarioTab.tsx` e
  `PersonagemTab.tsx` são apagados; `ContextSurface` importa `BestiaryTab`/`CharacterTab` direto
  e renderiza com os mesmos props.
- **R4 — e2e de prints.** [D1] Apagar `web/e2e/deck-342-prints.spec.ts`,
  `spec347-prints.spec.ts`, `spec354-prints.spec.ts` e `diagnostics/spec201-capture.spec.ts`,
  **depois** de mover `retrato_marcador_sem_flag_1440`/`_390` (`spec354-prints.spec.ts:12-27`,
  com `withMarkers` e o `log`) para `spec347-retrato.spec.ts`, mesmos nomes e asserções.
  `deck-342-helpers.ts`, `spec347-helpers.ts` e `fixtures/spec354/save-real.json` ficam (outros
  specs usam). Diretórios de evidência em `docs/spec201|342|347|354/` ficam. Consolidação dos
  e2e de combate nomeados por spec: **fora**, salvo [D2]; vale só a regra do R4.1.
- **R4.1 — Regra para e2e novos.** `docs/guias/TESTES.md` ganha 3 linhas: e2e novo vai no
  arquivo da **feature** (tabuleiro, Livro, retrato, loja…), não `specNNN-*.spec.ts`; prints de
  evidência ficam fora do repo ou num script opt-in em `scripts/`, nunca em `web/e2e/`.
- **R5 — CSS morto.** Remover `.diary__summary` (`styles.css:607`) e o seletor `.image-offers`
  (`styles.css:1185`, mantendo `.image-quote-actions` na mesma regra; e `:1186` inteira), após
  confirmar que nenhuma classe é montada em runtime com esses pedaços (§3.4).
- **R6 — Governança de efeitos.** [D3] Default: **manter** `design/effects.registry.ts`,
  `e2e/effects.spec.ts` e o projeto `chromium-motion` (`playwright.config.ts:68-72`) como estão.
  Esta spec não toca neles.
- **R7 — Oráculo (análogo ao W2 para o front).** Antes e depois de **cada** etapa: `npm test`,
  `npm run typecheck`, `npm run typecheck:e2e`, `npm run lint` e `npm run build` verdes;
  e2e do escopo da etapa verdes com `--workers=1`; ao fim, a suíte e2e completa
  (`npm run test:e2e -- --workers=1`, coordenador, 1×) verde, com contagem de testes listados
  (`npm run test:e2e:list`) = antes − testes dos 4 arquivos apagados + 0 (os 2 movidos contam
  igual). Bundle: soma de bytes de `web/dist/assets/*.js` e `*.css` não cresce mais de 2 %.
- **R8 — W3.** Nenhuma asserção muda. Em teste só pode mudar caminho de arquivo/import (lista em
  §3.5). Se alguma etapa exigir asserção nova ou diferente, para, registra no hand-back e não
  segue.

### Fora de escopo

- Trocar `motion` por CSS (`@starting-style`/View Transitions) — saiu na auditoria §6.4.
- Apagar `currentPurchaseAdapter`/`WebStripeAdapter`/`selectPurchaseAdapter` — gancho da
  SPEC-198 (§6.4); também `purchases/androidPlay.ts` e Capacitor.
- Consolidar os e2e de combate por spec (salvo [D2]); renomear arquivos `specNNN-*` existentes.
- Reduzir `effects.spec.ts`/registry (salvo [D3], que vira spec própria).
- Mover `workspace/tabs/CombateTab.tsx`/`MapTab.tsx` para `components/tabs/` (salvo [D4]).
- Qualquer mudança em `components/combat/*`, `types.ts`, `combat/deck.ts`, `CodexTab.tsx`,
  `tabs/DossierDetail.tsx` (W1), `http.ts`/`api.ts`, `web/e2e/contracts/` (W5), backend.
- Corrigir os comportamentos "estranhos" que a refatoração deixa à vista (closure velho de
  `busy`, ordem de `setState`): anote como follow-up, não conserte aqui.
- Testes unitários de hook com renderer (não há `jsdom`/testing-library no projeto; adicionar
  dep não compensa).

## 3. Design técnico

### 3.1 Estado compartilhado e ordem de chamada

Os hooks compartilham estado. Fica no `App` (e desce como um objeto `core` montado a cada render,
tipado em `web/src/hooks/core.ts`, **sem** memo): `screen`, `data`, `log`, `busy`, `thinking`,
`banner`, `pending`, `saves`, `continueData`, `authRequired`, `authConfig` e os refs `session`,
`owner`, `gameId`, `logSeq`, `accountReturn`, `deletionInProgress`, mais os setters. Cada hook
recebe `core` e as funções de que depende como argumento.

Grafo de dependência (verificado nos corpos atuais) e **ordem de chamada final** no `App`:

| # | Hook | Precisa de |
|---|---|---|
| 1 | `useAccountBalance` | `core` |
| 2 | `useImageQuote` | `core`, `refreshBalance` (`:432`) |
| 3 | `loadHistory` (exportado de `useSaves.ts`, sem estado) | `core` |
| 4 | `useTurn` | `core`, `loadHistory` (`:606,736`), `refreshBalance` (`:577`) |
| 5 | `useAuthSession` | `core`, `resetImageQuote`, `resetTurn` (`:262`), `loadHistory` (`:146`), `refreshBalance` |
| 6 | `useSaves` | `core`, `onTurn`, `openImageQuote`, `resetImageQuote`, `resetTurn` |
| 7 | `useGameActions` + provider | `core`, `loadHistory` (`:938`), `handleGeneratePortrait` |

[F] O app só tem 3 `useEffect` (`:98`, `:115`, `:155`), todos no item 5, então a ordem relativa
dos efeitos se mantém trivialmente. A ordem dos **commits** (R1) é outra (menor risco primeiro):
enquanto um hook ainda não foi extraído, a função continua no `App` como declaração (hoisted) e
entra por argumento; no commit do `useTurn` a ordem de chamada é ajustada para a tabela.
`nativeCtx.current = {…}` (`:113`) continua sendo atribuído no render, dentro do `useAuthSession`.

### 3.2 Arquivos

- **Novos:** `web/src/hooks/core.ts` (tipo `AppCore`), `useAccountBalance` (em
  `useAuthSession.ts`), `useAuthSession.ts`, `useImageQuote.ts`, `useSaves.ts`, `useTurn.ts`,
  `useGameActions.ts`; `web/src/context/GameActionsContext.tsx` (`GameActionsContext`,
  `GameActionsProvider`, `useGameActions()` de leitura — nome do hook de leitura:
  `useGameActionsContext` para não colidir); `web/src/components/tabs/{FichaTab,PeopleTab,
  FactionsTab,HeardNews,ChronicleTab,PartyBars,CombatTab,hudParts}.tsx`.
- **Alterados:** `App.tsx`; `PlayScreen.tsx`, `Workspace.tsx`, `ContextSurface.tsx`,
  `workspace/tabs/CombateTab.tsx`, `components/tabs/CharacterTab.tsx` (props do R2, imports do
  R3); `styles.css` (R5); `e2e/spec347-retrato.spec.ts` (R4); `docs/guias/TESTES.md` (R4.1).
- **Apagados:** `components/Hud.tsx`, `workspace/tabs/BestiarioTab.tsx`,
  `workspace/tabs/PersonagemTab.tsx`, os 4 specs do R4.
- `design/primitives.tsx:61` já tem um Context (`ArrivalsContext`); o novo segue o mesmo estilo.
- Hooks não importam `motion` (`design.test.mjs:90-103` permite `motion` só por nome de arquivo;
  `MotionConfig`/`AnimatePresence` ficam no `App`, como `design.test.mjs:108-111` exige).

### 3.3 Assinatura do Context

```ts
export type GameActions = {
  onEquip?: (pick: { item_id?: string; unequip_slot?: string }) => void;
  onPrepareCards?: (prepared: string[]) => Promise<string | null>;
  onCardReward?: RewardSender;
  onGeneratePortrait?: (enemyId: string, priceShards: number, priceMilli?: string) => void;
};
export const GameActionsContext = createContext<GameActions>({});
```

### 3.4 Prova de classe CSS morta (R5)

[F] Em 03/11 `Grep` por `diary`, `__summary`, `image-offer`, `"image-` e `` `image- `` em
`web/src/**/*.{ts,tsx}` não acha montagem dinâmica dessas classes (as ocorrências são
`wizard__summary`, `espolio__offers`, `msg__offers`, `image-quote-*`, `image-generations`).
O executor repete o `Grep` em `web/src`, `web/e2e` e `web/tests` antes de apagar e cola o
resultado no hand-back.

### 3.5 Testes que leem fonte e mudam só de caminho (W3)

| Teste | Lê hoje | Depois |
|---|---|---|
| `tests/test_frontend_auth_bootstrap.py:5-9` (ordem de 3 strings) | `App.tsx` | `hooks/useAuthSession.ts` — se a 379 R6 ainda não tiver tratado (ver [D5]) |
| `tests/test_visual_assets.py:209,214` (`"visual: r.visual?.cue"`) | `App.tsx` | `hooks/useTurn.ts` — idem |
| `web/tests/workspaceModel.test.mjs:253-254` (lista de arquivos da shell) | inclui `PersonagemTab.tsx`, `BestiarioTab.tsx` | troca pelos arquivos que passam a montar (`ContextSurface.tsx` já está; acrescenta `components/tabs/BestiaryTab.tsx`) — lista de nomes do `for` intacta |
| `web/tests/spec347-components.test.mjs:53` | `components/Hud.tsx` | `components/tabs/CombatTab.tsx` |
| `web/tests/design.test.mjs:108-111` | `App.tsx` (`MotionConfig`) | sem mudança (fica no App) |
| `web/tests/deck.test.mjs:49-52` | `CharacterTab.tsx`, `CombateTab.tsx` | sem mudança (regex continuam batendo) |

`tests/test_ci_eval_gates.py:21` só classifica o caminho `web\src\App.tsx`; não muda.

## 4. Plano passo a passo

Antes de **cada** etapa: W1 (cruzar arquivos da etapa com branches abertas; interseção ≠ vazio
⇒ a etapa espera) e medir RAM livre. Cada etapa = 1 commit (W4). Rodar o oráculo do R7 antes
(saída A) e depois (saída B) da etapa; colar as contagens no hand-back.

### Etapa 0 — Linha de base

1. `npm run build` → anotar bytes de `dist/assets/*.{js,css}`; `npm run test:e2e:list` → contagem
   por arquivo; `npm test` → contagem.
2. **Matriz de caracterização do turno** (`handoffs/SPEC-383-turn-matrix.md`): para cada ramo de
   `handleAction`/`retryTurnInner` (`completed` por `operation_id`; `running`; `narrativeShown`
   definitivo e não definitivo; 4xx com `shouldClearPending`; `invalid_target`; falha do stream →
   POST; retry `completed`/`running`/`unknown`; descarte) apontar o e2e que o cobre
   (`turn-wait.spec.ts`, `pending-discard.spec.ts`, `critical-journeys.spec.ts`,
   `spec364-409.spec.ts`, `spec363-board.spec.ts`…). [H] Algum ramo sem cobertura.

### Etapa 1 — Testes de caracterização (testes primeiro)

1. **Testes** (`web/e2e/turn-retry.spec.ts`, nome por feature): um caso por ramo sem cobertura da
   matriz, com o backend falso de `fixtures.ts`; cada um asserta o log visível, o botão
   "Tentar de novo"/"Descartar ação pendente", o banner e o número de `POST /game/action*`
   (nenhum envio duplicado). Rodam verdes **contra o código atual**.
2. Só acrescenta teste (W3 permite); nenhum teste existente muda.

### Etapa 2 — `useImageQuote` (R1 item 1)

1. Testes: `image-quote.spec.ts`, `spec352-retrato-pago.spec.ts`, `portrait-overlay.spec.ts`,
   `spec347-retrato.spec.ts` (antes/depois).
2. Extrair; `refreshBalance` ainda vem do App por argumento.

### Etapa 3 — `useSaves` (R1 item 2)

1. Testes: `critical-journeys.spec.ts`, `livro.spec.ts`, `spec354-livro.spec.ts`,
   `vertical-journey.spec.ts`.
2. Extrair `loadHistory` + handlers de save/criação.

### Etapa 4 — `useAuthSession` + `useAccountBalance` (R1 item 3, R1.3)

1. Testes: `account.spec.ts`, `account-lifecycle.spec.ts`, `checkout.spec.ts`,
   `consent.spec.ts`; `web/tests/native.test.mjs`, `authErrors.test.mjs`; pytest
   `tests/test_frontend_auth_bootstrap.py` (§3.5).
2. Mover os 3 efeitos na ordem original; `nativeCtx` atribuído no render.

### Etapa 5 — `useTurn` (R1 item 4, R1.1, R1.2; o mais arriscado)

1. Testes: os da matriz (Etapa 0/1) + `turn-wait`, `pending-discard`, `latency`,
   `outcome-toast`, `interlocutor-speaker`, `spec364-409`; `web/tests/turnStatus.test.mjs`,
   `turnLatency.test.mjs`, `pending.test.mjs`, `typewriter.test.mjs`; pytest
   `tests/test_visual_assets.py` (§3.5).
2. Mover sem reordenar linha (R1.1/R1.2); ajustar ordem de chamada à tabela §3.1.
3. Revisor (W7) compara os corpos de `handleAction`/`retryTurnInner` com `git diff -w
   --color-moved` e confirma "só movido".

### Etapa 6 — `useGameActions` + `GameActionsContext` (R2)

1. Testes: `deck-character.spec.ts`, `card-shop-357.spec.ts`, `spec352-retrato-pago.spec.ts`,
   `combat-outcome.spec.ts`, `deck-combat-342.spec.ts`; `web/tests/deck.test.mjs`,
   `card-rewards.test.mjs`, `card-shop.test.mjs`, `spec347-components.test.mjs`.
2. Criar Context (R2.1), consumir em `CombateTab`/`CharacterTab`, remover as 4 props da cadeia.

### Etapa 7 — `Hud.tsx` por aba + wrappers (R3)

1. Testes: `web/tests/workspaceModel.test.mjs`, `spec347-components.test.mjs`,
   `heardNews.test.mjs`; e2e `workspace-shell.spec.ts`, `dossiers.spec.ts`,
   `mobile-single-pane.spec.ts` (projetos `mobile-320`/`mobile-390`).
2. Um commit para o split (move puro, `git diff --color-moved` mostra só bloco movido) e outro
   para apagar os 2 wrappers.

### Etapa 8 — e2e de prints (R4, se [D1] = sim) e regra (R4.1)

1. Mover os 2 `retrato_marcador_sem_flag_*` para `spec347-retrato.spec.ts`; rodar o arquivo;
   contar `expect(` antes/depois (tem que ser igual para esses 2 testes).
2. Apagar os 4 arquivos; `npm run test:e2e:list` = linha de base − testes deles + 2 (movidos).
3. Acrescentar a regra em `docs/guias/TESTES.md`.

### Etapa 9 — CSS morto (R5)

1. `Grep` da §3.4; `npm run lint` (inclui `css-lint.test.mjs`/`contrast.test.mjs`) verde.

### Etapa 10 — Fechamento

1. Bundle (R7) e `wc -l web/src/App.tsx` no hand-back.
2. Coordenador: e2e completo `--workers=1` e `uv run pytest` 1× no pouso.

## 5. Critérios de aceite

- [ ] R1: 5 hooks em `web/src/hooks/`, um commit cada; `App.tsx` ≤ 350 linhas
- [ ] R1.1/R1.2: revisor confirma por `git diff -w --color-moved` que `handleAction`/`retryTurnInner`
      só mudaram de lugar; nenhum `useCallback`/`useMemo` novo além do R2.1
- [ ] R1.3: nenhum `useEffect` novo além do R2.1; nenhum `eslint-disable` novo
- [ ] R2: as 4 props somem de `PlayScreen`/`Workspace`/`ContextSurface`; `components/combat/*` sem diff
- [ ] R3: `Hud.tsx` e os 2 wrappers apagados; corpos das funções movidos sem alteração
- [ ] R4 (se [D1]): 4 arquivos apagados; `retrato_marcador_sem_flag_1440/_390` verdes no novo arquivo
- [ ] R4.1: regra em `docs/guias/TESTES.md`
- [ ] R5: 2 classes removidas, `Grep` da §3.4 no hand-back
- [ ] R7: `npm test`, `typecheck`, `typecheck:e2e`, `lint`, `build` verdes; e2e completo
      `--workers=1` verde; bundle ≤ +2 %
- [ ] R8/W3: diff de teste só em caminho/import (lista §3.5) + arquivos novos da Etapa 1
- [ ] `uv run pytest` verde (suíte completa offline, coordenador)
- [ ] Nada em `web/e2e/contracts/`, `evals/`, `types.ts`, `combat/deck.ts`
- [ ] Smoke §6 executado
- [ ] Revisão independente (`Sol`, W7) com o oráculo do R7 refeito em ≥ 1 etapa

## 6. Smoke test com LLM real

Contra staging (`https://rpg-ia-master-staging.vercel.app`) **ou** local com chave real
(`uv run uvicorn api:app --port 8000` + `web/dist`), com o build desta branch. Nenhum LLM novo:
o objetivo é pegar regressão de estado/stream que o backend falso não reproduz.

1. Login com e-mail/senha (staging) ou perfil legacy (local); a tela de saves lista as campanhas.
2. Novo jogo com retrato marcado: prólogo chega por stream; a cotação de retrato abre.
3. 2 turnos de texto: chunks aparecem progressivamente, o selo "registrando…" some, custo do
   turno aparece no Livro (staging).
4. Forçar 1 combate; jogar 1 Carta; se houver oferta de retrato de inimigo, "Gerar" (custo pago:
   só se o dono autorizar no momento; senão só verificar que a oferta aparece).
5. Voltar para saves, reabrir a campanha (histórico completo), excluir um save de teste.
6. Logout → tela de login; recarregar e confirmar que não há pendência órfã.

Registrar no hand-back: o que foi feito em cada passo, ids de requisição de erros, se houve.

## 7. Riscos & compatibilidade

- **Corrida no stream/retry** (`App.tsx:580-758`): um "Tentar de novo" durante SSE pendurado
  depende de `turnToken`, `retryBypass` e do closure velho de `busy`. Mitigação: R1.1/R1.2,
  matriz + testes de caracterização antes (Etapas 0–1), extração por último, revisão por
  `--color-moved`.
- **Ordem de efeitos / closures velhas:** mover `useEffect` muda a ordem se os hooks forem
  chamados fora da tabela §3.1; o efeito do ciclo nativo (`:115-126`, deps `[]`) usa
  `resumeSession` do 1º render — continua igual porque `resumeSession` só lê refs. Qualquer
  mudança de deps é proibida (R1.3).
- **Re-render extra com Context:** valor estável (R2.1); sem ele, cada render do `App`
  re-renderizaria todos os consumidores. Hoje as props já mudam de identidade a cada render,
  então o estado final não é pior que o atual.
- **Presença dos handlers:** a UI de espólio/forja/loja/retrato aparece só quando o handler
  existe; o default `{}` do Context preserva isso fora do provider.
- **Conflito com outras sessões (W1):** `App.tsx` (367), `types.ts` (368/371),
  `components/combat/*` (368), `CodexTab.tsx`/`DossierDetail.tsx` (371). A spec não toca os
  quatro últimos; `App.tsx` só depois de 367 pousar.
- **Testes que leem fonte** (§3.5): se a 379 R6 não os tiver convertido, só o caminho muda.
- **Saves/backend:** nenhuma mudança; MockLLM/FallbackLLM inalterados; quota/latência inalteradas.
- **Lint do `react-hooks` v7** (`eslint.config.js:30`, regras do compilador): extrair pode
  acender regra nova (ex.: ref lido no render). Resolver sem `eslint-disable` novo; se não der,
  parar e reportar.

## 8. Decisões do dono

| # | Decisão | Default se o dono não disser |
|---|---|---|
| D1 | Apagar os 4 e2e de prints/diagnóstico (ferramenta de evidência das 201/342/347/354; recuperáveis pelo git). Os 2 testes que rodam sempre são movidos antes. | **Sim**, apagar |
| D2 | Consolidar os ~19 e2e de combate nomeados por spec em 3 por feature, com tabela antes/depois de `expect` e cenários | **Não**; só a regra do R4.1 para e2e novos |
| D3 | Governança de efeitos: manter registry + `effects.spec.ts` (28 testes, projeto `chromium-motion`) ou reduzir a kill switch + reduced-motion. A SPEC-208 R1 define o registry como "fonte da verdade lida pelos testes" (`SPEC-208…md:35,61`), por isso não tem importador no app; `design.test.mjs:62-88` cruza registry ↔ spec; SPEC-320 e 322 ainda o atualizaram. | **Manter** (reduzir seria spec própria) |
| D4 | Unificar de vez as pastas de aba (mover `CombateTab`/`MapTab` de `workspace/tabs/` para `components/tabs/`) | **Não** (churn em arquivo que a 368 toca de perto) |
| D5 | Se a 379 R6 não tiver tratado `test_frontend_auth_bootstrap.py` e `test_visual_assets.py`, a 383 pode trocar só o caminho lido (strings iguais)? | **Sim** |
