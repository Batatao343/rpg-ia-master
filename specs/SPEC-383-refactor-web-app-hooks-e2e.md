# SPEC-383 — Front: hooks do `App.tsx`, `GameActionsContext`, `Hud.tsx` por aba e poda de e2e de prints

> **Status:** `approved` (04/11, coordenador, autonomia do dono na onda: "vai executando o que puder"; D1 = sim, D2 = não, D3 = manter, D4 = não — defaults do §8)
> **Criada:** 2026-11-03 · **Atualizada:** 2026-11-03 (revisão independente aplicada: `handoffs/SPEC-383-independent-review.md`)
> **Origem:** auditoria de qualidade de 03/11 — `docs/auditorias/auditoria-qualidade-codigo-2026-11-03.md` §4.5 (itens 1–7) e §5 letra G; regras da onda em §6.2 (W1 revisada, W2–W8)
> **Depende de:** SPEC-379 R6 pousada (testes que leem o fonte de `App.tsx`); SPEC-367 pousada (commit `94be76db`, mexeu no `App.tsx`); SPEC-368 e SPEC-371 `done` no cabeçalho (tocam `types.ts`, `combat/deck.ts`, `CodexTab.tsx`, `tabs/DossierDetail.tsx`, `components/combat/*`). Gate por etapa: W1 revisada (§4)
> **Desbloqueia:** SPEC-385 (contrato front↔back)
> **EXECUTOR_MODEL obrigatório:** `Terra`
> **REVIEW_MODEL obrigatório:** `Sol`
> **REVIEW_REQUIRED:** `true`
> **EVAL_AUTHORING_REQUIRED:** `false` — `web/e2e/contracts` é caminho protegido de eval (`evals/protected-paths.txt:13`): **não criar nem tocar** (W5)

Rótulos: **[F]** fato conferido no fonte em 03/11 (main `2a6e0945`) · **[H]** hipótese a confirmar na execução · **[D]** decisão do dono (§8).
Números de linha são de `2a6e0945` e **só orientam**: o executor ancora por nome de função/trecho, não por linha.

---

## 1. Contexto & Objetivo

[F] `web/src/App.tsx` tem 1.141 linhas, 19 `useState`, 19 `useRef` (inclui `portraitInFlight`,
`:83`, SPEC-367 R5) e nenhum Context. Num só componente moram autenticação/sessão (`:99-332`),
cotação e confirmação de imagem (`:82-91`, `:379-447`), o turno com stream SSE, fallback POST e
"Tentar de novo" (`:334-377`, `:495-771`), saves/histórico (`:449-493`, `:773-848`) e as ações de
ficha/cartas (`:850-949`). Os quatro handlers `onEquip`/`onPrepareCards`/`onCardReward`/
`onGeneratePortrait` descem por props `App` → `PlayScreen` (`PlayScreen.tsx:27-31,130-131`) →
`Workspace` (`Workspace.tsx:42-46,365-366`) → `ContextSurface` (`ContextSurface.tsx:46-50,123,127`)
→ `CombateTab` (`CombateTab.tsx:62-79`) ou `PersonagemTab` → `CharacterTab`
(`CharacterTab.tsx:48-49,85`) → `FichaTab` (`Hud.tsx:39-40`). `onEquip` atravessa 6 níveis; os 3
de cartas, 5.

[F] `components/Hud.tsx` (577 linhas) não é um HUD: exporta 7 blocos de aba (`FichaTab:39`,
`PeopleTab:131`, `FactionsTab:170`, `HeardNews:239`, `ChronicleTab:274`, `PartyBars:390`,
`CombatTab:419`), os auxiliares `itemIcon:11`, `EquipFn:19`, `useVitalityHit:26` e os privados
`ProjectionSeal:264`, `Combat:443`, `Bar:524`, `AbyssChip:553`, `CondChips:567`. As abas vivem em
duas pastas: `components/tabs/` (implementações) e `workspace/tabs/` (onde `BestiarioTab.tsx` e
`PersonagemTab.tsx` só reexportam o componente de `components/tabs/`, 2–4 linhas cada).

[F] Em `web/e2e/` há 4 arquivos de captura de prints/diagnóstico, opt-in por variável de ambiente
(`deck-342-prints.spec.ts:6`, `spec347-prints.spec.ts:5`, `spec354-prints.spec.ts:30,42,80`,
`diagnostics/spec201-capture.spec.ts:12`). **Exceção:** `spec354-prints.spec.ts:16-27` define
`retrato_marcador_sem_flag_1440`/`_390`, que **rodam sempre** (o laço não tem `test.skip`; só o
`screenshot` é condicional) e são gate. O handoff da 354 (`SPEC-354-sol-review.md:63`) diz o
contrário e está errado. Apagar o arquivo sem mover esses testes perde cobertura. Há 2 classes
CSS sem uso (`styles.css:607`, `styles.css:1185-1186`).

[F] `eslint.config.js:30` aplica as regras recomendadas do `react-hooks` v7, que incluem as
regras do compilador. A revisão testou o mesmo código com `eslint --stdin`: ref lido/escrito
**no render dentro de um hook** acusa `react-hooks/refs`, e ref **devolvido por um hook e mutado
por quem chama** acusa `react-hooks/immutability`. Ref recebido **por argumento** e usado dentro
de callback/efeito não acusa. Hoje o `App` passa limpo (o compilador não o analisa; o motivo não
foi isolado).

Objetivo: refatoração **pura** (W2/W3) que deixa o `App.tsx` em ~300 linhas de composição e
JSX, troca o prop-drilling por um Context e quebra o `Hud.tsx` por aba, **sem mudar um
comportamento observável**. O trecho mais arriscado (turno/stream/retry) vai por último, com
testes de caracterização antes.

## 2. Requisitos

- **R1 — Hooks em `web/src/hooks/`.** O `App.tsx` passa a chamar hooks, um por commit (W4), do
  menos ao mais arriscado:
  1. `useImageQuote`: estado `imageQuote`/`imageBusy`/`imageError`, o ref `portraitInFlight`
     (usado só aqui), `resetImageQuote`, `openImageQuote`, `handleGeneratePortrait` e
     `confirmImageQuote` (`App.tsx:82-91`, `:379-447`).
  2. `useSaves`: `loadHistory`, `handleCreate`, `handleCreateSimulation`, `handleContinue`,
     `handleContinueSave`, `handleDeleteSave` e `handleNew` (`:449-493`, `:773-848`).
  3. `useAuthSession`: o listener `rpg:auth-expired` (`:99-110`), o efeito do ciclo nativo
     (`:116-127`), `resumeSession` (`:131-151`), o bootstrap (`:156-211`),
     `completeAuthenticatedSession`, login/logout/exclusão (`:213-304`) e o saldo
     (`refreshBalance`/`syncAccountBalance`, `:310-332`; pode ser um `useAccountBalance` no mesmo
     arquivo, que só **usa** os refs do `core`). A ordem **textual** dentro do hook é a atual
     (listener, efeito nativo, `resumeSession`, bootstrap, `completeAuthenticatedSession`, …):
     `tests/test_frontend_auth_bootstrap.py:6` acha a **1ª** ocorrência de
     `const config = await api.getAuthConfig()`, que é a de `resumeSession` (`:135`; o bootstrap
     usa `let config`, `:160`).
  4. `useTurn`: `turn`/`resetTurn`, os refs `turnToken`, `retryBypass`, `retrying`,
     `openingMemo`, `streamEntryId`, `pendingVisual`, `simNoticed` e `volatileWarned`, mais
     `markOpening`, `onTurn`, o stream (`ensureStreamId`…`finishStreamEntry`), `refreshTurnCost`,
     `handleAction`, `retryTurn`/`retryTurnInner` e `discardPending` (`:67-72`, `:334-377`,
     `:495-771`). Esses refs são privados do hook: nenhum sai dele.
  5. `useGameActions`: `handleEquip`, `handleCardReward`, `handlePrepareCards`, `handleLevelUp`,
     `handleDeathChoice` e `handleUiError` (`:850-949`). Alimenta o R2.
  Ao fim, o `App.tsx` tem no máximo 350 linhas (meta ~300) e contém só o estado compartilhado
  (§3.1), `nativeCtx`, as chamadas de hook, `artPanel`, o JSX e `LegalLinks`.
- **R1.1 — Guarda de corrida intacta.** O corpo de `handleAction` preserva **exatamente** a
  sequência atual, identificada por trecho:
  - a leitura e zeragem de `retryBypass` antes do teste de `busy` (`const bypass = retryBypass.current; retryBypass.current = false;`);
  - a captura de `gid`/`generation`/`user` e `const token = ++turnToken.current`;
  - `active()` comparando `session`, `gameId` e `turnToken`;
  - `clearOwnPending` com `clearPendingIfOwn`;
  - os ramos `narrativeShown`, 4xx e fallback POST;
  - o `finally` que só destrava se `active()`.

  Em `retryTurnInner` ficam como estão: os dois `turnToken.current++` antes de descartar o fluxo
  SSE (ramos `completed` e `unknown`/`failed`) e o `retryBypass.current = true` logo antes do
  reenvio. Nesses corpos, o diff só pode mudar indentação e o acesso ao `core`
  (ex.: `core.session.current`). Nenhuma linha é reordenada.
- **R1.2 — Semântica de closure intacta.** Todo handler devolvido por hook continua sendo uma
  função recriada a cada render, que lê o estado daquele render (`busy`, `data`, `imageQuote`,
  `imageBusy`, `authRequired`), como hoje. **Proibido** embrulhar em `useCallback`/`useMemo` o
  que hoje não é. Os 3 que já são (`resetTurn`, `clearBanner`, `handleUiError`) mantêm as mesmas
  deps. Motivo: `retryBypass` existe justamente porque o `busy` do closure é velho (comentário em
  `handleAction`). "Consertar" isso muda o comportamento do retry.
- **R1.3 — Nada de `useEffect` novo nem de deps diferentes.** Os 3 efeitos atuais mudam de
  arquivo sem mudar o corpo nem as deps, e o `eslint-disable … exhaustive-deps` do efeito nativo
  (`:126`) vai junto, com o mesmo texto. Nenhum `eslint-disable` novo, salvo a exceção única do
  R1.4(b).
- **R1.4 — `nativeCtx` (P0-1 da revisão).** O `useRef` de `nativeCtx` e a atribuição feita no
  render (`nativeCtx.current = { screen, busy, pending, hasSaves }`, `:114`) **ficam no `App`**.
  O `useAuthSession` recebe `nativeCtx` por argumento e só o lê dentro de callbacks/efeitos.
  (a) Esse é o default. (b) Se a sonda de lint (§4, Etapa 0 e cada etapa) mostrar que o `App`
  passou a ser analisado pelo compilador e `react-hooks/refs` acusar a atribuição no render, vale
  uma única exceção, com este texto exato:
  `// eslint-disable-next-line react-hooks/refs -- espelho do último render para listeners nativos (SPEC-193)`.
  Mover a atribuição para um efeito fica **proibido**, porque muda quando o valor é lido.
- **R1.5 — Refs compartilhados nascem no `App` (P1-2).** Todo ref que mais de um hook usa é
  criado no `App`, entra no `core` e desce por argumento. Nenhum hook devolve um ref para ser
  mutado fora dele. Os refs privados de um só hook (`portraitInFlight`; os do R1 item 4) ficam
  dentro do hook.
- **R2 — `GameActionsContext`.** Novo `web/src/context/GameActionsContext.tsx` com
  `{ onEquip?, onPrepareCards?, onCardReward?, onGeneratePortrait? }`, nas mesmas assinaturas de
  `PlayScreen.tsx:27-31`.
  - O `App` sempre provê os 4. O valor default (sem provider) é `{}`: componentes renderizados
    fora do app (SSR dos testes Node) continuam sem esses botões, como hoje quando a prop falta
    (`CombateTab.tsx:313,328,418,421`; `Hud.tsx:106,112`).
  - Só `CombateTab.tsx` e `CharacterTab.tsx` leem o Context. Eles repassam por prop aos filhos
    atuais (`FichaTab`, `EspolioPanel`, `ForjaPanel`, `LojaCartasPanel`, `CombatDeckTab`,
    `Arena`). **Nenhum arquivo de `components/combat/*` muda.**
  - As 4 props saem de `PlayScreen`, `Workspace`, `ContextSurface`, `CombateTab` e
    `CharacterTab`.
  - `busy`, `onAction` e `onOpenLevelUp` **não** entram no Context: `deck.test.mjs:52` exige
    `busy={busy}` no `<CombatDeckTab`.
- **R2.1 — Valor do provider (P1-1).** O valor é um objeto novo a cada render
  (`{ onEquip: handleEquip, onPrepareCards: handlePrepareCards, … }`), **sem** `useMemo`, ref ou
  efeito. Assim fica idêntico à semântica atual das props: o handler chamado é o do mesmo render
  que pintou o DOM. Um ref atualizado em `useEffect` abriria uma janela em que um clique rápido
  cairia no handler do render anterior (`busy=true`), e o `handlePrepareCards` desfaria a mudança
  otimista. O re-render não piora: nenhum consumidor é `memo()`, e todos já re-renderizam por
  `busy`/`data`.
- **R3 — `Hud.tsx` por aba (move puro).** Cada bloco vai para `web/src/components/tabs/`:
  `FichaTab.tsx`, `PeopleTab.tsx`, `FactionsTab.tsx`, `HeardNews.tsx`, `ChronicleTab.tsx`
  (com `ProjectionSeal`), `PartyBars.tsx` e `CombatTab.tsx` (com `Combat`).
  - Os auxiliares compartilhados (`Bar`, `AbyssChip`, `CondChips`, `itemIcon`, `EquipFn`,
    `useVitalityHit`) vão para `components/tabs/hudParts.tsx`.
  - O corpo das funções fica byte-igual; só os imports mudam.
  - `Hud.tsx` é apagado e os 4 importadores são atualizados (`Workspace.tsx:6`,
    `CombateTab.tsx:3`, `ContextSurface.tsx:4`, `CharacterTab.tsx:4`).
  - `workspace/tabs/BestiarioTab.tsx` e `PersonagemTab.tsx` são apagados. O `ContextSurface`
    passa a importar `BestiaryTab`/`CharacterTab` direto e renderiza com os mesmos props.
- **R4 — e2e de prints.** [D1] Apagar `web/e2e/deck-342-prints.spec.ts`,
  `spec347-prints.spec.ts`, `spec354-prints.spec.ts` e `diagnostics/spec201-capture.spec.ts`.
  - Antes, mover `retrato_marcador_sem_flag_1440`/`_390` (`spec354-prints.spec.ts:8-27`, com
    `withMarkers`, `base` e `log`) para `spec347-retrato.spec.ts`, com os mesmos nomes e
    asserções.
  - Ficam: `deck-342-helpers.ts`, `spec347-helpers.ts` e `fixtures/spec354/save-real.json`
    (outros specs usam), e os diretórios de evidência em `docs/spec201|342|347|354/`.
    `critical-journeys.yaml` não lista os 4 arquivos.
  - Consolidar os e2e de combate nomeados por spec fica **fora**, salvo [D2]; vale só a regra
    do R4.1.
- **R4.1 — Regra para e2e novos.** `docs/guias/TESTES.md` ganha 3 linhas:
  - e2e novo vai no arquivo da **feature** (tabuleiro, Livro, retrato, loja…), não num
    `specNNN-*.spec.ts`;
  - prints de evidência ficam fora do repo ou num script opt-in em `scripts/`, nunca em
    `web/e2e/`;
  - título de teste novo não começa por `F01`/`V01`/`M01` (prefixos do
    `scripts/frontend_eval_report.py:19-26`).
- **R5 — CSS morto.** Remover `.diary__summary` (`styles.css:607`). Remover o seletor
  `.image-offers` de `styles.css:1185`, mantendo `.image-quote-actions` na mesma regra, e a
  `:1186` inteira. Antes, confirmar que nenhuma classe é montada em runtime com esses pedaços
  (§3.4).
- **R6 — Governança de efeitos.** [D3] Default: **manter** `design/effects.registry.ts`,
  `e2e/effects.spec.ts` e o projeto `chromium-motion` (`playwright.config.ts:68-72`) como estão.
  Esta spec não toca neles.
- **R7 — Oráculo (análogo ao W2 para o front).** Em **cada** etapa, antes e depois:
  - `npm test`, `npm run typecheck`, `npm run typecheck:e2e`, `npm run lint` e `npm run build`
    verdes;
  - e2e do escopo da etapa verdes com `--workers=1`. Nas Etapas 4 e 5, também com
    `RPG_E2E_SERVER=preview` (build de produção, `playwright.config.ts:54`; o servidor `vite`
    dev roda com StrictMode).

  Ao fim:
  - suíte e2e completa (`npm run test:e2e -- --workers=1`; coordenador, 1×) verde;
  - contagem: `lista_final = lista_base − (testes dos 4 arquivos apagados, incluindo os 2
    movidos) + 2`, com a `lista_base` (`npm run test:e2e:list`) medida **depois** da Etapa 1;
  - bundle: a soma de bytes de `web/dist/assets/*.js` e `*.css` cresce no máximo 2 %.
- **R8 — W3.** Nenhuma asserção muda. Em teste, só pode mudar caminho de arquivo/import (lista
  em §3.5). Se uma etapa exigir asserção nova ou diferente, ela para, registra no hand-back e não
  segue.

### Fora de escopo

- Trocar `motion` por CSS (`@starting-style`/View Transitions): saiu na auditoria §6.4.
- Apagar `currentPurchaseAdapter`/`WebStripeAdapter`/`selectPurchaseAdapter`: são o gancho da
  SPEC-198 (§6.4). Vale também para `purchases/androidPlay.ts` e para o Capacitor.
- Consolidar os e2e de combate por spec (salvo [D2]) e renomear arquivos `specNNN-*` existentes.
- Reduzir `effects.spec.ts`/registry (salvo [D3], que vira spec própria).
- Mover `workspace/tabs/CombateTab.tsx`/`MapTab.tsx` para `components/tabs/` (salvo [D4]).
- Apagar `reinforcementNote` (`CombateTab.tsx:24,356-357`): é da SPEC-384 D3. A 384 (parte web)
  pousa antes ou depois desta, **nunca em paralelo** (W1), porque as duas editam `CombateTab.tsx`.
- Mudar `components/combat/*`, `types.ts`, `combat/deck.ts`, `CodexTab.tsx` ou
  `tabs/DossierDetail.tsx` (W1); `http.ts`/`api.ts`; `web/e2e/contracts/` (W5); backend.
- Corrigir os comportamentos "estranhos" que a refatoração deixa à vista (closure velho de
  `busy`, ordem de `setState`): anotar como follow-up, não consertar aqui.
- Testes unitários de hook com renderer: o projeto não tem `jsdom`/testing-library, e adicionar
  a dependência não compensa.

## 3. Design técnico

### 3.1 Estado compartilhado e ordem de chamada

Os hooks compartilham estado. Esse estado fica no `App` e desce como um objeto `core`, montado a
cada render, **sem** memo e tipado em `web/src/hooks/core.ts`. O `core` reúne:
- estado e setters: `screen`, `data`, `log`, `busy`, `thinking`, `banner`, `pending`, `saves`,
  `continueData`, `authRequired`, `authConfig`, `accountBalance`;
- refs compartilhados (R1.5): `session`, `owner`, `gameId`, `logSeq`, `accountReturn`,
  `deletionInProgress`, `accountBalanceGeneration`, `accountBalanceAbort` (os dois últimos são
  mutados por `refreshBalance`/`syncAccountBalance` **e** por `handleDeletionStarted`);
- `pushLog`, que o `useTurn` usa.

Cada hook recebe o `core` e, por argumento, as funções de que depende.

`nativeCtx` fica fora do `core`: nasce e é atribuído no `App` (R1.4) e desce só para o
`useAuthSession`. `renderedOwner`/`renderedSession` (`:971-972`) continuam lidos no render do
`App`, como hoje. Se o `App` passar a ser analisado pelo compilador e isso acusar `refs`, a
etapa para e reporta: não se cria disable para isso.

Grafo de dependência (verificado nos corpos atuais) e **ordem de chamada final** no `App`:

| # | Hook | Precisa de |
|---|---|---|
| 1 | `useAccountBalance` | `core` |
| 2 | `useImageQuote` | `core`, `refreshBalance` |
| 3 | `loadHistory` (exportado de `useSaves.ts`, sem estado) | `core` |
| 4 | `useTurn` | `core`, `loadHistory`, `refreshBalance` |
| 5 | `useAuthSession` | `core`, `nativeCtx`, `resetImageQuote`, `resetTurn` (em `handleDeletionStarted`), `loadHistory` (em `resumeSession`), `refreshBalance` |
| 6 | `useSaves` | `core`, `onTurn`, `openImageQuote`, `resetImageQuote`, `resetTurn` |
| 7 | `useGameActions` + valor do provider | `core`, `loadHistory` (em `handleDeathChoice`), `handleGeneratePortrait` |

[F] O app só tem 3 `useEffect` (`:99`, `:116`, `:156`), todos no item 5 e na mesma ordem textual,
então a ordem relativa dos efeitos se mantém. A ordem dos **commits** (R1) é outra: menor risco
primeiro. Enquanto um hook não foi extraído, a função continua no `App` como declaração
(hoisted) e entra por argumento. No commit do `useTurn`, a ordem de chamada passa a ser a da
tabela. Os efeitos com deps `[]` (nativo, bootstrap) usam o closure do 1º render, e hoje só
leem refs e setters. Isso continua valendo porque nenhum estado novo entra por argumento nesses
efeitos.

### 3.2 Arquivos

- **Novos:**
  - `web/src/hooks/core.ts` (tipo `AppCore`);
  - `web/src/hooks/useAuthSession.ts` (com `useAccountBalance`), `useImageQuote.ts`,
    `useSaves.ts`, `useTurn.ts` e `useGameActions.ts`;
  - `web/src/context/GameActionsContext.tsx`: `GameActionsContext`, `GameActionsProvider` e o
    hook de leitura `useGameActionsContext` (nome escolhido para não colidir com
    `useGameActions`);
  - `web/src/components/tabs/{FichaTab,PeopleTab,FactionsTab,HeardNews,ChronicleTab,PartyBars,CombatTab,hudParts}.tsx`.
- **Alterados:**
  - `App.tsx`;
  - `PlayScreen.tsx`, `Workspace.tsx`, `ContextSurface.tsx`, `workspace/tabs/CombateTab.tsx` e
    `components/tabs/CharacterTab.tsx` (props do R2, imports do R3);
  - `styles.css` (R5);
  - `e2e/spec347-retrato.spec.ts` (R4);
  - `e2e/turn-retry.spec.ts`, novo (Etapa 1);
  - `docs/guias/TESTES.md` (R4.1).
- **Apagados:** `components/Hud.tsx`, `workspace/tabs/BestiarioTab.tsx`,
  `workspace/tabs/PersonagemTab.tsx` e os 4 specs do R4.
- `design/primitives.tsx:61` já tem um Context (`ArrivalsContext`); o novo segue o mesmo estilo.
- Os hooks não importam `motion`: `design.test.mjs:90-103` só permite `motion` em arquivos com
  nome da lista. `MotionConfig`/`AnimatePresence` ficam no `App`, como `design.test.mjs:108-111`
  exige.

### 3.3 Assinatura do Context

```ts
export type GameActions = {
  onEquip?: (pick: { item_id?: string; unequip_slot?: string }) => void;
  onPrepareCards?: (prepared: string[]) => Promise<string | null>;
  onCardReward?: RewardSender;
  onGeneratePortrait?: (enemyId: string, priceShards: number, priceMilli?: string) => void;
};
export const GameActionsContext = createContext<GameActions>({});
// App: <GameActionsContext.Provider value={{ onEquip: handleEquip, onPrepareCards: handlePrepareCards,
//        onCardReward: handleCardReward, onGeneratePortrait: handleGeneratePortrait }}>  (R2.1: sem memo)
```

### 3.4 Prova de classe CSS morta (R5)

[F] Em 03/11, um `Grep` por `diary`, `__summary`, `image-offer`, `"image-` e `` `image- `` em
`web/src`, `web/e2e`, `web/tests` e `tests/` não acha montagem dinâmica dessas classes. As
ocorrências são `wizard__summary`, `espolio__offers`, `msg__offers`, `image-quote-*` e
`image-generations`. O executor repete o `Grep` antes de apagar e cola o resultado no hand-back.

### 3.5 Testes que leem fonte e mudam só de caminho (W3)

| Teste | Lê hoje | Depois |
|---|---|---|
| `tests/test_frontend_auth_bootstrap.py:5-9` (ordem de 3 strings) | `App.tsx` | a 379 R6 converte em e2e e apaga (379 §3.6). Se pousar sem tratar: só o caminho vira `hooks/useAuthSession.ts`, e a ordem textual do R1 item 3 faz o teste passar |
| `tests/test_visual_assets.py:209,214` (`"visual: r.visual?.cue"`) | `App.tsx` | idem; se sobrar, o caminho vira `hooks/useTurn.ts` |
| `web/tests/workspaceModel.test.mjs:253-254` (lista de arquivos da shell) | inclui `PersonagemTab.tsx` e `BestiarioTab.tsx` | só **tira** os 2 caminhos (os wrappers não têm `<X`); a lista de nomes do `for` fica intacta |
| `web/tests/spec347-components.test.mjs:53` | `components/Hud.tsx` | `components/tabs/CombatTab.tsx` |
| `web/tests/design.test.mjs:108-111` | `App.tsx` (`MotionConfig`) | sem mudança (fica no App) |
| `web/tests/deck.test.mjs:49-52` | `CharacterTab.tsx`, `CombateTab.tsx` | sem mudança (as regex continuam batendo) |

`tests/test_ci_eval_gates.py:21` só classifica o caminho `web\src\App.tsx` e não muda.

## 4. Plano passo a passo

**Gate antes de cada etapa:**
1. W1 revisada (auditoria §6.2), cruzando três fontes com os arquivos da etapa:
   - branches vivas (à frente da `main`, com commit nos últimos 7 dias);
   - mudanças não commitadas em todos os worktrees, inclusive o checkout principal;
   - `git log --since=2.days --name-only main`.

   Se a interseção não sair vazia, a etapa espera.
2. 368 e 371 `done` no cabeçalho, e `git log -1 --since=<início da etapa> -- <arquivos da etapa>`
   vazio na `main`.
3. RAM livre ≥ 3 GB.

Cada etapa é 1 commit (W4). O oráculo do R7 roda antes (saída A) e depois (saída B) de cada
etapa, e as contagens vão para o hand-back.

**Sonda de lint em cada etapa (P1-2):**
- `npx eslint src/App.tsx src/hooks` verde;
- os hooks novos passam no lint isoladamente;
- se o `App` passar a ser analisado pelo compilador (`refs`/`immutability` acusando no `App`),
  vale o R1.4(b) para `nativeCtx` e mais nada. Qualquer outro achado: parar e reportar.

### Etapa 0 — Linha de base e matriz

1. `npm run build` (anotar os bytes de `dist/assets/*.{js,css}`); `npm test` (contagem; 304 em
   `2a6e0945`); `npx eslint src/App.tsx src/components/Hud.tsx` (0 achados).
2. **Matriz de caracterização do turno** (`handoffs/SPEC-383-turn-matrix.md`). Para cada ramo
   abaixo, apontar o e2e que o cobre (`turn-wait.spec.ts:89,195,227` usa `delayStream()`;
   `pending-discard.spec.ts`, `critical-journeys.spec.ts`, `spec364-409.spec.ts`,
   `spec363-board.spec.ts`…):
   - de `handleAction`/`retryTurnInner`: `completed` por `operation_id`; `running`;
     `narrativeShown` definitivo e não definitivo; 4xx com `shouldClearPending`;
     `invalid_target`; falha do stream → POST; retry `completed`/`running`/`unknown`; descarte;
   - e os 4 casos sem cobertura apontados pela revisão (P1-3):
     - (a) 401 no meio do turno (`rpg:auth-expired` → `session++` → a resposta tardia é
       ignorada);
     - (b) logout ou "Nova jornada" com turno em voo;
     - (c) retry com `running`;
     - (d) duplo envio pelo botão "Consultar / retomar ação pendente" (`App.tsx:987`).

### Etapa 1 — Testes de caracterização (testes primeiro)

1. **Testes** (`web/e2e/turn-retry.spec.ts`, nome por feature): um caso por ramo sem cobertura
   na matriz, **incluindo obrigatoriamente (a)–(d)**. Usam o backend falso de `fixtures.ts` com
   `delayStream()`. O SSE do fake responde inteiro de uma vez (`fixtures.ts:368-376`), então o
   "em voo" é feito com atraso.

   Cada caso asserta:
   - o log visível, e que ele não recebe a resposta velha;
   - o botão "Tentar de novo"/"Descartar ação pendente";
   - o banner;
   - o número de `POST /game/action*` (nenhum envio duplicado).

   Títulos sem prefixo `F01`/`V01`/`M01`. Os casos rodam verdes **contra o código atual**, com
   o servidor dev e com `RPG_E2E_SERVER=preview`.
2. A etapa só acrescenta testes (W3 permite); nenhum teste existente muda. Depois dela, medir a
   `lista_base` (`npm run test:e2e:list`) do R7.

### Etapa 2 — `useImageQuote` (R1 item 1)

1. Testes antes/depois: `image-quote.spec.ts`, `spec352-retrato-pago.spec.ts`,
   `portrait-overlay.spec.ts`, `spec347-retrato.spec.ts`; `web/tests/spec352-portrait-order.test.mjs`,
   `spec363-portrait-offer.test.mjs`.
2. Extrair o hook. `refreshBalance` ainda vem do App por argumento; `portraitInFlight` entra no
   hook.

### Etapa 3 — `useSaves` (R1 item 2)

1. Testes: `critical-journeys.spec.ts`, `livro.spec.ts`, `spec354-livro.spec.ts`,
   `vertical-journey.spec.ts`.
2. Extrair `loadHistory` e os handlers de save/criação.

### Etapa 4 — `useAuthSession` + `useAccountBalance` (R1 item 3, R1.3, R1.4, R1.5)

1. Testes:
   - e2e: `account.spec.ts`, `account-lifecycle.spec.ts`, `checkout.spec.ts`,
     `consent.spec.ts`, `turn-retry.spec.ts` casos (a)/(b); também com
     `RPG_E2E_SERVER=preview`;
   - Node: `web/tests/native.test.mjs`, `authErrors.test.mjs`;
   - pytest: `tests/test_frontend_auth_bootstrap.py`, se ainda existir (§3.5).
2. Mover os 3 efeitos na ordem textual original. `nativeCtx` fica no `App` (R1.4). Os refs do
   saldo vão para o `core` (R1.5).

### Etapa 5 — `useTurn` (R1 item 4, R1.1, R1.2; o mais arriscado)

1. Testes:
   - e2e: toda a matriz (Etapas 0/1) mais `turn-wait`, `pending-discard`, `latency`,
     `outcome-toast`, `interlocutor-speaker` e `spec364-409`, também com
     `RPG_E2E_SERVER=preview`;
   - Node: `web/tests/turnStatus.test.mjs`, `turnLatency.test.mjs`, `pending.test.mjs`,
     `typewriter.test.mjs`;
   - pytest: `tests/test_visual_assets.py`, se ainda ler `App.tsx` (§3.5).
2. Mover sem reordenar linha (R1.1/R1.2) e ajustar a ordem de chamada à tabela da §3.1.
3. O revisor (W7) compara os corpos de `handleAction`/`retryTurnInner` com
   `git diff -w --color-moved` e confirma que foram só movidos.

### Etapa 6 — `useGameActions` + `GameActionsContext` (R2, R2.1)

1. Testes:
   - e2e: `deck-character.spec.ts`, `card-shop-357.spec.ts`, `spec352-retrato-pago.spec.ts`,
     `combat-outcome.spec.ts`, `deck-combat-342.spec.ts`;
   - Node: `web/tests/deck.test.mjs`, `card-rewards.test.mjs`, `card-shop.test.mjs`,
     `spec347-components.test.mjs`.
2. Criar o Context com o valor novo a cada render (R2.1), ler em `CombateTab`/`CharacterTab` e
   remover as 4 props da cadeia.

### Etapa 7 — `Hud.tsx` por aba + wrappers (R3)

1. Testes:
   - Node: `web/tests/workspaceModel.test.mjs`, `spec347-components.test.mjs`,
     `heardNews.test.mjs`;
   - e2e: `workspace-shell.spec.ts`, `dossiers.spec.ts`, `mobile-single-pane.spec.ts` (projetos
     `mobile-320`/`mobile-390`).
2. Dois commits:
   - o split, como move puro (`git diff --color-moved` mostra só bloco movido);
   - a remoção dos 2 wrappers, tirando os 2 caminhos do `workspaceModel.test.mjs`.

### Etapa 8 — e2e de prints (R4, se [D1] = sim) e regra (R4.1)

1. Mover os 2 `retrato_marcador_sem_flag_*` para `spec347-retrato.spec.ts` e rodar o arquivo.
   O número de `expect(` desses 2 testes tem que ser igual antes e depois.
2. Apagar os 4 arquivos e conferir a fórmula de contagem do R7.
3. Acrescentar a regra em `docs/guias/TESTES.md`.

### Etapa 9 — CSS morto (R5)

1. Repetir o `Grep` da §3.4 e rodar `npm run lint` (inclui `css-lint.test.mjs`/`contrast.test.mjs`)
   até ficar verde.

### Etapa 10 — Fechamento

1. Colocar no hand-back o bundle (R7) e o `wc -l web/src/App.tsx`.
2. Coordenador: e2e completo `--workers=1` e `uv run pytest` 1× no pouso.

## 5. Critérios de aceite

- [ ] R1: 5 hooks em `web/src/hooks/`, um commit cada; `App.tsx` com no máximo 350 linhas
- [ ] R1.1/R1.2: o revisor confirma por `git diff -w --color-moved` que `handleAction`/`retryTurnInner`
      só mudaram de lugar; nenhum `useCallback`/`useMemo` novo
- [ ] R1.3: nenhum `useEffect` novo; nenhum `eslint-disable` novo (salvo R1.4(b), se acionado e justificado no hand-back)
- [ ] R1.4/R1.5: `nativeCtx` e os refs compartilhados nascem no `App`; nenhum hook devolve ref
- [ ] R2/R2.1: as 4 props saem de `PlayScreen`/`Workspace`/`ContextSurface`; valor do provider sem memo/ref/efeito; `components/combat/*` sem diff
- [ ] R3: `Hud.tsx` e os 2 wrappers apagados; corpos das funções movidos sem alteração
- [ ] R4 (se [D1]): os 4 arquivos apagados; `retrato_marcador_sem_flag_1440/_390` verdes no novo arquivo
- [ ] R4.1: regra em `docs/guias/TESTES.md`
- [ ] R5: as 2 classes removidas, `Grep` da §3.4 no hand-back
- [ ] Etapa 1: `turn-retry.spec.ts` cobre (a)–(d) e os ramos sem cobertura, verde antes e depois, também em `preview`
- [ ] R7: `npm test`, `typecheck`, `typecheck:e2e`, `lint` e `build` verdes; e2e completo
      `--workers=1` verde; a fórmula de contagem confere; bundle com no máximo +2 %
- [ ] R8/W3: diff de teste só em caminho/import (lista da §3.5) mais os arquivos novos da Etapa 1
- [ ] `uv run pytest` verde (suíte completa offline, coordenador)
- [ ] Nada mudou em `web/e2e/contracts/`, `evals/`, `types.ts`, `combat/deck.ts`, `components/combat/*`
- [ ] Smoke §6 executado
- [ ] Revisão independente (`Sol`, W7) com o oráculo do R7 refeito em pelo menos 1 etapa

## 6. Smoke test com LLM real

Rodar com o build desta branch, contra staging (`https://rpg-ia-master-staging.vercel.app`)
**ou** local com chave real (`uv run uvicorn api:app --port 8000` + `web/dist`). Não há chamada
de LLM nova: o objetivo é pegar regressão de estado/stream que o backend falso não reproduz.

1. Login com e-mail/senha (staging) ou perfil legacy (local): a tela de saves lista as campanhas.
2. Novo jogo com retrato marcado: o prólogo chega por stream e a cotação de retrato abre.
3. 2 turnos de texto: os chunks aparecem aos poucos, o selo "registrando…" some e o custo do
   turno aparece no Livro (staging).
4. Forçar 1 combate e jogar 1 Carta. Se houver oferta de retrato de inimigo, clicar "Gerar"
   **só se o dono autorizar o custo na hora**; senão, só verificar que a oferta aparece.
5. Voltar para saves, reabrir a campanha (histórico completo) e excluir um save de teste.
6. Logout → tela de login. Recarregar e confirmar que não há pendência órfã.

Registrar no hand-back o que foi feito em cada passo e os ids de requisição dos erros, se houver.

## 7. Riscos & compatibilidade

- **Corrida no stream/retry** (`handleAction`/`retryTurnInner`). Um "Tentar de novo" durante um
  SSE pendurado depende de `turnToken`, `retryBypass` e do closure velho de `busy`. Mitigação:
  - R1.1/R1.2;
  - matriz e testes de caracterização antes, incluindo 401, logout e "Nova jornada" em voo
    (Etapas 0–1);
  - build de produção (`preview`) nas Etapas 4/5;
  - extração por último e revisão por `--color-moved`.
- **Ordem de efeitos / closures velhas.** Mover `useEffect` muda a ordem se os hooks forem
  chamados fora da tabela da §3.1. O efeito nativo e o bootstrap (deps `[]`) usam o closure do 1º
  render e só leem refs/setters. Mudar deps é proibido (R1.3).
- **Lint do `react-hooks` v7** (`eslint.config.js:30`). Ref no render dentro de hook acusa
  `refs`; ref devolvido e mutado fora acusa `immutability`. Mitigação: R1.4, R1.5 e a sonda por
  etapa. Achado novo que não caiba no R1.4(b): parar e reportar.
- **Context.** O valor novo a cada render (R2.1) reproduz as props atuais. Um valor memoizado
  por ref criaria a janela do clique rápido (P1-1). Nenhum consumidor é `memo()`, então não há
  re-render a mais.
- **Presença dos handlers.** A UI de espólio, forja, loja e retrato só aparece quando o handler
  existe. O default `{}` do Context preserva isso fora do provider.
- **Conflito com outras sessões (W1 revisada).**
  - `App.tsx` mudou hoje direto na `main` (`94be76db`, 367), e a 368 também commita na `main`.
    O gate da §4 olha `git log` e worktrees, não só branches.
  - A branch `spec-371` toca `types.ts`, `combat/deck.ts`, `CodexTab.tsx`,
    `tabs/DossierDetail.tsx`, `combat/TargetChip.tsx`, `FaunaSaber.tsx` e
    `e2e/dossiers.spec.ts`. A Etapa 7 roda `dossiers.spec.ts` só como teste, sem editá-lo.
  - A 384 D3 web edita `CombateTab.tsx`: pousa antes ou depois, nunca em paralelo.
- **Testes que leem fonte** (§3.5): a 379 R6 trata. Se sobrar algum, só o caminho muda.
- **Saves/backend:** nada muda. MockLLM/FallbackLLM, quota e latência ficam iguais. O bundle
  Android não é versionado (`git ls-files web/android` sem `assets/public`).

## 8. Decisões do dono

| # | Decisão | Default se o dono não disser |
|---|---|---|
| D1 | Apagar os 4 e2e de prints/diagnóstico (ferramenta de evidência das 201/342/347/354; recuperáveis pelo git). Os 2 testes que rodam sempre são movidos antes. | **Sim**, apagar |
| D2 | Consolidar os ~19 e2e de combate nomeados por spec em 3 por feature, com tabela antes/depois de `expect` e cenários | **Não**; só a regra do R4.1 para e2e novos |
| D3 | Governança de efeitos: manter o registry + `effects.spec.ts` (28 testes, projeto `chromium-motion`) ou reduzir a kill switch + reduced-motion. A SPEC-208 R1 define o registry como "fonte da verdade lida pelos testes" (`SPEC-208…md:35,61`), por isso ele não tem importador no app. `design.test.mjs:62-88` confere o registry contra o spec, e as SPEC-320 e 322 ainda o atualizaram. | **Manter** (reduzir seria spec própria) |
| D4 | Unificar de vez as pastas de aba (mover `CombateTab`/`MapTab` de `workspace/tabs/` para `components/tabs/`) | **Não** (churn num arquivo que a 368/384 tocam de perto) |

## 9. Resposta à revisão (`handoffs/SPEC-383-independent-review.md`)

| Achado | Resposta |
|---|---|
| P0-1 `nativeCtx` no render dentro de hook | **Aceito**, opção (a) como default e (b) como exceção textual única (R1.4). Divergência pequena: o **efeito** do ciclo nativo vai para o `useAuthSession` (recebe `nativeCtx` por argumento e só o lê em callback, que a sonda da revisão mostrou não acusar). Assim os 3 efeitos ficam juntos e na ordem original. Só o `useRef` e a atribuição no render ficam no `App`. Se a sonda da Etapa 4 acusar algo no efeito movido, ele volta ao `App` logo após a chamada do `useAuthSession` e a ordem é registrada no hand-back. |
| P1-1 Context com ref atualizado em efeito | **Aceito** (R2.1 reescrito: valor novo por render; exceção ao R1.3 removida). |
| P1-2 refs entre hooks / `immutability` | **Aceito** (R1.5; `core` completo com saldo, os 2 refs e `pushLog`; sonda de lint por etapa). |
| P1-3 casos de stream e build de produção | **Aceito** (casos (a)–(d) obrigatórios na Etapa 1; `RPG_E2E_SERVER=preview` nas Etapas 1, 4 e 5; regra de prefixo de título). |
| P2-1 ordem textual em `useAuthSession` | **Aceito** (R1 item 3). |
| P2-2 fórmula de contagem | **Aceito** (fórmula única no R7, base depois da Etapa 1). |
| P2-3 commits direto na `main` | **Aceito** (gate da §4 com W1 revisada + `git log`; cabeçalho e fatos atualizados: 1.141 linhas, 19 refs, 367 pousada). |
| P2-4 `reinforcementNote` × 384 D3 | **Aceito** (fora de escopo, nunca em paralelo). A retirada da oferta no texto da 384 é com o autor/coordenador da 384 (não edito outro arquivo). |
| P2-5 D5 × dependência | **Aceito** (D5 removida; dependência mantida; §3.5 diz que só o caminho muda se sobrar teste). |
| Nota sobre `workspaceModel.test.mjs:253` | **Aceito** (só tirar os 2 caminhos). |

Nada foi rejeitado.

## 9. Registro de execução (04/11, executor) — PARCIAL, etapas 4-5 bloqueadas

Entregue (1 commit por etapa, oráculo antes/depois verde): Etapa 1 (`turn-retry.spec.ts`, 7 casos, verdes em dev e `preview`; matriz em `handoffs/SPEC-383-turn-matrix.md`; `lista_base` = 500), Etapa 2 (`useImageQuote`), Etapa 3 (`useSaves` + `loadHistory`), Etapa 7 (split do `Hud.tsx` + remoção dos 2 wrappers), Etapa 8 (4 specs de print apagados, 40 testes; `retrato_marcador_sem_flag_*` movidos; lista final 462 = 500 − 40 + 2; regra R4.1), Etapa 9 (CSS morto), R2 (Context; ver desvio 3). Bundle 843.264 → 844.302 bytes (+0,12 %).

**Bloqueio (Etapa 4, `useAuthSession`)** — a sonda de lint do §4 reprovou. Ao extrair o hook, o compilador do `react-hooks` v7 passa a analisar `App` e o hook (nos commits 2 e 3 os hooks escaparam da análise por bailout, não porque estejam limpos). Achados, 20 erros no total:
1. `App`: `react-hooks/refs` em `nativeCtx.current = …` (R1.4(b) cobre) e em `renderedOwner = owner.current` / `renderedSession = session.current` (§3.1 manda parar e reportar, sem disable).
2. Hook: `react-hooks/immutability` "This value cannot be modified" em toda mutação de `owner.current`/`gameId.current`/`accountReturn.current`/… desestruturado do `core` (o compilador só reconhece ref por nome terminado em `Ref` ou por `useRef` local; ref dentro de objeto de argumento é "prop"). Testado: renomear no hook (`owner: ownerRef`) zera esses erros, mas altera todo corpo (`owner.current` → `ownerRef.current`).
3. Hook: `exhaustive-deps` nos efeitos `[]` (membros do `core` não são estáveis) — corrigir exige deps novas (proibido, R1.3) ou `eslint-disable` novo (proibido).
4. Hook: "accessed before it is declared" para `resumeSession` usada no efeito nativo (exige reordenar; o teste Python que travava a ordem já foi removido pela 379).
Trabalho em `spec-383-etapa4-wip` (branch local, não pousar). As etapas 5 (`useTurn`) e a parte `useGameActions` da Etapa 6 dependem da mesma decisão do coordenador/dono: (a) autorizar renomear os refs do `core` com sufixo `Ref` + os disables mínimos, ou (b) manter `useAuthSession`/`useTurn` fora e fechar a spec com o que foi entregue.

Desvios: (1) 1 `warning` `exhaustive-deps` (`resetImageQuote` no efeito `rpg:auth-expired`) desde a Etapa 2: a função agora vem de hook, deixa de ser reconhecida como estável; corrigir exigiria dep nova ou disable. (2) `web/tests/spec389-hud-subclass.test.mjs` também lia `Hud.tsx` (faltava na tabela §3.5): só o caminho virou `tabs/FichaTab.tsx`. (3) R2 foi feito sem `useGameActions`: `handleEquip`/`handleCardReward`/`handlePrepareCards` seguem no `App` e o `GameActionsProvider` recebe-os direto (valor novo a cada render, R2.1). (4) Ao mover `retrato_marcador_sem_flag_*`, o `screenshot` condicional a `RPG_SPEC354_PRINTS` (e `OUT`) ficou de fora, para não deixar print em `web/e2e/` (R4.1); `expect(` por teste igual (1). (5) Nas linhas de CSS do R5 houve deslocamento de +1. Playwright local sem ffmpeg: rodado com um config local não versionado (`video`/`trace` off).
