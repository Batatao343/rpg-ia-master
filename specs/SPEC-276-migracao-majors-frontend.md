# SPEC-276 — Migração das versões principais do frontend (Vite 8, React 19, TypeScript 7, Playwright 1.64)

> **Status:** `done` (parcial pela R5) — aprovada e executada em 19/10 ("escreve e executa"). Entregues Playwright 1.64,
> Vite 8 + plugin-react 6 e `npm audit` limpo; TypeScript 7 e React 19 **bloqueados** (ver §8).
> **Criada:** 2026-10-19 · **Atualizada:** 2026-10-19
> **Depende de:** nada (`web/` em `main`; rebaseada sobre `da6186b`, que trouxe ESLint/`typecheck:e2e`)
> **Desbloqueia:** fechar os PRs do Dependabot #35, #37, #40, #41, #42; atualizações semanais de npm voltam a ser minor/patch

---

## 1. Contexto & Objetivo

O Dependabot (SPEC-225 R3) abriu cinco PRs de versão principal em `web/` que ficaram parados por
serem mudanças quebradoras:

| PR | Pacote(s) | De → para |
|---|---|---|
| #35 | `vite` | 5.4.21 → 8.3.4 |
| #37 | `@playwright/test` | 1.55.1 → 1.64.1 |
| #40 | `react` + `@types/react` | 18.3 → 19.3.1 / 19.3.0 |
| #41 | `react-dom` + `@types/react-dom` | 18.3 → 19.3.1 / 19.3.0 |
| #42 | `typescript` | 5.9.3 → 7.0.2 |

Os PRs isolados não passam sozinhos: #40 e #41 separam `react` de `react-dom` (o 19 exige o par na
mesma versão) e #35 não sobe `@vitejs/plugin-react` (a 4.x não aceita Vite 8). Esta spec faz a
migração por etapas, um major por commit, com rollback por `git revert` do commit da etapa.

## 2. Requisitos

- **R1** — Cada major entra num commit próprio, na ordem da §4; cada commit deixa `web/` verde nos critérios da §5.
- **R2** — `react` e `react-dom` (e os `@types`) sobem juntos; `@vitejs/plugin-react` sobe com o Vite.
- **R3** — Nenhum arquivo protegido de eval é alterado (`evals/`, `web/e2e/critical-journeys.yaml`,
  metrics registry, manifest lock). Se uma etapa exigir isso, ela para e o caso vai para o coordenador.
- **R4** — Bundle de produção (JS+CSS em `web/dist/assets`, bytes brutos e gzip) não cresce mais de 5 % sobre a linha de base.
- **R5** — Major inviável (quebra sem saída razoável ou dependência sem suporte) é interrompido e documentado na §8;
  as etapas que passaram são entregues.
- **R6** — (pedido do coordenador, 19/10) `npm audit` da árvore completa limpo no fim; o que não tiver correção sem
  quebra vai para allowlist com prazo (padrão SPEC-225). Com o audit limpo, o job `npm-audit-full` deixa de ser informativo.
- **R7** — `npm run typecheck:e2e` e `npm run lint` (não bloqueantes no CI desde o Workspace #10) não pioram em relação à `main`.

### Fora de escopo

- Adotar recursos novos (React Compiler, Actions/`use`, Rolldown `codeSplitting`, API nova do TS 7.1).
- Mudar os workflows do GitHub (Node 20 do CI já atende Vite 8: `^20.19 || >=22.12`).
- Capacitor/Android, `motion`, `@axe-core/playwright` (sem major pendente).

## 3. Inventário de mudanças quebradoras (changelogs oficiais) e impacto no repo

### 3.1 Playwright 1.56 → 1.64 ([release notes](https://playwright.dev/docs/release-notes))
- 1.57 remove `page.accessibility`; 1.58 remove seletores `_react`/`_vue` e a opção `devtools`; 1.60 remove
  `ariaRef`, `videosPath`/`videoSize`, `logger` em `connect`; 1.62 isola o clipboard em headless;
  1.64: `window.screen`/media queries passam a refletir a tela emulada do descritor de dispositivo, JSX em
  arquivo de teste segue o `tsconfig`, `--update-snapshots=missing` passa, elementos em iframe oculto contam como ocultos.
- **Impacto:** nenhum uso das APIs removidas (`grep` em `e2e/`, `tests/`). O projeto `mobile-*` usa
  `devices["Pixel 5"]`; a mudança de `window.screen` só importa se o app ler `screen.*` — não lê (o layout usa
  `matchMedia`/largura do viewport, que já seguiam o viewport). Clipboard: `SupportCode` já trata falha.
  O navegador local (`~/.agent-browser/browsers/chrome-*`) continua sendo usado via `executablePath`; o CI baixa o Chromium do pacote.

### 3.2 TypeScript 5.9 → 7.0 ([anúncio 7.0](https://devblogs.microsoft.com/typescript/announcing-typescript-7-0/))
- Compilador nativo (Go). Viram erro: `target: es5`, `moduleResolution node/node10/classic`, `baseUrl`,
  `module amd/umd/system/none`, `esModuleInterop/allowSyntheticDefaultImports: false`, `asserts` em import.
- Defaults novos: `strict` ligado, `types: []`, `rootDir: ./`, `noUncheckedSideEffectImports` ligado.
- **Sem API programática** na 7.0 (`import ts from 'typescript'` deixa de existir).
- **Impacto:** os `tsconfig` já usam `bundler`/`ESNext`/`strict` e não dependem de `types` globais.
  `web/tests/voice.test.mjs` usa `ts.transpileModule` → passa a usar `transform` do `esbuild`
  (mesmo padrão dos demais testes Node). Efeito de side-effect imports (`import "./x.css"`) é verificado no `tsc -b`.

### 3.3 Vite 5 → 8 ([migração v8](https://vite.dev/guide/migration), v6/v7 idem)
- v6: API de ambiente, Sass moderno por padrão, `resolve.conditions` explícito. v7: Node `^20.19 || >=22.12`,
  `build.target` padrão `baseline-widely-available`. v8: Rolldown substitui Rollup e Oxc substitui esbuild
  (transform, minificação JS; Lightning CSS minifica CSS), `esbuild` vira opcional, `build.rollupOptions` →
  `rolldownOptions`, interop CJS consistente, `manualChunks` em objeto removido, alvo Chrome 111/Safari 16.4.
- `@vitejs/plugin-react` 4 → 6 (peer `vite ^8`).
- **Impacto:** `vite.config.ts` não usa `rollupOptions`, Sass nem `manualChunks`. Os testes Node
  (`web/tests/*.test.mjs`) importam `esbuild` diretamente, que vinha transitivo do Vite 5 → vira
  `devDependency` explícita. Minificador diferente muda o tamanho do bundle → medido contra R4.

### 3.4 React 18 → 19 ([guia de upgrade](https://react.dev/blog/2024/04/25/react-19-upgrade-guide))
- Removidos: `ReactDOM.render/hydrate`, `unmountComponentAtNode`, `findDOMNode`, string refs, contexto legado,
  `propTypes`/`defaultProps` em componente função. `ref` vira prop (`forwardRef` segue funcionando).
  Erros de render não são relançados (vão para `window.reportError`/`onUncaughtError`).
- Tipos: `useRef` exige argumento, namespace global `JSX` removido (usar `React.JSX`), `ReactElement["props"]`
  passa a `unknown`, callbacks de ref não podem retornar valor implícito.
- **Impacto:** o app usa `createRoot`; `forwardRef` em `ChatSurface`/`Workspace` continua válido. Erros de tipo
  são levantados pelo `tsc -b` e corrigidos pontualmente.

## 4. Plano passo a passo

Linha de base (main 4c4167b): `npm run build` verde, 133 testes Node, Playwright completo (§5), bundle
JS 510 743 B (gzip 163,1 kB) + CSS 91 981 B (gzip 17,8 kB).

### Etapa 1 — Playwright 1.64
1. `npm i -D @playwright/test@1.64.1`; ajustar só se algo quebrar.
2. Verificação: Playwright completo + testes Node. Rollback: `git revert` do commit.

### Etapa 2 — TypeScript 7
1. `voice.test.mjs` troca `typescript` por `esbuild.transform` (sem mudar asserts).
2. `npm i -D typescript@7.0.2`; corrigir erros de `tsc -b` se houver.
3. Verificação: `npm run build`, testes Node, Playwright.

### Etapa 3 — Vite 8 + @vitejs/plugin-react 6
1. `npm i -D vite@8.3.4 @vitejs/plugin-react@6 esbuild` (esbuild explícito para os testes Node).
2. Verificação: build, bundle (R4), testes Node, Playwright, smoke visual 390/1440.

### Etapa 4 — React 19 (+ react-dom e tipos)
1. `npm i react@19.3.1 react-dom@19.3.1 && npm i -D @types/react@19.3.0 @types/react-dom@19.3.0`.
2. Corrigir erros de tipo/comportamento; verificar os mesmos critérios.

## 5. Critérios de aceite

- [ ] `npm run build` verde (inclui `tsc -b` sem erro) após cada etapa
- [ ] Testes Node (`npm test`) 100 % verdes
- [ ] Playwright completo verde em Chromium (todos os projetos, inclui jornadas críticas F01–F40, M01–M07 e efeitos)
- [ ] Bundle JS+CSS (bruto e gzip) ≤ linha de base + 5 %
- [ ] Smoke visual 390×844 e 1440×900 contra `vite preview` sem erro de console/pageerror
- [ ] Nenhum arquivo protegido de eval alterado
- [ ] `npm audit` (árvore completa) com 0 vulnerabilidades
- [ ] `typecheck:e2e`/`lint` sem piora contra a `main`
- [ ] `uv run pytest` verde (o backend serve `web/dist`)
- [x] Revisão independente Opus em `handoffs/SPEC-276-review.md` — APPROVED_WITH_FOLLOWUPS (F1 aplicado)

## 6. Smoke

Sem LLM: a mudança é só de toolchain do cliente. O smoke é visual/console (§5) contra o build.

## 7. Riscos & compatibilidade

- Saves/API: inalterados (só `web/`).
- CI usa Node 20 (`setup-node` resolve 20.19+); Vite 8/Rolldown exigem `^20.19`.
- Tamanho do bundle muda com Oxc/Lightning CSS; R4 controla.
- Rollback: cada etapa é um commit; `git revert <sha>` + `npm ci` restaura o major anterior.

## 8. Execução (registro)

Medição de tamanho: soma dos `.js`/`.css` de `web/dist/assets`, bytes brutos e gzip -9 (Python `gzip`).
Linha de base final = `main` `da6186b`: **607 570 B / 181 877 B gzip**.

| Etapa | Resultado | Commit |
|---|---|---|
| 1 Playwright 1.64.1 | **entregue.** Nenhuma API removida em uso. Exige `npx playwright install chromium` (o CI já faz). `typecheck:e2e` cai de 25 para 4 erros (tipos novos do runner). | `0375dba` |
| 2 TypeScript 7.0.2 | **bloqueado.** Funcionou antes do rebase (só `src/vite-env.d.ts` para `noUncheckedSideEffectImports` e `voice.test.mjs` sem `ts.transpileModule`), mas a `main` trouxe `typescript-eslint` 8.71 com peer `typescript >=4.8.4 <6.1.0`: o TS 7 não tem API programática e o `npm ci` recusaria o peer. Sem saída razoável até o typescript-eslint suportar o TS 7 (ou a 7.1 trazer a API nova). Caminho intermediário possível: TS 6.0 (fora do escopo dos PRs). | — |
| 3 Vite 8.3.4 + plugin-react 6.1.2 | **entregue.** `esbuild` explícito (os testes Node o importam; o Vite 8 o tornou opcional). `build.target` fixado no alvo `modules` do Vite 5 (es2020/chrome87/safari14/firefox78/edge88) para não derrubar WebView/iOS antigos. Bundle **622 832 B (+2,5 %) / 181 058 B gzip (−0,5 %)**; o CSS cresce ~13 kB porque o Lightning CSS gera fallbacks para esse alvo. Build 1,7 s → 0,36 s. | `962ce43` |
| 4 React 19.3.1 | **bloqueado pela R4.** Compila com uma mudança de tipo (`useModalFocus(ref: RefObject<HTMLElement \| null>)`), mas o bundle sobe para **697 188 B (+15,7 %) / 201 905 B gzip (+12,1 %)** — o `react-dom` 19 é ~79 kB maior minificado. Não há corte razoável que compense; decidir com o dono se o teto de 5 % vale para o React (code splitting das abas reduziria só o carregamento inicial, não o total). | — |
| R6 audit | **entregue.** O Vite 8 elimina esbuild/postcss/nanoid/source-map-js; `npm audit fix` sobe browserslist/baseline-browser-mapping (via eslint-plugin-react-hooks); `uuid <11.1.1` (via `@capacitor/cli` > `xcode`) fica fixado por `overrides` em `^11.1.1` — o xcode só chama `require('uuid').v4()`, mantido no uuid 11 (o `--force` rebaixaria o `@capacitor/cli`). Sem allowlist. `npm audit`: **0**. `npm-audit-full` passa a bloqueante com `--audit-level=moderate` (revisão: advisory `low` novo não deve travar todos os PRs). | `c6eb24c` |

Verificação do estado final (branch rebaseada sobre `da6186b`):

- `npm run build` verde; `npm run typecheck` 0 erros; `npm test` **147/147**; `typecheck:e2e` 4 erros (main 25); `lint` 93 problemas (= main).
- Playwright completo (280 testes; `RPG_E2E_SERVER=preview`, que mede o build real e é estável nesta máquina compartilhada):
  234 passados, 38 pulados (opt-in), 8 falhas; reexecução das falhas com 1 worker no dev server (modo do CI): 5 passam,
  **3 falham igual na `main` `da6186b`**: `account.spec` "fallback updates technical cost", F14 `network_failure_recovery`
  e `workspace-shell` "10 trocas de aba" — o beacon novo `POST /telemetry/client-error` responde 404 no servidor de teste
  e o guard de console reprova. Não é regressão desta spec (arquivo de fixture/eval protegido — fica para o coordenador).
  As falhas de 1ª passada que somem na reexecução são timing de máquina carregada (as duas `voice-input` dependem do dev
  server, pois servem `/tests/*.fixture.html`; os `perf 4x CPU` medem long task sob carga) e aparecem igual na linha de base.
- Smoke visual contra a API real (MockLLM) servindo `web/dist`, 390×844 e 1440×900: tela inicial e arena do Laboratório
  de combate sem erro de console/pageerror e sem overflow horizontal.
- Validação por etapa antes do rebase (sobre `4c4167b`): Playwright completo verde (mesmo critério) após Playwright 1.64 e após Vite 8.

PRs do Dependabot: #35 (vite) e #37 (playwright) ficam obsoletos com o merge; #40/#41 (React) e #42 (TS 7) seguem bloqueados.
