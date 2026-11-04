# SPEC-383 — revisão sol (review)

> **Veredito:** `APPROVED_WITH_FOLLOWUPS`
> **Revisor:** Sol (Opus, spec-reviewer) · **Data:** 2026-11-04 · **Commit revisado:** `c622fc0f`

## Escopo

Branch `spec-383`, `main...c622fc0f` (31a875c4..c622fc0f, 9 commits), revisada como refatoração pura do
front. O escopo segue a decisão do coordenador de 04/11: Etapas 1–3, Hud por aba + wrappers, poda dos 4 e2e
de prints, CSS morto e `GameActionsContext`. Etapas 4–5 (`useAuthSession`/`useTurn`) e `useGameActions` ficam
para spec própria. `spec-383-etapa4-wip` **não** foi revisada.

O que conferi:
- Equivalência de `useImageQuote`/`useSaves`/`loadHistory`: corpos byte-iguais aos de `main`; `resetImageQuote`
  só chama setters estáveis do hook; handlers recriados a cada render (R1.2); nenhum `useCallback`/`useMemo`/
  `useEffect` novo nem `eslint-disable` novo (os `useEffect` e o disable `set-state-in-effect` que aparecem no
  diff vieram do `Hud.tsx`, movidos sem mudança); `loadHistory` virou `const` mas só é chamada dentro de
  callbacks e efeitos; `onTurn`/`refreshBalance`/`pushLog` continuam como declarações içadas; todos os refs do
  `core` são declarados antes do `core`.
- Efeitos: os 3 `useEffect` continuam no `App`, na mesma ordem, com as mesmas deps. O `[]` do `rpg:auth-expired`
  captura o `resetImageQuote` do 1º render. Isso é equivalente, porque ele só usa os setters de `useState` do
  hook, que são estáveis.
- `nativeCtx` (R1.4): o `useRef` e a atribuição no render continuam no `App`, intocados.
- Provider (R2/R2.1): valor literal novo a cada render, sem memo, ref ou efeito; os 4 handlers são providos
  sempre; o default é `{}`; só `CombateTab` e `CharacterTab` leem; as props saíram de `PlayScreen`,
  `Workspace`, `ContextSurface`, `CombateTab` e `CharacterTab`; `components/combat/*` sem diff.
- Hud (R3): comparei as linhas de `main:Hud.tsx` com a concatenação dos 8 arquivos novos, sem imports e sem
  `export`. As únicas diferenças são o comentário de cabeçalho do módulo e `../types` → `../../types`.
  É move puro.
- e2e (R4): os 4 arquivos apagados eram opt-in (`test.skip` por env), exceto `retrato_marcador_sem_flag_*`,
  que foi movido para `spec347-retrato.spec.ts:44-63` com `base`/`log`/`withMarkers` e o mesmo `expect`. Omitir
  o `screenshot` condicional é **aceitável**: não era asserção, rodava só com `RPG_SPEC354_PRINTS` e mantê-lo
  violaria o R4.1. A lista dá 462 = 500 − 40 + 2.
- CSS (R5): `.diary__summary` e `.image-offers` removidos; `.image-quote-actions` mantido na regra.
- W3: o diff de teste toca só caminhos (`spec347-components`, `spec389-hud-subclass`, `workspaceModel`, este
  último só tirando os 2 caminhos). `turn-retry.spec.ts` é arquivo novo. Nenhuma asserção mudou.
- `web/e2e/contracts/`, `evals/`, `types.ts`, `combat/deck.ts` e `components/combat/*` sem diff.

## Achados

| ID | Sev. | Arquivo:linha | Problema | Correção |
|---|---|---|---|---|
| P2-1 | P2 | `specs/SPEC-383-refactor-web-app-hooks-e2e.md:442` (§5) e `:535` | O cabeçalho e os critérios ainda descrevem o escopo cheio: R1 com 5 hooks e `App.tsx` ≤ 350 linhas (hoje tem 950), R1.1/R1.2 com `--color-moved` do `useTurn`, Etapa 6 com `useGameActions`. Há duas seções `## 9`. O "Registro de execução" pede uma decisão (a/b) que o coordenador já tomou (b). Do jeito que está, a spec não fecha como `done` com critério honesto. | Coordenador, no pouso: registrar a decisão (b) com data; marcar R1 itens 3–5, R1.1, R1.4(b) e a Etapa 6/`useGameActions` como "movido para SPEC-NNN"; ajustar o critério de linhas ao entregue; renumerar o 2º `## 9` para `## 10`. |
| P2-2 | P2 | `web/e2e/turn-retry.spec.ts:41-43` | No caso (a) (401 no meio do turno), `toHaveCount(0)` da narração tardia é checado com a tela de login aberta, onde o log nem é montado: a asserção sai verdadeira de qualquer jeito. Só a 2ª checagem do heading de login pega uma regressão parcial. Se a resposta tardia for aplicada a `data`/`log` depois do `session++`, o teste não pega. Não bloqueia esta spec, porque o diff não toca `handleAction`, mas este caso é a rede de segurança da futura extração do `useTurn`/`useAuthSession`. | Na spec de seguimento (antes de mover `useTurn`), reforçar com um oráculo observável: por exemplo, logar de novo ou reabrir o save e afirmar que a narração tardia não está no log, e que `posts`/`streams` não cresceram. |
| P3-1 | P3 | `web/src/App.tsx:111` | Warning novo `react-hooks/exhaustive-deps` (`resetImageQuote` no efeito `rpg:auth-expired`); em `main` o `App.tsx` passa sem warning. O comportamento é equivalente (ver Escopo). Corrigir agora exigiria dep nova ou `eslint-disable`, e os dois o R1.3 proíbe. O `lint` não é bloqueante no CI. **Aceitável como está.** | Some naturalmente quando o efeito for para o `useAuthSession` na spec de seguimento. Registrar lá. |
| P3-2 | P3 | `docs/spec201/README.md:15`, `docs/spec201/medicoes.md:14`, `docs/spec201/capturas/INDEX.md` | Apontam para `web/e2e/diagnostics/spec201-capture.spec.ts`, que foi apagado. O arquivo é recuperável pelo git (D1), mas os ponteiros ficaram sem destino. | Uma linha em `docs/spec201/README.md`: "removido na SPEC-383 (D1); recuperar com `git show 1cc92907:web/e2e/diagnostics/spec201-capture.spec.ts`". Opcional. |
| P3-3 | P3 | `web/src/hooks/useSaves.ts:30-151`, `web/src/hooks/useImageQuote.ts:8-107` | As funções-hook têm ~120 e ~100 linhas, acima da regra de função nova ≤ 60. Isso é inerente ao desenho da §3.2: são contêineres de handlers movidos sem mudança, e cada handler interno tem ≤ 30 linhas. O gate de tamanho não cobre `web/`. | Nenhuma ação. Só registro. |

Sem P0/P1.

## Correções aplicadas

Nenhuma: o revisor não edita código. Os achados são todos follow-up ou ajuste do coordenador no pouso.

## Pendências

- P2-1: coordenador, no pouso da 383 (texto da spec).
- P2-2 e P3-1: spec de seguimento de `useAuthSession`/`useTurn`/`useGameActions`, que trata também o lint do
  compilador `react-hooks` v7 (sufixo `Ref` nos refs do `core` ou desenho alternativo).
- Smoke §6 da spec (build da branch contra staging ou local com chave): não executado por esta revisão.
  Decisão do coordenador: rodar ou registrar a dispensa (refatoração sem chamada de LLM nova, e e2e cobre
  saves, retrato e turno).
- Suíte e2e completa `--workers=1` e `uv run pytest`: coordenador, 1×, no pouso.

## Comandos rodados

```text
cd web && npm test                         → 312 pass, 0 fail
npm run typecheck                          → limpo
npm run typecheck:e2e                      → limpo
npm run lint                               → 0 erros, 1 warning (App.tsx:111 exhaustive-deps, P3-1); css-lint/contrast 15/15
git show main:web/src/App.tsx | npx eslint --stdin → 0 achados (o warning é novo)
npx playwright test -c playwright.local.config.ts --workers=1 --project=chromium \
  turn-retry spec347-retrato image-quote spec352-retrato-pago             → 27 passed
  deck-character card-shop-357 combat-outcome workspace-shell dossiers livro → 42 passed
  critical-journeys pending-discard turn-wait                             → 61 passed
npm run build && RPG_E2E_SERVER=preview ... turn-retry spec352-retrato-pago → 15 passed
npm run test:e2e:list                      → Total: 462 tests in 54 files (500 − 40 + 2)
dup_helpers.py --diff main...HEAD          → nenhuma função nova com nome já usado
comparação de linhas main:Hud.tsx × components/tabs/{8 arquivos} → só comentário de cabeçalho e caminho ../../types
git diff main...HEAD --stat -- web/e2e/contracts evals web/src/components/combat web/src/types.ts web/src/combat/deck.ts → vazio
```
