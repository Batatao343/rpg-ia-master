# SPEC-365 — revisão sol (review)

> **Veredito:** `APPROVED_WITH_FOLLOWUPS`
> **Revisor:** Opus / Sol · **Data:** 2026-11-02 · **Commit revisado:** `34a1263a`

## Escopo

Branch `spec-365`, `main...34a1263a`: `web/package.json` (overrides `minimatch ^11.0.1`,
`glob ^14.0.2`), `web/package-lock.json`, `web/eslint.config.js` (shim do `require.cache` +
`await import("eslint-plugin-jsx-a11y")`) e a spec. Fora do escopo: Playwright e2e completo
(RAM) e `npm ci` em Linux (só verificado em Windows/npm 11; o CI usa Node 22 via `.nvmrc`).

Verificações:

1. **Gate não afrouxado.** `.github/` sem alteração no diff; não há `.npmrc` (raiz nem `web/`);
   `npm-audit-full` segue `npm audit --audit-level=moderate` e `validate` segue
   `--omit=dev --audit-level=high`; sem allowlist/ignore. OK.
2. **Shim.** `require.resolve("minimatch")` a partir de `web/eslint.config.js` e o
   `require("minimatch")` de `eslint-plugin-jsx-a11y/lib/util/*` resolvem o mesmo
   `web/node_modules/minimatch/dist/commonjs/index.js` (o lock não tem cópia aninhada; `npm ls`
   mostra tudo `deduped` em 11.0.4). Imports estáticos (`@eslint/js`, `globals`,
   `react-hooks`, `typescript-eslint`) não carregam o jsx-a11y, então o patch roda antes do
   `import()` dinâmico. O shim é idempotente (`typeof mm !== "function"`), por isso tolera a
   reavaliação do config pelo eslint. Consumidores que já tinham a referência original (eslint,
   `@eslint/config-array` cjs, `@eslint/eslintrc` cjs, typescript-estree) só usam
   `.Minimatch`/`.minimatch`, que continuam no objeto original e foram copiados para a função.
   `Object.assign` não copia o `__esModule`, que não é enumerável, e por isso o
   `_interopRequireDefault` do plugin embrulha `{default: fn}` e chama a função. Está correto.
   Se o shim quebrar no futuro, a falha é ruidosa (TypeError derruba o lint) e não silenciosa.
3. **Prova com arquivo de erro proposital** (temporário, removido): `src/__proof365.tsx` com
   `label-has-associated-control` e `control-has-associated-label` ligados com
   `controlComponents: ["Custom*"]`, para exercitar os dois caminhos com minimatch
   (`mayContainChildComponent` e `mayHaveAccessibleLabel`) e um glob de verdade:
   - `<label>Nome<input/></label>` → sem erro de label (casou `input` aninhado);
   - `<label><CustomInput/></label>` → "must have accessible text" (glob `Custom*` casou);
   - `<label htmlFor><span/></label>` → "accessible text";
   - `<label><Foo/></label>` → "must be associated with a control";
   - `<button><CustomInput/></button>` → control-has-associated-label (glob casou);
   - `<button><Icon/></button>` → sem erro (não casou e conta como rótulo);
   - `<img>` → alt-text.
   São 6 erros, todos os esperados com a semântica do minimatch v3, e nenhum crash. Só essas
   duas regras do jsx-a11y usam minimatch.
4. **Consumidores reais.** Do minimatch: eslint (`{ Minimatch }`, `minimatch.Minimatch`),
   `@eslint/config-array` cjs (`.Minimatch`), `@eslint/eslintrc` cjs (`.Minimatch`, `matchBase`
   ainda existe no v11), typescript-estree (`{ minimatch }`) e jsx-a11y (shim). Do glob: só
   `rimraf@6.1.3` (`{ glob, globSync }`, via `@capacitor/cli`). Testei `rimraf(..., {glob:true})`
   e `rimraf(dir)` em runtime com glob 14 e funcionou. Vite/rolldown/tinyglobby usam picomatch;
   Playwright tem dependências embutidas; `ajv/scripts/compile-dots.js` não roda. Nenhum script
   de `web/` (`scripts/`, `tests/`, `e2e/`, `src/`, configs) importa glob ou minimatch.
5. **Status da spec:** o cabeçalho já está `done` antes desta revisão (ver P2-1).

## Achados

| ID | Sev. | Arquivo:linha | Problema | Correção |
|---|---|---|---|---|
| P2-1 | P2 | specs/SPEC-365-deps-eslint-minimatch.md:3 | Status `done` gravado antes da revisão independente ("revisão independente pendente"), o que contraria o fluxo (status final só depois da revisão). | Com este APPROVED, o coordenador pode manter `done`, mas deve tirar o "revisão independente pendente" do cabeçalho e citar este handoff. |
| P3-1 | P3 | web/eslint.config.js:12-17 | O shim resolve `minimatch` a partir do config, não do plugin. Hoje é o mesmo arquivo (deduped), mas uma cópia aninhada futura em `eslint-plugin-jsx-a11y/node_modules` ficaria sem o patch. A falha seria ruidosa e não mascarada. | Opcional: `createRequire(require.resolve("eslint-plugin-jsx-a11y"))` para resolver o minimatch no contexto do plugin. |
| P3-2 | P3 | web/tests/ (ausente) | Nada no repo fixa a prova acima. O lint só exercita o minimatch se o código tiver `<label>` com filhos elemento. | Opcional: um `node --test` que roda `ESLint.lintText` com o caso `<label><CustomInput/></label>` + `controlComponents:["Custom*"]` e asserta 1 erro sem exceção. |
| P3-3 | P3 | (dependência) | O ESM do minimatch 11 não tem `export default`. `@eslint/config-array/dist/esm` e `@eslint/eslintrc/lib` fazem `import minimatch from "minimatch"` e quebrariam se carregados como ESM. Hoje o eslint 9 (CJS) usa os builds cjs. | Só registrar no §7 da spec como risco; reavaliar ao subir o eslint. |

## Correções aplicadas

Nenhuma (revisão só leitura).

## Pendências

- P3-1/P3-2/P3-3: opcionais, sem spec de destino; podem entrar quando o jsx-a11y suportar
  minimatch ≥ 11 (aí sai o shim).
- Prova em Linux: o primeiro run do CI (`npm ci` em Node 22/npm 10 + `npm-audit-full`) confirma.

## Comandos rodados

```text
npm ci (web/, node_modules real, não junção)             → exit 0
npm audit --audit-level=moderate                           → found 0 vulnerabilities
npm run lint                                               → exit 0 (eslint + css-lint/contrast)
npm run typecheck                                          → exit 0
npm test                                                   → 290/290 pass
npm run build                                              → exit 0 (vite + legal pages)
npx cap --version                                          → 8.5.3
npm ls glob minimatch --all                                → tudo 11.0.4/14.0.3 deduped
node -e rimraf(glob:true)+rimraf(dir) com glob 14          → OK
npx eslint -c __proof365.config.js src/__proof365.tsx      → 6 erros esperados, sem crash (arquivos removidos)
```
