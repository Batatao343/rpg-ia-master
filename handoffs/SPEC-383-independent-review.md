# SPEC-383 — revisão independente da spec `draft` (independent-review)

> **Veredito da spec:** `SAFE-WITH-CHANGES` (equivale a `CHANGES_REQUIRED` na spec antes de `approved`; nenhum código revisado)
> **Revisor:** Opus (spec-reviewer, não autor) · **Data:** 2026-11-03 · **Commit revisado:** `2a6e0945` (main)

## Escopo

`specs/SPEC-383-refactor-web-app-hooks-e2e.md` contra o fonte de `web/` em `2a6e0945`, mais a
auditoria §4.5/§6/§6.5, SPEC-379 R6, SPEC-384 D3 e SPEC-385. Só leitura. Sondas de lint feitas
por `eslint --stdin` (nenhum arquivo versionado escrito). Fora do escopo: e2e e build (proibidos).

## Fatos [F] conferidos

| Fato da spec | Real em `2a6e0945` | OK? |
|---|---|---|
| `App.tsx` 1.136 linhas | **1.141** (commit `94be76db` da SPEC-367 R4–R6, 03/11 15:47, entrou depois da spec) | desatualizado |
| 19 `useState` | 19 | sim |
| 18 `useRef` | **19** (`portraitInFlight`, `App.tsx:83`, SPEC-367 R5) | desatualizado |
| 3 `useEffect` (`:98,:115,:155`) | 3, agora em `:99,:116,:156` | linhas +1 |
| `useCallback` só em `resetTurn`/`clearBanner`/`handleUiError` | sim (`:72,:74,:850`) | sim |
| Linhas do R1.1 (`:581-585`, `:620`, `:654-709`, `:730-753`) | deslocadas em +4/+5 (`handleAction` começa em `:584`, `retryBypass` em `:585/:756`) | ancorar por trecho, não por linha |
| Cadeia das 4 props (`PlayScreen:27-31,130-131`; `Workspace:42-46,365-366`; `ContextSurface:46-50,123,127`; `CombateTab:62-79`; `CharacterTab:48-49,85`; `Hud:39-40`) | todas conferem | sim |
| `Hud.tsx` 577 linhas, 7 abas e auxiliares | confere (`:11,19,26,39,131,170,239,274,390,419`; privados `ProjectionSeal:264`, `Combat:443`, `Bar:524`, `AbyssChip:553`, `CondChips:567`) | sim |
| 4 importadores do `Hud` | confere (`Workspace:6`, `CombateTab:3`, `ContextSurface:4`, `CharacterTab:4`) | sim |
| Wrappers `BestiarioTab`/`PersonagemTab` só reexportam | confere | sim |
| `spec354-prints.spec.ts:16-27` com 2 testes sempre ativos | confere (o loop não tem `test.skip`; só o `screenshot` é condicional). O handoff da 354 (`SPEC-354-sol-review.md:63`) diz o contrário e está errado | sim |
| CSS morto `styles.css:607`, `:1185-1186` | confere; Grep em `web/src`, `web/e2e`, `web/tests`, `tests/` não acha montagem dinâmica | sim |
| Testes que leem fonte (§3.5) | conferem. Não há outros leitores de `App.tsx`/`Hud.tsx`/wrappers além de `tests/test_ci_eval_gates.py:21` (só classifica o caminho). `styles.css` é lido por `test_frontend_visual_contracts.py`, `deck-tokens-342`, `design`, `turnStatus` e `contrast`, nenhum pelas 2 classes | sim |
| Nenhum teste renderiza `CombateTab`/`CharacterTab`/`ContextSurface` com as 4 props | confere (SSR só de `ForjaPanel`, `Arena`, `CombatTab` do Hud) | sim |
| Sem `lazy()`/`import()` dinâmico, sem `manualChunks` | confere | sim |
| Bundle Android versionado | `git ls-files web/android` não tem `assets/public` (a afirmação da 384 D8 não vale para a 383) | sem risco |
| `effects.registry` lido por `design.test.mjs:62-88` | confere; a 383 não toca nele (R6) | sim |

## Requisito a requisito

| Req | Situação | Observação |
|---|---|---|
| R1 (5 hooks, App ≤ 350) | viável | JSX+`artPanel` ≈ 195 linhas; ≤ 350 dá. Ver P0-1, P1-2 e P2-1 |
| R1.1 corpos intactos | ok com ajuste | ancorar por trecho; a revisão por `--color-moved` é boa |
| R1.2 closures | ok | é o ponto certo: o `busy` velho do closure é o motivo do `retryBypass` |
| R1.3 sem efeito/disable novo | **inviável como está** | P0-1 |
| R2 Context | ok | default `{}` preserva a regra "botão só com handler" |
| R2.1 valor estável por ref | **arriscado** | P1-1 |
| R3 split do Hud | ok | move puro; `workspaceModel.test.mjs:253` não precisa acrescentar `BestiaryTab.tsx` (o wrapper não tem `<X`), basta tirar os 2 caminhos |
| R4/R4.1 | ok com ajuste | P2-2 (fórmula de contagem) |
| R5 | ok | |
| R6 | ok | |
| R7 oráculo | fraco para stream real | P1-3 |
| R8/W3 | ok | |

## Achados

| ID | Sev. | Arquivo:linha | Problema | Correção |
|---|---|---|---|---|
| P0-1 | P0 | spec §3.1 último parágrafo + R1.3; `App.tsx:113-114` | A spec manda `nativeCtx.current = {…}` continuar **no render, dentro de `useAuthSession`**, sem `eslint-disable` novo. Sonda (`eslint --stdin` com o mesmo padrão num hook, inclusive com o mesmo `eslint-disable exhaustive-deps` ao lado): `react-hooks/refs` "Cannot access refs during render" → **lint vermelho**. No `App` atual o compilador não analisa o componente (motivo não isolado; não é o disable nem o hoisting), por isso passa hoje. O executor fica travado entre R1.3 e R7. | Decidir na spec antes de aprovar: (a) **default** — `nativeCtx` (o `useRef`, a atribuição no render e o efeito do ciclo nativo) ficam no `App`, e `useAuthSession` recebe `nativeCtx` por argumento; ou (b) exceção explícita a R1.3: 1 `// eslint-disable-next-line react-hooks/refs -- espelho do último render para listeners nativos (SPEC-193)`. Mover para efeito muda o tempo de leitura e fica proibido. |
| P1-1 | P1 | R2.1 | Ref atualizado em `useEffect` (passivo) cria janela entre o commit (DOM já mostra o botão habilitado com `busy=false`) e o flush do efeito, em que o ref ainda aponta para o handler do render anterior, com `busy=true`. Um clique rápido (Playwright clica assim que habilita) cai em `handlePrepareCards` → "Aguarde a ação em andamento." e a aba **desfaz a mudança otimista**; `handleEquip` vira no-op. Hoje a prop é do mesmo render do DOM. Ganho do memo é zero: nenhum consumidor é `memo()` (só `StoryLog`), e todos já re-renderizam por `busy`/`data`. O precedente de `ChatSurface.tsx:59-61` alimenta o `StoryLog` memoizado, outro caso. | Trocar o R2.1 por: o valor do provider é um objeto novo a cada render (`{ onEquip: handleEquip, … }`), **sem** `useMemo`, ref ou efeito. É idêntico à semântica atual das props e dispensa a exceção ao R1.3. (O `react-hooks` v7 não tem regra de valor de context instável; `eslint-plugin-react` não está instalado.) |
| P1-2 | P1 | §3.1 / §3.2 (`core` e refs compartilhados) | Sondas do `react-hooks/immutability`: ref **devolvido por um hook** e mutado por quem chama (`const { gen } = useAccountBalance(); gen.current++`) → "This value cannot be modified". Ref recebido como **argumento** e mutado dentro do hook não acusa. `handleDeletionStarted` (`App.tsx:251-254`) muta `accountBalanceAbort`/`accountBalanceGeneration`, que a spec põe em `useAccountBalance`. Ref só lido no render (`renderedOwner = owner.current :971`, `session.current :979`) acusa `refs` se o `App` passar a ser analisado. | Regra na §3.1: todo ref usado por mais de um hook nasce no `App` (dentro do `core`) e desce por argumento; hook nenhum devolve ref para ser mutado fora. Os refs do saldo entram no `core` (a lista da §3.1 hoje omite `accountBalance`/`setAccountBalance`/os 2 refs e o `pushLog`, que `useTurn` usa em `:625`). Na Etapa 0, rodar `eslint` no `App.tsx` e, a cada etapa, num hook isolado (`--stdin`), para ver cedo se o `App` passou a ser analisado. |
| P1-3 | P1 | R7 / Etapa 1 | O backend falso responde o SSE inteiro de uma vez (`fixtures.ts:368-376`, `route.fulfill`). Existe `delayStream()` e os casos de pendurado e retry (`turn-wait.spec.ts:89,195,227`), mas não há: 401 no meio do turno (`rpg:auth-expired` → `session++` → resposta tardia ignorada); logout ou "Nova jornada" com turno em voo; retry com `running`; duplo envio pelo botão da barra de pendência (`App.tsx:986`). O e2e roda no `vite` dev (StrictMode ligado): bom para efeito duplo, mas nunca exercita o build de produção. | Etapa 1: incluir esses 4 casos na matriz e em `turn-retry.spec.ts`, cada um contando `POST /game/action*` e conferindo que o log não recebe a resposta velha. Etapas 4 e 5: rodar também o escopo com `RPG_E2E_SERVER=preview` (build de produção, `playwright.config.ts:54`). Títulos novos não podem começar por `F01`/`V01`/`M01` (`scripts/frontend_eval_report.py:19-26`). |
| P2-1 | P2 | `tests/test_frontend_auth_bootstrap.py:6`; Etapa 4 | `source.index("const config = await api.getAuthConfig()")` acha a 1ª ocorrência, que hoje é `resumeSession` (`App.tsx:136`), porque o bootstrap usa `let config` (`:160`). Se `useAuthSession` puser o efeito de bootstrap antes de `resumeSession`, a 1ª `const config` vira a de `completeAuthenticatedSession` (depois do guard) e o teste **falha**. Se a 379 já tiver apagado o teste, não se aplica. | Em `useAuthSession`, manter a ordem textual atual: listener, `nativeCtx`, `resumeSession`, bootstrap, `completeAuthenticatedSession`. |
| P2-2 | P2 | R7 × Etapa 8.2 | Fórmula de contagem contraditória: R7 diz "antes − testes dos 4 + 0", a Etapa 8 diz "− testes deles + 2"; e as duas ignoram os testes novos da Etapa 1 (e os e2e que a 379 cria). | Uma fórmula só: `lista_final = lista_pós-Etapa-1 − (testes dos 4 arquivos, incluindo os 2 movidos) + 2`, com a linha de base medida **depois** da Etapa 1. |
| P2-3 | P2 | W1 / cabeçalho | A trava da W1 só olha branches. A 367 (`approved`) e a 368 (`in-progress`) estão sendo commitadas **direto na `main`** (o `App.tsx` mudou hoje às 15:47 sem branch). A W1 sai vazia e mesmo assim haveria corrida. | Gate: 367 e 368 `done` no cabeçalho **e** `git log -1 --since=<início da etapa> -- <arquivos da etapa>` vazio na `main` antes de cada etapa. Atualizar no texto da spec as contagens e linhas de `App.tsx` (1.141 / 19 refs). |
| P2-4 | P2 | SPEC-384 R3.4 × R2/R3 | A 384 D3 apaga `reinforcementNote` em `workspace/tabs/CombateTab.tsx:24,356-357` e oferece "pode ficar para a SPEC-383". A 383 edita o mesmo arquivo (props do R2 e import do R3) e não responde. | Na 383: "fora de escopo; a 384 D3 web pousa antes ou depois, nunca em paralelo (W1)". Na 384, retirar a oferta. |
| P2-5 | P2 | D5 × cabeçalho | O cabeçalho exige a 379 R6 pousada e a D5 cobre o caso de ela não ter tratado. Se a dependência vale, a D5 é morta; se não vale, o cabeçalho está errado. Pela 379 §3.6, os 2 testes Python viram e2e e somem. | Manter a dependência e trocar a D5 por: "se a 379 R6 pousar sem tratar algum desses testes, só o caminho muda". |

**Sem achado:** guard de structured output, valor de LLM, writer persistente e segredo em log
não se aplicam (front puro). A spec não toca `web/e2e/contracts` nem `evals/`.
`critical-journeys.yaml` não lista os 4 arquivos apagados.

## Riscos residuais (aceitos)

- Ordem dos hooks muda de commit para commit; é estática por build, sem efeito persistido.
- `resumeSession` e o bootstrap usam o closure do 1º render (deps `[]`). Hoje só leem refs e
  setters, então mover para o hook não muda nada. Só deixa de valer se alguém passar estado por argumento.
- O smoke §6 é o único oráculo de stream real; o passo 4 (retrato pago) precisa de autorização do dono.

## Mudanças objetivas na spec (para aprovar)

1. P0-1: decidir (a) `nativeCtx` fica no `App` (default) ou (b) disable `refs` explícito.
2. P1-1: R2.1 sem memo e sem ref; tirar a exceção ao R1.3.
3. P1-2: regra "ref compartilhado nasce no `App`"; completar o `core`; sonda de lint por etapa.
4. P1-3: 4 casos novos na Etapa 1; `RPG_E2E_SERVER=preview` nas Etapas 4 e 5.
5. P2-1 a P2-5: ordem textual em `useAuthSession`, fórmula única de contagem, gate de commits diretos na `main`, fronteira com a 384 D3, D5 coerente com a dependência; atualizar 1.141 linhas e 19 refs.

## Comandos rodados

```text
W1 (branches com commits à frente da main, só web/) → spec-371: types.ts, combat/deck.ts, CodexTab.tsx, tabs/DossierDetail.tsx, combat/TargetChip.tsx, FaunaSaber.tsx, e2e/dossiers.spec.ts; App.tsx/Hud/CombateTab/CharacterTab fora de qualquer branch
npx tsc -p tsconfig.json --noEmit → verde (15 s)
npm test → 304 pass, 0 fail (9 s)
npx eslint src/App.tsx src/components/Hud.tsx → 0 achados
eslint --stdin (sondas em $TEMP: ref no render em hook; ref devolvido por hook e mutado; disable ao lado) → refs/immutability acusam como descrito em P0-1/P1-2
git status depois das sondas → nada versionado alterado
```
