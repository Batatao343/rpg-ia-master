# SPEC-276 — Revisão independente (Opus)

- **Escopo:** `git diff main...spec-276` (4 commits: `0375dba`, `962ce43`, `c6eb24c`, `3e82941`). Arquivos: `validate.yml`, `web/package.json`, `web/package-lock.json`, `web/vite.config.ts`, spec.
- **Revisor:** não escreveu o código. Playwright completo **não** foi re-executado (restrição de máquina); os demais gates foram rodados localmente em Node 24.19.0.
- **Veredito: APPROVED_WITH_FOLLOWUPS**

## Verificações executadas

| Item | Comando | Resultado |
|---|---|---|
| Versões | `npm ls vite @vitejs/plugin-react @playwright/test esbuild typescript uuid` | vite 8.3.4, plugin-react 6.1.2, @playwright/test 1.64.1, esbuild 0.28.2 (dedupe com o peer opcional do vite `^0.27 \|\| ^0.28`), typescript 5.9.3, xcode→uuid 11.1.1 |
| Lockfile limpo | `npm ci --ignore-scripts` em diretório vazio só com package.json+lock | ok, `found 0 vulnerabilities` |
| Bindings Linux no lock | grep no lock | `@rolldown/binding-linux-x64-gnu`, `lightningcss-linux-x64-gnu`, `@esbuild/linux-x64` presentes; `rollup` ausente |
| Engines | `npm view vite@8.3.4 engines` | `^20.19.0 \|\| >=22.12.0` — CI usa `node-version: 20` (resolve 20.x mais recente, ≥ 20.19) |
| Build | `npm run build` | verde (689 ms), só o aviso de chunk > 500 kB (pré-existente) |
| Testes Node | `npm test` | 147/147 |
| Typecheck | `npm run typecheck` / `typecheck:e2e` | 0 erros / 4 erros (spec diz main = 25) |
| Lint | `npm run lint` | 93 problemas (= main, conforme spec) |
| Audit | `npm audit` | 0 vulnerabilidades |
| Arquivos protegidos | `git diff main...spec-276 --name-only \| grep -E 'evals/\|e2e/\|metrics\|manifest'` | nenhum |

## Achados

1. **[OK] Versões e lockfile consistentes.** Ver tabela. `esbuild` explícito é necessário (os `tests/*.test.mjs` o importam e o Vite 8 o tornou opcional) e casa com o range de peer do Vite.

2. **[OK] `build.target` antigo é correto e respeitado.** O array é exatamente o valor `'modules'` do Vite 5. Verificado no `dist`: 0 ocorrências de `??=`/`||=`/`&&=`, `static {`, `.at(` nos `.js` → Oxc rebaixa sintaxe ES2021+ para es2020. Lightning CSS herda `cssTarget` do `build.target` (explica +13 kB de CSS com fallbacks). Risco Capacitor: nenhum novo — `minSdkVersion = 24` com WebView atualizável; o alvo é o mesmo de antes. Ressalva (não regressão): `target` só rebaixa sintaxe, não faz polyfill de APIs; `:has()`/`color-mix()` já eram usados em `src/*.css` antes e seguem sem fallback em navegadores antigos.

3. **[OK] Override `uuid ^11.1.1` para `xcode` é seguro.** `xcode/lib/pbxProject.js:22` faz `require('uuid')` e só usa `uuid.v4()` (linha 90). uuid 11 ainda publica CJS (`node -e "require('./node_modules/uuid').v4"` → `function`). O override é escopado a `xcode` e o `xcode` só roda em `cap add/sync ios` (o projeto não tem `ios/`). Alternativa (`npm audit fix --force`) rebaixaria `@capacitor/cli`; o override é a melhor saída. **Follow-up:** remover o override quando `@capacitor/cli`/`xcode` subirem o uuid; **não** subir para uuid ≥ 12 (ESM-only quebraria o `require`).

4. **[Média] `npm-audit-full` bloqueante sem `--audit-level`.** O job não tem `if:` — roda em push, PR **e** no cron semanal — e usa `npm audit` puro (falha em `low`). Qualquer advisory novo de dev (mesmo low/moderate, sem relação com o PR) deixa todo PR vermelho até alguém agir. Recomendo **manter bloqueante**, mas com `npm audit --audit-level=moderate` (ou `high`, coerente com o job de runtime), e deixar o cron/Dependabot pegar os low. Não bloqueia o merge; ajuste de uma linha.

5. **[OK] Justificativa do bloqueio do TypeScript 7 confere.** `npm view typescript-eslint peerDependencies` → `typescript: '>=4.8.4 <6.1.0'`; `latest` = 8.71.2, sem dist-tag com suporte a 7.x. `npm ci` recusaria o peer (ERESOLVE). Correto deixar #42 bloqueado.

6. **[OK] Justificativa do bloqueio do React 19 é coerente com a R4.** Não re-medi o bundle com React 19, mas +15,7 % bruto / +12,1 % gzip excede o teto de 5 % da própria spec; react-dom 19 é de fato maior. A decisão (dono decide se o teto vale para o React) está corretamente escalada.

7. **[OK, plausível] As 3 falhas Playwright são pré-existentes.** Na `main`, `web/src/lib/clientErrors.ts` (SPEC-244, `69a9f70`/`fb9b457`) envia `POST /telemetry/client-error` via `sendBeacon`/`fetch`. `web/e2e/fixtures.ts` não trata essa rota: cai no catch-all `fixture route missing` com **404** (linha 418), e o guard de console (linha 436) reprova o `Failed to load resource`. Só `/telemetry/client-latency` é tratado (em `vertical-support.ts`). Os 3 testes (account fallback cost, F14 network failure, 10 trocas de aba) exercitam caminhos de erro que disparam o beacon. Não reproduzi a execução, mas o mecanismo está no código da `main` e independe do toolchain. **Follow-up:** mock da rota no backend determinístico do e2e (arquivo protegido → publicação via `eval-governance`).

8. **[Baixa] Node 20 no CI.** Vite 8 funciona em 20.19+, mas Node 20 saiu de suporte (abr/2026). Follow-up: subir `node-version` para 22/24 em `validate.yml`, `eval-gates.yml` e `audit-local.yml` numa spec própria.

9. **[OK] Sem mudança de comportamento do app identificada.** `vite.config.ts` só ganha `build.target`; sem `rollupOptions`/`manualChunks`/`import.meta.glob`. Bundle (spec): +2,5 % bruto / −0,5 % gzip, dentro da R4. Playwright 1.64 alinha com o `playwright>=1.58` do `pyproject` (o pacote Python é independente).

## Follow-ups

- F1 (achado 4): `npm audit --audit-level=moderate` (ou `high`) no `npm-audit-full`.
- F2 (achado 7): mock de `/telemetry/client-error` no backend e2e via fluxo `eval-governance`.
- F3 (achado 3): remover o override de uuid quando o `@capacitor/cli` atualizar o `xcode`.
- F4 (achado 8): Node 22/24 no CI.
- F5: React 19 e TS 7 seguem bloqueados (decisão do dono sobre a R4; aguardar typescript-eslint com suporte a TS 7).
